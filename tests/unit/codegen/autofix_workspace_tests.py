"""Tests for FlextInfraCodegenFixer workspace-level operations.

Validates project exclusion, empty src handling, and files_modified tracking.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.codegen.fixer import FlextInfraCodegenFixer
from tests import u

if TYPE_CHECKING:
    from tests import m


class TestsFlextInfraCodegenAutofixWorkspace:
    """Test suite for FlextInfraCodegenFixer workspace-level operations."""

    def _project_info(
        self, project: Path, *, package_name: str = "test_proj"
    ) -> m.Infra.ProjectInfo:
        return u.Tests.create_project_info(
            project, name=project.name, package_name=package_name
        )

    @pytest.mark.slow
    def test_project_without_pyproject_excluded_from_run(self, tmp_path: Path) -> None:
        external_project = tmp_path / "external-project"
        external_project.mkdir()
        (external_project / "Makefile").touch()
        (external_project / ".git").mkdir()
        pkg = external_project / "src" / "external_project"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        (pkg / "typings.py").write_text("pass\n")
        (pkg / "constants.py").write_text("pass\n")
        (pkg / "base.py").write_text("import typing\nT = typing.TypeVar('T')\n")
        managed_project = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="test-proj",
            pkg_name="test_proj",
            files={
                "base.py": "import typing\nT = typing.TypeVar('T')\n"
                "class TestProjBase:\n    pass\n\n"
                '__all__: list[str] = ["TestProjBase", "T"]\n'
            },
        )
        u.Tests.declare_workspace_projects(tmp_path, (managed_project.name,))
        fixer = FlextInfraCodegenFixer(repository_root=tmp_path)
        results = fixer.fix_workspace()
        project_names = [res.project for res in results]
        tm.that("external-project" not in project_names, eq=True)
        tm.that(project_names, has="test-proj")

    def test_project_without_src_returns_empty(self, tmp_path: Path) -> None:
        project = tmp_path / "no-src-proj"
        project.mkdir()
        (project / "Makefile").touch()
        (project / "pyproject.toml").write_text("[project]\nname='no-src-proj'\n")
        (project / ".git").mkdir()
        fixer = FlextInfraCodegenFixer(repository_root=tmp_path)
        [result] = fixer.fix_workspace(
            projects=[self._project_info(project, package_name="")]
        )
        tm.that(result.project, eq="no-src-proj")
        tm.that(result.violations_fixed, empty=True)
        tm.that(result.violations_skipped, empty=True)
        tm.that(result.files_modified, empty=True)

    def test_files_modified_tracks_affected_files(self, tmp_path: Path) -> None:
        project = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="test-proj",
            pkg_name="test_proj",
            files={
                "base.py": "from typing import Final\nMAX_RETRIES: Final = 3\n"
                "class TestProjBase:\n    pass\n\n"
                '__all__: list[str] = ["MAX_RETRIES", "TestProjBase"]\n',
                "constants.py": "class TestProjConstants:\n    pass\n",
            },
        )
        fixer = FlextInfraCodegenFixer(repository_root=tmp_path)
        [result] = fixer.fix_workspace(projects=[self._project_info(project)])
        modified_paths = tuple(Path(path) for path in result.files_modified)
        tm.that(modified_paths, length_gte=1)
        tm.that(all(path.is_file() for path in modified_paths), where=bool)
        tm.that(any(path.name == "constants.py" for path in modified_paths), where=bool)
        tm.that(any(path.name == "__init__.py" for path in modified_paths), eq=False)
