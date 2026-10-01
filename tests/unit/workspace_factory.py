"""Workspace factory for FLEXT infra tests.

Creates real FLEXT project structures using centralized test contracts.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import config
from tests import c

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraWorkspaceFactory:
    """Factory for creating test workspaces with real project structures."""

    default_python: str = f"^{config.Infra.codegen.toolchain.python_version}"
    default_version: str = c.Tests.RELEASE_VERSION_BASE
    encoding: str = c.Cli.ENCODING_DEFAULT

    def create_minimal(self, tmp_path: Path, name: t.NonEmptyStr = "test-proj") -> Path:
        """Create a minimal project with pyproject.toml, Makefile, and src/."""
        return self._create_project(tmp_path=tmp_path, name=name, deps=[])

    def create_full(self, tmp_path: Path, name: t.NonEmptyStr) -> Path:
        """Create a full project with docs/, AGENTS.md, and README.md."""
        project_root = self.create_minimal(tmp_path=tmp_path, name=name)
        docs_dir = project_root / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (project_root / "AGENTS.md").write_text(
            "# AGENTS\n\nProject rules.\n", encoding=self.encoding
        )
        (project_root / "README.md").write_text(
            f"# {name}\n\nGenerated full project fixture.\n", encoding=self.encoding
        )
        (docs_dir / "README.md").write_text(
            "# Docs\n\nDocumentation placeholder.\n", encoding=self.encoding
        )
        return project_root

    def create_with_deps(
        self, tmp_path: Path, name: t.NonEmptyStr, deps: t.StrSequence
    ) -> Path:
        """Create a project with the specified dependencies."""
        return self._create_project(tmp_path=tmp_path, name=name, deps=deps)

    def create_workspace(self, tmp_path: Path, projects: int = 3) -> Path:
        """Create a multi-project workspace using real project fixtures."""
        repository_root: Path = tmp_path / "workspace"
        repository_root.mkdir(parents=True, exist_ok=True)
        project_names = [f"test-proj-{idx + 1}" for idx in range(projects)]
        for project_name in project_names:
            self.create_minimal(tmp_path=repository_root, name=project_name)
        workspace_pyproject = (
            "[tool.poetry]\n"
            '"name" = "workspace"\n'
            f'"version" = "{self.default_version}"\n'
            '"description" = "Generated workspace fixture"\n'
            '"authors" = ["FLEXT Tests <tests@flext.dev>"]\n'
        )
        (repository_root / "pyproject.toml").write_text(
            workspace_pyproject, encoding=self.encoding
        )
        (repository_root / "Makefile").write_text(
            "check:\n\t@echo workspace-check\n", encoding=self.encoding
        )
        (repository_root / ".gitmodules").write_text(
            "".join(
                f'[submodule "{name}"]\n\tpath = {name}\n'
                f"\turl = https://github.com/flext-sh/{name}.git\n"
                for name in project_names
            ),
            encoding=self.encoding,
        )
        return repository_root

    def _create_project(
        self, tmp_path: Path, name: t.NonEmptyStr, deps: t.StrSequence
    ) -> Path:
        """Create a project structure with package and tests directories."""
        project_name = name
        project_root: Path = tmp_path / project_name
        package_dir: Path = project_root / "src" / project_name.replace("-", "_")
        tests_dir: Path = project_root / "tests"
        package_dir.mkdir(parents=True, exist_ok=True)
        tests_dir.mkdir(parents=True, exist_ok=True)
        (project_root / "pyproject.toml").write_text(
            self._project_pyproject(name=name, deps=deps), encoding=self.encoding
        )
        (project_root / "Makefile").write_text(
            "check:\n\t@echo project-check\n", encoding=self.encoding
        )
        (package_dir / "__init__.py").write_text(
            f'"""{name} package."""\n', encoding=self.encoding
        )
        (tests_dir / "__init__.py").write_text("", encoding=self.encoding)
        return project_root

    def _project_pyproject(self, name: t.NonEmptyStr, deps: t.StrSequence) -> str:
        """Generate pyproject.toml content using infra constants."""
        project_name: str = name
        default_python: str = self.default_python
        default_version: str = self.default_version
        poetry_tool: str = c.Infra.POETRY
        dependency_group: str = c.Infra.DEPENDENCIES
        dependency_lines = [f'python = "^{default_python.removeprefix("^")}"']
        dependency_lines.extend(f'{dep} = "*"' for dep in deps)
        dependencies = "\n".join(dependency_lines)
        tool_poetry = f"[tool.{poetry_tool}]\n"
        poetry_deps = f"[tool.{poetry_tool}.{dependency_group}]\n"
        return (
            tool_poetry
            + f'name = "{project_name}"\n'
            + f'version = "{default_version}"\n'
            + 'description = "Generated test project"\n'
            + 'authors = ["FLEXT Tests <tests@flext.dev>"]\n'
            + 'packages = [{ include = "'
            + project_name.replace("-", "_")
            + '", from = "src" }]\n\n'
            + poetry_deps
            + f"{dependencies}\n"
        )
