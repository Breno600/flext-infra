"""Member propagation: this workspace's flext-infra reaches each member as one lane.

Every case drives the public ``workspace propagate`` CLI (what ``make
propagate`` runs) over a real workspace: a superproject declaring two member
repositories in ``.gitmodules``, each pushing to its own local bare origin,
with a recording ``gh`` on PATH instead of GitHub.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import infra, main
from flext_infra.codegen import FlextInfraCodegenConform
from tests import c, t, u

if TYPE_CHECKING:
    from collections.abc import Generator


pytestmark = pytest.mark.slow


class TestsFlextInfraWorkspaceMemberPropagation:
    """Behavior contract for ``make propagate``."""

    CHANGED = "fixture-alpha"
    SETTLED = "fixture-beta"
    MEMBERS = (CHANGED, SETTLED)

    RECEIPT = "propagation-workspace.receipt"

    def _template(self, settled: t.StrSequence, hermetic: t.StrMapping) -> Path:
        """Return the declared workspace with ``settled`` conformed, built once.

        Declaring members and settling one is this class's arrange phase, not
        its behavior under test, so it runs once per locked-source set (the
        hermetic mirror routes encode it) and member layout under the canonical
        lease; the first consumer pays it inside its own deadline and every
        test clones the result.

        Returns:
            The declared workspace with ``settled`` conformed, built once.

        """
        material = "\n".join((
            *(f"{name}={value}" for name, value in sorted(hermetic.items())),
            *self.MEMBERS,
            "settled:",
            *settled,
        ))
        key = hashlib.sha256(material.encode()).hexdigest()[:16]
        parent = Path(tempfile.gettempdir()) / "propagation-workspace" / key
        parent.mkdir(parents=True, exist_ok=True)
        with u.Infra.codegen_transaction_lease(parent / self.RECEIPT):
            if not (parent / self.RECEIPT).is_file():
                root = u.Tests.WorktreeFixture.governed_workspace(parent, "workspace")
                for name in self.MEMBERS:
                    u.Tests.WorktreeFixture.initialize_governed_project(
                        root / name,
                        name,
                        beads=u.Tests.BeadsIdentity(
                            workspace="fixture-workspace",
                            database="fixture_workspace",
                            issue_prefix="fixture-workspace",
                        ),
                    )
                    u.Tests.checkout_integration(root / name)
                u.Tests.WorktreeFixture.write_gitmodules(root, self.MEMBERS)
                for name in self.MEMBERS:
                    head = u.Tests.git_capture(
                        root / name,
                        "rev-parse",
                        c.Infra.GIT_HEAD,
                    )
                    u.Tests.git_run(
                        root,
                        "update-index",
                        "--add",
                        "--cacheinfo",
                        f"160000,{head.strip()},{name}",
                    )
                u.Tests.commit_git_changes(root, "declare members")
                for name in settled:
                    tm.ok(
                        FlextInfraCodegenConform.settle_repository(
                            root / name,
                            ports=infra.codegen_conform_collaborators(),
                        ),
                    )
                    u.Tests.commit_git_changes(root / name, "settle projections")
                tm.ok(u.Cli.atomic_write_text_file(parent / self.RECEIPT, key + "\n"))
        return parent / "workspace"

    @contextmanager
    def _workspace(
        self,
        tmp_path: Path,
        *,
        settled: t.StrSequence,
        hermetic: t.StrMapping,
    ) -> Generator[t.Pair[Path, Path]]:
        """Yield a clone of the workspace whose ``settled`` members are propagated.

        Yields:
            Each ``t.Pair[Path, Path]``.

        """
        # Every settle and propagation locks against the run's local mirrors.
        with u.Tests.env_vars_context(env_vars=hermetic):
            root = tmp_path / "workspace"
            shutil.copytree(self._template(settled, hermetic), root, symlinks=True)
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
        """Run the public propagation CLI once.

        Returns:
            The resulting ``int``.

        """
        return main([
            c.Infra.CLI_GROUP_WORKSPACE,
            "propagate",
            "--repository-root",
            str(root),
        ])

    @staticmethod
    def _lane_commits(member: Path) -> str:
        """Count the lane's commits beyond the member's integration branch.

        Returns:
            The resulting ``str``.

        """
        base = u.Tests.integration_branch(member)
        return u.Tests.git_capture(
            member,
            "rev-list",
            "--count",
            f"{base}..{c.Infra.PROPAGATION_BRANCH}",
        ).strip()

    @staticmethod
    def _published(tmp_path: Path, name: str) -> str:
        """Return the lane tip the member's bare origin carries, or empty.

        Returns:
            The lane tip the member's bare origin carries, or empty.

        """
        return u.Tests.git_capture(
            tmp_path / "remotes" / name / "origin.git",
            "for-each-ref",
            "--format=%(objectname)",
            f"refs/heads/{c.Infra.PROPAGATION_BRANCH}",
        ).strip()

    @staticmethod
    def _on_clean_base(member: Path) -> bool:
        """Return whether the member checkout rests clean on its integration line.

        Returns:
            Whether the member checkout rests clean on its integration line.

        """
        current = u.Tests.git_capture(member, "branch", "--show-current").strip()
        status = u.Tests.git_capture(member, "status", "--porcelain").strip()
        return current == u.Tests.integration_branch(member) and not status

    def test_changed_member_gets_one_lane_and_settled_member_nothing(
        self,
        tmp_path: Path,
        hermetic_git_environment: t.StrMapping,
    ) -> None:
        """Only the member whose projections change is proposed, exactly once."""
        with self._workspace(
            tmp_path,
            settled=(self.SETTLED,),
            hermetic=hermetic_git_environment,
        ) as (root, gh_log):
            tm.that(self._propagate(root), eq=0)

            changed, settled = root / self.CHANGED, root / self.SETTLED
            tm.that(self._lane_commits(changed), eq="1")
            subject = u.Tests.git_capture(
                changed,
                "log",
                "-1",
                "--format=%s",
                c.Infra.PROPAGATION_BRANCH,
            ).strip()
            tm.that(subject, eq=c.Infra.PROPAGATION_COMMIT_SUBJECT)
            tm.that(self._published(tmp_path, self.CHANGED), ne="")
            tm.that(self._on_clean_base(changed), eq=True)
            tm.that(
                u.Tests.git_ref_exists(
                    settled,
                    f"refs/heads/{c.Infra.PROPAGATION_BRANCH}",
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

    def test_rerun_commits_nothing_new(
        self,
        tmp_path: Path,
        hermetic_git_environment: t.StrMapping,
    ) -> None:
        """A second run continues the open lane and changes no published tip."""
        with self._workspace(
            tmp_path,
            settled=(self.SETTLED,),
            hermetic=hermetic_git_environment,
        ) as (root, _):
            tm.that(self._propagate(root), eq=0)
            first = self._published(tmp_path, self.CHANGED)

            tm.that(self._propagate(root), eq=0)

            tm.that(self._lane_commits(root / self.CHANGED), eq="1")
            tm.that(self._published(tmp_path, self.CHANGED), eq=first)
            tm.that(self._published(tmp_path, self.SETTLED), eq="")
            tm.that(self._on_clean_base(root / self.CHANGED), eq=True)

    def test_failing_member_stops_the_run(
        self,
        tmp_path: Path,
        hermetic_git_environment: t.StrMapping,
    ) -> None:
        """The first member failure ends the run before any later member."""
        with self._workspace(
            tmp_path,
            settled=(),
            hermetic=hermetic_git_environment,
        ) as (root, gh_log):
            (root / self.CHANGED / "stray.txt").write_text("wip\n", encoding="utf-8")

            tm.that(self._propagate(root), ne=0)

            for name in self.MEMBERS:
                tm.that(
                    u.Tests.git_ref_exists(
                        root / name,
                        f"refs/heads/{c.Infra.PROPAGATION_BRANCH}",
                    ),
                    eq=False,
                )
                tm.that(self._published(tmp_path, name), eq="")
            tm.that(gh_log.exists(), eq=False)

    def test_external_consumer_lane_runs_its_own_verbs(
        self,
        tmp_path: Path,
        hermetic_git_environment: t.StrMapping,
    ) -> None:
        """A declared external consumer advances its lane through its make verbs."""
        consumer_root = tmp_path / "consumer"
        consumer_root.mkdir()
        (consumer_root / "Makefile").write_text(
            "upg gen fix-namespace fix-accessors fix fmt:\n"
            "\tprintf '%s\\n' \"$@\" >> ran.txt\n",
            encoding="utf-8",
        )
        u.Tests.git_run(consumer_root, "init", "--initial-branch", "main")
        u.Tests.git_run(consumer_root, "add", "Makefile")
        u.Tests.commit_git_changes(consumer_root, "consumer base")
        self._publish_to_local_origin(consumer_root, tmp_path / "remotes" / "consumer")
        with self._workspace(
            tmp_path,
            settled=(self.SETTLED,),
            hermetic=hermetic_git_environment,
        ) as (root, gh_log):
            manifest = root / "config" / "workspace.yaml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8")
                + (
                    "external_consumers:\n"
                    f"  - name: consumer-x\n"
                    f"    root: {consumer_root}\n"
                ),
                encoding="utf-8",
            )

            tm.that(self._propagate(root), eq=0)

            lane = self._published(tmp_path, "consumer")
            tm.that(lane, ne="")
            tm.that(self._on_clean_base(consumer_root), eq=True)
            verbs_ran = u.Tests.git_capture(
                consumer_root,
                "show",
                f"{c.Infra.PROPAGATION_BRANCH}:ran.txt",
            )
            tm.that(
                verbs_ran.splitlines(),
                eq=[
                    "upg",
                    "gen",
                    "fix-namespace",
                    "fix-accessors",
                    "fix",
                    "fmt",
                ],
            )
            recorded = gh_log.read_text(encoding="utf-8")
            tm.that(recorded.count("pr create"), eq=2)
            tm.that(recorded, has="pr create --base main --head")
