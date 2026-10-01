"""Fail-closed public behavior for the qlty smells gate."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c
from flext_infra.check.gate_registry import FlextInfraGateRegistry
from flext_infra.gates.smells import FlextInfraSmellsGate
from tests import m, u


@pytest.fixture
def smells_project(tmp_path: Path) -> Path:
    """One declared project inside ``tmp_path`` for qlty to scan."""
    name = f"smells-{tmp_path.name}"
    project = u.Tests.mk_project(
        tmp_path,
        name,
        pyproject=f'[project]\nname = "{name}"\nversion = "0.1.0"\n',
        with_src=True,
    )
    return project


class TestsFlextInfraSmellsGate:
    """Exercise observable gate behavior with the real setup-provisioned tool."""

    @staticmethod
    def _ctx(root: Path) -> m.Infra.GateContext:
        return m.Infra.GateContext(repository_root=root, reports_dir=root / "reports")

    @staticmethod
    def _package(project: Path) -> Path:
        return project / "src" / project.name.replace("-", "_")

    @staticmethod
    def test_registry_exposes_the_canonical_gate() -> None:
        gate = FlextInfraGateRegistry.default().get("smells")
        tm.that(gate is FlextInfraSmellsGate, eq=True)

    def test_missing_project_configuration_is_a_blocking_failure(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project,
            self._ctx(tmp_path),
        )

        tm.that(execution.result.passed, eq=False)
        tm.that(len(execution.issues), eq=1)
        tm.that(execution.issues[0].severity, eq=str(c.Infra.GateSeverity.ERROR.value))
        tm.that(
            "generated qlty configuration is absent" in execution.issues[0].message,
            eq=True,
        )

    @staticmethod
    def _configure(root: Path) -> None:
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

    def test_zero_findings_scan_is_a_pass(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        self._configure(tmp_path)

        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project,
            self._ctx(tmp_path),
        )

        tm.that(execution.result.passed, eq=True)
        tm.that(len(execution.issues), eq=0)

    def test_finding_states_the_concrete_problem_and_the_fix(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        self._configure(tmp_path)
        params = ", ".join(
            f"p{index}" for index in range(c.SMELL_THRESHOLDS["params"] * 2)
        )
        (self._package(smells_project) / "wide.py").write_text(
            f"def wide({params}):\n    return p0\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project,
            self._ctx(tmp_path),
        )

        tm.that(execution.result.passed, eq=False)
        messages = [issue.message for issue in execution.issues]
        tm.that(any("wide" in message for message in messages), eq=True)
        tm.that(any("{" in message for message in messages), eq=False)
        tm.that(all(" Fix: " in message for message in messages), eq=True)

    def test_qlty_scan_does_not_run_runtime_census(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        """Qlty owns this gate even when census project metadata is unavailable."""
        self._configure(tmp_path)
        (smells_project / c.PYPROJECT_FILENAME).unlink()

        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project,
            self._ctx(tmp_path),
        )

        tm.that(execution.result.passed, eq=True)
        tm.that(execution.issues, length=0)
