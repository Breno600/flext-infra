"""``run_pip_check`` executes the environment's real ``pip`` executable."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra.deps.detection import FlextInfraDependencyDetectionService


class TestsFlextInfraDepsDetectionPipCheck:
    """Behaviour of ``run_pip_check`` against executables on disk."""

    @staticmethod
    def _venv_bin(tmp_path: Path, pip_script: str | None) -> Path:
        venv_bin = tmp_path / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        if pip_script is not None:
            pip = venv_bin / "pip"
            pip.write_text(f"#!/bin/sh\n{pip_script}\n", encoding="utf-8")
            pip.chmod(0o755)
        return venv_bin

    def test_absent_pip_reports_no_conflicts(self, tmp_path: Path) -> None:
        venv_bin = self._venv_bin(tmp_path, None)

        result = FlextInfraDependencyDetectionService().run_pip_check(
            tmp_path, venv_bin
        )

        tm.that(tm.ok(result), eq=([], 0))

    def test_conflicts_and_exit_code_are_reported(self, tmp_path: Path) -> None:
        venv_bin = self._venv_bin(
            tmp_path, "printf 'pkg1 has requirement\\npkg2 conflict\\n'\nexit 1"
        )

        lines, exit_code = tm.ok(
            FlextInfraDependencyDetectionService().run_pip_check(tmp_path, venv_bin)
        )

        tm.that(list(lines), eq=["pkg1 has requirement", "pkg2 conflict"])
        tm.that(exit_code, eq=1)

    def test_clean_environment_reports_no_conflicts(self, tmp_path: Path) -> None:
        venv_bin = self._venv_bin(tmp_path, "exit 0")

        result = FlextInfraDependencyDetectionService().run_pip_check(
            tmp_path, venv_bin
        )

        tm.that(tm.ok(result), eq=([], 0))

    def test_unlaunchable_pip_is_a_failure(self, tmp_path: Path) -> None:
        venv_bin = tmp_path / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "pip").write_text("", encoding="utf-8")

        tm.fail(
            FlextInfraDependencyDetectionService().run_pip_check(tmp_path, venv_bin)
        )
