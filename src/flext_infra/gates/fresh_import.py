"""Fresh-process import quality gate.

Imports the checkout's published package and its declared entry points in
fresh child processes of the checkout's own runtime. The proof belongs to
``make check``: it needs the environment ``make setup`` provisions, so it is
never a precondition of the generation that publishes the package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u
from flext_infra.gates.base_gate import FlextInfraGate
from flext_infra.validate.fresh_import import FlextInfraValidateFreshImport

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraFreshImportGate(FlextInfraGate):
    """Fresh-process import gate over the checkout's own package."""

    gate_id: ClassVar[str] = c.Infra.FRESH_IMPORT
    gate_name: ClassVar[str] = "Fresh-Process Import"
    can_fix: ClassVar[bool] = False
    requires_python_targets: ClassVar[bool] = True

    @override
    def selected_for(self, project_dir: Path) -> bool:
        """Select a project that publishes an importable package layout.

        A repository whose manifest declares ``package: false`` (a workspace
        umbrella root) publishes no package, whatever its tree holds; an
        unreadable manifest fails loud.

        Returns:
            Whether the project publishes a Python package to import.

        """
        manifests = u.Infra.load_workspace_manifest(project_dir).unwrap()
        return (
            super().selected_for(project_dir)
            and all(manifest.repository.package for manifest in manifests)
            and u.Infra.layout(project_dir) is not None
        )

    @override
    def check(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Import the project's package and entry points in fresh processes.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        _ = ctx
        started = time.monotonic()
        # The runtime is derived from the gated checkout itself (a subproject
        # uses its workspace's, a standalone checkout its own), never from the
        # process that runs the gate. ``build_report`` keeps violations
        # structured so a broken invocation (missing runtime, unreadable
        # manifest) grades apart from failed probes.
        return self._build_validation_report_result(
            project_dir,
            FlextInfraValidateFreshImport(
                repository_root=project_dir,
                runtime_root=None,
            ).build_report(repository_roots=(project_dir,)),
            started=started,
        )


__all__: list[str] = ["FlextInfraFreshImportGate"]
