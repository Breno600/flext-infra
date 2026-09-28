"""Member propagation: this workspace's flext-infra reaches each member as one lane.

Every case drives the public ``workspace propagate`` CLI (what ``make
propagate`` runs) over a real workspace: a superproject declaring two member
repositories in ``.gitmodules``, each pushing to its own local bare origin,
with a recording ``gh`` on PATH instead of GitHub.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import main
from flext_infra.codegen import FlextInfraCodegenConform
from tests import TestsFlextInfraUtilities as u, c, t

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


# Why: each propagation conforms and relocks real member repositories, the
# same slow harness the release protocol's version phase already declares.
pytestmark = pytest.mark.slow


class TestsFlextInfraWorkspaceMemberPropagation:
    """Behavior contract for ``make propagate``."""

    CHANGED = "fixture-alpha"
    SETTLED = "fixture-beta"
    MEMBERS = (CHANGED, SETTLED)

    @contextmanager
    def _workspace(
        self, tmp_path: Path, *, settled: t.StrSequence
    ) -> Generator[t.Pair[Path, Path]]:
        """Yield a workspace whose ``settled`` members are already propagated."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "workspace")
        for name in self.MEMBERS:
            u.Tests.WorktreeFixture.initialize_governed_project(
                root / name,
                name,
                workspace="fixture-workspace",
                database="fixture_workspace",
                issue_prefix="fixture-workspace",
            )
            u.Tests.checkout_integration(root / name)
        u.Tests.WorktreeFixture.write_gitmodules(root, self.MEMBERS)
        for name in self.MEMBERS:
            head = u.Tests.git_capture(root / name, "rev-parse", c.Infra.GIT_HEAD)
            u.Tests.git_run(
                root,
                "update-index",
                "--add",
                "--cacheinfo",
                f"160000,{head.strip()},{name}",
            )
        u.Tests.commit_git_changes(root, "declare members")
        for name in settled:
            tm.ok(FlextInfraCodegenConform.settle_repository(root / name))
            u.Tests.commit_git_changes(root / name, "settle projections")
        for name in self.MEMBERS:
            self._publish_to_local_origin(root / name, tmp_path / "remotes" / name)
        gh_log = u.Tests.cli_shim(tmp_path / "bin", c.Infra.GH)
        shim_path = f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}"
        with u.Tests.env_vars_context(env_vars={"PATH": shim_path}):
            yield root, gh_log

    @staticmethod
    def _publish_to_local_origin(member: Path, remote_root: Path) -> None:
        """Push to a local bare origin while fetching from the declared identity."""
        bare = u.Tests.configure_local_origin(member, remote_root)
        declared = u.Tests.WorktreeFixture.governed_repository_url(member.name)
        u.Tests.git_run(member, "remote", "set-url", c.Infra.GIT_ORIGIN, declared)
        u.Tests.git_run(
            member,
            "remote",
            "set-url",
            "--add",
            "--push",
            c.Infra.GIT_ORIGIN,
            str(bare),
        )

    @staticmethod
    def _propagate(root: Path) -> int:
        """Run the public propagation CLI once."""
        return main([
            c.Infra.CLI_GROUP_WORKSPACE,
            "propagate",
            "--repository-root",
            str(root),
        ])

    @staticmethod
    def _lane_commits(member: Path) -> str:
        """Count the lane's commits beyond the member's integration branch."""
        base = u.Tests.integration_branch(member)
        return u.Tests.git_capture(
            member, "rev-list", "--count", f"{base}..{c.Infra.PROPAGATION_BRANCH}"
        ).strip()

    @staticmethod
    def _published(tmp_path: Path, name: str) -> str:
        """Return the lane tip the member's bare origin carries, or empty."""
        return u.Tests.git_capture(
            tmp_path / "remotes" / name / "origin.git",
            "for-each-ref",
            "--format=%(objectname)",
            f"refs/heads/{c.Infra.PROPAGATION_BRANCH}",
        ).strip()

    @staticmethod
    def _on_clean_base(member: Path) -> bool:
        """Return whether the member checkout rests clean on its integration line."""
        current = u.Tests.git_capture(member, "branch", "--show-current").strip()
        status = u.Tests.git_capture(member, "status", "--porcelain").strip()
        return current == u.Tests.integration_branch(member) and not status

    def test_changed_member_gets_one_lane_and_settled_member_nothing(
        self, tmp_path: Path
    ) -> None:
        """Only the member whose projections change is proposed, exactly once."""
        with self._workspace(tmp_path, settled=(self.SETTLED,)) as (root, gh_log):
            tm.that(self._propagate(root), eq=0)

            changed, settled = root / self.CHANGED, root / self.SETTLED
            tm.that(self._lane_commits(changed), eq="1")
            subject = u.Tests.git_capture(
                changed, "log", "-1", "--format=%s", c.Infra.PROPAGATION_BRANCH
            ).strip()
            tm.that(subject, eq=c.Infra.PROPAGATION_COMMIT_SUBJECT)
            tm.that(self._published(tmp_path, self.CHANGED), ne="")
            tm.that(self._on_clean_base(changed), eq=True)
            tm.that(
                u.Tests.git_ref_exists(
                    settled, f"refs/heads/{c.Infra.PROPAGATION_BRANCH}"
                ),
                eq=False,
            )
            tm.that(self._published(tmp_path, self.SETTLED), eq="")
            tm.that(self._on_clean_base(settled), eq=True)
            # A member is standalone: its generated Makefile never declares the
            # workspace-only verb.
            public = next(
                line
                for line in (settled / c.Infra.MAKEFILE_FILENAME)
                .read_text(encoding="utf-8")
                .splitlines()
                if line.startswith("PUBLIC_VERBS")
            )
            tm.that("propagate" in public.split(), eq=False)
            recorded = gh_log.read_text(encoding="utf-8")
            tm.that(recorded.count("pr create"), eq=1)
            tm.that(
                recorded,
                has=(
                    f"pr create --base {u.Tests.integration_branch(changed)} "
                    f"--head {c.Infra.PROPAGATION_BRANCH}"
                ),
            )

    def test_rerun_commits_nothing_new(self, tmp_path: Path) -> None:
        """A second run continues the open lane and changes no published tip."""
        with self._workspace(tmp_path, settled=(self.SETTLED,)) as (root, _):
            tm.that(self._propagate(root), eq=0)
            first = self._published(tmp_path, self.CHANGED)

            tm.that(self._propagate(root), eq=0)

            tm.that(self._lane_commits(root / self.CHANGED), eq="1")
            tm.that(self._published(tmp_path, self.CHANGED), eq=first)
            tm.that(self._published(tmp_path, self.SETTLED), eq="")
            tm.that(self._on_clean_base(root / self.CHANGED), eq=True)

    def test_failing_member_stops_the_run(self, tmp_path: Path) -> None:
        """The first member failure ends the run before any later member."""
        with self._workspace(tmp_path, settled=()) as (root, gh_log):
            (root / self.CHANGED / "stray.txt").write_text("wip\n", encoding="utf-8")

            tm.that(self._propagate(root), ne=0)

            for name in self.MEMBERS:
                tm.that(
                    u.Tests.git_ref_exists(
                        root / name, f"refs/heads/{c.Infra.PROPAGATION_BRANCH}"
                    ),
                    eq=False,
                )
                tm.that(self._published(tmp_path, name), eq="")
            tm.that(gh_log.exists(), eq=False)
