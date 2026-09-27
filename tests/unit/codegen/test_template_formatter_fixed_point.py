"""Generated template formatter fixed-point contracts."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import c, t

from ... import m, u
from ._support import CodegenTestSupport


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
            exports_tuple="()",
            lazy_module_mapping="        MappingProxyType({}),",
            lazy_alias_mapping="        alias_groups=MappingProxyType({}),",
            lazy_call_arguments=(
                "MappingProxyType({}), alias_groups=MappingProxyType({}), "
                "sort_keys=False"
            ),
        )

    @staticmethod
    def _workflow_spec(
        *,
        workspace_repositories: t.VariadicTuple[m.Infra.RepositoryRef],
        has_devcontainer: bool,
    ) -> m.Infra.GithubWorkflowRenderSpec:
        return CodegenTestSupport.Ci.workflow_spec(
            dist="demo",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch="develop",
            ci_trigger_branches=CodegenTestSupport.Ci.CI_TRIGGER_BASELINE_BRANCHES,
            workspace_repositories=workspace_repositories,
            has_devcontainer=has_devcontainer,
        )

    def test_standalone_pyproject_does_not_declare_empty_workspace(
        self, tmp_path: Path
    ) -> None:
        """Keep standalone projects eligible for a real parent uv workspace."""
        rendered = u.Tests.scaffold_text(
            tmp_path / "fixture-project", c.PYPROJECT_FILENAME
        )

        tm.that(rendered, has="[project]")
        tm.that(rendered, lacks="[tool.uv.workspace]")

    def test_dependabot_render_has_one_terminal_newline(self) -> None:
        empty = tm.ok(
            u.Cli.template_render(
                self._TEMPLATES / ".github/dependabot.yml.j2",
                self._workflow_spec(workspace_repositories=(), has_devcontainer=False),
            )
        )
        repository = u.Tests.repository_ref("member", path=Path("member"))
        populated = tm.ok(
            u.Cli.template_render(
                self._TEMPLATES / ".github/dependabot.yml.j2",
                self._workflow_spec(
                    workspace_repositories=(repository,), has_devcontainer=False
                ),
            )
        )

        for rendered in (empty, populated):
            tm.that(rendered.endswith("\n") and not rendered.endswith("\n\n"), eq=True)

    def test_dependabot_projects_devcontainers_only_when_one_exists(self) -> None:
        without = tm.ok(
            u.Cli.template_render(
                self._TEMPLATES / ".github/dependabot.yml.j2",
                self._workflow_spec(workspace_repositories=(), has_devcontainer=False),
            )
        )
        with_devcontainer = tm.ok(
            u.Cli.template_render(
                self._TEMPLATES / ".github/dependabot.yml.j2",
                self._workflow_spec(workspace_repositories=(), has_devcontainer=True),
            )
        )

        tm.that(without, lacks="devcontainers")
        tm.that(with_devcontainer, has="package-ecosystem: devcontainers")
        for rendered in (without, with_devcontainer):
            tm.that(rendered, has="package-ecosystem: pip")

    def test_empty_lazy_root_renders_joined_call_arguments(self) -> None:
        """Keep empty-map roots a fixed point of ``make gen`` and ``make fix``.

        The fixer joins call arguments that fit on one continuation line; a
        template that always explodes them oscillates between the two verbs
        and leaves every member checkout dirty after generation.
        """
        rendered = tm.ok(
            u.Cli.template_render(self._ROOT_TEMPLATE, self._empty_root_render())
        )

        tm.that(
            rendered,
            has="    build_lazy_import_map(\n"
            "        MappingProxyType({}), alias_groups=MappingProxyType({}), "
            "sort_keys=False\n    )",
        )
        tm.that(rendered, lacks="sort_keys=False,")

    def test_lazy_root_keeps_exploded_call_without_joined_arguments(self) -> None:
        """Populated roots still render one argument per line."""
        context = self._empty_root_render().model_copy(
            update={"lazy_call_arguments": ""}
        )

        rendered = tm.ok(u.Cli.template_render(self._ROOT_TEMPLATE, context))

        tm.that(rendered, has="        sort_keys=False,\n    )")
        tm.that(rendered, lacks="sort_keys=False\n")
