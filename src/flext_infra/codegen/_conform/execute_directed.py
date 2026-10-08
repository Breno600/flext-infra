"""Transactional publication of exactly selected conformance files.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, p, r, t, u
from flext_infra.codegen import FlextInfraCodegenTransaction
from flext_infra.codegen._conform.execute_scaffold import (
    FlextInfraCodegenConformExecuteScaffold,
)
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts


class FlextInfraCodegenConformExecuteDirected(FlextInfraCodegenConformExecuteScaffold):
    """Publish file-only surfaces through the existing locked transaction."""

    def _execute_lazy_init(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Run the initializer-only surface under the existing file transaction.

        Returns:
            The checked or atomically published initializer plan.

        """
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=request.root),
        )
        roots = {f"@{request.what}-0": request.root.expanduser().resolve()}
        if c.Infra.CodegenConformMode(request.mode) is c.Infra.CodegenConformMode.CHECK:
            return self._execute_lazy_init_locked(
                request,
                transaction,
                roots,
                request.root.expanduser().resolve(),
            )
        return transaction.run_files_locked(
            roots,
            lambda scope_root: self._execute_lazy_init_locked(
                request,
                transaction,
                roots,
                scope_root,
            ),
        )

    def _execute_lazy_init_locked(
        self,
        request: m.Infra.CodegenConformRequest,
        transaction: FlextInfraCodegenTransaction,
        roots: t.MappingKV[str, Path],
        scope_root: Path,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Plan after lease acquisition and publish the exact authenticated receipt.

        Returns:
            The initializer result, retaining any planner or transaction failure.

        """
        planned = self._plan_single_surface(request)
        if planned.failure:
            return r[m.Infra.CodegenResult].from_failure(planned)
        plan, analysis = planned.value
        if request.what == c.Infra.CodegenConformSurface.FACADES:
            u.Cli.info(f"stage=facades-plan files={len(plan.files)} environments=0")
            for file in plan.files:
                u.Cli.info(f"  destination={file.path}")
        changed = tuple(
            file
            for file in analysis.files
            if u.Infra.codegen_file_requires_effect(file)
        )
        if c.Infra.CodegenConformMode(request.mode) is c.Infra.CodegenConformMode.CHECK:
            drift = self._drift_message(changed, str(request.what))
            if drift is not None:
                return r[m.Infra.CodegenResult].fail(drift)
            return r[m.Infra.CodegenResult].ok(m.Infra.CodegenResult(plan=plan))
        if not changed:
            return r[m.Infra.CodegenResult].ok(m.Infra.CodegenResult(plan=plan))
        published = transaction.publish_file_phase_locked(
            scope_root,
            roots,
            analysis,
            tuple(
                sorted({
                    file.path.parent
                    for file in changed
                    if not file.path.parent.is_dir()
                }),
            ),
            lambda: self._verify_lazy_init(request, analysis),
        )
        if published.failure:
            return r[m.Infra.CodegenResult].from_failure(published)
        return r[m.Infra.CodegenResult].ok(
            m.Infra.CodegenResult(plan=plan, written_files=published.value),
        )

    def _verify_lazy_init(
        self,
        request: m.Infra.CodegenConformRequest,
        analysis: m.Infra.CodegenPhaseAnalysis,
    ) -> p.Result[bool]:
        """Authenticate published bytes and require an initializer fixed point.

        Returns:
            Whether the unchanged sources reproduce every published initializer.

        """
        receipt = FlextInfraCodegenTransaction.validate_phase_analysis_locked(analysis)
        if receipt.failure:
            return receipt
        planned = self._plan_single_surface(request)
        if planned.failure:
            return r[bool].from_failure(planned)
        return u.Infra.codegen_fixed_point(
            planned.value[1].files,
            subject=str(request.what),
        )

    @staticmethod
    def _drift_message(
        changed: t.VariadicTuple[m.Infra.CodegenFilePlan],
        label: str,
    ) -> str | None:
        """Render the drift failure message for a changed file set, if any.

        Returns:
            The drift message, or None when the set is empty.

        """
        if not changed:
            return None
        paths = ", ".join(str(file.path) for file in changed)
        report = u.Infra.codegen_file_drift_report(changed)
        return f"{label} drift detected: {paths}\n{report}"


__all__: list[str] = ["FlextInfraCodegenConformExecuteDirected"]
