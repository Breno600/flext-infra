"""Semantic publication through the canonical recoverable file transaction."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m
from flext_infra.codegen import (
    FlextInfraCodegenMiseArtifacts,
    FlextInfraCodegenTransaction,
)

if TYPE_CHECKING:
    from flext_infra import p, t


def publish_semantic_file_plan(
    plan: m.Infra.SemanticFilePlan, *, repository_root: Path
) -> p.Result[bool]:
    """Publish one plan with the same batch preflight and rollback contract."""
    return publish_semantic_file_plans((plan,), repository_root=repository_root).map(
        lambda _: True
    )


def publish_semantic_file_plans(
    plans: t.SequenceOf[m.Infra.SemanticFilePlan],
    *,
    repository_root: Path,
    validator: Callable[[], p.Result[bool]] | None = None,
) -> p.Result[t.VariadicTuple[Path]]:
    """Preflight every plan and commit only after byte and caller acceptance.

    ``None`` content means no semantic change, never deletion. The existing
    transaction owns identity checks, staging, durable recovery and rollback.
    """
    files: list[m.Infra.CodegenFilePlan] = []
    for plan in plans:
        if plan.desired_content is None:
            continue
        if plan.desired_mode is None:
            return r[tuple[Path, ...]].fail(
                f"semantic desired mode is absent: {plan.path}"
            )
        if plan.before.content is not None and plan.before.content.decode(
            c.Cli.ENCODING_DEFAULT
        ).startswith(c.Infra.AUTOGEN_HEADERS):
            return r[tuple[Path, ...]].fail(
                f"generated findings require canonical generator repair: {plan.path}"
            )
        files.append(
            m.Infra.CodegenFilePlan(
                project=plan.project,
                path=plan.path,
                before=plan.before,
                desired_content=plan.desired_content,
                desired_mode=plan.desired_mode,
                source_states=(plan.before,),
                owner="semantic",
            )
        )
    if not files:
        return r[tuple[Path, ...]].ok(())
    analysis = m.Infra.CodegenPhaseAnalysis(
        phase="semantic",
        files=tuple(files),
        inputs=tuple(plan.before for plan in plans),
    )
    roots = {
        f"@semantic-{index}": project
        for index, project in enumerate(sorted({plan.project for plan in files}))
    }
    transaction = FlextInfraCodegenTransaction(
        FlextInfraCodegenMiseArtifacts(repository_root=repository_root)
    )

    def validate_published() -> p.Result[bool]:
        checked = transaction.validate_phase_analysis_locked(analysis)
        if checked.failure or not checked.value or validator is None:
            return checked
        return validator()

    def publish(scope_root: Path) -> p.Result[t.VariadicTuple[Path]]:
        started = transaction.begin_files_locked(scope_root, roots, analysis.inputs)
        if started.failure:
            return r[tuple[Path, ...]].from_failure(started)

        def apply(
            session: m.Infra.CodegenTransactionSession,
        ) -> p.Result[t.VariadicTuple[Path]]:
            published = transaction.append_phase_locked(
                session, analysis.phase, analysis.files
            )
            if published.failure:
                return r[tuple[Path, ...]].from_failure(published)
            return transaction.commit_locked(published.value, validate_published)

        return transaction.publish_prepared_locked(started.value, apply)

    return transaction.run_files_locked(roots, publish)


__all__: list[str] = ["publish_semantic_file_plan", "publish_semantic_file_plans"]
