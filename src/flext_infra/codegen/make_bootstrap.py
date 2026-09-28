"""Hermetic Makefile-only bootstrap for stale generated dispatchers."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_core import r

from .. import c, m, u
from ._execution import FlextInfraCodegenExecutionBase
from .conform import FlextInfraCodegenConform

if TYPE_CHECKING:
    from .. import p


class FlextInfraCodegenMakeBootstrap(FlextInfraCodegenExecutionBase[bool]):
    """Delegate one Makefile projection exclusively to codegen conform."""

    @override
    def execute(self) -> p.Result[bool]:
        """Apply or check only this checkout's canonical Makefile projection."""
        # Why: `init` bootstraps a fresh checkout, so it must reject the same
        # non-exact/unregistered-nested roots the Mise workspace planner
        # rejects, through the shared `u.Infra.exact_worktree_root` owner.
        requested = self.repository_root.expanduser().absolute()
        identity = u.Infra.exact_worktree_root(requested)
        if identity.failure:
            return r[bool].from_failure(identity)
        mode = (
            c.Infra.CodegenConformMode.CHECK
            if self.effective_dry_run
            else c.Infra.CodegenConformMode.APPLY
        )
        conformed = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=self.repository_root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=mode,
            )
        )
        if conformed.failure:
            return r[bool].from_failure(conformed)
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraCodegenMakeBootstrap"]
