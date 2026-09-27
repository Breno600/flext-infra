"""Tests for FlextInfraValidateMetadataDiscipline.

Guard 8: metadata-discipline enforcer. Direct runtime ``tomllib`` imports
must remain in canonical metadata utility modules only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tf, tm

from flext_infra.validate.metadata_discipline import (
    FlextInfraValidateMetadataDiscipline,
)
from tests import m

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraMetadataDiscipline:
    """Rogue metadata parser imports are blocked outside allowlist."""

    @pytest.fixture
    def v(self) -> FlextInfraValidateMetadataDiscipline:
        """Shared validator instance."""
        return FlextInfraValidateMetadataDiscipline()

    def _seed_pkg(self, root: Path, name: str = "pkg") -> Path:
        project_root = root / "flext-infra"
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "pyproject.toml").write_text(
            "[project]\nname = 'flext-infra'\nversion = '0.0.0'\n", encoding="utf-8"
        )
        package_root = project_root / "src" / "flext_infra"
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text("", encoding="utf-8")
        pkg = package_root / name
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        return pkg

    def test_empty_workspace_passes(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report, is_=m.Infra.ValidationReport)
        tm.that(report.passed, eq=True)

    def test_non_tomllib_import_passes(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        pkg = self._seed_pkg(tmp_path)
        tf(base_dir=pkg).create("import json\n", "ok.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=True)

    def test_direct_tomllib_import_fails(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        pkg = self._seed_pkg(tmp_path)
        tf(base_dir=pkg).create("import tomllib\n", "bad.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=False)
        tm.that(" | ".join(report.violations), has="tomllib")

    def test_allowlisted_core_metadata_module_passes(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        allowlisted = (
            tmp_path
            / "flext-core"
            / "src"
            / "flext_core"
            / "_utilities"
            / "project_metadata.py"
        )
        allowlisted.parent.mkdir(parents=True, exist_ok=True)
        allowlisted.write_text("import tomllib\n", encoding="utf-8")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=True)

    def test_outside_flext_infra_scope_is_ignored(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        external = tmp_path / "other" / "src" / "other_pkg"
        external.mkdir(parents=True, exist_ok=True)
        (external / "__init__.py").write_text("", encoding="utf-8")
        (external / "bad.py").write_text("import tomllib\n", encoding="utf-8")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=True)
