"""Destination-local staging for generic generated-file plans.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import stat
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from flext_infra import c, m, r, t, u
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)
from flext_infra.codegen._mise_artifacts_process import (
    FlextInfraMiseArtifactsProcess as process,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenStaging:
    """Stage generated-file plans beside their live destinations."""

    _phases: ClassVar[frozenset[str]] = frozenset(c.Infra.CodegenStagedFilePhase)

    @classmethod
    def stage_file_plans(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        phase: str,
        plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
        *,
        directories: t.VariadicTuple[m.Cli.AtomicDirectoryState] = (),
        intents: t.VariadicTuple[m.Infra.CodegenStagingIntent] = (),
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
        verified = cls.plan_file_staging(
            layout,
            phase,
            changed,
            directories=directories,
        )
        if verified.failure:
            return result_type.from_failure(verified)
        prepared, phase_roots = verified.value
        # Reject every invalid destination before creating any phase artifact.
        # Recovery cannot authorize partial staging absent from the durable
        # journal.
        for phase_root_state in phase_roots.values():
            if phase_root_state.exists:
                continue
            created = u.Cli.atomic_create_empty_directory_guarded(
                phase_root_state,
                permission_mode=0o700,
            )
            if created.failure:
                return result_type.from_failure(created)
        return cls._write_staged_publications(phase, prepared, intents=intents)

    @classmethod
    def plan_file_staging(
        cls,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        phase: str,
        changed: t.VariadicTuple[m.Infra.CodegenFilePlan],
        *,
        directories: t.VariadicTuple[m.Cli.AtomicDirectoryState] = (),
    ) -> p.Result[
        t.Pair[
            t.VariadicTuple[
                tuple[
                    m.Infra.CodegenFilePlan,
                    m.Cli.AtomicFileState,
                    tuple[Path, bytes, int],
                    bool,
                ]
            ],
            t.MappingKV[Path, m.Cli.AtomicDirectoryState],
        ]
    ]:
        """Prove every changed plan is stageable and collect its inputs.

        Returns:
            The resulting ``p.Result[t.Pair[t.VariadicTuple[tuple[
                m.Infra.CodegenFilePlan, m.Cli.AtomicFileState, tuple[Path,
                bytes, int], bool]], t.MappingKV[Path,
                m.Cli.AtomicDirectoryState]]]``.

        """
        result_type = r[
            t.Pair[
                t.VariadicTuple[
                    tuple[
                        m.Infra.CodegenFilePlan,
                        m.Cli.AtomicFileState,
                        tuple[Path, bytes, int],
                        bool,
                    ]
                ],
                t.MappingKV[Path, m.Cli.AtomicDirectoryState],
            ]
        ]
        prepared: list[
            tuple[
                m.Infra.CodegenFilePlan,
                m.Cli.AtomicFileState,
                tuple[Path, bytes, int],
                bool,
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
            before = current.value
            planned = cls._verified_planned_state(phase, file_plan, before)
            if planned.failure:
                return result_type.from_failure(planned)
            physical = cls._verified_staging_filesystem(
                phase,
                file_plan,
                project.transaction_root,
            )
            if physical.failure:
                return result_type.from_failure(physical)
            replacement_input = cls._staged_replacement_input(
                phase,
                file_plan,
                project.transaction_root,
                phase_roots,
                directories,
            )
            if replacement_input.failure:
                return result_type.from_failure(replacement_input)
            prepared.append((
                file_plan,
                before,
                replacement_input.value[0],
                replacement_input.value[1],
            ))
        return result_type.ok((tuple(prepared), phase_roots))

    @staticmethod
    def _verified_planned_state(
        phase: str,
        file_plan: m.Infra.CodegenFilePlan,
        before: m.Cli.AtomicFileState,
    ) -> p.Result[bool]:
        """Prove the live destination still matches its planned state.

        A plan captured before its parent chain existed carries no parent
        identity (chain plan, or file state with ``parent_device`` None); the
        parent may legitimately appear before staging, and the journal owns
        its identity check. Staging only proves the file itself stayed absent.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        result_type = r[bool]
        planned_before = file_plan.before
        if (
            isinstance(planned_before, m.Cli.AtomicDirectoryChainPlan)
            or planned_before.parent_device is None
        ):
            if before.content is not None:
                return result_type.fail(
                    f"{phase} destination appeared after planning: {file_plan.path}",
                )
            return result_type.ok(value=True)
        if before != planned_before:
            return result_type.fail(
                f"{phase} destination changed after planning: {file_plan.path}",
            )
        return result_type.ok(value=True)

    @staticmethod
    def _verified_staging_filesystem(
        phase: str,
        file_plan: m.Infra.CodegenFilePlan,
        transaction_root: Path,
    ) -> p.Result[bool]:
        """Prove the destination parent is physical and on the staging device.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        result_type = r[bool]
        if not file_plan.path.parent.is_dir() or file_plan.path.parent.is_symlink():
            return result_type.fail(
                f"{phase} destination parent is not physical: {file_plan.path.parent}",
            )
        try:
            parent_state = file_plan.path.parent.lstat()
            transaction_parent = transaction_root.parent.lstat()
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
                f"{phase} staging is not on destination filesystem: {file_plan.path}",
            )
        return result_type.ok(value=True)

    @staticmethod
    def _staged_replacement_input(
        phase: str,
        file_plan: m.Infra.CodegenFilePlan,
        transaction_root: Path,
        phase_roots: MutableMapping[Path, m.Cli.AtomicDirectoryState],
        directories: t.VariadicTuple[m.Cli.AtomicDirectoryState] = (),
    ) -> p.Result[t.Pair[tuple[Path, bytes, int], bool]]:
        """Reserve the phase staging root for a content-bearing plan.

        Returns:
            The resulting ``p.Result[t.Pair[tuple[Path, bytes, int],
            bool]]`` where the boolean marks staging presence (False marks a
            deletion-only plan).

        """
        result_type = r[t.Pair[tuple[Path, bytes, int], bool]]
        desired_mode = file_plan.desired_mode
        if file_plan.desired_content is None:
            return result_type.ok(((Path(), b"", 0), False))
        if desired_mode is None:
            return result_type.fail(f"{phase} desired mode is absent: {file_plan.path}")
        phase_root = transaction_root / f"phase-{phase}"
        if phase_root not in phase_roots:
            # Distinct name: the plan's `before` is this file's
            # AtomicFileState and is published below; reusing it here bound a
            # Result and the staged-file model rejected it.
            phase_root_before = u.Cli.atomic_read_empty_directory_state(
                phase_root,
                required=False,
            )
            if phase_root_before.failure:
                return result_type.from_failure(phase_root_before)
            if (
                phase_root_before.value.exists
                and phase_root_before.value not in directories
            ):
                return result_type.fail(
                    f"{phase} staging root already exists: {phase_root}",
                )
            phase_roots[phase_root] = phase_root_before.value
        return result_type.ok((
            (phase_root, file_plan.desired_content, desired_mode),
            True,
        ))

    @staticmethod
    def _write_staged_publications(
        phase: str,
        prepared: t.VariadicTuple[
            tuple[
                m.Infra.CodegenFilePlan,
                m.Cli.AtomicFileState,
                tuple[Path, bytes, int],
                bool,
            ]
        ],
        *,
        intents: t.VariadicTuple[m.Infra.CodegenStagingIntent] = (),
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]:
        """Write every staged replacement and bind the staged-file models.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]
            ``.

        """
        result_type = r[tuple[m.Infra.CodegenStagedFile, ...]]
        publications: list[m.Infra.CodegenStagedFile] = []
        for index, (file_plan, before, replacement_input, staged_present) in enumerate(
            prepared,
        ):
            replacement: m.Cli.AtomicFileState | None = None
            if staged_present:
                phase_root, desired_content, desired_mode = replacement_input
                staged_path = phase_root / f"{index:06d}.replacement"
                intent = next(
                    (item for item in intents if item.before.path == staged_path),
                    None,
                )
                if intents and intent is None:
                    return result_type.fail(
                        f"replacement has no durable intention: {staged_path}",
                    )
                staged = process.write_new(
                    staged_path,
                    desired_content,
                    desired_mode,
                    intent=intent,
                )
                if staged.failure:
                    return result_type.from_failure(staged)
                staged_state = files.read_state(staged_path, required=True)
                if staged_state.failure:
                    return result_type.from_failure(staged_state)
                replacement = staged_state.value
            publications.append(
                m.Infra.CodegenStagedFile(
                    phase=c.Infra.CodegenStagedFilePhase(phase),
                    project=file_plan.project,
                    before=before,
                    replacement=replacement,
                ),
            )
        return result_type.ok(tuple(publications))


__all__: list[str] = ["FlextInfraCodegenStaging"]
