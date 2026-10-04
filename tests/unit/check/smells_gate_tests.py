"""Fail-closed public behavior for the qlty smells gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c
from flext_infra.check.gate_registry import FlextInfraGateRegistry
from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from flext_infra.gates.smells import FlextInfraSmellsGate
from tests import m, u


@pytest.fixture
def smells_project(tmp_path: Path) -> Path:
    """One declared project inside ``tmp_path`` for qlty to scan.

    Returns:
        The resulting ``Path``.

    """
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
        """Test registry exposes the canonical gate."""
        gate = FlextInfraGateRegistry.default().get("smells")
        tm.that(gate is FlextInfraSmellsGate, eq=True)

    def test_missing_project_configuration_is_a_blocking_failure(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        """Test missing project configuration is a blocking failure."""
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
        """Test zero findings scan is a pass."""
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
        """Test finding states the concrete problem and the fix."""
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

    def test_workspace_report_round_trips_native_comparison_spans(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        """The public checker retains exactly the spans emitted by real qlty."""
        self._configure(tmp_path)
        source = (
            Path(__file__).resolve().parents[3] / "src/flext_infra/gates/smells.py"
        ).read_text(encoding=c.Cli.ENCODING_DEFAULT)
        for name in ("first.py", "second.py", "third.py"):
            (self._package(smells_project) / name).write_text(
                source,
                encoding=c.Cli.ENCODING_DEFAULT,
            )
        reports_dir = tmp_path / "reports"
        projects = tm.ok(
            FlextInfraWorkspaceChecker.model_validate({
                "repository_root": tmp_path,
            }).run_projects(
                [smells_project.name],
                [c.Infra.SMELLS],
                reports_dir=reports_dir,
            ),
        )
        execution = projects[0].gates[c.Infra.SMELLS]
        native = u.Cli.json_as_mapping(tm.ok(u.Cli.json_parse(execution.raw_output)))
        report = m.Infra.SarifReport.model_validate_json(
            (reports_dir / c.Infra.CHECK_REPORT_SARIF_FILENAME).read_text(
                encoding=c.Cli.ENCODING_DEFAULT,
            ),
        )
        native_results = tuple(
            result
            for run in u.Cli.json_deep_mapping_list(native, "runs")
            for result in u.Cli.json_deep_mapping_list(run, "results")
        )
        report_results = tuple(result for run in report.runs for result in run.results)
        tm.that(len(report_results), eq=len(native_results))
        tm.that(execution.finding_count, eq=len(native_results))
        for observed, published in zip(native_results, report_results, strict=True):
            tm.that(
                published.locations,
                eq=[
                    m.Infra.SarifLocation.model_validate(location)
                    for location in u.Cli.json_deep_mapping_list(observed, "locations")
                ],
            )
            tm.that(
                published.related_locations,
                eq=tuple(
                    m.Infra.SarifLocation.model_validate(location)
                    for location in u.Cli.json_deep_mapping_list(
                        observed, "relatedLocations",
                    )
                ),
            )
        round_trip = m.Infra.SarifReport.model_validate_json(report.model_dump_json())
        tm.that(round_trip, eq=report)
