"""Contract tests for the generated documentation workflow projection."""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config, m


class TestsFlextInfraCodegenDocsWorkflowProfile:
    """Every checkout that owns a docs gate also owns the workflow that runs it.

    The docs workflow calls ``uv sync``; the generated projection is what
    installs uv beforehand. Restricting the projection to ``workspace`` left
    standalone projects with a stale hand-written copy that never installed uv, so
    the job died with "uv: command not found" (exit 127).
    """

    _DOCS_DESTINATION = ".github/workflows/docs.yml"
    _CI_DESTINATION = ".github/workflows/ci.yml"

    def _artifact(self, destination: str) -> m.Infra.TemplateEntrySpec:
        """Return the declared render artifact for one destination."""
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
