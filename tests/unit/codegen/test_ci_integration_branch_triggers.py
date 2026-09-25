"""Verify ci.yml branch-trigger generation matches the declared baseline."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from flext_tests import tm

from flext_infra import c, config, u

from ._support import CodegenTestSupport


class TestsFlextInfraCiIntegrationBranchTriggers:
    """Keep integration triggers on one typed owner."""

    ci_template = (
        Path(__file__).resolve().parents[3]
        / "src/flext_infra/templates/project/base/.github/workflows/ci.yml.j2"
    )
    baseline_branches = tuple(config.Infra.codegen.branch_policy.ci_trigger_branches)

    @classmethod
    def render_ci(cls, *, repository_branch: str) -> str:
        spec = CodegenTestSupport.Ci.workflow_spec(
            dist="mcb",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch=repository_branch,
            # The repository's own integration branch joins the SSOT baselines;
            # no positional or named assumption about the baseline contents.
            ci_trigger_branches=tuple(
                dict.fromkeys((*cls.baseline_branches, repository_branch))
            ),
        )
        return tm.ok(u.Cli.template_render(cls.ci_template, spec))

    @staticmethod
    def _trigger_section(rendered: str) -> str:
        return rendered.split('"on":', maxsplit=1)[1].split(
            "# End SECTION: triggers", maxsplit=1
        )[0]

    @staticmethod
    def _branch_count(triggers: str, branch: str) -> int:
        return triggers.splitlines().count(f"      - {branch}")

    def test_ci_triggers_include_custom_workspace_integration_branch(self) -> None:
        custom_branch = "feature/v0-4-0-multitenant-weaviate"
        triggers = self._trigger_section(
            self.render_ci(repository_branch=custom_branch)
        )

        tm.that(self._branch_count(triggers, custom_branch), eq=2)
        for baseline in self.baseline_branches:
            tm.that(self._branch_count(triggers, baseline), eq=2)

    def test_ci_triggers_deduplicate_integration_branch_against_baselines(self) -> None:
        triggers = self._trigger_section(self.render_ci(repository_branch="develop"))

        for branch in self.baseline_branches:
            tm.that(self._branch_count(triggers, branch), eq=2)

    def test_pull_request_title_edits_revalidate_release_metadata(self) -> None:
        """GitHub dispatches the workflow when release-plan's PR title changes."""
        workflow = tm.ok(u.Cli.yaml_parse(self.render_ci(repository_branch="develop")))
        events = workflow["on"]
        assert isinstance(events, Mapping)
        pull_request = events["pull_request"]
        assert isinstance(pull_request, Mapping)
        activities = pull_request["types"]
        assert isinstance(activities, list)

        tm.that(activities, has="edited")


__all__: list[str] = ["TestsFlextInfraCiIntegrationBranchTriggers"]
