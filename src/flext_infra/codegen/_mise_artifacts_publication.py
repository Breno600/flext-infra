"""Guarded live publication for one fully journaled generation phase.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r, t, u
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraMisePublication:
    """Publish staged generated files through full-state guarded primitives."""

    @staticmethod
    def _invalidate_project_document(path: Path) -> None:
        """Drop the process-wide parsed pyproject after this writer replaces it.

        Why: flext-core caches the parsed pyproject per process keyed by root; a
        plan built right after publication must read the published document.
        """
        if path.name == c.PYPROJECT_FILENAME:
            u.read_project_document_cached.cache_clear()

    @classmethod
    def publish_file_plan(
        cls,
        plan: m.Infra.CodegenFilePlan,
        *,
        phase: str,
    ) -> p.Result[bool]:
        """Publish one FilePlan through write_publication without a journal.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not u.Infra.codegen_file_requires_effect(plan):
            return r[bool].ok(value=True)
        before = u.Infra.codegen_file_before_state(plan)
        if before.failure:
            return r[bool].from_failure(before)
        staged_publication = cls._staged_publication(
            plan,
            phase=phase,
            before=before.value,
        )
        if staged_publication.failure:
            return r[bool].from_failure(staged_publication)
        published = files.write_publication(staged_publication.value)
        FlextInfraMisePublication._invalidate_project_document(plan.path)
        return published

    @classmethod
    def _staged_publication(
        cls,
        plan: m.Infra.CodegenFilePlan,
        *,
        phase: str,
        before: m.Cli.AtomicFileState,
    ) -> p.Result[m.Infra.CodegenStagedFile]:
        """Stage one plan's desired content beside its destination.

        A deletion-only plan stages the journal entry whose replacement is
        None; the model owns that contract.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenStagedFile]``.

        """
        result_type = r[m.Infra.CodegenStagedFile]
        if plan.desired_content is None:
            return result_type.ok(
                m.Infra.CodegenStagedFile(
                    phase=c.Infra.CodegenStagedFilePhase(phase),
                    project=plan.project,
                    before=before,
                    replacement=None,
                ),
            )
        mode = plan.desired_mode
        if mode is None:
            return result_type.fail(f"codegen desired mode is absent: {plan.path}")
        staging_path = plan.path.with_name(f".{plan.path.name}.codegen-staging")
        staged_before = u.Cli.atomic_read_binary_file_state(
            staging_path,
            required=False,
        )
        if staged_before.failure:
            return result_type.from_failure(staged_before)
        written = u.Cli.atomic_write_binary_file_guarded(
            staged_before.value,
            plan.desired_content,
            permission_mode=mode,
        )
        if written.failure:
            return result_type.from_failure(written)
        staged = files.read_state(staging_path, required=True)
        if staged.failure:
            return result_type.from_failure(staged)
        return result_type.ok(
            m.Infra.CodegenStagedFile(
                phase=c.Infra.CodegenStagedFilePhase(phase),
                project=plan.project,
                before=before,
                replacement=staged.value,
            ),
        )

    @staticmethod
    def publish(
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Apply an already durable phase through full-state guarded primitives.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        written: list[Path] = []
        total = len(publications)
        for index, publication in enumerate(publications, start=1):
            u.Cli.emit_raw(f"  publish [{index}/{total}] {publication.before.path}\n")
            changed = files.write_publication(publication)
            if changed.failure:
                return r[t.VariadicTuple[Path]].from_failure(changed)
            FlextInfraMisePublication._invalidate_project_document(
                publication.before.path,
            )
            written.append(publication.before.path)
        return r[t.VariadicTuple[Path]].ok(tuple(written))


__all__: list[str] = ["FlextInfraMisePublication"]
