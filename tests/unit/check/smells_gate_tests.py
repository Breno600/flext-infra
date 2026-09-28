"""Fail-closed public behavior for the qlty smells gate."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c
from flext_infra.check.gate_registry import FlextInfraGateRegistry
from flext_infra.gates.smells import FlextInfraSmellsGate
from tests import m, u


class TestsFlextInfraSmellsGate:
    """Exercise observable gate behavior with the real setup-provisioned tool."""

    def _ctx(self, root: Path) -> m.Infra.GateContext:
        return m.Infra.GateContext(repository_root=root, reports_dir=root / "reports")

    def test_registry_exposes_the_canonical_gate(self) -> None:
        gate = FlextInfraGateRegistry.default().get("smells")
        tm.that(gate is FlextInfraSmellsGate, eq=True)

    def test_missing_project_configuration_is_a_blocking_failure(
        self, tmp_path: Path
    ) -> None:
        project = u.Tests.mk_project(tmp_path, "smells-project", with_src=True)

        execution = FlextInfraSmellsGate(tmp_path).check(project, self._ctx(tmp_path))

        tm.that(execution.result.passed, eq=False)
        tm.that(len(execution.issues), eq=1)
        tm.that(execution.issues[0].severity, eq=str(c.Infra.GateSeverity.ERROR.value))
        tm.that(
            "generated qlty configuration is absent" in execution.issues[0].message,
            eq=True,
        )

    def _configured_project(self, root: Path) -> Path:
        tm.ok(u.Cli.run_checked(["git", "init", "-q", str(root)]))
        config_dir = root / c.Infra.QLTY_CONFIG_DIRNAME
        config_dir.mkdir()
        generated_config = (
            Path(__file__).resolve().parents[3]
            / c.Infra.QLTY_CONFIG_DIRNAME
            / c.Infra.QLTY_CONFIG_FILENAME
        )
        (config_dir / c.Infra.QLTY_CONFIG_FILENAME).write_text(
            generated_config.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        return u.Tests.mk_project(root, "smells-project", with_src=True)

    def test_zero_findings_scan_is_a_pass(self, tmp_path: Path) -> None:
        project = self._configured_project(tmp_path)

        execution = FlextInfraSmellsGate(tmp_path).check(project, self._ctx(tmp_path))

        tm.that(execution.result.passed, eq=True)
        tm.that(len(execution.issues), eq=0)

    def test_finding_states_the_concrete_problem_and_the_fix(
        self, tmp_path: Path
    ) -> None:
        project = self._configured_project(tmp_path)
        params = ", ".join(
            f"p{index}" for index in range(c.SMELL_THRESHOLDS["params"] * 2)
        )
        (project / "src" / "smells_project" / "wide.py").write_text(
            f"def wide({params}):\n    return p0\n", encoding=c.Cli.ENCODING_DEFAULT
        )

        execution = FlextInfraSmellsGate(tmp_path).check(project, self._ctx(tmp_path))

        tm.that(execution.result.passed, eq=False)
        messages = [issue.message for issue in execution.issues]
        tm.that(any("wide" in message for message in messages), eq=True)
        tm.that(any("{" in message for message in messages), eq=False)
        tm.that(all(" Fix: " in message for message in messages), eq=True)
