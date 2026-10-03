"""Public tests for docs scope utilities.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsShared:
    """Public tests for docs scope utilities."""

    @staticmethod
    def test_doc_scope_creation(tmp_path: Path) -> None:
        """Test doc scope creation."""
        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        scope = m.Infra.DocScope(name="flext-a", path=tmp_path, report_dir=report_dir)

        tm.that(scope.name, eq="flext-a")
        tm.that(scope.path, eq=tmp_path)
        tm.that(scope.report_dir, eq=report_dir)

    @staticmethod
    def test_doc_scope_requires_name(tmp_path: Path) -> None:
        """Test doc scope requires name."""
        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(c.ValidationError):
            m.Infra.DocScope(name="", path=tmp_path, report_dir=report_dir)

    @staticmethod
    def test_build_scopes_returns_root_and_selected_projects(
        tmp_path: Path,
    ) -> None:
        """Test build scopes returns root and selected projects."""
        workspace = u.Tests.create_docs_workspace(
            tmp_path,
            project_names=("flext-a", "flext-b"),
        )

        result = u.Infra.build_scopes(
            workspace,
            projects=["flext-a"],
            output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR,
        )

        tm.ok(result)
        tm.that([scope.name for scope in result.value], eq=["root", "flext-a"])

    @staticmethod
    def test_build_scopes_without_filter_still_returns_root_scope(
        tmp_path: Path,
    ) -> None:
        # Why (X-70): a member-less workspace root that declares its own
        # pyproject.toml is a governed single-project scope named after itself
        # ("workspace"), not the synthetic "root" scope used for a member-bearing
        # workspace.
        """Test build scopes without filter still returns root scope."""
        workspace = u.Tests.create_docs_workspace(tmp_path)

        result = u.Infra.build_scopes(
            workspace,
            projects=None,
            output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR,
        )

        tm.ok(result)
        tm.that([scope.name for scope in result.value], eq=["workspace"])

    @staticmethod
    def test_build_scopes_treats_non_flext_project_as_its_own_root(
        tmp_path: Path,
    ) -> None:
        """Test build scopes treats non flext project as its own root."""
        project_root = tmp_path / "acme-content"
        project_root.mkdir()
        (project_root / c.PYPROJECT_FILENAME).write_text(
            "[project]\nname='acme-content'\n",
            encoding="utf-8",
        )

        result = u.Infra.build_scopes(
            project_root,
            projects=None,
            output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR,
        )

        tm.ok(result)
        tm.that(
            [(scope.name, scope.path) for scope in result.value],
            eq=[("acme-content", project_root)],
        )

    @staticmethod
    def test_build_scopes_preserves_declared_repository_root_and_projects(
        tmp_path: Path,
    ) -> None:
        """Test build scopes preserves declared repository root and projects."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        (workspace / c.PYPROJECT_FILENAME).write_text(
            "[project]\nname='workspace'\n\n[tool.uv.workspace]\nmembers=['flext-a']\n",
            encoding="utf-8",
        )

        result = u.Infra.build_scopes(
            workspace,
            projects=["flext-a"],
            output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR,
        )

        tm.ok(result)
        tm.that(
            [(scope.name, scope.path) for scope in result.value],
            eq=[("root", workspace), ("flext-a", workspace / "flext-a")],
        )

    @staticmethod
    def test_build_scopes_skips_declared_workspace_without_materialized_projects(
        tmp_path: Path,
    ) -> None:
        """Test build scopes skips declared workspace without materialized projects."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / c.PYPROJECT_FILENAME).write_text(
            "[project]\nname='workspace'\n\n[tool.uv.workspace]\nmembers=['flext-a']\n",
            encoding="utf-8",
        )
        (workspace / ".gitmodules").write_text(
            '[submodule "flext-a"]\n\tpath = flext-a\n'
            "\turl = https://github.com/flext-sh/flext-a.git\n",
            encoding="utf-8",
        )

        result = u.Infra.build_scopes(
            workspace,
            projects=None,
            output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR,
        )

        tm.ok(result)
        tm.that(
            [(scope.name, scope.path) for scope in result.value],
            eq=[("root", workspace)],
        )

    @staticmethod
    def test_build_scopes_preserves_disabled_root_policy(tmp_path: Path) -> None:
        """Test build scopes preserves disabled root policy."""
        project_root = tmp_path / "acme-content"
        project_root.mkdir()
        (project_root / c.PYPROJECT_FILENAME).write_text(
            "[project]\nname='acme-content'\n\n[tool.flext.docs]\nenabled=false\n",
            encoding="utf-8",
        )
        result = u.Infra.build_scopes(
            project_root,
            projects=None,
            output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR,
        )

        tm.ok(result)
        tm.that(
            [(scope.name, scope.path) for scope in result.value],
            eq=[("root", project_root)],
        )

    @staticmethod
    def test_build_scopes_uses_custom_output_dir(tmp_path: Path) -> None:
        """Test build scopes uses custom output dir."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        result = u.Infra.build_scopes(
            workspace,
            projects=["flext-a"],
            output_dir=".custom-docs",
        )

        tm.ok(result)
        tm.that(result.value[0].report_dir, eq=workspace / ".custom-docs")
        tm.that(result.value[1].report_dir, eq=workspace / "flext-a/.custom-docs")

    @staticmethod
    def test_build_scopes_skips_missing_projects(tmp_path: Path) -> None:
        # Why (X-70): see test_build_scopes_without_filter_still_returns_root_scope.
        """Test build scopes skips missing projects."""
        workspace = u.Tests.create_docs_workspace(tmp_path)

        result = u.Infra.build_scopes(
            workspace,
            projects=["flext-missing"],
            output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR,
        )

        tm.ok(result)
        tm.that([scope.name for scope in result.value], eq=["workspace"])

    @staticmethod
    def test_build_scopes_preserves_discovered_package_name(
        tmp_path: Path,
    ) -> None:
        """Test build scopes preserves discovered package name."""
        workspace = tmp_path / "workspace"
        project_root = workspace / "flext-demo"
        package_root = project_root / "src" / "demo_pkg"
        package_root.mkdir(parents=True)
        (workspace / c.PYPROJECT_FILENAME).write_text(
            "[project]\nname='workspace'\n\n[tool.uv.workspace]\nmembers=['flext-demo']\n",
            encoding="utf-8",
        )
        (package_root / "__init__.py").write_text("", encoding="utf-8")
        (project_root / c.PYPROJECT_FILENAME).write_text(
            "[project]\n"
            "name='flext-demo'\n"
            "dependencies=['flext-core>=0.1.0']\n\n"
            "[tool.hatch.build.targets.wheel]\n"
            "packages=['src/demo_pkg']\n",
            encoding="utf-8",
        )
        u.Tests.declare_workspace_projects(workspace, ("flext-demo",))

        result = u.Infra.build_scopes(
            workspace,
            projects=["flext-demo"],
            output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR,
        )

        tm.ok(result)
        tm.that(len(result.value), eq=2)
        tm.that(
            [scope.name for scope in result.value],
            eq=[c.Infra.RK_ROOT, "flext-demo"],
        )
        tm.that(result.value[1].package_name, eq="demo_pkg")
