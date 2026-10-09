"""A member attached to a uv workspace never relocks that workspace's lock.

uv resolves a checkout inside an enclosing ``[tool.uv.workspace]`` as one of
its members, so ``uv lock --project <member>`` rewrites the workspace lock and
leaves the member's own stale. Settling and propagation stop before that
effect; a checkout uv resolves alone keeps owning its lock.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import infra
from flext_infra.codegen import FlextInfraCodegenConform
from flext_infra.workspace import FlextInfraWorkspacePropagation
from tests import c, u


class TestsFlextInfraWorkspaceMemberLockOwnership:
    """Behavior contract of the lock owner a member settle resolves."""

    MEMBER = "fixture-alpha"

    @classmethod
    def _workspace(cls, tmp_path: Path, *, uv_workspace: bool) -> Path:
        """Compose a governed root with one gitlinked member.

        ``uv_workspace`` declares the member in the root's
        ``[tool.uv.workspace]``, as the real composed root does.

        Returns:
            The workspace root.

        """
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "workspace")
        u.Tests.WorktreeFixture.initialize_governed_project(
            root / cls.MEMBER,
            cls.MEMBER,
            beads=u.Tests.BeadsIdentity(
                workspace="fixture-workspace",
                database="fixture_workspace",
                issue_prefix="fixture-workspace",
            ),
        )
        u.Tests.checkout_integration(root / cls.MEMBER)
        u.Tests.WorktreeFixture.write_gitmodules(root, (cls.MEMBER,))
        head = u.Tests.git_capture(root / cls.MEMBER, "rev-parse", c.Infra.GIT_HEAD)
        u.Tests.git_run(
            root,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{head.strip()},{cls.MEMBER}",
        )
        if uv_workspace:
            pyproject = root / c.PYPROJECT_FILENAME
            pyproject.write_text(
                pyproject.read_text(encoding="utf-8")
                + f'\n[tool.uv.workspace]\nmembers = ["{cls.MEMBER}"]\n',
                encoding="utf-8",
            )
        u.Tests.commit_git_changes(root, "declare members")
        return root

    def test_standalone_member_owns_its_lock(self, tmp_path: Path) -> None:
        """Without an enclosing uv workspace the member resolves alone."""
        member = self._workspace(tmp_path, uv_workspace=False) / self.MEMBER

        tm.that(tm.ok(FlextInfraCodegenConform.require_own_lock(member)), eq=member)

    def test_attached_member_settle_stops_before_any_lock(
        self,
        tmp_path: Path,
    ) -> None:
        """Settling an attached member fails naming the workspace; no lock moves."""
        root = self._workspace(tmp_path, uv_workspace=True)
        member = root / self.MEMBER

        settled = FlextInfraCodegenConform.settle_repository(member, ports=None)

        tm.that(settled.failure, eq=True)
        tm.that(settled.error or "", has=[str(root.resolve()), "uv workspace"])
        tm.that((root / c.Infra.UV_LOCK_FILENAME).exists(), eq=False)
        tm.that((member / c.Infra.UV_LOCK_FILENAME).exists(), eq=False)

    def test_propagation_preflight_stops_before_any_lane(
        self,
        tmp_path: Path,
    ) -> None:
        """`make propagate` refuses attached members before opening a lane."""
        root = self._workspace(tmp_path, uv_workspace=True)
        member = root / self.MEMBER
        head = u.Tests.git_capture(member, "rev-parse", c.Infra.GIT_HEAD)

        propagated = infra.workspace_propagate(
            FlextInfraWorkspacePropagation(repository_root=root),
        )

        tm.that(propagated.failure, eq=True)
        tm.that(propagated.error or "", has=[str(member), "uv workspace"])
        tm.that(
            u.Tests.git_ref_exists(
                member,
                f"refs/heads/{c.Infra.PROPAGATION_BRANCH}",
            ),
            eq=False,
        )
        tm.that(u.Tests.git_capture(member, "rev-parse", c.Infra.GIT_HEAD), eq=head)
        tm.that((root / c.Infra.UV_LOCK_FILENAME).exists(), eq=False)
        tm.that((member / c.Infra.UV_LOCK_FILENAME).exists(), eq=False)
