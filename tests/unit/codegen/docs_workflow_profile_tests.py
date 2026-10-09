"""Contract tests for the generated documentation workflow projection.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from pathlib import Path

from flext_tests import tm

from flext_infra import c, config, m
from tests import u


class TestsFlextInfraCodegenDocsWorkflowProfile:
    """Every checkout that owns a docs gate also owns the workflow that runs it.

    The docs workflow calls ``uv sync``; the generated projection is what
    installs uv beforehand. Restricting the projection to ``workspace`` left
    standalone projects with a stale hand-written copy that never installed uv, so
    the job died with "uv: command not found" (exit 127).
    """

    _DOCS_DESTINATION = ".github/workflows/docs.yml"
    _CI_DESTINATION = ".github/workflows/ci.yml"

    @staticmethod
    def _artifact(destination: str) -> m.Infra.TemplateEntrySpec:
        """Return the declared render artifact for one destination.

        Returns:
            The declared render artifact for one destination.

        Raises:
            AssertionError: If artifact is not declared.

        """
        for entry in config.Infra.codegen.templates.entries:
            if entry.destination == destination:
                return entry
        msg = f"artifact is not declared: {destination}"
        raise AssertionError(msg)

    def test_docs_workflow_reaches_every_profile_that_ci_reaches(self) -> None:
        """The docs workflow is projected wherever the CI workflow is."""
        docs = self._artifact(self._DOCS_DESTINATION)
        ci = self._artifact(self._CI_DESTINATION)

        tm.that(sorted(docs.profiles), eq=sorted(ci.profiles))

    def test_docs_workflow_is_projected_to_standalone_projects(self) -> None:
        """A standalone project receives the generated docs workflow."""
        docs = self._artifact(self._DOCS_DESTINATION)

        tm.that("standalone" in docs.profiles, eq=True)

    @staticmethod
    def test_docs_setup_keeps_the_minted_app_token_on_github_fetches() -> None:
        """Docs setup fetches private submodules with the minted App token.

        Setup clears credential.helper and would send github.token. The
        url.insteadOf rewrite CI already uses is applied from the same minted
        token, before make setup, and no second token reader is introduced.
        """
        app_id_setting = "CI_DEPENDENCIES_APP_ID"
        signing_setting = "CI_DEPENDENCIES_APP_PRIVATE_KEY"
        granted = ("example-private-a", "example-private-b")
        auth = m.Infra.CiPrivateDependencyAuthSpec.model_validate({
            "app_id_secret": app_id_setting,
            "private_key_secret": signing_setting,
            "repositories": granted,
        })
        template = (
            Path(__file__).resolve().parents[3]
            / "src/flext_infra/templates/project/base/.github/workflows/docs.yml.j2"
        )
        spec = u.CodegenTestSupport.Ci.workflow_spec(
            dist="example-workspace",
            make_profile=c.Infra.MakeProfile.WORKSPACE,
            repository_branch="develop",
            ci_trigger_branches=("develop", "main"),
        ).model_copy(update={"private_dependency_auth": auth})
        rendered = u.Cli.template_render(template, spec)
        tm.ok(rendered)
        rendered_text: str = rendered.value
        marker = (
            "git config --global "
            'url."https://x-access-token:${PRIVATE_DEPENDENCY_TOKEN}@github.com/"'
            '.insteadOf "https://github.com/"'
        )
        tm.that(rendered_text.count("app/installations"), eq=0)
        _, jobs = rendered_text.split("\njobs:\n", maxsplit=1)
        setup_jobs = [
            job for job in re.split(r"\n  (?=\S)", jobs) if "run: make setup" in job
        ]
        tm.that(setup_jobs, empty=False)
        action = config.Infra.codegen.github_actions["create-github-app-token"]
        for job in setup_jobs:
            tm.that(job, has="id: private_dependency_token")
            tm.that(job, has=f"uses: {action.repository}@{action.version}")
            tm.that(job, has=f"client-id: ${{{{ secrets.{app_id_setting} }}}}")
            tm.that(job, lacks="app-id:")
            tm.that(job, has=f"repositories: {','.join(granted)}")
            tm.that(job, has=marker)
            tm.that(job.index(marker) < job.index("run: make setup"), eq=True)
