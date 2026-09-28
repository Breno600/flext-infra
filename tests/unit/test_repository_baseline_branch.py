"""Baseline branch derives from live repository reality, not a provider constant.

A provider declares ONE branch, but managed repositories under the same provider
legitimately integrate on different branches (for example ``dev`` and
``develop``). Deriving the baseline from ``provider.branch`` therefore fails
closed on every repository whose integration branch differs from the provider
default. The canonical baseline is the integration branch the repository really
publishes, discovered from Git itself.
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import u
from tests import u as test_u


class TestsFlextInfraRepositoryBaselineBranch:
    """Contract for deriving one repository's integration baseline branch."""

    @staticmethod
    def _seed_remote_branch(repository_root: Path, branch: str) -> None:
        """Publish one remote-tracking branch exactly as a real clone would."""
        tm.ok(
            test_u.Cli.run_checked(
                ["git", "update-ref", f"refs/remotes/origin/{branch}", "HEAD"],
                cwd=repository_root,
            )
        )

    def test_baseline_follows_the_published_integration_branch(
        self, infra_git_repo: Path
    ) -> None:
        """The derived baseline is the integration branch the repository has."""
        # A repository that publishes ONLY `dev` must resolve to `dev`, proving
        # the derivation reads live Git instead of a provider constant.
        seeded = test_u.Cli.capture(
            ["git", "for-each-ref", "--format=%(refname)", "refs/remotes/origin"],
            cwd=infra_git_repo,
        )
        tm.ok(seeded)
        for reference in seeded.value.split():
            tm.ok(
                test_u.Cli.run_checked(
                    ["git", "update-ref", "-d", reference], cwd=infra_git_repo
                )
            )
        self._seed_remote_branch(infra_git_repo, "dev")

        resolved = u.Infra.repository_baseline_branch(infra_git_repo)

        tm.ok(resolved)
        tm.that(resolved.value, eq="dev")

    def test_baseline_fails_closed_without_any_integration_branch(
        self, tmp_path: Path
    ) -> None:
        """A checkout without a published integration branch never guesses."""
        empty = tmp_path / "no-integration-branch"
        empty.mkdir(parents=True, exist_ok=True)
        tm.ok(test_u.Cli.run_checked(["git", "init"], cwd=empty))

        resolved = u.Infra.repository_baseline_branch(empty)

        tm.fail(resolved)

    def test_declared_preference_orders_the_search(self, infra_git_repo: Path) -> None:
        """A workspace names its own release line instead of a constant.

        The built-in ordering carries conventional names only, so a fleet that
        integrates on a versioned line has to be able to declare it. Without
        that, the release name has to live inside this package — which is how
        `0.12.0-dev` came to be hardcoded next to `develop` and `dev`.
        """
        seeded = test_u.Cli.capture(
            ["git", "for-each-ref", "--format=%(refname)", "refs/remotes/origin"],
            cwd=infra_git_repo,
        )
        tm.ok(seeded)
        for reference in seeded.value.split():
            tm.ok(
                test_u.Cli.run_checked(
                    ["git", "update-ref", "-d", reference], cwd=infra_git_repo
                )
            )
        # Both are published, so only the declared order can decide between them.
        self._seed_remote_branch(infra_git_repo, "dev")
        self._seed_remote_branch(infra_git_repo, "9.9.9-dev")

        declared = u.Infra.repository_baseline_branch(
            infra_git_repo, preference=("9.9.9-dev", "develop", "dev")
        )

        tm.ok(declared)
        tm.that(declared.value, eq="9.9.9-dev")

        # And the built-in ordering, which cannot know that release name,
        # resolves the conventional one instead.
        builtin = u.Infra.repository_baseline_branch(infra_git_repo)

        tm.ok(builtin)
        tm.that(builtin.value, eq="dev")
