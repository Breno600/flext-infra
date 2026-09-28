"""Conform never leaks orphan ``-transaction-<hex>`` sibling worktrees (flext-f73ii)."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c
from flext_infra.codegen import FlextInfraCodegenConform
from tests import t, u

_TRANSACTION_MARKER = "-transaction-"


@pytest.mark.slow
class TestsFlextInfraCodegenConformNoTransactionWorktrees:
    """Conform mutates the repository in place; no detached sibling may survive.

    flext-f73ii: the retired isolated-transaction mechanism spawned a sibling
    ``<repo>-transaction-<hex>`` detached worktree and leaked it on the
    drift/error exit path, holding staged generated output in a commit
    unreachable from any branch (one ``git gc`` away from destruction).
    """

    def _transaction_worktree_siblings(self, root: Path) -> t.VariadicTuple[str]:
        """Name sibling directories that look like detached transaction worktrees."""
        return tuple(
            entry.name
            for entry in root.parent.iterdir()
            if entry.is_dir() and _TRANSACTION_MARKER in entry.name
        )

    def _seed_committed_drift(self, tmp_path: Path) -> t.Pair[Path, Path]:
        """Materialize the managed tree, then commit one drifted managed Makefile.

        Returns the conformed repository root and the drifted file: the shared
        builder owns where the repository lives below ``tmp_path``.
        """
        root = u.Tests.WorktreeFixture.conformed_root(tmp_path)
        drifted = root / c.Infra.MAKEFILE_FILENAME
        drifted.write_text(
            f"{drifted.read_text(encoding='utf-8')}# managed drift\n", encoding="utf-8"
        )
        u.Tests.commit_git_changes(root, "Seed committed managed drift")
        return root, drifted

    def test_drift_check_error_path_leaves_no_transaction_worktree(
        self, tmp_path: Path
    ) -> None:
        """The read-only drift exit fails loud without spawning any worktree."""
        root, drifted = self._seed_committed_drift(tmp_path)
        before = self._transaction_worktree_siblings(root)
        drifted_bytes = drifted.read_bytes()

        result = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            )
        )

        tm.fail(result, has="codegen drift detected")
        tm.that(self._transaction_worktree_siblings(root), eq=before)
        tm.that(drifted.read_bytes(), eq=drifted_bytes)

    def test_apply_convergence_leaves_no_transaction_worktree(
        self, tmp_path: Path
    ) -> None:
        """The apply path converges in place and never leaks a sibling worktree."""
        root, drifted = self._seed_committed_drift(tmp_path)
        before = self._transaction_worktree_siblings(root)

        # Convergence is proven behaviorally: the drift marker is rewritten
        # away and a second apply reaches a byte-identical fixed point; the
        # execute return shape is not part of this invariant.
        FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )
        tm.that(drifted.read_text(encoding="utf-8"), lacks="# managed drift")
        converged_bytes = drifted.read_bytes()
        FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )
        tm.that(drifted.read_bytes(), eq=converged_bytes)
        tm.that(self._transaction_worktree_siblings(root), eq=before)
