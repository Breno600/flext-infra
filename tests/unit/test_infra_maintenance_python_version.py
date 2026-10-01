"""Tests for FlextInfraPythonVersionEnforcer.

Tests Python version enforcement with real pyproject.toml and tmp_path.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, override

from flext_tests import tm

from flext_infra.maintenance.python_version import FlextInfraPythonVersionEnforcer
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraInfraMaintenancePythonVersion:
    """Validate Python version enforcement via the public execute() surface."""

    _MINOR: int = sys.version_info.minor
    _BAD: int = _MINOR + 1

    def _ws(self, root: Path, *, minor: int | None = None) -> Path:
        """Create repository root with required markers."""
        resolved_minor = self._MINOR if minor is None else minor
        root.mkdir(exist_ok=True)
        (root / ".git").mkdir(exist_ok=True)
        (root / "Makefile").touch()
        (root / "pyproject.toml").write_text(
            (
                "[project]\n"
                'name = "workspace"\n'
                'version = "0.1.0"\n'
                f'requires-python = ">=3.{resolved_minor}"\n'
            ),
            encoding="utf-8",
        )
        (root / ".python-version").write_text(f"3.{resolved_minor}\n", encoding="utf-8")
        return root

    def _proj(self, root: Path, name: str, *, minor: int | None = None) -> Path:
        resolved_minor = self._MINOR if minor is None else minor
        proj = root / name
        proj.mkdir(exist_ok=True)
        (proj / ".git").mkdir(exist_ok=True)
        (proj / "Makefile").touch()
        (proj / "src").mkdir(exist_ok=True)
        (proj / "pyproject.toml").write_text(
            (
                "[project]\n"
                f'name = "{name}"\n'
                'version = "0.1.0"\n'
                f'requires-python = ">=3.{resolved_minor}"\n'
                'dependencies = ["flext-core>=0"]\n'
            ),
            encoding="utf-8",
        )
        (proj / ".python-version").write_text(f"3.{resolved_minor}\n", encoding="utf-8")
        return proj

    def _svc(self, ws: Path) -> FlextInfraPythonVersionEnforcer:
        class _TestEnforcer(FlextInfraPythonVersionEnforcer):
            @override
            def _repository_root_from_file(self, file: str | Path) -> Path:
                _ = file
                return ws

        return _TestEnforcer()

    def test_check_only_success(self, tmp_path: Path) -> None:
        tm.ok(
            self._svc(self._ws(tmp_path / "ws")).execute(
                check_only=True, verbose=False
            ),
            eq=0,
        )

    def test_enforce_mode(self, tmp_path: Path) -> None:
        tm.ok(
            self._svc(self._ws(tmp_path / "ws")).execute(
                check_only=False, verbose=False
            ),
            eq=0,
        )

    def test_verbose_mode(self, tmp_path: Path) -> None:
        svc = self._svc(self._ws(tmp_path / "ws"))
        tm.ok(svc.execute(check_only=True, verbose=True))
        tm.that(svc.verbose, eq=True)

    def test_failure_on_workspace_mismatch(self, tmp_path: Path) -> None:
        tm.fail(
            self._svc(self._ws(tmp_path / "ws", minor=self._BAD)).execute(
                check_only=True
            )
        )

    def test_failure_on_project_mismatch(self, tmp_path: Path) -> None:
        ws = self._ws(tmp_path / "ws")
        self._proj(ws, "project-a", minor=self._BAD)
        u.Tests.declare_workspace_projects(ws, ("project-a",))
        tm.fail(self._svc(ws).execute(check_only=True, verbose=False))

    def test_empty_workspace(self, tmp_path: Path) -> None:
        tm.ok(self._svc(self._ws(tmp_path / "ws")).execute(check_only=True))

    def test_check_only_fails_when_python_version_file_is_missing(
        self, tmp_path: Path
    ) -> None:
        ws = self._ws(tmp_path / "ws")
        (ws / ".python-version").unlink()

        tm.fail(self._svc(ws).execute(check_only=True, verbose=False))

    def test_check_only_fails_when_python_version_file_is_stale(
        self, tmp_path: Path
    ) -> None:
        ws = self._ws(tmp_path / "ws")
        (ws / ".python-version").write_text(f"3.{self._BAD}\n", encoding="utf-8")

        tm.fail(self._svc(ws).execute(check_only=True, verbose=False))

    def test_apply_mode_conforms_python_version_file_and_is_idempotent(
        self, tmp_path: Path
    ) -> None:
        ws = self._ws(tmp_path / "ws")
        version_file = ws / ".python-version"
        version_file.unlink()
        svc = self._svc(ws)

        tm.ok(svc.execute(check_only=False, verbose=False), eq=0)
        tm.that(version_file.read_text(encoding="utf-8"), eq=f"3.{self._MINOR}\n")
        version_file.write_text(f"3.{self._BAD}\n", encoding="utf-8")
        tm.ok(svc.execute(check_only=False, verbose=False), eq=0)
        tm.that(version_file.read_text(encoding="utf-8"), eq=f"3.{self._MINOR}\n")
        tm.ok(svc.execute(check_only=True, verbose=False), eq=0)
        tm.that(version_file.read_text(encoding="utf-8"), eq=f"3.{self._MINOR}\n")

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        result = u.Infra.discover_projects(d)
        tm.ok(result)
        tm.that(result.value, empty=True)
