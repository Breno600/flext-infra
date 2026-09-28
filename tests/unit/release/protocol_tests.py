"""Release protocol behavior: plan, guard, version, and tag against real Git.

Every case drives the public CLI over a real repository whose merge commits
carry pull-request titles, exactly as GitHub leaves them when the merge commit
subject is the pull-request title.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from flext_cli import cli
from flext_tests import tm

from tests import TestsFlextInfraUtilities as u, c, m, t

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


# Why (flext-oftik class, flext-2j4lr): 15 of this module's 21 cases drive real
# release phases over a real Git repository, and one phase costs ~8-9 s today
# because pydantic rebuilds every r[T] generic per call (profiled 73% of the
# phase). That is the slow HARNESS the 60 s arm of OPERATOR LAW flext-38p39
# declares an exception for -- the per-case ceiling itself is never raised.
# Declared once for the module, exactly as the three sibling real-harness
# modules under tests/unit/deps already declare it. The previous per-case
# expression drifted: two cases fired `Timeout (>10.0s)` while identical-cost
# siblings carried no marker at all.
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

    @contextmanager
    def _lane_with_shim(self, tmp_path: Path) -> Generator[t.Pair[Path, Path]]:
        """Yield the release-lane fixture with the recording ``gh`` shim on PATH.

        Why: PATH is restored by the public ``env_vars_context`` facade rather
        than ``monkeypatch``, so the fixture stays inside the test utilities
        contract.
        """
        workspace = self._release_lane_workspace(tmp_path)
        gh_log = u.Tests.cli_shim(tmp_path / "bin", c.Infra.GH)
        shim_path = f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}"
        with u.Tests.env_vars_context(env_vars={"PATH": shim_path}):
            yield workspace, gh_log

    def _apply_release_version(self, workspace: Path, integration: str) -> None:
        """Stamp the release version once and return to the integration branch."""
        tm.that(
            u.Tests.run_release_main(workspace, "--phase", "version", "--apply"), eq=0
        )
        tm.ok(cli.run_checked([c.Infra.GIT, "switch", integration], cwd=workspace))

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

    def test_apply_opens_the_release_pull_request(self, tmp_path: Path) -> None:
        """Stamp, commit on the release lane, push it, and open the pull request."""
        with self._lane_with_shim(tmp_path) as (workspace, gh_log):
            integration = u.Tests.integration_branch(workspace)
            # flext-core caches the parsed pyproject per process; a warm cache
            # holding the pre-stamp document must not leak into the projections.
            tm.ok(u.Infra.read_project_metadata_result(workspace))

            result = u.Tests.run_release_main(
                workspace, "--phase", "version", "--apply"
            )

            tm.that(result, eq=0)
            tm.ok(
                u.Infra.current_workspace_version(workspace),
                eq=c.Tests.RELEASE_VERSION_BASE,
            )
            tm.that((workspace / "docs" / "CHANGELOG.md").is_file(), eq=True)
            head = tm.ok(
                cli.capture([c.Infra.GIT, "log", "-1", "--format=%s"], cwd=workspace)
            ).strip()
            tm.that(head, eq=c.Infra.RELEASE_COMMIT_SUBJECT.format(version="0.1.0"))
            # The docs projections render the version; the release commit
            # carries them regenerated, so the lane is a `gen check` fixed point.
            # The committed uv.lock records the stamped version, so it rides
            # in the same commit (operator 2026-09-24: locks are committed).
            committed = tm.ok(
                cli.capture(
                    [c.Infra.GIT, "show", "--name-only", "--format=", c.Infra.GIT_HEAD],
                    cwd=workspace,
                )
            )
            tm.that(committed, has=["pyproject.toml", "docs/index.md", "uv.lock"])
            tm.that(
                (workspace / "uv.lock").read_text(encoding="utf-8"),
                has=f'version = "{c.Tests.RELEASE_VERSION_BASE}"',
            )
            tm.that(
                (workspace / "docs" / "index.md").read_text(encoding="utf-8"),
                has=f"- Version: `{c.Tests.RELEASE_VERSION_BASE}`",
                lacks=c.Tests.RELEASE_VERSION_PRERELEASE,
            )
            tm.that(
                u.Infra.git_status(
                    m.Infra.GitStatusRequest(repo_root=workspace)
                ).value.dirty,
                eq=False,
            )
            tm.that(
                tm.ok(
                    cli.capture(
                        [c.Infra.GIT, "branch", "--show-current"], cwd=workspace
                    )
                ).strip(),
                eq=c.Infra.RELEASE_BRANCH,
            )
            remote_ref = tm.ok(
                cli.capture(
                    [c.Infra.GIT, "rev-parse", f"refs/heads/{c.Infra.RELEASE_BRANCH}"],
                    cwd=tmp_path / "remote" / "origin.git",
                )
            ).strip()
            tm.that(len(remote_ref), eq=40)
            recorded = gh_log.read_text(encoding="utf-8")
            tm.that(
                recorded,
                has=(f"pr create --base {integration} --head {c.Infra.RELEASE_BRANCH}"),
            )
            tm.that(recorded, has="--title chore(release): v0.1.0")

    def test_rerun_continues_the_lane_without_a_second_commit(
        self, tmp_path: Path
    ) -> None:
        """A retry from the integration branch is idempotent on the open lane."""
        with self._lane_with_shim(tmp_path) as (workspace, _):
            integration = u.Tests.integration_branch(workspace)
            self._apply_release_version(workspace, integration)

            result = u.Tests.run_release_main(
                workspace, "--phase", "version", "--apply"
            )

            tm.that(result, eq=0)
            lane_commits = tm.ok(
                cli.capture(
                    [
                        c.Infra.GIT,
                        "rev-list",
                        "--count",
                        f"{integration}..{c.Infra.RELEASE_BRANCH}",
                    ],
                    cwd=workspace,
                )
            ).strip()
            tm.that(lane_commits, eq="1")
            head = tm.ok(
                cli.capture([c.Infra.GIT, "log", "-1", "--format=%s"], cwd=workspace)
            ).strip()
            tm.that(head, eq=c.Infra.RELEASE_COMMIT_SUBJECT.format(version="0.1.0"))

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

    def test_merged_release_commit_is_tagged_and_pushed(self, tmp_path: Path) -> None:
        """After the release pull request merges, HEAD earns its tag once."""
        with self._lane_with_shim(tmp_path) as (workspace, _):
            integration = u.Tests.integration_branch(workspace)
            self._apply_release_version(workspace, integration)
            # GitHub merges the release pull request under its title plus the
            # pull-request number.
            subject = f"{c.Infra.RELEASE_COMMIT_SUBJECT.format(version='0.1.0')} (#1)"
            tm.ok(cli.run_checked([c.Infra.GIT, "switch", integration], cwd=workspace))
            tm.ok(
                cli.run_checked(
                    [
                        c.Infra.GIT,
                        "merge",
                        "--no-ff",
                        "-m",
                        subject,
                        c.Infra.RELEASE_BRANCH,
                    ],
                    cwd=workspace,
                )
            )

            first = u.Tests.run_release_main(workspace, "--phase", "tag", "--apply")
            second = u.Tests.run_release_main(workspace, "--phase", "tag", "--apply")

            tm.that(first, eq=0)
            tm.that(second, eq=0)
            tm.that(
                tm.ok(
                    cli.capture([c.Infra.GIT, "tag", "-l", "v0.1.0"], cwd=workspace)
                ).strip(),
                eq="v0.1.0",
            )
            tm.that(
                tm.ok(
                    cli.capture(
                        [c.Infra.GIT, "tag", "-l", "v0.1.0"],
                        cwd=tmp_path / "remote" / "origin.git",
                    )
                ).strip(),
                eq="v0.1.0",
            )

    def test_head_without_release_commit_is_refused(self, tmp_path: Path) -> None:
        """Only the protocol's release commit may be tagged."""
        workspace = self._released_workspace(tmp_path)
        u.Tests.merge_pull_request(workspace, "feat: not a release commit")

        tm.that(u.Tests.run_release_main(workspace, "--phase", "tag", "--apply"), ne=0)
