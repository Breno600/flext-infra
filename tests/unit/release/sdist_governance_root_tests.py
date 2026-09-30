"""Release sdist root boundary admits declared governance manifests.

A project may ship its governance agent manifest as one declared runtime
asset at the sdist root (ai-hub embeds AGENTS.md for the agents it
deploys); the boundary constant must admit it by name.
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import c


class TestsFlextInfraReleaseSdistGovernanceRoot:
    """Behavior contract for the public sdist root-file boundary."""

    def test_governance_agent_manifest_is_admitted_at_the_sdist_root(self) -> None:
        """The deployed-agents governance manifest is public root content."""
        tm.that(c.Infra.RELEASE_SDIST_ROOT_FILES, has={"agents.md"})

    def test_boundary_still_refuses_operational_roots(self) -> None:
        """The root-file set admits no directories, only named files."""
        tm.that(
            all(not name.endswith("/") for name in c.Infra.RELEASE_SDIST_ROOT_FILES),
            eq=True,
        )
