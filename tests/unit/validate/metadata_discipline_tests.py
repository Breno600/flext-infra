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
from tests import c, m

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraMetadataDiscipline:
    """Rogue metadata parser imports are blocked outside allowlist."""

    @pytest.fixture
    def v(self) -> FlextInfraValidateMetadataDiscipline:
        """Shared validator instance."""
        return FlextInfraValidateMetadataDiscipline()

    @staticmethod
    def _seed_project(root: Path) -> Path:
        """Seed one governed project whose package sits under the target scope."""
        project_root = root / "project"
        package = project_root / c.Infra.METADATA_TARGET_SCOPE_MARKERS[0].strip("/")
        package.mkdir(parents=True, exist_ok=True)
        (project_root / "pyproject.toml").write_text(
            "[project]\nname = 'project'\nversion = '0.0.0'\n", encoding="utf-8"
        )
        (package / "__init__.py").write_text("", encoding="utf-8")
        return project_root

    def test_empty_workspace_passes(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report, is_=m.Infra.ValidationReport)
        tm.that(report.passed, eq=True)

    def test_non_tomllib_import_passes(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        project_root = self._seed_project(tmp_path)
        package = project_root / c.Infra.METADATA_TARGET_SCOPE_MARKERS[0].strip("/")
        tf(base_dir=package).create("import json\n", "ok.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(project_root))
        tm.that(report.passed, eq=True)

    def test_direct_tomllib_import_fails(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        project_root = self._seed_project(tmp_path)
        package = project_root / c.Infra.METADATA_TARGET_SCOPE_MARKERS[0].strip("/")
        tf(base_dir=package).create("import tomllib\n", "bad.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(project_root))
        tm.that(report.passed, eq=False)
        tm.that(" | ".join(report.violations), has="tomllib")

    def test_allowlisted_metadata_module_passes(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        project_root = self._seed_project(tmp_path)
        scope = c.Infra.METADATA_TARGET_SCOPE_MARKERS[0]
        allowlisted = next(
            marker
            for marker in c.Infra.METADATA_ALLOWLIST_PATH_MARKERS
            if marker.startswith(scope)
        )
        (project_root / allowlisted.lstrip("/")).write_text(
            "import tomllib\n", encoding="utf-8"
        )
        report: m.Infra.ValidationReport = tm.ok(v.build_report(project_root))
        tm.that(report.passed, eq=True)

    def test_outside_target_scope_is_ignored(
        self, tmp_path: Path, v: FlextInfraValidateMetadataDiscipline
    ) -> None:
        external = tmp_path / "other"
        package = external / "src" / "other_pkg"
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "bad.py").write_text("import tomllib\n", encoding="utf-8")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(external))
        tm.that(report.passed, eq=True)
