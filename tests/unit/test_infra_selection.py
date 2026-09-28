"""Tests for u.Infra.

Tests cover project resolution, filtering, and error handling.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import u

if TYPE_CHECKING:
    from tests import m, t


class TestsFlextInfraInfraSelection:
    """Test suite for u.Infra."""

    @pytest.fixture
    def workspace_with_projects(self, tmp_path: Path) -> Path:
        """Create a temporary workspace with test projects."""
        for name in ["alpha", "beta", "gamma"]:
            proj = tmp_path / name
            proj.mkdir()
            (proj / ".git").mkdir()
            (proj / "Makefile").touch()
            (proj / "pyproject.toml").write_text(
                f'[project]\nname = "{name}"\ndependencies = ["flext-core"]\n'
            )
            package_dir = proj / "src" / name.replace("-", "_")
            package_dir.mkdir(parents=True)
            (package_dir / "__init__.py").write_text("")
        (tmp_path / ".gitmodules").write_text(
            "".join(
                f'[submodule "{name}"]\n\tpath = {name}\n'
                f"\turl = https://github.com/flext-sh/{name}.git\n"
                for name in ("alpha", "beta", "gamma")
            )
        )
        return tmp_path

    @pytest.fixture
    def selector(self) -> type[u.Infra]:
        """Provide project selector utilities class."""
        selector_cls: type[u.Infra] = u.Infra
        return selector_cls

    @pytest.fixture
    def workspace_with_declared_names(self, tmp_path: Path) -> Path:
        """Create projects whose declared names differ from directory names."""
        for directory_name, project_name in [
            ("core-alias", "flext-core"),
            ("cli-alias", "flext-cli"),
        ]:
            proj = tmp_path / directory_name
            proj.mkdir()
            (proj / ".git").mkdir()
            (proj / "Makefile").touch()
            package_dir = proj / "src" / project_name.replace("-", "_")
            package_dir.mkdir(parents=True)
            (proj / "pyproject.toml").write_text(
                f'[project]\nname = "{project_name}"\ndependencies = ["flext-core"]\n'
            )
            (package_dir / "__init__.py").write_text("")
        (tmp_path / ".gitmodules").write_text(
            "".join(
                f'[submodule "{directory}"]\n\tpath = {directory}\n'
                f"\turl = https://github.com/flext-sh/{project}.git\n"
                for directory, project in (
                    ("core-alias", "flext-core"),
                    ("cli-alias", "flext-cli"),
                )
            )
        )
        return tmp_path

    @pytest.fixture
    def workspace_with_nested_members(self, tmp_path: Path) -> Path:
        (tmp_path / ".git").mkdir()
        (tmp_path / "Makefile").touch()
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "workspace"\ndependencies = ["flext-core"]\n'
        )
        (tmp_path / ".gitmodules").write_text(
            '[submodule "member-one"]\n\tpath = apps/member-one\n'
            "\turl = https://github.com/flext-sh/member-one.git\n"
            '[submodule "member-two"]\n\tpath = apps/member-two\n'
            "\turl = https://github.com/flext-sh/member-two.git\n"
        )
        root_package = tmp_path / "src" / "workspace"
        root_package.mkdir(parents=True)
        (root_package / "__init__.py").touch()
        for name in ("member-one", "member-two"):
            project = tmp_path / "apps" / name
            project.mkdir(parents=True)
            (project / "Makefile").touch()
            (project / "pyproject.toml").write_text(
                f'[project]\nname = "{name}"\ndependencies = ["flext-core"]\n'
            )
            package = project / "src" / name.replace("-", "_")
            package.mkdir(parents=True)
            (package / "__init__.py").touch()
        return tmp_path

    def test_resolve_projects_all_projects(
        self, selector: type[u.Infra], workspace_with_projects: Path
    ) -> None:
        """Test resolving all projects when names list is empty."""
        result = selector.resolve_projects(workspace_with_projects, [])
        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that(projects, length=3)
        tm.that([p.name for p in projects], eq=["alpha", "beta", "gamma"])

    def test_resolve_projects_specific_names(
        self, selector: type[u.Infra], workspace_with_projects: Path
    ) -> None:
        """Test resolving specific projects by name."""
        result = selector.resolve_projects(workspace_with_projects, ["beta", "alpha"])
        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that(projects, length=2)
        tm.that([p.name for p in projects], eq=["alpha", "beta"])

    def test_resolve_projects_single_project(
        self, selector: type[u.Infra], workspace_with_projects: Path
    ) -> None:
        """Test resolving a single project."""
        result = selector.resolve_projects(workspace_with_projects, ["gamma"])
        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that(projects, length=1)
        tm.that(projects[0].name, eq="gamma")

    def test_resolve_projects_unknown_project(
        self, selector: type[u.Infra], workspace_with_projects: Path
    ) -> None:
        """Test resolving with unknown project name."""
        result = selector.resolve_projects(workspace_with_projects, ["unknown"])
        tm.fail(result, has="unknown projects")

    def test_resolve_projects_mixed_known_unknown(
        self, selector: type[u.Infra], workspace_with_projects: Path
    ) -> None:
        """Test resolving with mix of known and unknown projects."""
        result = selector.resolve_projects(
            workspace_with_projects, ["alpha", "unknown", "beta"]
        )
        tm.fail(result, has="unknown projects")

    def test_resolve_projects_discovery_failure(self, selector: type[u.Infra]) -> None:
        """Test handling discovery failure with non-existent path."""
        result = selector.resolve_projects(Path("/nonexistent/path"), ["alpha"])
        tm.fail(result)

    def test_resolve_projects_sorted_output(
        self, selector: type[u.Infra], workspace_with_projects: Path
    ) -> None:
        """Test that resolved projects are sorted by name."""
        result = selector.resolve_projects(
            workspace_with_projects, ["gamma", "alpha", "beta"]
        )
        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that([p.name for p in projects], eq=["alpha", "beta", "gamma"])

    def test_resolve_projects_result_type(
        self, selector: type[u.Infra], workspace_with_projects: Path
    ) -> None:
        """Test that result contains properly typed ProjectInfo items."""
        result = selector.resolve_projects(workspace_with_projects, [])
        tm.ok(result)
        projects: t.SequenceOf[m.Infra.ProjectInfo] = result.value
        tm.that(len(projects), eq=3)
        tm.that([p.name for p in projects], eq=["alpha", "beta", "gamma"])

    def test_resolve_projects_accepts_directory_aliases(
        self, selector: type[u.Infra], workspace_with_declared_names: Path
    ) -> None:
        """Test resolving projects by directory name alias."""
        result = selector.resolve_projects(
            workspace_with_declared_names, ["core-alias", "cli-alias"]
        )
        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that([p.name for p in projects], eq=["flext-cli", "flext-core"])

    def test_resolve_projects_accepts_declared_names(
        self, selector: type[u.Infra], workspace_with_declared_names: Path
    ) -> None:
        """Test resolving projects by declared project.name."""
        result = selector.resolve_projects(
            workspace_with_declared_names, ["flext-core", "flext-cli"]
        )
        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that([p.path.name for p in projects], eq=["cli-alias", "core-alias"])

    def test_selector_with_default_discovery(
        self, selector: type[u.Infra], workspace_with_projects: Path
    ) -> None:
        """Test selector uses default discovery service implicitly."""
        result = selector.resolve_projects(workspace_with_projects, [])
        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that(projects, length=3)

    def test_selector_resolve_projects_empty_list(
        self, selector: type[u.Infra], tmp_path: Path
    ) -> None:
        """Test resolve_projects returns empty list when no projects match."""
        result = selector.resolve_projects(tmp_path, [])
        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that(projects, empty=True)

    def test_resolve_projects_includes_root_and_nested_members(
        self, selector: type[u.Infra], workspace_with_nested_members: Path
    ) -> None:
        result = selector.resolve_projects(workspace_with_nested_members, ())

        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that(
            [project.name for project in projects],
            eq=["member-one", "member-two", "workspace"],
        )

    @pytest.mark.parametrize("name", [".", "workspace"])
    def test_resolve_projects_accepts_root_aliases(
        self, selector: type[u.Infra], workspace_with_nested_members: Path, name: str
    ) -> None:
        result = selector.resolve_projects(workspace_with_nested_members, (name,))

        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that([project.name for project in projects], eq=["workspace"])

    def test_resolve_projects_accepts_nested_member_path(
        self, selector: type[u.Infra], workspace_with_nested_members: Path
    ) -> None:
        result = selector.resolve_projects(
            workspace_with_nested_members, ("apps/member-one",)
        )

        projects: t.SequenceOf[m.Infra.ProjectInfo] = tm.ok(result)
        tm.that([project.name for project in projects], eq=["member-one"])
