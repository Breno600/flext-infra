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
from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts
from flext_infra.codegen.staged_package import FlextInfraStagedPackage
from flext_infra.validate import FlextInfraValidateFreshImport


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
        if request.what == c.Infra.CodegenConformSurface.FACADES:
            workspace = FlextInfraStagedPackage.workspace_root(request.root)
            if workspace.failure:
                return r[m.Infra.CodegenResult].from_failure(workspace)
            if workspace.value != request.root.expanduser().resolve():
                roots["@stage-inputs-0"] = workspace.value
        if c.Infra.CodegenConformMode(request.mode) is c.Infra.CodegenConformMode.CHECK:
            if request.what != c.Infra.CodegenConformSurface.FACADES:
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
                prepare=False,
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
        return self._publish_directed_phase(
            request,
            transaction,
            (roots, scope_root),
            (plan, analysis, changed),
        )

    def _publish_directed_phase(
        self,
        request: m.Infra.CodegenConformRequest,
        transaction: FlextInfraCodegenTransaction,
        scope: t.Pair[t.MappingKV[str, Path], Path],
        candidate: t.Triple[
            m.Infra.CodegenPlan,
            m.Infra.CodegenPhaseAnalysis,
            t.VariadicTuple[m.Infra.CodegenFilePlan],
        ],
    ) -> p.Result[m.Infra.CodegenResult]:
        """Authenticate staged inputs and publish the selected phase under its lease.

        Returns:
            The original plan and published paths, or the first phase failure.

        """
        roots, scope_root = scope
        plan, analysis, changed = candidate
        staged = self._directed_stage_inputs(request, analysis)
        if staged.failure:
            return r[m.Infra.CodegenResult].from_failure(staged)
        analysis, stage_plan = staged.value

        def validate_stage(
            session: m.Infra.CodegenTransactionSession,
            publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
        ) -> p.Result[m.Infra.CodegenTransactionSession]:
            return self._validate_directed_stage(
                request.root,
                transaction,
                stage_plan,
                session,
                publications,
            )

        published = transaction.publish_file_phase_locked(
            scope_root,
            roots,
            analysis,
            m.Infra.CodegenPhasePublicationPolicy(
                directories=tuple(
                    sorted({
                        file.path.parent
                        for file in changed
                        if not file.path.parent.is_dir()
                    }),
                ),
                validator=lambda: self._verify_lazy_init(request, analysis),
            ),
            staged_validator=validate_stage if stage_plan is not None else None,
        )
        if published.failure:
            return r[m.Infra.CodegenResult].from_failure(published)
        return r[m.Infra.CodegenResult].ok(
            m.Infra.CodegenResult(plan=plan, written_files=published.value),
        )

    @staticmethod
    def _directed_stage_inputs(
        request: m.Infra.CodegenConformRequest,
        analysis: m.Infra.CodegenPhaseAnalysis,
    ) -> p.Result[
        t.Pair[m.Infra.CodegenPhaseAnalysis, m.Infra.StagePackagePlan | None]
    ]:
        """Pin the type facade's staged contract and merge its authenticated inputs.

        Returns:
            The phase analysis and optional staged plan, or a planning failure.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenPhaseAnalysis, m.Infra.StagePackagePlan | None]
        ]
        if request.what != c.Infra.CodegenConformSurface.FACADES:
            return result_type.ok((analysis, None))
        selected_file = analysis.files[0]
        if selected_file.desired_content is None:
            return result_type.ok((analysis, None))
        source = selected_file.desired_content.decode(c.Cli.ENCODING_DEFAULT)
        if "t" not in u.Infra.facade_letter_names_source(source):
            return result_type.ok((analysis, None))
        candidate = FlextInfraStagedPackage.plan(request.root, selected_file)
        if candidate.failure:
            return result_type.from_failure(candidate)
        stage_plan = candidate.value
        source_states = FlextInfraCodegenPreconditions.unique_states((
            *analysis.inputs,
            *stage_plan.inputs,
        ))
        authenticated = analysis.model_copy(
            update={
                "inputs": source_states,
                "files": (
                    selected_file.model_copy(update={"source_states": source_states}),
                ),
            },
        )
        return result_type.ok((authenticated, stage_plan))

    @staticmethod
    def _validate_directed_stage(
        root: Path,
        transaction: FlextInfraCodegenTransaction,
        stage_plan: m.Infra.StagePackagePlan | None,
        session: m.Infra.CodegenTransactionSession,
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Materialize and validate the exact journal-owned candidate package view.

        Returns:
            The materialized session after consumer validation, or its first failure.

        """
        result_type = r[m.Infra.CodegenTransactionSession]
        if stage_plan is None or len(publications) != 1:
            return result_type.fail(
                "staged facade requires one exact candidate contract",
            )
        materialized = transaction.materialize_package_view_locked(
            session,
            stage_plan,
            publications[0],
        )
        if materialized.failure:
            return result_type.from_failure(materialized)
        current, view = materialized.value
        checked = FlextInfraValidateFreshImport(
            repository_root=root,
            runtime_root=None,
        ).validate_stage_view(view, current)
        if checked.failure:
            return result_type.from_failure(checked)
        return result_type.ok(current)

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
