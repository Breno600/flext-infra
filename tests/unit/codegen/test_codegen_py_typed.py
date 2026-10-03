"""Tests for FlextInfraCodegenPyTyped.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.codegen.py_typed import FlextInfraCodegenPyTyped
from tests import c

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraCodegenPyTyped:
    """Tests for ``FlextInfraCodegenPyTyped``."""

    @staticmethod
    def test_creates_marker_in_dir_with_py_files(tmp_path: Path) -> None:
        """Test creates marker in dir with py files."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run()

        tm.that(count, eq=1)
        tm.that((pkg / c.Infra.PY_TYPED).exists(), eq=True)

    @staticmethod
    def test_removes_stale_marker_when_no_py_files(tmp_path: Path) -> None:
        """Test removes stale marker when no py files."""
        pkg = tmp_path / "src" / "emptypkg"
        pkg.mkdir(parents=True)
        (pkg / c.Infra.PY_TYPED).touch()
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run()

        tm.that(count, eq=1)
        tm.that((pkg / c.Infra.PY_TYPED).exists(), eq=False)

    @staticmethod
    def test_check_only_does_not_write_marker(tmp_path: Path) -> None:
        """Test check only does not write marker."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run(check_only=True)

        tm.that(count, eq=1)
        tm.that((pkg / c.Infra.PY_TYPED).exists(), eq=False)

    @staticmethod
    def test_check_only_does_not_remove_marker(tmp_path: Path) -> None:
        """Test check only does not remove marker."""
        pkg = tmp_path / "src" / "emptypkg"
        pkg.mkdir(parents=True)
        (pkg / c.Infra.PY_TYPED).touch()
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run(check_only=True)

        tm.that(count, eq=1)
        tm.that((pkg / c.Infra.PY_TYPED).exists(), eq=True)

    @staticmethod
    @pytest.mark.parametrize("skip_dir", tuple(c.Tests.CODEGEN_SKIPPED_DIRS))
    def test_skips_known_excluded_directories(
        tmp_path: Path,
        skip_dir: str,
    ) -> None:
        """Test skips known excluded directories."""
        skipped_pkg = tmp_path / "src" / skip_dir / "mypkg"
        skipped_pkg.mkdir(parents=True)
        (skipped_pkg / "__init__.py").write_text("", encoding="utf-8")
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run()

        tm.that(count, eq=0)
        tm.that((skipped_pkg / c.Infra.PY_TYPED).exists(), eq=False)

    @staticmethod
    def test_no_change_when_marker_already_exists(tmp_path: Path) -> None:
        """Test no change when marker already exists."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / c.Infra.PY_TYPED).touch()
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run()

        tm.that(count, eq=0)

    @staticmethod
    def test_execute_returns_success(tmp_path: Path) -> None:
        """Test execute returns success."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        result = svc.execute()

        tm.ok(result)

    @staticmethod
    def test_tests_dir_packages_also_scanned(tmp_path: Path) -> None:
        """Test tests dir packages also scanned."""
        test_pkg = tmp_path / "tests" / "unit"
        test_pkg.mkdir(parents=True)
        (test_pkg / "__init__.py").write_text("", encoding="utf-8")
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run()

        tm.that(count, eq=1)
        tm.that((test_pkg / c.Infra.PY_TYPED).exists(), eq=True)

    @staticmethod
    def test_skips_nested_hidden_virtualenv_directories(tmp_path: Path) -> None:
        """Test skips nested hidden virtualenv directories."""
        venv_pkg = tmp_path / "src" / ".cache" / ".venv" / "mypkg"
        venv_pkg.mkdir(parents=True)
        (venv_pkg / "__init__.py").write_text("", encoding="utf-8")
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run()

        tm.that(count, eq=0)

    @staticmethod
    def test_only_expected_namespace_marker_is_created(tmp_path: Path) -> None:
        """Test only expected namespace marker is created."""
        pkg = tmp_path / "src" / "mypkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run()

        tm.that(count, eq=1)
        tm.that((pkg / c.Infra.PY_TYPED).exists(), eq=True)
        for namespace_file in c.Tests.CODEGEN_NAMESPACE_FILES - {
            c.Infra.PY_TYPED,
            c.Infra.INIT_PY,
        }:
            tm.that((pkg / namespace_file).exists(), eq=False)

    @staticmethod
    def test_multiple_packages_all_get_markers(tmp_path: Path) -> None:
        """Test multiple packages all get markers."""
        for name in ("pkga", "pkgb", "pkgc"):
            pkg = tmp_path / "src" / name
            pkg.mkdir(parents=True)
            (pkg / "__init__.py").write_text("", encoding="utf-8")
        svc = FlextInfraCodegenPyTyped.model_validate({"repository_root": tmp_path})

        count = svc.run()

        tm.that(count, eq=3)
        for name in ("pkga", "pkgb", "pkgc"):
            tm.that((tmp_path / "src" / name / c.Infra.PY_TYPED).exists(), eq=True)
