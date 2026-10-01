"""A project extends its generated CI through its own custom-steps file.

The generator injects the declared block verbatim and never interprets it, so a
project adds a step its pipeline needs — a credential, a service, a probe —
without the generator carrying that project's concerns. This is the CI
counterpart of ``custom.mk``.
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, m

from ._support import CodegenTestSupport


class TestsFlextInfraCodegenCiCustomSteps:
    """The declared contract of the project-owned CI extension point."""

    @staticmethod
    def _workflow_spec(*, custom_steps: str = "") -> m.Infra.GithubWorkflowRenderSpec:
        return CodegenTestSupport.Ci.workflow_spec(
            dist="mcb",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch="main",
            ci_trigger_branches=CodegenTestSupport.Ci.CI_TRIGGER_BASELINE_BRANCHES,
            custom_steps=custom_steps,
        )

    def test_a_project_declaring_nothing_changes_nothing(self) -> None:
        """The extension is absent by default, so generation is unaffected."""
        spec = self._workflow_spec()

        tm.that(spec.custom_steps, eq="")

    def test_declared_steps_reach_the_workflow_verbatim(self) -> None:
        """The block is carried as text; the generator never parses it."""
        block = "      - name: Authenticate\n        run: echo declared"
        spec = self._workflow_spec(custom_steps=block)

        tm.that(spec.custom_steps, eq=block)

    def test_the_extension_file_sits_beside_the_workflows(self) -> None:
        """GitHub parses everything inside ``workflows``; a step list is not one.

        Placing the extension there would surface as a permanent workflow syntax
        error in the repository's Actions tab.
        """
        location = Path(c.Infra.CUSTOM_CI_STEPS_FILENAME)

        tm.that(location.parts[0], eq=".github")
        tm.that("workflows" in location.parts, eq=False)
        tm.that(location.suffix, eq=".yml")
