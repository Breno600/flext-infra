"""Physical topology, source, destination, and real-consumer verification.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m, t, u
from flext_infra.codegen._mise_artifacts_files import FlextInfraMiseArtifactsFiles
from flext_infra.codegen._mise_artifacts_verification_manifest import (
    FlextInfraMiseArtifactsVerificationManifest,
)
from flext_infra.codegen._mise_artifacts_verification_topology import (
    FlextInfraMiseArtifactsVerificationTopology,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraMiseArtifactsVerification(
    FlextInfraMiseArtifactsVerificationManifest,
    FlextInfraMiseArtifactsVerificationTopology,
):
    """Manifest, topology, and liveness verification for Mise transactions."""

    @classmethod
    def states_current(
        cls,
        states: t.VariadicTuple[m.Cli.AtomicFileState],
        *,
        journal: m.Infra.CodegenTransactionJournal | None = None,
    ) -> p.Result[bool]:
        """Prove every full file state still equals its authenticated snapshot.

        This barrier is what makes the transaction atomic: it proves nothing
        moved between planning and publication. It compares the FULL state --
        content, mode and physical identity -- because a snapshot whose inode or
        device changed underneath the transaction is exactly the race the
        barrier exists to catch.

        It must never be softened to make a run pass. It briefly was: content
        was compared whitespace-normalised, mode drift was downgraded to a
        warning "logged but does not block the pipeline", and a literal
        `_models/config.py` was skipped as "expected to drift". That file
        carries no generation marker -- it is authored source and is not
        expected to drift at all; the drift being masked was the truncation
        churn of that same afternoon. A verifier that cannot fail is not a
        verifier, and a hardcoded path exemption in a fleet-wide generator hides
        the next real corruption just as effectively as it hid that one.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for original_expected in states:
            expected = original_expected
            if expected.parent_device is None and journal is not None:
                rebound = cls._bind_source_parent(expected, journal)
                if rebound.failure:
                    return r[bool].from_failure(rebound)
                rebound_expected = rebound.value
            else:
                rebound_expected = expected
            observed = FlextInfraMiseArtifactsFiles.read_state(
                rebound_expected.path,
                required=rebound_expected.content is not None,
            )
            if observed.failure:
                return r[bool].from_failure(observed)
            if observed.value != rebound_expected:
                return r[bool].fail(
                    f"generation authenticated state changed: {rebound_expected.path}",
                )
        return r[bool].ok(value=True)

    @classmethod
    def _bind_source_parent(
        cls,
        expected: m.Cli.AtomicFileState,
        journal: m.Infra.CodegenTransactionJournal,
    ) -> p.Result[m.Cli.AtomicFileState]:
        """Recognize only parent identities created under the durable absence witness.

        Returns:
            The resulting ``p.Result[m.Cli.AtomicFileState]``.

        """
        result = r[m.Cli.AtomicFileState]
        source = next(
            (item for item in journal.sources if item.path == expected.path),
            None,
        )
        if (
            source is None
            or source.absent_parent is None
            or expected.content is not None
        ):
            return result.fail(
                f"generation source has no absence witness: {expected.path}",
            )
        witness = source.absent_parent
        current = u.Cli.atomic_plan_directory_chain(witness.target)
        if current.failure:
            return result.from_failure(current)
        if current.value == witness:
            return result.ok(expected)
        ancestry = cls._verified_parent_ancestry(journal, witness)
        if ancestry.failure:
            return result.from_failure(ancestry)
        observed = current.value
        if observed.directories or observed.anchor_ancestry != ancestry.value:
            return result.fail(
                f"generation source parent identity changed: {expected.path}",
            )
        return result.ok(
            expected.model_copy(
                update={
                    "parent_device": ancestry.value[-1][0],
                    "parent_inode": ancestry.value[-1][1],
                },
            ),
        )

    @classmethod
    def _verified_parent_ancestry(
        cls,
        journal: m.Infra.CodegenTransactionJournal,
        witness: m.Cli.AtomicDirectoryChainPlan,
    ) -> p.Result[t.VariadicTuple[t.Pair[int, int]]]:
        """Rebuild the parent ancestry chain from journal-created directories.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[t.Pair[int, int]]]``.

        """
        result_type = r[t.VariadicTuple[t.Pair[int, int]]]
        created = {
            item.created.path: item.created
            for item in journal.directories
            if item.created is not None and item.disposition == "generated"
        }
        ancestry = list(witness.anchor_ancestry)
        for path in witness.directories:
            identity = created.get(path)
            if identity is None or identity.device is None or identity.inode is None:
                return result_type.fail(
                    f"generation source parent was not created by this journal: {path}",
                )
            if (identity.parent_device, identity.parent_inode) != ancestry[-1]:
                return result_type.fail(
                    (
                        f"generation source parent ancestry "
                        f"differs from its journal: {path}"
                    ),
                )
            ancestry.append((identity.device, identity.inode))
        return result_type.ok(tuple(ancestry))

    @classmethod
    def phase_analysis_live(
        cls,
        analysis: m.Infra.CodegenPhaseAnalysis,
    ) -> p.Result[bool]:
        """Prove one published phase from its authenticated analysis receipt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        destination_paths = frozenset(file.path for file in analysis.files)
        u.Cli.info(
            f"phase={analysis.phase} verify inputs={len(analysis.inputs)} "
            f"destinations={len(analysis.files)}",
        )
        source_state = cls.states_current(
            tuple(
                state
                for state in analysis.inputs
                if state.path not in destination_paths
            ),
        )
        if source_state.failure:
            return source_state
        for plan in analysis.files:
            before = u.Infra.codegen_file_before_state(plan)
            if before.failure:
                return r[bool].from_failure(before)
            observed = FlextInfraMiseArtifactsFiles.read_state(
                plan.path,
                required=plan.desired_content is not None,
            )
            if observed.failure:
                return r[bool].from_failure(observed)
            current = observed.value
            if (
                current.content,
                current.mode,
                current.parent_device,
                current.parent_inode,
            ) != (
                plan.desired_content,
                plan.desired_mode,
                before.value.parent_device,
                before.value.parent_inode,
            ):
                return r[bool].fail(
                    f"published {analysis.phase} destination differs from receipt: "
                    f"{plan.path}",
                )
        return r[bool].ok(value=True)

    @classmethod
    def sources(cls, plan: m.Infra.MiseToolchainWorkspacePlan) -> p.Result[bool]:
        """Prove every Mise config source still equals its full snapshot.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for project in plan.projects:
            if project.config.before.content is None:
                # First publication: the config sources are themselves created
                # by this transaction, so their post-transaction bytes cannot
                # equal a pre-publication snapshot. Integrity for these is
                # owned by the publication-receipt verification.
                continue
            current = u.Infra.snapshot_config_sources(project.layout.root)
            if current.failure:
                return r[bool].from_failure(current)
            if current.value != project.config.sources:
                return r[bool].fail(f"Mise sources changed: {project.layout.selector}")
        return r[bool].ok(value=True)

    @classmethod
    def destinations(cls, plan: m.Infra.MiseToolchainWorkspacePlan) -> p.Result[bool]:
        """Prove all Mise destinations still equal the captured preflight snapshot.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for project in plan.projects:
            current = cls.states_current((project.config.before,))
            if current.failure:
                return current
        return r[bool].ok(value=True)

    @classmethod
    def publications_live(
        cls,
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[bool]:
        """Prove live destinations have the exact staged inode or planned absence.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for publication in publications:
            observed = FlextInfraMiseArtifactsFiles.read_state(
                publication.before.path,
                required=False,
            )
            if observed.failure:
                return r[bool].from_failure(observed)
            current = observed.value
            before = publication.before
            if (
                current.parent_device is None
                or current.parent_inode is None
                or before.parent_device is None
                or before.parent_inode is None
            ):
                return r[bool].fail(
                    (
                        f"generation destination parent "
                        f"identity is incomplete: {before.path}"
                    ),
                )
            replacement = publication.replacement
            if replacement is None:
                if (
                    observed.value.content is not None
                    or observed.value.parent_device != publication.before.parent_device
                    or observed.value.parent_inode != publication.before.parent_inode
                ):
                    return r[bool].fail(
                        "deleted generation destination or its parent changed: "
                        f"{publication.before.path}",
                    )
                continue
            if cls._file_identity(
                current,
                parent_device=current.parent_device,
                parent_inode=current.parent_inode,
            ) != cls._file_identity(
                replacement,
                parent_device=before.parent_device,
                parent_inode=before.parent_inode,
            ):
                return r[bool].fail(
                    (
                        f"live generation destination differs "
                        f"from staged identity: {current.path}"
                    ),
                )
        return r[bool].ok(value=True)

    @classmethod
    def live(
        cls,
        owner: p.Infra.MiseArtifactsOwner,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile] | None = None,
    ) -> p.Result[bool]:
        """Exercise every real Mise consumer while guarding sources and live bytes.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        source_before = cls.sources(plan)
        if source_before.failure:
            return source_before
        staged = cls._staged_replacements(publications or ())
        if staged.failure:
            return r[bool].from_failure(staged)
        stable = cls._stable_artifact_snapshot(plan, staged.value, owner)
        if stable.failure:
            return r[bool].from_failure(stable)
        source_after = cls.sources(plan)
        if source_after.failure:
            return source_after
        return r[bool].ok(value=True)

    @staticmethod
    def _staged_replacements(
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[t.MappingKV[Path, t.Pair[bytes, int | None]]]:
        """Collect every staged Mise replacement keyed by its live path.

        Returns:
            The resulting ``p.Result[t.MappingKV[Path, t.Pair[bytes,
                int | None]]]``.

        """
        result_type = r[t.MappingKV[Path, t.Pair[bytes, int | None]]]
        replacements: MutableMapping[Path, t.Pair[bytes, int | None]] = {}
        for publication in publications:
            replacement = publication.replacement
            if replacement is None or replacement.content is None:
                return result_type.fail(
                    f"Mise replacement is absent: {publication.before.path}",
                )
            replacements[publication.before.path] = (
                replacement.content,
                replacement.mode,
            )
        return result_type.ok(replacements)

    @classmethod
    def _stable_artifact_snapshot(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        replacements: t.MappingKV[Path, t.Pair[bytes, int | None]],
        owner: p.Infra.MiseArtifactsOwner,
    ) -> p.Result[bool]:
        """Exercise real consumers and prove the rendered artifacts unchanged.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        artifact_before = cls._artifact_snapshot(plan, replacements)
        if artifact_before.failure:
            return r[bool].from_failure(artifact_before)
        for project in plan.projects:
            validated = owner.validate_artifacts(
                project.layout.root,
                plan.layout.scope_root,
            )
            if validated.failure:
                return r[bool].from_failure(validated)
        artifact_after = cls._artifact_snapshot(plan, replacements)
        if artifact_after.failure:
            return r[bool].from_failure(artifact_after)
        if artifact_after.value != artifact_before.value:
            return r[bool].fail("published Mise artifacts changed during validation")
        return r[bool].ok(value=True)

    @classmethod
    def _artifact_snapshot(
        cls,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        replacements: t.MappingKV[Path, t.Pair[bytes, int | None]],
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]:
        states: list[m.Cli.AtomicFileState] = []
        for project in plan.projects:
            artifacts = (project.config.before,)
            for expected, required_mode in zip(
                artifacts,
                (project.config.replacement_mode,),
                strict=True,
            ):
                current = FlextInfraMiseArtifactsFiles.read_state(
                    expected.path,
                    required=False,
                )
                if current.failure:
                    return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(current)
                if current.value.content is None:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"published Mise artifact is absent: {expected.path}; "
                        "run make gen",
                    )
                if current.value.mode is None:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"published Mise artifact mode is unreadable: {expected.path}",
                    )
                expected_state = replacements.get(
                    expected.path,
                    (expected.content, expected.mode),
                )
                if (current.value.content, current.value.mode) != expected_state:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        f"published Mise artifact differs from plan: {expected.path}",
                    )
                if current.value.mode != required_mode:
                    return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                        "published Mise artifact mode is noncanonical:"
                        f" {expected.path}"
                        f" (observed {oct(current.value.mode)},"
                        f" canonical {oct(required_mode)})",
                    )
                states.append(current.value)
        return r[tuple[m.Cli.AtomicFileState, ...]].ok(tuple(states))

    @classmethod
    def _file_identity(
        cls,
        value: m.Cli.AtomicFileState,
        *,
        parent_device: int,
        parent_inode: int,
    ) -> tuple[
        int,
        int,
        bytes | None,
        int | None,
        int | None,
        int | None,
        int | None,
        int | None,
        int | None,
    ]:
        """Return every physical and byte field except the intentionally moved path.

        Returns:
            Every physical and byte field except the intentionally moved path.

        """
        return (
            parent_device,
            parent_inode,
            value.content,
            value.mode,
            value.device,
            value.inode,
            value.link_count,
            value.file_attributes,
            value.reparse_tag,
        )


__all__: list[str] = ["FlextInfraMiseArtifactsVerification"]
