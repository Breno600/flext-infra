"""Release protocol behavior: plan, guard, version, and tag against real Git.

Every case drives the public CLI over a real repository whose merge commits
carry pull-request titles, exactly as GitHub leaves them when the merge commit
subject is the pull-request title.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_cli import cli
from flext_tests import tm

from tests import TestsFlextInfraUtilities as u, c, m

if TYPE_CHECKING:
    from pathlib import Path


# Real Git repositories and public release phases require the slow harness.
pytestmark = pytest.mark.slow


class TestsFlextInfraReleaseProtocol:
    """Behavior contract for the release protocol."""

    def _plan(self, workspace: Path) -> m.Infra.ReleasePlan:
        """Read the plan receipt the last ``plan`` phase wrote."""
        payload = workspace / ".reports" / "release" / c.Infra.RELEASE_PLAN_FILENAME
        return m.Infra.ReleasePlan.model_validate_json(
            payload.read_text(encoding="utf-8")
        )

    def _tag(self, repo: Path, tag: str) -> None:
        """Mark HEAD as an already-released version."""
        tm.ok(cli.run_checked([c.Infra.GIT, "tag", "-a", tag, "-m", tag], cwd=repo))

    def _released_workspace(self, tmp_path: Path) -> Path:
        """Return a workspace on its integration branch with ``v0.1.0`` released."""
        workspace = u.Tests.create_release_workspace(tmp_path)
        u.Tests.checkout_integration(workspace)
        self._tag(workspace, "v0.1.0")
        return workspace

    def _release_lane_workspace(self, tmp_path: Path) -> Path:
        """Return a pre-release workspace that can push to a local bare origin."""
        workspace = u.Tests.create_release_workspace(
            tmp_path, version=c.Tests.RELEASE_VERSION_PRERELEASE
        )
        local_origin = tmp_path / "remote"
        bare_origin = u.Tests.configure_local_origin(workspace, local_origin)
        provider = u.Tests.provider()
        tm.ok(
            cli.run_checked(
                [
                    c.Infra.GIT,
                    "remote",
                    "set-url",
                    "origin",
                    f"{provider.base_url}/release-fixture.git",
                ],
                cwd=workspace,
            )
        )
        tm.ok(
            cli.run_checked(
                [
                    c.Infra.GIT,
                    "remote",
                    "set-url",
                    "--add",
                    "--push",
                    "origin",
                    # Why: the push URL must name the bare repository itself; the
                    # parent directory is not a git repository (git push exit 128).
                    # The bare path is the canonical return of configure_local_origin.
                    bare_origin.as_posix(),
                ],
                cwd=workspace,
            )
        )
        u.Tests.checkout_integration(workspace)
        return workspace

    def _commit_merge_subject(self, workspace: Path, subject: str) -> None:
        """Record one empty commit whose subject a merge left on the lane."""
        tm.ok(
            cli.run_checked(
                [c.Infra.GIT, "commit", "--allow-empty", "-m", subject], cwd=workspace
            )
        )

    def _planned_release(self, workspace: Path) -> m.Infra.ReleasePlan:
        """Run the plan phase once and return its receipt."""
        tm.that(u.Tests.run_release_main(workspace, "--phase", "plan"), eq=0)
        return self._plan(workspace)

    def test_first_release_finalizes_the_declared_prerelease(
        self, tmp_path: Path
    ) -> None:
        """Without any tag the declared pre-release ships as its base version."""
        workspace = u.Tests.create_release_workspace(
            tmp_path, version=c.Tests.RELEASE_VERSION_PRERELEASE
        )

        result = u.Tests.run_release_main(workspace, "--phase", "plan")

        plan = self._plan(workspace)
        tm.that(result, eq=0)
        tm.that(plan.next, eq=c.Tests.RELEASE_VERSION_BASE)
        tm.that(plan.previous_tag, eq=None)
        tm.that(plan.releasable, eq=True)

    def test_first_release_ships_a_final_version_unchanged(
        self, tmp_path: Path
    ) -> None:
        """A final version without a tag is released as declared, never bumped."""
        workspace = u.Tests.create_release_workspace(tmp_path)
        u.Tests.merge_pull_request(workspace, "feat: history before the first tag")

        result = u.Tests.run_release_main(workspace, "--phase", "plan")

        plan = self._plan(workspace)
        tm.that(result, eq=0)
        tm.that(plan.next, eq=c.Tests.RELEASE_VERSION_BASE)
        tm.that(plan.releasable, eq=True)

    def test_declared_prerelease_finalizes_without_consulting_titles(
        self, tmp_path: Path
    ) -> None:
        """A pre-release was decided when it was cut; history since then is not parsed."""
        workspace = u.Tests.create_release_workspace(
            tmp_path, version=c.Tests.RELEASE_VERSION_PRERELEASE
        )
        u.Tests.checkout_integration(workspace)
        self._tag(workspace, "v0.1.0rc0")
        u.Tests.merge_pull_request(workspace, "Merge pull request #1 from x/y")

        result = u.Tests.run_release_main(workspace, "--phase", "plan")

        plan = self._plan(workspace)
        tm.that(result, eq=0)
        tm.that(plan.next, eq=c.Tests.RELEASE_VERSION_BASE)
        tm.that(plan.previous_tag, eq="v0.1.0rc0")
        tm.that(plan.releasable, eq=True)

    def test_final_version_is_ahead_of_its_own_prerelease_tag(
        self, tmp_path: Path
    ) -> None:
        """A final version whose last tag is one of its pre-releases ships as declared.

        The release triple is shared, so only a comparison that keeps the
        pre-release segment sees that ``0.1.0`` follows ``v0.1.0rc2``.
        """
        workspace = u.Tests.create_release_workspace(tmp_path)
        u.Tests.checkout_integration(workspace)
        self._tag(workspace, "v0.1.0rc2")
        self._commit_merge_subject(workspace, "Merge pull request #4 from legacy/lane")
        tm.ok(
            cli.run_checked([c.Infra.GIT, "fetch", c.Infra.GIT_ORIGIN], cwd=workspace)
        )

        plan = self._planned_release(workspace)
        tm.that(plan.next, eq=c.Tests.RELEASE_VERSION_BASE)
        tm.that(plan.previous_tag, eq="v0.1.0rc2")
        tm.that(plan.releasable, eq=True)

    def test_declared_version_ahead_of_the_last_tag_is_the_next_release(
        self, tmp_path: Path
    ) -> None:
        """A version declared beyond the last tag was decided before the protocol.

        It ships as declared; the titles merged since the tag (including
        GitHub's default merge subjects) are not consulted.
        """
        workspace = self._released_workspace(tmp_path)
        self._commit_merge_subject(workspace, "Merge pull request #3 from legacy/lane")
        tm.ok(u.Infra.replace_project_version(workspace, "0.2.0"))
        tm.ok(
            cli.run_checked(
                [c.Infra.GIT, "commit", "-am", "chore: baseline 0.2.0"], cwd=workspace
            )
        )
        # The fixture's origin is the repository itself: refresh the remote
        # ref so the integration base carries the declared version.
        tm.ok(
            cli.run_checked([c.Infra.GIT, "fetch", c.Infra.GIT_ORIGIN], cwd=workspace)
        )

        plan = self._planned_release(workspace)
        tm.that(plan.next, eq="0.2.0")
        tm.that(plan.bump, eq=c.Infra.VersionBump.NONE)
        tm.that(plan.releasable, eq=True)

    def test_pull_request_titles_decide_the_bump(self, tmp_path: Path) -> None:
        """The most significant Conventional title since the last tag wins."""
        workspace = self._released_workspace(tmp_path)
        u.Tests.merge_pull_request(workspace, "fix(core): patch level")
        u.Tests.merge_pull_request(workspace, "feat(cli): minor level")
        u.Tests.merge_pull_request(workspace, "[WIP] merge origin/integration")

        result = u.Tests.run_release_main(workspace, "--phase", "plan")

        plan = self._plan(workspace)
        tm.that(result, eq=0)
        tm.that(plan.next, eq="0.2.0")
        tm.that(plan.bump, eq=c.Infra.VersionBump.MINOR)
        tm.that(plan.previous_tag, eq="v0.1.0")
        tm.that(len(plan.merges), eq=3)

    def test_breaking_marker_earns_a_major_bump(self, tmp_path: Path) -> None:
        """``!`` in a pull-request title is a breaking change."""
        workspace = self._released_workspace(tmp_path)
        u.Tests.merge_pull_request(workspace, "feat!: remove the legacy surface")

        tm.that(self._planned_release(workspace).next, eq="1.0.0")

    def test_non_releasing_titles_release_nothing(self, tmp_path: Path) -> None:
        """Docs and chores keep the version; the plan is not releasable."""
        workspace = self._released_workspace(tmp_path)
        u.Tests.merge_pull_request(workspace, "docs: explain the protocol")

        plan = self._planned_release(workspace)
        tm.that(plan.next, eq=plan.current)
        tm.that(plan.releasable, eq=False)

    def test_default_github_merge_subject_fails_loud(self, tmp_path: Path) -> None:
        """A merged pull request without its title carries no release truth."""
        workspace = self._released_workspace(tmp_path)
        u.Tests.merge_pull_request(workspace, "Merge pull request #7 from x/y")

        tm.that(u.Tests.run_release_main(workspace, "--phase", "plan"), ne=0)

    def test_pull_request_title_is_validated_when_given(self, tmp_path: Path) -> None:
        """A CI check passes a title; only a Conventional title is accepted."""
        workspace = u.Tests.create_release_workspace(tmp_path)

        accepted = u.Tests.run_release_main(
            workspace, "--phase", "plan", "--pr-title", "feat(core): accepted"
        )
        rejected = u.Tests.run_release_main(
            workspace, "--phase", "plan", "--pr-title", "Accepted without a type"
        )

        tm.that(accepted, eq=0)
        tm.that(rejected, ne=0)

    def test_manual_version_edit_is_rejected(self, tmp_path: Path) -> None:
        """A hand-edited pyproject version fails the plan, naming the commit."""
        workspace = self._released_workspace(tmp_path)
        tm.ok(u.Infra.replace_project_version(workspace, "0.1.1"))
        tm.ok(
            cli.run_checked(
                [c.Infra.GIT, "commit", "-am", "chore: bump"], cwd=workspace
            )
        )

        tm.that(u.Tests.run_release_main(workspace, "--phase", "plan"), ne=0)

    def test_protocol_release_commit_is_accepted(self, tmp_path: Path) -> None:
        """Only the release commit may carry the version it names."""
        workspace = self._released_workspace(tmp_path)
        tm.ok(u.Infra.replace_project_version(workspace, "0.1.1"))
        subject = c.Infra.RELEASE_COMMIT_SUBJECT.format(version="0.1.1")
        tm.ok(cli.run_checked([c.Infra.GIT, "commit", "-am", subject], cwd=workspace))

        plan = self._planned_release(workspace)
        tm.that(plan.next, eq="0.1.1")
        tm.that(plan.releasable, eq=False)

    def test_merged_release_commit_awaits_its_tag_from_any_head(
        self, tmp_path: Path
    ) -> None:
        """GitHub's merged form of the release commit, below HEAD, ends the plan.

        The merge appends the pull-request number to the subject, and CI plans
        on a synthetic merge commit above it; neither may reopen the release
        nor consult the titles merged before it.
        """
        workspace = self._released_workspace(tmp_path)
        self._commit_merge_subject(workspace, "Merge pull request #7 from legacy/lane")
        tm.ok(u.Infra.replace_project_version(workspace, "0.1.1"))
        merged_subject = (
            f"{c.Infra.RELEASE_COMMIT_SUBJECT.format(version='0.1.1')} (#8)"
        )
        tm.ok(
            cli.run_checked(
                [c.Infra.GIT, "commit", "-am", merged_subject], cwd=workspace
            )
        )
        self._commit_merge_subject(workspace, "Merge abc123 into def456")

        plan = self._planned_release(workspace)
        tm.that(plan.next, eq="0.1.1")
        tm.that(plan.bump, eq=c.Infra.VersionBump.NONE)
        tm.that(plan.releasable, eq=False)

    def test_dry_run_changes_nothing(self, tmp_path: Path) -> None:
        """Without apply the plan is reported and the checkout is untouched."""
        workspace = self._release_lane_workspace(tmp_path)

        tm.that(u.Tests.run_release_main(workspace, "--phase", "version"), eq=0)
        tm.ok(
            u.Infra.current_workspace_version(workspace),
            eq=c.Tests.RELEASE_VERSION_PRERELEASE,
        )
        tm.that((workspace / "docs").exists(), eq=False)

    def test_dirty_checkout_is_refused(self, tmp_path: Path) -> None:
        """A release commit never absorbs unrelated working-tree changes."""
        workspace = self._release_lane_workspace(tmp_path)
        (workspace / "stray.txt").write_text("wip\n", encoding="utf-8")

        tm.that(
            u.Tests.run_release_main(workspace, "--phase", "version", "--apply"), ne=0
        )

    def test_non_integration_branch_is_refused(self, tmp_path: Path) -> None:
        """The release pull request is cut from the integration branch only."""
        workspace = u.Tests.create_release_workspace(
            tmp_path, version=c.Tests.RELEASE_VERSION_PRERELEASE
        )

        tm.that(
            u.Tests.run_release_main(workspace, "--phase", "version", "--apply"), ne=0
        )

    def test_nothing_to_release_is_a_clean_no_op(self, tmp_path: Path) -> None:
        """A tagged repository with no releasing titles opens no pull request."""
        workspace = self._released_workspace(tmp_path)
        u.Tests.merge_pull_request(workspace, "docs: nothing to ship")

        tm.that(
            u.Tests.run_release_main(workspace, "--phase", "version", "--apply"), eq=0
        )
        tm.that(
            tm.ok(
                cli.capture(
                    [c.Infra.GIT, "branch", "--list", c.Infra.RELEASE_BRANCH],
                    cwd=workspace,
                )
            ).strip(),
            eq="",
        )

    def test_head_without_release_commit_is_refused(self, tmp_path: Path) -> None:
        """Only the protocol's release commit may be tagged."""
        workspace = self._released_workspace(tmp_path)
        u.Tests.merge_pull_request(workspace, "feat: not a release commit")

        tm.that(u.Tests.run_release_main(workspace, "--phase", "tag", "--apply"), ne=0)


__all__: list[str] = ["TestsFlextInfraReleaseProtocol"]
