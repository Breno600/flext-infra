"""CI workflow triggers cover every declared integration branch."""

from __future__ import annotations

from pathlib import Path

from flext_cli import u as cli_u
from flext_infra import c, config, m
from flext_tests import tm


_CI_TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "src/flext_infra/templates/project/base/.github/workflows/ci.yml.j2"
)
_BASELINE_BRANCHES = ("dev", "develop", "0.12.0-dev", "main")


def _render_ci(*, repository_branch: str) -> str:
    codegen = config.Infra.codegen
    spec = m.Infra.GithubWorkflowRenderSpec(
        dist="mcb",
        make_profile=c.Infra.MakeProfile.STANDALONE,
        repository_branch=repository_branch,
        ci_trigger_branches=tuple(
            dict.fromkeys((*_BASELINE_BRANCHES[:-1], repository_branch, "main"))
        ),
        python_version=codegen.toolchain.python_version,
        dependency_cooldown_days=codegen.toolchain.dependency_cooldown_days,
        github_actions=codegen.github_actions,
        make=codegen.make,
        workspace_repositories=(),
        checkout_submodules=codegen.checkout_submodules,
    )
    return tm.ok(cli_u.Cli.template_render(_CI_TEMPLATE, spec))


def _trigger_section(rendered: str) -> str:
    return rendered.split('"on":', maxsplit=1)[1].split(
        "# End SECTION: triggers", maxsplit=1
    )[0]


def _branch_count(triggers: str, branch: str) -> int:
    return triggers.splitlines().count(f"      - {branch}")


def test_ci_triggers_include_custom_workspace_integration_branch() -> None:
    custom_branch = "feature/v0-4-0-multitenant-weaviate"

    triggers = _trigger_section(_render_ci(repository_branch=custom_branch))

    tm.that(_branch_count(triggers, custom_branch), eq=2)
    for baseline in _BASELINE_BRANCHES:
        tm.that(_branch_count(triggers, baseline), eq=2)


def test_ci_triggers_deduplicate_integration_branch_against_baselines() -> None:
    triggers = _trigger_section(_render_ci(repository_branch="develop"))

    for branch in _BASELINE_BRANCHES:
        tm.that(_branch_count(triggers, branch), eq=2)


__all__: tuple[str, ...] = ()
