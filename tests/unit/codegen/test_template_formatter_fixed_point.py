"""Generated template formatter fixed-point contracts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import c, m, t, u


class TestsFlextInfraTemplateFormatterFixedPoint:
    """Verify generated template formatter fixed-point contracts."""

    _TEMPLATES = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "flext_infra"
        / "templates"
        / "project"
        / "base"
    )

    _ROOT_TEMPLATE = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "flext_infra"
        / "templates"
        / "lazy_init_root.py.j2"
    )

    @staticmethod
    def _empty_root_render() -> m.Infra.LazyInitRootRender:
        return m.Infra.LazyInitRootRender(
            autogen_header=c.Infra.AUTOGEN_HEADER,
            docstring='"""Tests package."""',
            runtime_import_lines=(
                f"from {c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE} import "
                "install_lazy_exports"
            ),
            exports_tuple="()",
            lazy_export_mapping="    MappingProxyType({}),",
        )

    @staticmethod
    def _workflow_spec(
        *,
        workspace_repositories: t.VariadicTuple[m.Infra.RepositoryRef],
        has_devcontainer: bool,
    ) -> m.Infra.GithubWorkflowRenderSpec:
        return u.CodegenTestSupport.Ci.workflow_spec(
            dist="demo",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch="develop",
            ci_trigger_branches=u.CodegenTestSupport.Ci.ci_trigger_branches("develop"),
            overrides=u.CodegenTestSupport.Ci.WorkflowRenderOverrides(
                workspace_repositories=workspace_repositories,
                has_devcontainer=has_devcontainer,
            ),
        )

    @staticmethod
    def test_standalone_pyproject_does_not_declare_empty_workspace(
        tmp_path: Path,
    ) -> None:
        """Keep standalone projects eligible for a real parent uv workspace."""
        rendered = u.Tests.scaffold_text(
            tmp_path / "fixture-project",
            c.PYPROJECT_FILENAME,
        )

        tm.that(rendered, has="[project]")
        tm.that(rendered, lacks="[tool.uv.workspace]")

    def test_dependabot_render_has_one_terminal_newline(self) -> None:
        """Test dependabot render has one terminal newline."""
        empty = tm.ok(
            u.Cli.template_render(
                self._TEMPLATES / ".github/dependabot.yml.j2",
                self._workflow_spec(workspace_repositories=(), has_devcontainer=False),
            ),
        )
        repository = u.Tests.repository_ref("member", path=Path("member"))
        populated = tm.ok(
            u.Cli.template_render(
                self._TEMPLATES / ".github/dependabot.yml.j2",
                self._workflow_spec(
                    workspace_repositories=(repository,),
                    has_devcontainer=False,
                ),
            ),
        )

        for rendered in (empty, populated):
            tm.that(rendered.endswith("\n") and not rendered.endswith("\n\n"), eq=True)

    def test_dependabot_projects_devcontainers_only_when_one_exists(self) -> None:
        """Test dependabot projects devcontainers only when one exists."""
        without = tm.ok(
            u.Cli.template_render(
                self._TEMPLATES / ".github/dependabot.yml.j2",
                self._workflow_spec(workspace_repositories=(), has_devcontainer=False),
            ),
        )
        with_devcontainer = tm.ok(
            u.Cli.template_render(
                self._TEMPLATES / ".github/dependabot.yml.j2",
                self._workflow_spec(workspace_repositories=(), has_devcontainer=True),
            ),
        )

        tm.that(without, lacks="devcontainers")
        tm.that(with_devcontainer, has="package-ecosystem: devcontainers")
        for rendered in (without, with_devcontainer):
            tm.that(rendered, has="package-ecosystem: pip")

    def test_lazy_root_renders_one_argument_per_line_with_trailing_commas(self) -> None:
        """Render the formatter fixed point under magic trailing commas.

        Ruff respects magic trailing commas and COM812 demands one on every
        exploded call, so the projection is the one-argument-per-line form
        with a trailing comma after each argument, including the flat map.
        """
        rendered = tm.ok(
            u.Cli.template_render(self._ROOT_TEMPLATE, self._empty_root_render()),
        )

        tm.that(
            rendered,
            has="    MappingProxyType({}),\n    public_exports=__all__,\n)",
        )
