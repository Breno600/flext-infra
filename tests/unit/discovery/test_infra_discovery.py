"""Tests for FlextInfraDiscoveryService.

Tests cover project discovery, pyproject file discovery, and error handling.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import c, m, u

if TYPE_CHECKING:
    from tests import t


class TestsFlextInfraDiscoveryInfraDiscovery:
    @pytest.fixture
    def service(self) -> u.Infra:
        return u.Infra()

    @pytest.fixture
    def workspace_with_projects(self, tmp_path: Path) -> Path:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='workspace'\n", encoding="utf-8"
        )
        proj1 = tmp_path / "project1"
        proj1.mkdir()
        (proj1 / "pyproject.toml").write_text(
            "[project]\nname='project1'\nversion='0.1.0'\n"
            "dependencies=['flext-core>=0.1.0']\n",
            encoding="utf-8",
        )
        (proj1 / "src").mkdir()
        (proj1 / "tests").mkdir()
        proj2 = tmp_path / "project2"
        proj2.mkdir()
        (proj2 / "pyproject.toml").write_text(
            "[project]\nname='project2'\n", encoding="utf-8"
        )
        invalid = tmp_path / "invalid"
        invalid.mkdir()
        (invalid / "pyproject.toml").write_text(
            "[project]\nname='invalid'\n", encoding="utf-8"
        )
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "pyproject.toml").write_text(
            "[project]\nname='hidden'\ndependencies=['flext-core>=0.1.0']\n",
            encoding="utf-8",
        )
        (tmp_path / ".gitmodules").write_text(
            '[submodule "project1"]\n\tpath = project1\n\turl = https://github.com/flext-sh/project1.git\n'
            '[submodule "project2"]\n\tpath = project2\n\turl = https://github.com/flext-sh/project2.git\n',
            encoding="utf-8",
        )
        return tmp_path

    def test_discover_projects_happy_path(
        self, service: u.Infra, workspace_with_projects: Path
    ) -> None:
        result = service.discover_projects(workspace_with_projects)
        tm.ok(result)
        projects = result.value
        tm.that(len(projects), eq=2)
        tm.that(projects[0].name, eq="project1")
        tm.that(projects[1].name, eq="project2")
        tm.that(projects[0].has_tests, eq=True)
        tm.that(projects[0].has_src, eq=True)
        tm.that(projects[1].has_src, eq=False)
        tm.that(projects[1].has_tests, eq=False)
        tm.that(projects[0].make_profile, eq=c.Infra.MakeProfile.STANDALONE)
        tm.that(projects[0].declared_subproject, eq=True)
        tm.that(projects[1].declared_subproject, eq=True)

    def test_discover_projects_empty_workspace(
        self, service: u.Infra, tmp_path: Path
    ) -> None:
        result = service.discover_projects(tmp_path)
        tm.ok(result)
        tm.that(result.value, eq=[])

    def test_discover_projects_nonexistent_path(
        self, service: u.Infra, tmp_path: Path
    ) -> None:
        nonexistent = tmp_path / "missing"
        result = service.discover_projects(nonexistent)
        tm.fail(result)
        tm.that(result.error or "", has=str(nonexistent))

    def test_find_all_pyproject_files_happy_path(
        self, service: u.Infra, tmp_path: Path
    ) -> None:
        (tmp_path / "project1").mkdir()
        (tmp_path / "project1" / "pyproject.toml").touch()
        (tmp_path / "project2").mkdir()
        (tmp_path / "project2" / "pyproject.toml").touch()
        (tmp_path / "project2" / "subdir").mkdir()
        (tmp_path / "project2" / "subdir" / "pyproject.toml").touch()
        result = service.find_all_pyproject_files(tmp_path)
        tm.ok(result)
        files = result.value
        tm.that(len(files), eq=3)
        tm.that(all(f.name == "pyproject.toml" for f in files), eq=True)

    def test_find_all_pyproject_files_with_skip_dirs(
        self, service: u.Infra, tmp_path: Path
    ) -> None:
        (tmp_path / "project1").mkdir()
        (tmp_path / "project1" / "pyproject.toml").touch()
        (tmp_path / "skip_me").mkdir()
        (tmp_path / "skip_me" / "pyproject.toml").touch()
        result = service.find_all_pyproject_files(
            tmp_path, skip_dirs=frozenset({"skip_me"})
        )
        tm.ok(result)
        files = result.value
        tm.that(len(files), eq=1)
        tm.that(str(files[0]), lacks="skip_me")

    def test_find_all_pyproject_files_with_project_paths(
        self, service: u.Infra, tmp_path: Path
    ) -> None:
        proj1 = tmp_path / "project1"
        proj2 = tmp_path / "project2"
        proj1.mkdir()
        proj2.mkdir()
        (proj1 / "pyproject.toml").touch()
        (proj2 / "pyproject.toml").touch()
        result = service.find_all_pyproject_files(tmp_path, project_paths=[proj1])
        tm.ok(result)
        files = result.value
        tm.that(len(files), eq=1)
        tm.that(files[0].parent, eq=proj1)

    def test_discover_projects_result_type(
        self, service: u.Infra, workspace_with_projects: Path
    ) -> None:
        result = service.discover_projects(workspace_with_projects)
        tm.ok(result)
        projects: t.SequenceOf[m.Infra.ProjectInfo] = result.value
        for item in projects:
            tm.that(item, is_=m.Infra.ProjectInfo)

    def test_discover_projects_empty_workspace_v2(
        self, service: u.Infra, tmp_path: Path
    ) -> None:
        result = service.discover_projects(tmp_path)
        tm.ok(result)
        tm.that(result.value, eq=[])

    def test_discover_projects_prefers_workspace_children_over_root_project(
        self, service: u.Infra, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='workspace'\ndependencies=['flext-core>=0.1.0']\n",
            encoding="utf-8",
        )
        project1 = tmp_path / "project1"
        project1.mkdir()
        (project1 / "pyproject.toml").write_text(
            "[project]\nname='project1'\nversion='0.1.0'\n"
            "dependencies=['flext-core>=0.1.0']\n",
            encoding="utf-8",
        )
        project2 = tmp_path / "project2"
        project2.mkdir()
        (project2 / "pyproject.toml").write_text(
            "[project]\nname='project2'\n", encoding="utf-8"
        )
        (tmp_path / ".gitmodules").write_text(
            '[submodule "project1"]\n\tpath = project1\n\turl = https://github.com/flext-sh/project1.git\n'
            '[submodule "project2"]\n\tpath = project2\n\turl = https://github.com/flext-sh/project2.git\n',
            encoding="utf-8",
        )

        result = service.discover_projects(tmp_path)

        tm.ok(result)
        tm.that([project.name for project in result.value], eq=["project1", "project2"])

    def test_discover_projects_derives_package_name_from_hatch_packages(
        self, service: u.Infra, tmp_path: Path
    ) -> None:
        project = tmp_path
        package_dir = project / "src" / "custom_pkg"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            "[project]\n"
            "name='project1'\n"
            "dependencies=['flext-core>=0.1.0']\n\n"
            "[tool.hatch.build.targets.wheel]\n"
            "packages=['src/custom_pkg']\n",
            encoding="utf-8",
        )

        result = service.discover_projects(tmp_path)

        tm.ok(result)
        tm.that(len(result.value), eq=1)
        tm.that(result.value[0].package_name, eq="custom_pkg")

    def test_discover_projects_accepts_standalone_governed_root_without_core_dep(
        self, service: u.Infra, tmp_path: Path
    ) -> None:
        package_dir = tmp_path / "src" / "demo_pkg"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "Makefile").write_text("check:\n\t@true\n", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='demo-project'\nversion='0.1.0'\n", encoding="utf-8"
        )

        result = service.discover_projects(tmp_path)

        tm.ok(result)
        tm.that(len(result.value), eq=1)
        tm.that(result.value[0].path, eq=tmp_path.resolve())
        tm.that(result.value[0].name, eq="demo-project")
        tm.that(result.value[0].package_name, eq="demo_pkg")
