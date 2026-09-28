"""Structural-residue cleanup for the generated ``clean`` verb.

Git-ignored runtime and bytecode artifacts are valid caches, never residue.
Cleanup owns only broken managed workspace links; every source inventory uses
the Git-aware ``u.Infra`` scope facade.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import c, u

from ..base import s

if TYPE_CHECKING:
    from flext_infra import p, t

logger = u.fetch_logger(__name__)


class FlextInfraCleanService(s[int]):
    """Report or remove broken links below the managed workspace container."""

    def _broken_worktree_links(self) -> t.VariadicTuple[Path]:
        """Return broken symlinks left below the managed worktree container."""
        worktrees_root = self.repository_root / c.Infra.WORKTREES_DIRNAME
        if not worktrees_root.is_dir():
            return ()
        return tuple(
            path
            for path in worktrees_root.rglob("*")
            if path.is_symlink() and not path.exists()
        )

    @override
    def execute(self) -> p.Result[int]:
        """Report broken managed links, removing them when apply is requested."""
        if not self.repository_root.is_dir():
            return r[int].fail(f"workspace is not a directory: {self.repository_root}")
        targets = self._broken_worktree_links()
        if not targets:
            u.Cli.info("clean: no broken managed workspace links")
            return r[int].ok(0)
        if not self.apply_changes:
            for target in targets:
                u.Cli.info(f"  {target.relative_to(self.repository_root)}")
            u.Cli.info(f"clean: {len(targets)} broken managed workspace link(s)")
            return r[int].ok(0)
        removed = 0
        for target in targets:
            u.Cli.info(f"clean: remove {target.relative_to(self.repository_root)}")
            outcome = u.Cli.files_delete(target)
            if outcome.failure:
                return r[int].from_failure(outcome)
            removed += 1
        u.Cli.info(f"clean: removed {removed} broken managed workspace link(s)")
        return r[int].ok(0)


__all__: list[str] = ["FlextInfraCleanService"]
