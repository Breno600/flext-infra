"""Tests for the abstraction-boundary gate (AGENTS.md §2.7).

Behaviour parity with the two retired scripts: banned CLI-domain libs are
flagged in consumers, ``click`` is exempt in Singer-SDK boundary files, and
concrete ``FlextCli<X>`` imports are flagged outside src extension files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
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

    def test_live_print_call_is_flagged(self, tmp_path: Path) -> None:
        project = self._project(
            tmp_path, name="flext-demo", filename="logic.py", src="print('live')\n"
        )

        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, project
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(any("cli.print" in issue.message for issue in result.issues), eq=True)

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

    def test_renamed_owner_retains_declared_boundary_policy(
        self, tmp_path: Path
    ) -> None:
        """A worktree directory does not replace the declared distribution identity."""
        project = self._project(
            tmp_path,
            name=min(c.Infra.BOUNDARY_SKIP_PROJECTS),
            filename="logic.py",
            src="import typer\n",
        )
        renamed = project.rename(tmp_path / "owner-worktree")
        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, renamed
        )
        tm.that(result.result.passed, eq=True)
        tm.that(result.issues, eq=[])

    def test_owner_directory_does_not_exempt_consumer(self, tmp_path: Path) -> None:
        """A consumer cannot acquire an owner's policy by renaming its checkout."""
        project = self._project(
            tmp_path, name="flext-demo", filename="logic.py", src="import typer\n"
        )
        renamed = project.rename(tmp_path / min(c.Infra.BOUNDARY_SKIP_PROJECTS))
        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, renamed
        )
        tm.that(result.result.passed, eq=False)
        tm.that(any("typer" in issue.message for issue in result.issues), eq=True)

    def test_renamed_toml_owner_retains_declared_policy(self, tmp_path: Path) -> None:
        """The TOML allowance follows the typed project identity too."""
        project = self._project(
            tmp_path,
            name=min(c.Infra.BOUNDARY_TOML_ALLOWED),
            filename="logic.py",
            src="import tomllib\n",
        )
        renamed = project.rename(tmp_path / "toml-owner-worktree")
        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, renamed
        )
        tm.that(result.result.passed, eq=True)
        tm.that(result.issues, eq=[])

    @pytest.mark.parametrize("metadata_text", [None, "[project\n"])
    def test_invalid_metadata_cannot_inherit_owner_directory_policy(
        self, tmp_path: Path, metadata_text: str | None
    ) -> None:
        """Missing or malformed metadata fails even inside an owner's named folder."""
        project = tmp_path / min(c.Infra.BOUNDARY_SKIP_PROJECTS)
        project.mkdir()
        if metadata_text is not None:
            (project / c.PYPROJECT_FILENAME).write_text(metadata_text, encoding="utf-8")
        result = u.Tests.run_gate_check(
            FlextInfraAbstractionBoundaryGate, tmp_path, project
        )
        tm.that(result.result.passed, eq=False)
        tm.that(bool(result.issues), eq=True)
        tm.that(result.raw_output, has=c.PYPROJECT_FILENAME)
