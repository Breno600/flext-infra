"""Conform one declared sibling candidate with the current Infra generator."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_core import r

from .. import c, u
from ..workspace.detector import FlextInfraWorkspaceDetector
from ._execution import FlextInfraCodegenExecutionBase
from .make_bootstrap import FlextInfraCodegenMakeBootstrap

if TYPE_CHECKING:
    from .. import p


class FlextInfraCodegenCandidateBootstrap(FlextInfraCodegenExecutionBase[bool]):
    """Project branch-matched artifacts into one declared sibling worktree."""

    @override
    def execute(self) -> p.Result[bool]:
        """Conform declared targets through the same generator as local gen."""
        source = u.Infra.exact_worktree_root(
            self.repository_root.expanduser().absolute()
        )
        if source.failure:
            return r[bool].from_failure(source)
        source_root = source.value.repo_root
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(source_root)
        if workspace.failure:
            return r[bool].from_failure(workspace)
        declared_targets = workspace.value.candidate_bootstrap_targets
        if not declared_targets:
            return r[bool].fail("candidate bootstrap targets are not declared")
        mode = (
            c.Infra.CodegenConformMode.CHECK
            if self.effective_dry_run
            else c.Infra.CodegenConformMode.APPLY
        )
        for declared_target in declared_targets:
            target = u.Infra.exact_worktree_root(
                (source_root / declared_target.path).resolve(strict=True)
            )
            if target.failure:
                return r[bool].from_failure(target)
            conformed = FlextInfraCodegenMakeBootstrap.conform_target(
                target.value.repo_root, surface=declared_target.what, mode=mode
            )
            if conformed.failure:
                return r[bool].from_failure(conformed)
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraCodegenCandidateBootstrap"]
