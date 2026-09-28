"""Tests for the silent-failure quality gate.

The gate enforces silent-failure detection on every Python project the
workspace discovers — there is no project-name allowlist. Tests assert
that the gate detects violations universally and accepts clean code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.gates.silent_failure import FlextInfraSilentFailureGate
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraSilentFailureGate:
    _DIRTY_UTILITIES = (
        "from __future__ import annotations\n\n"
        "from collections.abc import Mapping, Sequence\n\n"
        "from flext_core import r\n\n"
        "def run(validation_result: p.Result[bool]) -> p.Result[bool]:\n"
        "    if validation_result.failure:\n"
        "        return False\n"
        "    return r[bool].ok(True)\n"
    )
    _CLEAN_UTILITIES = (
        "from __future__ import annotations\n\n"
        "from flext_core import r\n\n"
        "def run(validation_result: p.Result[bool]) -> p.Result[bool]:\n"
        "    return validation_result.flat_map(lambda  value:  r[bool].ok(value))\n"
    )

    def _create_gate_project(
        self, tmp_path: Path, *, name: str, utilities_src: str
    ) -> Path:
        project_dir: Path = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name=name,
            pkg_name=name.replace("-", "_"),
            files={"utilities.py": utilities_src},
        )
        return project_dir

    def test_silent_failure_detected_in_any_project(self, tmp_path: Path) -> None:
        project = self._create_gate_project(
            tmp_path, name="demo-project", utilities_src=self._DIRTY_UTILITIES
        )

        result = u.Tests.run_gate_check(FlextInfraSilentFailureGate, tmp_path, project)

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), eq=1)
        tm.that(result.issues[0].code, eq="silent-failure-guard")

    def test_clean_project_passes(self, tmp_path: Path) -> None:
        project = self._create_gate_project(
            tmp_path, name="demo-project", utilities_src=self._CLEAN_UTILITIES
        )

        result = u.Tests.run_gate_check(FlextInfraSilentFailureGate, tmp_path, project)

        tm.that(result.result.passed, eq=True)
        tm.that(len(result.issues), eq=0)

    def test_adr0018_island_file_is_exempt(self, tmp_path: Path) -> None:
        """The declared stdlib island stays out of the no-hidden-errors scan."""
        project = self._create_gate_project(
            tmp_path, name="demo-project", utilities_src=self._CLEAN_UTILITIES
        )
        island_dir = project / "src" / "ai_hub"
        island_dir.mkdir(parents=True)
        (island_dir / "hook_client.py").write_text(
            self._DIRTY_UTILITIES, encoding="utf-8"
        )

        result = u.Tests.run_gate_check(FlextInfraSilentFailureGate, tmp_path, project)

        tm.that(result.result.passed, eq=True)
        tm.that(len(result.issues), eq=0)
