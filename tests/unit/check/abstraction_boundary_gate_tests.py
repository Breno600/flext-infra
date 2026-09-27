"""Tests for the abstraction-boundary gate (AGENTS.md §2.7).

Behaviour parity with the two retired scripts: banned CLI-domain libs are
flagged in consumers, ``click`` is exempt in Singer-SDK boundary files, and
concrete ``FlextCli<X>`` imports are flagged outside src extension files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.gates.abstraction_boundary import FlextInfraAbstractionBoundaryGate
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraAbstractionBoundaryGate:
    def _project(self, tmp_path: Path, *, name: str, filename: str, src: str) -> Path:
        project_path: Path = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name=name,
            pkg_name=name.replace("-", "_"),
            files={filename: src},
        )
        return project_path

    def test_gate_identity(self) -> None:
        tm.that(FlextInfraAbstractionBoundaryGate.gate_id, eq="boundary")
        tm.that(FlextInfraAbstractionBoundaryGate.can_fix, eq=False)

    def test_banned_cli_lib_is_flagged(self, tmp_path: Path) -> None:
        project = self._project(
            tmp_path, name="flext-demo", filename="logic.py", src="import typer\n"
        )

        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, project
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(any("typer" in issue.message for issue in result.issues), eq=True)

    def test_click_allowed_in_singer_boundary(self, tmp_path: Path) -> None:
        project = self._project(
            tmp_path, name="flext-tap-demo", filename="logic.py", src="import click\n"
        )

        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, project
        )

        tm.that(result.result.passed, eq=True)

    def test_concrete_flext_cli_import_flagged(self, tmp_path: Path) -> None:
        project = self._project(
            tmp_path,
            name="flext-demo",
            filename="service.py",
            src="from flext_cli import FlextCliService\n",
        )

        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, project
        )

        tm.that(not result.result.passed, eq=True)

    def test_concrete_flext_cli_allowed_in_extension_file(self, tmp_path: Path) -> None:
        project = self._project(
            tmp_path,
            name="flext-demo",
            filename="models.py",
            src="from flext_cli import FlextCliService\n",
        )

        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, project
        )

        tm.that(result.result.passed, eq=True)

    def test_print_detection_ignores_embedded_source_text(self, tmp_path: Path) -> None:
        project = self._project(
            tmp_path,
            name="flext-demo",
            filename="logic.py",
            src="PAYLOAD = 'print(\"fixture\")\\n'\n",
        )

        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, project
        )

        tm.that(result.result.passed, eq=True)

    def test_declared_boundary_owner_passes_by_design(self, tmp_path: Path) -> None:
        """A declared boundary owner is exempt: the gate passes with no issues."""
        owner = min(c.Infra.BOUNDARY_SKIP_PROJECTS)
        project = self._project(
            tmp_path, name=owner, filename="logic.py", src="import typer\n"
        )

        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, project
        )

        tm.that(result.result.passed, eq=True)
        tm.that(len(result.issues), eq=0)
        tm.that(len(result.result.errors), eq=0)
