"""Public tests for docs scope utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsShared:
    """Public tests for docs scope utilities."""

    def test_doc_scope_creation(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        scope = m.Infra.DocScope(name="flext-a", path=tmp_path, report_dir=report_dir)

        tm.that(scope.name, eq="flext-a")
        tm.that(scope.path, eq=tmp_path)
        tm.that(scope.report_dir, eq=report_dir)

    def test_doc_scope_requires_name(self, tmp_path: Path) -> None:
        report_dir = tmp_path / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        with pytest.raises(c.ValidationError):
            m.Infra.DocScope(name="", path=tmp_path, report_dir=report_dir)

    def test_build_scopes_returns_root_and_selected_projects(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(
            tmp_path, project_names=("flext-a", "flext-b")
        )

        result = u.Infra.build_scopes(
            workspace, projects=["flext-a"], output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR
        )

        tm.ok(result)
        tm.that([scope.name for scope in result.value], eq=["root", "flext-a"])

    def test_build_scopes_without_filter_still_returns_root_scope(
        self, tmp_path: Path
    ) -> None:
        # Why (X-70): a member-less workspace root that declares its own
        # pyproject.toml is a governed single-project scope named after itself
        # ("workspace"), not the synthetic "root" scope used for a member-bearing
        # workspace.
        workspace = u.Tests.create_docs_workspace(tmp_path)

        result = u.Infra.build_scopes(
            workspace, projects=None, output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR
        )

        tm.ok(result)
        tm.that([scope.name for scope in result.value], eq=["workspace"])

    def test_build_scopes_treats_non_flext_project_as_its_own_root(
        self, tmp_path: Path
    ) -> None:
        project_root = tmp_path / "acme-content"
        project_root.mkdir()
        (project_root / c.PYPROJECT_FILENAME).write_text(
            "[project]\nname='acme-content'\n", encoding="utf-8"
        )

        result = u.Infra.build_scopes(
            project_root, projects=None, output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR
        )

        tm.ok(result)
        tm.that(
            [(scope.name, scope.path) for scope in result.value],
            eq=[("acme-content", project_root)],
        )

    def test_build_scopes_preserves_declared_repository_root_and_projects(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        (workspace / c.PYPROJECT_FILENAME).write_text(
            "[project]\nname='workspace'\n\n[tool.uv.workspace]\nmembers=['flext-a']\n",
            encoding="utf-8",
        )

        result = u.Infra.build_scopes(
            workspace, projects=["flext-a"], output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR
        )

        tm.ok(result)
        tm.that(
            [(scope.name, scope.path) for scope in result.value],
            eq=[("root", workspace), ("flext-a", workspace / "flext-a")],
        )

    def test_build_scopes_skips_declared_workspace_without_materialized_projects(
        self, tmp_path: Path
    ) -> None:
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
            workspace, projects=None, output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR
        )

        tm.ok(result)
        tm.that(
            [(scope.name, scope.path) for scope in result.value],
            eq=[("root", workspace)],
        )

    def test_build_scopes_preserves_disabled_root_policy(self, tmp_path: Path) -> None:
        project_root = tmp_path / "acme-content"
        project_root.mkdir()
        (project_root / c.PYPROJECT_FILENAME).write_text(
            "[project]\nname='acme-content'\n\n[tool.flext.docs]\nenabled=false\n",
            encoding="utf-8",
        )
        result = u.Infra.build_scopes(
            project_root, projects=None, output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR
        )

        tm.ok(result)
        tm.that(
            [(scope.name, scope.path) for scope in result.value],
            eq=[("root", project_root)],
        )

    def test_build_scopes_uses_custom_output_dir(self, tmp_path: Path) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        result = u.Infra.build_scopes(
            workspace, projects=["flext-a"], output_dir=".custom-docs"
        )

        tm.ok(result)
        tm.that(result.value[0].report_dir, eq=workspace / ".custom-docs")
        tm.that(result.value[1].report_dir, eq=workspace / "flext-a/.custom-docs")

    def test_build_scopes_skips_missing_projects(self, tmp_path: Path) -> None:
        # Why (X-70): see test_build_scopes_without_filter_still_returns_root_scope.
        workspace = u.Tests.create_docs_workspace(tmp_path)

        result = u.Infra.build_scopes(
            workspace,
            projects=["flext-missing"],
            output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR,
        )

        tm.ok(result)
        tm.that([scope.name for scope in result.value], eq=["workspace"])

    def test_build_scopes_preserves_discovered_package_name(
        self, tmp_path: Path
    ) -> None:
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
            [scope.name for scope in result.value], eq=[c.Infra.RK_ROOT, "flext-demo"]
        )
        tm.that(result.value[1].package_name, eq="demo_pkg")
