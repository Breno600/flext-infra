"""Hermetic declared Make bootstrap surface for stale generated dispatchers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra.codegen._execution import FlextInfraCodegenExecutionBase
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.constants import c
from flext_infra.models import m
from flext_infra.utilities import u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraCodegenMakeBootstrap(FlextInfraCodegenExecutionBase[bool]):
    """Delegate declared Make bootstrap surface exclusively to codegen conform."""

    @override
    def execute(self) -> p.Result[bool]:
        """Apply or check this checkout's canonical declared Make bootstrap surface.

        Returns:
            The resulting ``p.Result[bool]``.

        """
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
        return self.conform_target(
            self.repository_root,
            surface=c.Infra.CodegenConformSurface.MAKEFILE,
            mode=mode,
        )

    @staticmethod
    def conform_target(
        root: Path,
        *,
        surface: c.Infra.CodegenConformSurface,
        mode: c.Infra.CodegenConformMode,
    ) -> p.Result[bool]:
        """Run the owned conform transaction for a checked bootstrap target.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        conformed = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                what=surface,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=mode,
            ),
            # The bootstrap surface publishes one file and never crosses into
            # the docs or fresh-import families.
            ports=None,
        )
        if conformed.failure:
            return r[bool].from_failure(conformed)
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraCodegenMakeBootstrap"]
