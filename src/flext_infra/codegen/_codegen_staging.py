"""Destination-local staging for generic generated-file plans.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import stat
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, get_args

from flext_infra import m, r, u
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)
from flext_infra.codegen._mise_artifacts_process import (
    FlextInfraMiseArtifactsProcess as process,
)

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraCodegenStaging:
    """Stage generated-file plans beside their live destinations."""

    _phases: ClassVar[frozenset[str]] = frozenset({
        "conform",
        *get_args(m.Infra.CodegenPhaseAnalysis.model_fields["phase"].annotation),
    })

    @staticmethod
    def stage_file_plans(
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        phase: str,
        plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]:
        """Stage one exact phase without changing any live destination.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]``.

        """
        result_type = r[tuple[m.Infra.CodegenStagedFile, ...]]
        if phase not in FlextInfraCodegenStaging._phases:
            return result_type.fail(f"unsupported generation phase: {phase}")
        changed = tuple(
            plan for plan in plans if u.Infra.codegen_file_requires_effect(plan)
        )
        paths = tuple(plan.path for plan in changed)
        if len(set(paths)) != len(paths):
            return result_type.fail(f"duplicate {phase} generation destination")
        prepared: list[
            tuple[
                m.Infra.CodegenFilePlan,
                m.Cli.AtomicFileState,
                tuple[Path, bytes, int] | None,
            ]
        ] = []
        phase_roots: MutableMapping[Path, m.Cli.AtomicDirectoryState] = {}
        for file_plan in changed:
            project = next(
                (
                    item
                    for item in files.transaction_participants(layout)
                    if item.root == file_plan.project
                ),
                None,
            )
            if project is None or project.transaction_root is None:
                return result_type.fail(
                    f"{phase} file has no transaction participant: {file_plan.path}",
                )
            current = files.read_state(file_plan.path, required=False)
            if current.failure:
                return result_type.from_failure(current)
            # A plan captured before its parent chain existed carries no parent
            # identity (chain plan, or file state with ``parent_device`` None);
            # the parent may legitimately appear before staging, and the journal
            # owns its identity check. Staging only proves the file itself
            # stayed absent.
            before = current.value
            planned_before = file_plan.before
            if (
                isinstance(planned_before, m.Cli.AtomicDirectoryChainPlan)
                or planned_before.parent_device is None
            ):
                if before.content is not None:
                    return result_type.fail(
                        f"{phase} destination appeared after planning: "
                        f"{file_plan.path}",
                    )
            elif before != planned_before:
                return result_type.fail(
                    f"{phase} destination changed after planning: {file_plan.path}",
                )
            if not file_plan.path.parent.is_dir() or file_plan.path.parent.is_symlink():
                return result_type.fail(
                    f"{phase} destination parent is not physical: "
                    f"{file_plan.path.parent}",
                )
            try:
                parent_state = file_plan.path.parent.lstat()
                transaction_parent = project.transaction_root.parent.lstat()
            except OSError as exc:
                return result_type.fail_op(f"inspect {phase} staging filesystem", exc)
            reparse = getattr(parent_state, "st_file_attributes", 0) & getattr(
                stat,
                "FILE_ATTRIBUTE_REPARSE_POINT",
                0,
            )
            if (
                not stat.S_ISDIR(parent_state.st_mode)
                or reparse
                or parent_state.st_dev != transaction_parent.st_dev
            ):
                return result_type.fail(
                    f"{phase} staging is not on destination filesystem: "
                    f"{file_plan.path}",
                )
            replacement_input: tuple[Path, bytes, int] | None = None
            if file_plan.desired_content is not None:
                desired_mode = file_plan.desired_mode
                if desired_mode is None:
                    return result_type.fail(
                        f"{phase} desired mode is absent: {file_plan.path}",
                    )
                phase_root = project.transaction_root / f"phase-{phase}"
                if phase_root not in phase_roots:
                    # Distinct name: `before` above is this file's
                    # AtomicFileState and is published below; reusing it here
                    # bound a Result and the staged-file model rejected it.
                    phase_root_before = u.Cli.atomic_read_empty_directory_state(
                        phase_root,
                        required=False,
                    )
                    if phase_root_before.failure:
                        return result_type.from_failure(phase_root_before)
                    if phase_root_before.value.exists:
                        return result_type.fail(
                            f"{phase} staging root already exists: {phase_root}",
                        )
                    phase_roots[phase_root] = phase_root_before.value
                replacement_input = (
                    phase_root,
                    file_plan.desired_content,
                    desired_mode,
                )
            prepared.append((file_plan, before, replacement_input))

        # Reject every invalid destination before creating any phase artifact.
        # Recovery cannot authorize partial staging absent from the durable
        # journal.
        for phase_root_state in phase_roots.values():
            created = u.Cli.atomic_create_empty_directory_guarded(
                phase_root_state,
                permission_mode=0o700,
            )
            if created.failure:
                return result_type.from_failure(created)
        publications: list[m.Infra.CodegenStagedFile] = []
        for index, (file_plan, before, replacement_input) in enumerate(prepared):
            replacement: m.Cli.AtomicFileState | None = None
            if replacement_input is not None:
                phase_root, desired_content, desired_mode = replacement_input
                staged_path = phase_root / f"{index:06d}.replacement"
                staged = process.write_new(staged_path, desired_content, desired_mode)
                if staged.failure:
                    return result_type.from_failure(staged)
                staged_state = files.read_state(staged_path, required=True)
                if staged_state.failure:
                    return result_type.from_failure(staged_state)
                replacement = staged_state.value
            publications.append(
                m.Infra.CodegenStagedFile(
                    phase=phase,
                    project=file_plan.project,
                    before=before,
                    replacement=replacement,
                ),
            )
        return result_type.ok(tuple(publications))


__all__: list[str] = ["FlextInfraCodegenStaging"]
