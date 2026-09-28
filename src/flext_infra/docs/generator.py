"""Documentation generator service driven by code, exports, and docstrings."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, override

from flext_core import r
from flext_infra import c, m, t, u
from flext_infra.codegen.codegen_transaction import FlextInfraCodegenTransaction
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts

from ._generator_bundle import FlextInfraDocGeneratorBundleMixin
from .base import FlextInfraDocServiceBase

if TYPE_CHECKING:
    from flext_infra import p

type _DocsScopePlan = t.Pair[m.Infra.DocScope, t.VariadicTuple[m.Infra.CodegenFilePlan]]


class FlextInfraDocGenerator(
    FlextInfraDocServiceBase, FlextInfraDocGeneratorBundleMixin
):
    """Generate managed docs artifacts from package exports and docstrings."""

    # Why (X-47): standalone `docs generate` renders the workspace root by
    # default; codegen conform overrides this per plan (DECLARED scope
    # excludes the root repository from the render entirely).
    include_root: Annotated[
        bool, m.Field(description="Render the workspace root as a docs output scope")
    ] = True

    @classmethod
    def execute_request(cls, request: m.Infra.DocsGenerateRequest) -> p.Result[bool]:
        """Expose one fixed-effect CLI request without inherited mode controls."""
        owner = cls(repository_root=request.repository_root)
        return owner._propagate_phase_outcome(
            "generate",
            owner.generate(request),
            failure_predicate=lambda report: not report.passed,
        )

    def generate(
        self, request: m.Infra.DocsGenerateRequest
    ) -> p.Result[t.SequenceOf[m.Infra.DocsPhaseReport]]:
        """Publish generated docs through the existing durable file lifecycle."""
        prepared = self._prepare_request(request)
        if prepared.failure:
            return r[t.SequenceOf[m.Infra.DocsPhaseReport]].from_failure(prepared)
        roots = {
            f"@docs-{index}": path
            for index, path in enumerate(
                sorted({item.scope.path for item in prepared.value.scopes})
            )
        }
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(
                repository_root=prepared.value.repository_root
            )
        )

        def publish(
            scope_root: Path,
        ) -> p.Result[t.SequenceOf[m.Infra.DocsPhaseReport]]:
            current = self._prepare_request(request)
            if current.failure:
                return r[t.SequenceOf[m.Infra.DocsPhaseReport]].from_failure(current)
            if {item.scope.path for item in current.value.scopes} != set(
                roots.values()
            ):
                return r[t.SequenceOf[m.Infra.DocsPhaseReport]].fail(
                    "docs scope inventory changed before publication"
                )
            plans = self.plan_files(current.value)
            if plans.failure:
                return r[t.SequenceOf[m.Infra.DocsPhaseReport]].from_failure(plans)
            directories = self.required_directories(current.value)
            if directories.failure:
                return r[t.SequenceOf[m.Infra.DocsPhaseReport]].from_failure(
                    directories
                )
            analysis = m.Infra.CodegenPhaseAnalysis(
                phase="docs", files=plans.value, inputs=current.value.source_states
            )
            written = transaction.publish_file_phase_locked(
                scope_root,
                roots,
                analysis,
                tuple(path for path in directories.value if path not in roots.values()),
                lambda: self._verify_generated(request, current.value, plans.value),
            )
            if written.failure:
                return r[t.SequenceOf[m.Infra.DocsPhaseReport]].from_failure(written)
            return self._generation_reports(
                current.value, plans.value, frozenset(written.value)
            )

        return transaction.run_files_locked(roots, publish)

    def _verify_generated(
        self,
        request: m.Infra.DocsGenerateRequest,
        bundle: m.Infra.DocsGenerationBundle,
        plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[bool]:
        """Require exact untouched sources and a fresh unchanged render."""
        outputs = {plan.path for plan in plans}
        for expected in bundle.source_states:
            if expected.path in outputs:
                continue
            observed = u.Cli.atomic_read_binary_file_state(expected.path, required=True)
            if observed.failure:
                return r[bool].from_failure(observed)
            if observed.value != expected:
                return r[bool].fail(
                    f"docs source changed during publication: {expected.path}"
                )
        prepared = self._prepare_request(request)
        if prepared.failure:
            return r[bool].from_failure(prepared)
        before_paths = {item.path for item in bundle.source_states} - outputs
        after_paths = {item.path for item in prepared.value.source_states} - outputs
        if before_paths != after_paths:
            return r[bool].fail("docs source inventory changed during publication")
        current = self.plan_files(prepared.value)
        if current.failure:
            return r[bool].from_failure(current)
        if any(u.Infra.codegen_file_requires_effect(plan) for plan in current.value):
            return r[bool].fail("docs generation did not reach an unchanged render")
        return r[bool].ok(True)

    def _generation_reports(
        self,
        bundle: m.Infra.DocsGenerationBundle,
        committed_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
        written: frozenset[Path],
    ) -> p.Result[t.SequenceOf[m.Infra.DocsPhaseReport]]:
        """Report only destinations committed by the shared transaction."""
        reports: list[m.Infra.DocsPhaseReport] = []
        first_scope = bundle.scopes[0].scope
        root_scope = first_scope if first_scope.name == c.Infra.RK_ROOT else None
        offset = 0
        for scoped in bundle.scopes:
            scope = scoped.scope
            plans = committed_plans[offset : offset + len(scoped.artifacts)]
            offset += len(scoped.artifacts)
            changed = tuple(plan for plan in plans if plan.path in written)
            collocated = self._is_collocated_workspace_project(
                scope, root_scope=root_scope
            )
            report = m.Infra.DocsPhaseReport(
                phase="generate",
                scope=scope.name,
                changed_files=len(changed),
                generated=len(changed),
                applied=True,
                source="code-docstring-ssot",
                items=tuple(
                    m.Infra.DocsPhaseItemModel(
                        phase="generate",
                        path=str(plan.path),
                        written=plan.path in written,
                    )
                    for plan in plans
                ),
                result=c.Infra.ResultStatus.OK,
                reason=(
                    "aggregate-root-owner" if collocated else f"changes:{len(changed)}"
                ),
                passed=True,
            )
            self.logger.info(
                "docs_generate_scope_planned",
                project=scope.name,
                phase="generate",
                result=report.result,
                reason=report.reason,
            )
            reports.append(report)
        return r[t.SequenceOf[m.Infra.DocsPhaseReport]].ok(tuple(reports))

    def plan_files(
        self, bundle: m.Infra.DocsGenerationBundle
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]:
        """Bind one prepared render bundle to exact live destination states."""
        return u.Infra.docs_file_plans(bundle)

    def required_directories(
        self, bundle: m.Infra.DocsGenerationBundle
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Derive target parent chains from the exact prepared render bundle.

        Source-state race verification is owned by ``docs_file_plans``.
        """
        # Why (X-47): the physical workspace root is not necessarily
        # `bundle.scopes[0]` once the root is excluded as an output scope
        # (DECLARED conform scope); use the bundle's own authenticated root.
        return u.Infra.docs_required_directories(bundle)

    def prepare_bundle(self) -> p.Result[m.Infra.DocsGenerationBundle]:
        """Freeze the configured render and all of its authenticated inputs."""
        return self._prepare_request(self._configured_request())

    @override
    def execute(self) -> p.Result[bool]:
        """Execute the configured docs generation flow."""
        return self._propagate_phase_outcome(
            "generate",
            self.generate(
                m.Infra.DocsGenerateRequest(
                    repository_root=self.repository_root,
                    projects=self.selected_projects,
                    output_dir=self.output_dir,
                    include_root=self.include_root,
                )
            ),
            failure_predicate=lambda report: not report.passed,
        )

    def _configured_request(self) -> m.Infra.DocsGenerateRequest:
        """Return the pure render request shared by both planner entry points."""
        return m.Infra.DocsGenerateRequest(
            repository_root=self.repository_root,
            projects=self.selected_projects,
            output_dir=self.output_dir,
            include_root=self.include_root,
        )

    @staticmethod
    def _plan_bundle(
        bundle: m.Infra.DocsGenerationBundle,
    ) -> p.Result[t.VariadicTuple[_DocsScopePlan]]:
        """Build every scope plan from one already prepared docs bundle."""
        planned = u.Infra.docs_file_plans(bundle)
        if planned.failure:
            return r[tuple[_DocsScopePlan, ...]].from_failure(planned)
        scope_plans: list[_DocsScopePlan] = []
        offset = 0
        for scoped in bundle.scopes:
            size = len(scoped.artifacts)
            scope_plans.append((scoped.scope, planned.value[offset : offset + size]))
            offset += size
        return r[tuple[_DocsScopePlan, ...]].ok(tuple(scope_plans))


__all__: list[str] = ["FlextInfraDocGenerator"]
