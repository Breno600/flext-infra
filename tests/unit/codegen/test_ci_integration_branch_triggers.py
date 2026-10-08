"""Verify ci.yml branch-trigger generation matches the declared baseline.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m
from tests import u


class TestsFlextInfraCiIntegrationBranchTriggers:
    """Keep integration triggers on one typed owner."""

    ci_template = (
        Path(__file__).resolve().parents[3]
        / "src/flext_infra/templates/project/base/.github/workflows/ci.yml.j2"
    )
    baseline_branches = tuple(config.Infra.codegen.branch_policy.ci_trigger_branches)

    @classmethod
    def render_ci(cls, *, repository_branch: str) -> str:
        """Provide ``render_ci``.

        Returns:
            The resulting ``str``.

        """
        spec = u.CodegenTestSupport.Ci.workflow_spec(
            dist="mcb",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch=repository_branch,
            # The repository's own integration branch joins the SSOT baselines;
            # no positional or named assumption about the baseline contents.
            ci_trigger_branches=tuple(
                dict.fromkeys((*cls.baseline_branches, repository_branch)),
            ),
        )
        return tm.ok(u.Cli.template_render(cls.ci_template, spec))

    @staticmethod
    def _trigger_section(rendered: str) -> str:
        return rendered.split('"on":', maxsplit=1)[1].split(
            "# End SECTION: triggers",
            maxsplit=1,
        )[0]

    @staticmethod
    def _branch_count(triggers: str, branch: str) -> int:
        return triggers.splitlines().count(f"      - {branch}")

    def test_ci_triggers_include_custom_workspace_integration_branch(self) -> None:
        """Test ci triggers include custom workspace integration branch."""
        custom_branch = "feature/v0-4-0-multitenant-weaviate"
        triggers = self._trigger_section(
            self.render_ci(repository_branch=custom_branch),
        )

        tm.that(self._branch_count(triggers, custom_branch), eq=2)
        for baseline in self.baseline_branches:
            tm.that(self._branch_count(triggers, baseline), eq=2)

    def test_ci_triggers_deduplicate_integration_branch_against_baselines(self) -> None:
        """Test ci triggers deduplicate integration branch against baselines."""
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

    @staticmethod
    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_ci_and_hook_share_the_mandatory_public_approval(
        profile: c.Infra.MakeProfile,
    ) -> None:
        """Both projected profiles invoke the same typed approval."""
        codegen = config.Infra.codegen
        spec = u.CodegenTestSupport.Ci.workflow_spec(
            dist="approval-consumer",
            make_profile=profile,
            repository_branch="integration/approval-consumer",
            ci_trigger_branches=(),
        )
        root = (
            Path(__file__).resolve().parents[3]
            / "src/flext_infra/templates/project/base"
        )
        rendered = tm.ok(
            u.Cli.template_render(
                root / ".github/workflows/ci.yml.j2",
                spec,
            ),
        )
        steps = u.CodegenTestSupport.Ci.ci_job_steps(rendered)
        approval = tuple(step for step in steps if step.get("id") == "approval")
        tm.that(approval, len=1)
        tm.that(
            approval[0]["run"],
            eq=f"{codegen.make.ci.variable}={codegen.make.ci.value} make pre-commit",
        )
        # Quoted diagnostics may recommend a local resolver without executing it.
        for step in steps:
            for line in str(step.get("run", "")).splitlines():
                command = c.Infra.DOCS_MAKE_COMMAND_RE.match(line)
                if command is not None:
                    tm.that(
                        command.group("verb") in {"gen", "upg", "dep"},
                        eq=False,
                    )
        tm.that(rendered, lacks=["Candidate cleanliness", "continue-on-error"])
        hook = tm.ok(
            u.Cli.template_render(
                root / ".pre-commit-config.yaml.j2",
                m.Infra.MakeWorkflowRenderSpec(dist=spec.dist, make=codegen.make),
            ),
        )
        tm.that(hook, has="make pre-commit")
        tm.that(hook, lacks=["make fmt", "make fix"])
        tm.that(
            codegen.make.approval_verbs,
            eq=tuple(
                step.verb
                for step in codegen.make.workflow
                if "pre_commit" in step.contexts
            ),
        )

    @staticmethod
    def test_testmon_save_requires_a_trusted_fresh_project_receipt() -> None:
        """Actions archives only the typed project database, never a cache tree."""
        spec = u.CodegenTestSupport.Ci.workflow_spec(
            dist="cache-consumer",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch="integration/cache-consumer",
            ci_trigger_branches=(),
        )
        rendered = tm.ok(
            u.Cli.template_render(
                TestsFlextInfraCiIntegrationBranchTriggers.ci_template,
                spec,
            ),
        )
        steps = u.CodegenTestSupport.Ci.ci_job_steps(rendered)
        saves = tuple(
            step for step in steps if step.get("name") == "Save testmon database"
        )
        tm.that(bool(saves), eq=spec.make.testmon_cache_policy.save_enabled)
        if saves:
            tm.that(
                saves[0]["if"],
                has=[
                    "github.event_name == 'push'",
                    "!cancelled()",
                    "testmon_saveable",
                    "testmon_digest",
                    *spec.make.testmon_cache_policy.allowed_save_refs,
                ],
            )
            if (
                spec.repository_branch
                not in spec.make.testmon_cache_policy.allowed_save_refs
            ):
                tm.that(saves[0]["if"], lacks=spec.repository_branch)
            cache_input = u.Cli.json_as_mapping(saves[0]["with"])
            restore = next(
                step for step in steps if step.get("name") == "Restore testmon database"
            )
            tm.that(
                cache_input["path"],
                eq="${{ steps.approval.outputs.testmon_database }}",
            )
            tm.that(
                cache_input["key"],
                eq=u.Cli.json_as_mapping(restore["with"])["key"],
            )

    @staticmethod
    @pytest.mark.parametrize("missing", ["setup", "audit", "check", "test"])
    def test_typed_approval_rejects_missing_stages(missing: str) -> None:
        """A truncated workflow cannot become an approval contract."""
        owner = config.Infra.codegen.make
        payload = owner.model_dump(exclude=set(type(owner).model_computed_fields))
        payload["workflow"] = [
            step.model_dump() for step in owner.workflow if step.verb != missing
        ]
        with pytest.raises(ValueError, match="workflow"):
            m.Infra.MakeSpec.model_validate(payload)

    @staticmethod
    def test_typed_approval_cannot_disable_pre_commit() -> None:
        """Projection enablement is mandatory rather than a per-project option."""
        owner = config.Infra.codegen.make
        payload = owner.model_dump(exclude=set(type(owner).model_computed_fields))
        payload["pre_commit"] = False
        with pytest.raises(ValueError, match="pre_commit"):
            m.Infra.MakeSpec.model_validate(payload)
