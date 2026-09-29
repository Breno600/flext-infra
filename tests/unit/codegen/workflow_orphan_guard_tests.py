"""Contract tests for the declared GitHub workflow surface."""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config
from tests import t


class TestsFlextInfraWorkflowOrphanGuard:
    """The SSOT owns the CI surface, so it must name every workflow it allows.

    conform only iterates declared artifacts: a workflow added by hand is
    never visited, never regenerated, and never pruned. `codeql.yml` survived
    that way in a single member for months and blocked a promotion, because
    Code Scanning needs a paid entitlement on private repositories and the
    job could only ever fail.
    """

    _WORKFLOW_PREFIX = ".github/workflows/"

    _ALLOWED_WORKFLOWS: t.VariadicTuple[str] = (
        "ci-matrix.yml",
        "ci.yml",
        "docs.yml",
        "release.yml",
    )

    def _declared_workflows(self) -> set[str]:
        """Return every workflow filename the SSOT owns."""
        declared: set[str] = set()
        for entry in config.Infra.codegen.templates.entries:
            destination = entry.destination
            if destination.startswith(self._WORKFLOW_PREFIX):
                declared.add(destination.removeprefix(self._WORKFLOW_PREFIX))
        for managed in config.Infra.codegen.managed_files:
            destination = managed.path.as_posix()
            if destination.startswith(self._WORKFLOW_PREFIX):
                declared.add(destination.removeprefix(self._WORKFLOW_PREFIX))
        return declared

    def test_the_declared_workflow_surface_is_explicit(self) -> None:
        """The SSOT declares the exact workflow set it governs."""
        tm.that(sorted(self._declared_workflows()), eq=sorted(self._ALLOWED_WORKFLOWS))

    def test_code_scanning_is_not_projected_to_private_repositories(self) -> None:
        """No workflow requires a paid Code Security entitlement.

        CodeQL only runs on a private repository with GitHub Advanced
        Security. Projecting it without that entitlement guarantees a red
        check, so it stays out of the governed surface until the entitlement
        is an explicit, funded decision.
        """
        tm.that("codeql.yml" in self._declared_workflows(), eq=False)

    def test_ci_matrix_uses_only_canonical_profiles(self) -> None:
        """ci-matrix is projected for workspace and standalone repositories."""
        entries = tuple(
            entry
            for entry in config.Infra.codegen.templates.entries
            if entry.destination == ".github/workflows/ci-matrix.yml"
        )
        tm.that(len(entries), eq=1)
        profiles = {
            p.value if hasattr(p, "value") else str(p) for p in entries[0].profiles
        }
        tm.that(profiles, eq={"workspace", "standalone"})
