"""Contract test for isolated release policy fixtures.

The release workspace factory copies repository-owned test policies into a
temporary workspace. The fixture must remain independent from an enclosing
FLEXT workspace so a standalone clone and a linked worktree behave identically.
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c
from flext_tests import tm
from tests import u


class TestsReleasePolicyFixtureRoot:
    """Policy sources are located by discovery, not by parent counting."""

    def test_policy_sources_resolve_from_the_checkout_in_use(self) -> None:
        """The fixture's policy sources must exist for the current checkout.

        This is the invariant the release suite depends on. It holds in a plain
        clone and must equally hold in a linked worktree, where the repository
        sits deeper in the filesystem.
        """
        workspace_root = u.Tests.release_policy_root()

        for policy_path in (
            c.Infra.RELEASE_BUILD_CONSTRAINTS_PATH,
            c.Infra.RELEASE_GITLEAKS_CONFIG_PATH,
        ):
            tm.that((workspace_root / policy_path).is_file(), eq=True)

    def test_policy_root_is_not_derived_by_counting_parents(self) -> None:
        """The fixture belongs to this test package, not an ambient parent."""
        expected = Path(__file__).resolve().parents[2] / "fixtures" / "release"
        tm.that(u.Tests.release_policy_root(), eq=expected)
