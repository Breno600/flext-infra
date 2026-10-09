"""Index-vs-declarations quality gate.

An undeclared gitlink makes a repository unfetchable, and nothing local says
so. Git records a directory carrying its own ``.git`` as a gitlink (mode
``160000``) the moment it is staged -- a linked worktree swept in by a broad
``git add`` is enough, with no warning. With no matching ``.gitmodules``
section Git cannot resolve a URL for it, so ``git submodule update --init``
exits 128 during checkout. Every consumer fetching the repository as a Git
dependency then fails before a line of its code is read, taking the whole
fleet down while the repository looks healthy to whoever committed it.

The vocabulary is the repository's own ``.gitmodules``; this gate declares no
path, name, or prefix.

Scope deliberately stops here. "Tracked while its own ignore rules match it"
was measured across the fleet and is a legitimate, widely used pattern:
projects ignore a directory broadly and then track specific files inside it
(committed projections, a pinned tracker identity). Treating that as a defect
produced 297 findings across five repositories, none of them real. An
undeclared gitlink has no legitimate form -- Git itself cannot resolve it --
which is why it is the invariant worth a gate.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import m, r, t, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraIndexDeclarationsGate(FlextInfraGate):
    """Prove every indexed gitlink is declared by the repository itself."""

    gate_id: ClassVar[str] = "index-declarations"
    gate_name: ClassVar[str] = "Index Declarations"
    can_fix: ClassVar[bool] = False

    @override
    def check(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Report every index entry the repository's declarations contradict.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        _ = ctx
        started = time.monotonic()
        errors = self._collect(project_dir)
        if errors.failure:
            return self._build_project_error_gate_result(
                project_dir,
                passed=False,
                errors=[errors.error or "index-declarations scan failed"],
                started=started,
            )
        defects = errors.unwrap()
        return self._build_project_error_gate_result(
            project_dir,
            passed=not defects,
            errors=list(defects),
            started=started,
        )

    @staticmethod
    def _collect(project_dir: Path) -> p.Result[t.StrSequence]:
        """Compare every indexed gitlink against the `.gitmodules` declarations.

        Returns:
            The resulting ``p.Result[t.StrSequence]``.

        """
        gitlinks = u.Infra.git_index_gitlink_paths(project_dir)
        if gitlinks.failure:
            return r[t.StrSequence].from_failure(gitlinks)
        declared = u.Infra.git_declared_submodule_paths(project_dir)
        if declared.failure:
            return r[t.StrSequence].from_failure(declared)
        declared_paths = {path.as_posix() for path in declared.unwrap()}
        defects = tuple(
            f"{path}: gitlink is not declared in .gitmodules — Git cannot resolve"
            " a URL for it, so every consumer fetching this repository fails"
            " during checkout"
            for path in gitlinks.unwrap()
            if path not in declared_paths
        )
        return r[t.StrSequence].ok(defects)


__all__: list[str] = ["FlextInfraIndexDeclarationsGate"]
