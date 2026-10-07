"""Single extensible transaction coordinator for complete project generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m, t, u
from flext_infra.codegen._codegen_staging import FlextInfraCodegenStaging
from flext_infra.codegen._codegen_transaction_recovery import (
    FlextInfraCodegenTransactionRecovery,
)
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)
from flext_infra.codegen._mise_artifacts_journal import (
    FlextInfraMiseArtifactsJournal as journal_io,
)
from flext_infra.codegen._mise_artifacts_publication import FlextInfraMisePublication
from flext_infra.codegen._mise_artifacts_staging import FlextInfraMiseStaging
from flext_infra.codegen._mise_artifacts_state import (
    FlextInfraMiseArtifactsState as state,
)
from flext_infra.codegen._mise_artifacts_verification import (
    FlextInfraMiseArtifactsVerification as verify,
)
from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenTransaction(FlextInfraCodegenTransactionRecovery):
    """Keep every generation phase recoverable until one final fixed point."""

    def __init__(self, owner: p.Infra.MiseArtifactsOwner) -> None:
        """Initialize the transaction with its configured Mise artifact owner."""
        super().__init__(owner)
        self._owner = owner
        self._mise_staging = FlextInfraMiseStaging()

    def run_files_locked[T](
        self,
        roots: t.MappingKV[str, Path],
        operation: Callable[[Path], p.Result[T]],
    ) -> p.Result[T]:
        """Hold Git and shared destination leases before planning or recovery.

        Returns:
            The resulting ``p.Result[T]``.

        """
        identity = self._planner.scope_identity()
        if identity.failure:
            return r[T].from_failure(identity)
        proposed = self._planner.file_layout(
            identity.value.repo_root,
            roots,
            transaction_id=secrets.token_hex(16),
        )
        if proposed.failure:
            return r[T].from_failure(proposed)
        with u.Infra.codegen_transaction_lease(
            self._planner.journal_path(identity.value),
        ):
            participants = {
                item.root: item for item in proposed.value.file_participants
            }
            observed = state.journal_state(proposed.value)
            if observed.failure:
                return r[T].from_failure(observed)
            snapshot = state.journal_snapshot(observed.value)
            if snapshot is not None and snapshot.content is not None:
                loaded = journal_io.read(proposed.value)
                if loaded.failure:
                    return r[T].from_failure(loaded)
                for participant in loaded.value[0].file_participants:
                    current = participants.get(participant.root)
                    if current is not None and (current.device, current.inode) != (
                        participant.device,
                        participant.inode,
                    ):
                        return r[T].fail(
                            "file capability identity changed before recovery",
                        )
                    participants[participant.root] = participant
            with self._lease_file_participants(
                tuple(participants.values()),
                held_roots=frozenset({identity.value.repo_root.resolve()}),
            ):
                return self._run_locked_operation(
                    identity.value,
                    prepare=True,
                    operation=operation,
                )

    def begin_files_locked(
        self,
        scope_root: Path,
        roots: t.MappingKV[str, Path],
        inputs: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Create a durable file-only cursor using the existing journal lifecycle.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionSession]``.

        """
        result_type = r[m.Infra.CodegenTransactionSession]
        if set(roots.values()) - self._file_leases.keys():
            return result_type.fail("file session requires every destination lease")
        transaction_id = secrets.token_hex(16)
        prepared = self._planner.file_layout(
            scope_root,
            roots,
            transaction_id=transaction_id,
        )
        if prepared.failure:
            return result_type.from_failure(prepared)
        layout = prepared.value
        mismatch = self._file_lease_mismatch(layout)
        if mismatch is not None:
            return result_type.fail(mismatch)
        plan = m.Infra.CodegenFileSessionPlan(layout=layout)
        opened = self._open_file_transaction_journal(
            layout,
            plan,
            inputs,
            transaction_id,
        )
        if opened.failure:
            return result_type.from_failure(opened)
        journal, journal_state = opened.value
        return result_type.ok(
            m.Infra.CodegenTransactionSession(
                plan=plan,
                journal=journal,
                journal_state=journal_state,
            ),
        )

    def _file_lease_mismatch(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
    ) -> str | None:
        """Describe the first file participant whose identity left its lease.

        Returns:
            The mismatch message, or None when every participant still matches.

        """
        for participant in layout.file_participants:
            leased = self._file_leases[participant.root]
            if (participant.device, participant.inode) != (leased.device, leased.inode):
                return "file capability root changed after lease acquisition"
        return None

    @staticmethod
    def _file_transaction_guard(
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        inputs: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> p.Result[
        t.Pair[t.VariadicTuple[m.Infra.CodegenJournalDirectory], m.Cli.AtomicFileState]
    ]:
        """Require a recovered-absent journal, no residue, and stable inputs.

        Returns:
            The resulting ``p.Result[t.Pair[t.VariadicTuple[
                m.Infra.CodegenJournalDirectory], m.Cli.AtomicFileState]]`` with
            the planned transaction directories and the absent-journal baseline.

        """
        result_type = r[
            t.Pair[
                t.VariadicTuple[m.Infra.CodegenJournalDirectory],
                m.Cli.AtomicFileState,
            ]
        ]
        observed = state.journal_state(layout)
        if observed.failure:
            return result_type.from_failure(observed)
        before = state.journal_snapshot(observed.value)
        if before is None or before.content is not None:
            return result_type.fail(
                "file transaction journal is not absent after recovery",
            )
        if state.transaction_residue(layout):
            return result_type.fail("file transaction has unowned staging residue")
        stable = verify.states_current(inputs)
        if stable.failure:
            return result_type.from_failure(stable)
        directories = state.plan_transaction_directories(layout)
        if directories.failure:
            return result_type.from_failure(directories)
        return result_type.ok((directories.value, before))

    def _open_file_transaction_journal(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        plan: m.Infra.CodegenFileSessionPlan,
        inputs: t.VariadicTuple[m.Cli.AtomicFileState],
        transaction_id: str,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Open, persist, materialize, and durably prepare the file journal.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        guarded = self._file_transaction_guard(layout, inputs)
        if guarded.failure:
            return result_type.from_failure(guarded)
        directories, before = guarded.value
        journal = journal_io.begin(
            plan,
            transaction_id=transaction_id,
            sources=tuple(("docs", source) for source in inputs),
            directories=directories,
        )
        if journal.failure:
            return result_type.from_failure(journal)
        opened = self._materialize_journal(layout, journal.value, expected=before)
        if opened.failure:
            return result_type.from_failure(opened)
        recorded, recorded_state = opened.value
        prepared_journal = journal_io.append_prepared(plan, recorded, ())
        if prepared_journal.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    prepared_journal.error or "file preparation failed",
                ),
            )
        ready = self._write_journal(
            layout,
            prepared_journal.value,
            expected=recorded_state,
        )
        if ready.failure:
            return result_type.from_failure(
                self._handle_journal_write_failure(
                    layout,
                    ready.error or "file cursor persistence failed",
                ),
            )
        return result_type.ok((prepared_journal.value, ready.value))

    def _materialize_journal(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        *,
        expected: m.Cli.AtomicFileState,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Persist one journal revision, then materialize its planned directories.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        persisted = self._write_journal(layout, journal, expected=expected)
        if persisted.failure:
            return result_type.from_failure(persisted)
        materialized = self._materialize_directories(layout, journal, persisted.value)
        if materialized.failure:
            return result_type.from_failure(materialized)
        recorded, recorded_state = materialized.value
        return result_type.ok((recorded, recorded_state))

    def publish_file_phase_locked(
        self,
        scope_root: Path,
        roots: t.MappingKV[str, Path],
        analysis: m.Infra.CodegenPhaseAnalysis,
        directories: t.VariadicTuple[Path],
        validator: Callable[[], p.Result[bool]],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Compose file publication through the same durable phase lifecycle.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        result_type = r[t.VariadicTuple[Path]]
        started = self.begin_files_locked(scope_root, roots, analysis.inputs)
        if started.failure:
            return result_type.from_failure(started)
        prepared = self.append_directories_locked(
            started.value,
            analysis.phase,
            directories,
        )
        if prepared.failure:
            return result_type.from_failure(prepared)
        published = self.append_phase_locked(
            prepared.value,
            analysis.phase,
            analysis.files,
        )
        if published.failure:
            return result_type.from_failure(published)
        return self.commit_locked(published.value, validator)

    def validate(
        self,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan] = (),
    ) -> p.Result[bool]:
        """Validate a coherent committed Mise snapshot under the generation lock.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return self.run_locked(
            prepare=False,
            operation=lambda scope_root: self.validate_locked(scope_root, config_plans),
        )

    def validate_locked(
        self,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan] = (),
    ) -> p.Result[bool]:
        """Reject pending recovery/residue, then exercise real Mise consumers.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        selected = self._selected_validate_layout(scope_root, config_plans)
        if selected.failure:
            return r[bool].from_failure(selected)
        layout = selected.value
        journal = state.journal_state(layout)
        if journal.failure:
            return r[bool].from_failure(journal)
        journal_snapshot = state.journal_snapshot(journal.value)
        if journal_snapshot is not None and journal_snapshot.content is not None:
            return r[bool].fail(
                "pending generation transaction requires apply-mode recovery",
            )
        residue = state.transaction_residue(layout)
        if residue:
            return r[bool].fail(
                f"generation staging has no journal authority: {residue[0]}",
            )
        plan = self._planner.snapshot(layout, config_plans)
        if plan.failure:
            return r[bool].from_failure(plan)
        return verify.live(self._owner, plan.value)

    def _selected_validate_layout(
        self,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[m.Infra.MiseToolchainWorkspaceLayout]:
        """Derive the exact topology for a validation pass and select its scope.

        Returns:
            The resulting ``p.Result[m.Infra.MiseToolchainWorkspaceLayout]``.

        """
        layout_result = (
            self._planner.layout_for_config_plans(scope_root, config_plans)
            if config_plans
            else self._planner.layout(scope_root)
        )
        if layout_result.failure:
            return r[m.Infra.MiseToolchainWorkspaceLayout].from_failure(layout_result)
        return self._planner.select_layout(layout_result.value, config_plans)

    @staticmethod
    def validate_phase_analysis_locked(
        analysis: m.Infra.CodegenPhaseAnalysis,
    ) -> p.Result[bool]:
        """Validate a published phase from its immutable planning receipt.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return verify.phase_analysis_live(analysis)

    def run_locked[T](
        self,
        *,
        prepare: bool,
        operation: Callable[[Path], p.Result[T]],
    ) -> p.Result[T]:
        """Own the shared journal before recovery through final publication cleanup.

        Returns:
            The resulting ``p.Result[T]``.

        """
        identity = self._planner.scope_identity()
        if identity.failure:
            return r[T].from_failure(identity)
        with u.Infra.codegen_transaction_lease(
            self._planner.journal_path(identity.value),
        ):
            return self._run_locked_operation(
                identity.value,
                prepare=prepare,
                operation=operation,
            )

    def _run_locked_operation[T](
        self,
        identity: m.Infra.GitIdentityReport,
        *,
        prepare: bool,
        operation: Callable[[Path], p.Result[T]],
    ) -> p.Result[T]:
        """Reauthenticate and reconcile after the descriptor lock is held.

        Returns:
            The resulting ``p.Result[T]``.

        """
        if prepare:
            reconciled = self._reconcile(identity)
            if reconciled.failure:
                return r[T].from_failure(reconciled)
        return operation(identity.repo_root)

    def begin_locked(
        self,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
        file_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Publish conform+Mise as the first fully journaled prepared phase.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionSession]``.

        """
        result_type = r[m.Infra.CodegenTransactionSession]
        settled = self._stage_generation_transaction(
            scope_root,
            config_plans,
            file_plans,
        )
        if settled.failure:
            return result_type.from_failure(settled)
        published = self._publish_generation_transaction(settled.value)
        if published.failure:
            return result_type.from_failure(published)
        return result_type.ok(published.value)

    def _validated_generation_topology(
        self,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
        file_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
        transaction_id: str,
    ) -> p.Result[
        t.Triple[
            m.Infra.MiseToolchainWorkspaceLayout,
            t.VariadicTuple[m.Infra.CodegenJournalDirectory],
            m.Infra.MiseToolchainWorkspacePlan,
        ]
    ]:
        """Derive transaction topology, reject residue, and plan its directories.

        Returns:
            The resulting ``p.Result[t.Triple[m.Infra.MiseToolchainWorkspaceLayout,
                t.VariadicTuple[m.Infra.CodegenJournalDirectory],
                m.Infra.MiseToolchainWorkspacePlan]]``.

        """
        result_type = r[
            t.Triple[
                m.Infra.MiseToolchainWorkspaceLayout,
                t.VariadicTuple[m.Infra.CodegenJournalDirectory],
                m.Infra.MiseToolchainWorkspacePlan,
            ]
        ]
        layout_result = self._planner.layout_for_config_plans(
            scope_root,
            config_plans,
            transaction_id=transaction_id,
        )
        if layout_result.failure:
            return result_type.from_failure(layout_result)
        layout = layout_result.value
        residue = state.transaction_residue(layout)
        if residue:
            return result_type.fail(
                f"generation residue has no journal authority: {residue[0]}",
            )
        transaction_directories = state.plan_transaction_directories(
            layout,
            destinations=tuple(
                item.path
                for item in file_plans
                if item.desired_content is not None
                and u.Infra.codegen_file_requires_effect(item)
            ),
        )
        if transaction_directories.failure:
            return result_type.from_failure(transaction_directories)
        plan = self._planner.snapshot(layout, config_plans)
        if plan.failure:
            return result_type.from_failure(plan)
        return result_type.ok((layout, transaction_directories.value, plan.value))

    @staticmethod
    def _generation_source_barrier(
        file_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
        plan: m.Infra.MiseToolchainWorkspacePlan,
    ) -> p.Result[t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]]]:
        """Prove conform and Mise sources unchanged, and tag them per phase.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[t.Pair[str,
                m.Cli.AtomicFileState]]]``.

        """
        source_states = FlextInfraCodegenPreconditions.phase_sources(
            "conform",
            file_plans,
        )
        if source_states.failure:
            return source_states
        all_sources = (
            *source_states.value,
            *(("mise", source) for source in plan.sources),
        )
        return verify.states_current(
            FlextInfraCodegenPreconditions.unique_states(
                tuple(source for _phase, source in all_sources),
            ),
        ).map(lambda _ok: all_sources)

    def _open_generation_journal(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        all_sources: t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
        transaction_id: str,
        transaction_directories: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Open the generation journal on an absent baseline and materialize it.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        journal_before = state.journal_state(layout)
        if journal_before.failure:
            return result_type.from_failure(journal_before)
        journal_before_snapshot = state.journal_snapshot(journal_before.value)
        if journal_before_snapshot is None:
            return result_type.fail("generation journal state is unavailable")
        if journal_before_snapshot.content is not None:
            return result_type.fail("generation journal appeared after locked recovery")
        staging_journal = journal_io.begin(
            plan,
            transaction_id=transaction_id,
            sources=all_sources,
            directories=transaction_directories,
        )
        if staging_journal.failure:
            return result_type.from_failure(staging_journal)
        return self._materialize_journal(
            layout,
            staging_journal.value,
            expected=journal_before_snapshot,
        )

    def _register_mise_staging(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
    ) -> p.Result[
        t.Triple[
            m.Infra.CodegenTransactionJournal,
            m.Cli.AtomicFileState,
            t.VariadicTuple[m.Infra.CodegenStagedFile],
        ]
    ]:
        """Stage Mise artifacts and record their manifests into the journal.

        Returns:
            The resulting ``p.Result[t.Triple[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState, t.VariadicTuple[
                m.Infra.CodegenStagedFile]]]``.

        """
        result_type = r[
            t.Triple[
                m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState,
                t.VariadicTuple[m.Infra.CodegenStagedFile],
            ]
        ]
        mise_staged = self._mise_staging.stage(plan)
        if mise_staged.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    mise_staged.error or "cannot stage Mise artifacts",
                ),
            )
        mise_files, mise_directories = mise_staged.value
        staged_manifest = verify.register_transaction_manifests(
            layout,
            journal,
            created=(
                *mise_directories,
                *(
                    item.replacement
                    for item in mise_files
                    if item.replacement is not None
                ),
            ),
        )
        if staged_manifest.failure:
            return result_type.from_failure(staged_manifest)
        recorded = journal_io.record_directories(journal, staged_manifest.value)
        if recorded.failure:
            return result_type.from_failure(recorded)
        persisted = self._write_journal(layout, recorded.value, expected=journal_state)
        if persisted.failure:
            return result_type.from_failure(persisted)
        return result_type.ok((recorded.value, persisted.value, mise_files))

    def _stage_generation_transaction(
        self,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
        file_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[
        tuple[
            m.Infra.MiseToolchainWorkspaceLayout,
            m.Infra.MiseToolchainWorkspacePlan,
            t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState],
            t.VariadicTuple[m.Infra.CodegenStagedFile],
            t.VariadicTuple[m.Infra.CodegenFilePlan],
        ]
    ]:
        """Validate topology, open the journal, and register Mise staging.

        Returns:
            The resulting staged tuple carrying the layout, plan, tagged
            sources, journal pair, staged Mise files, and the ordinary
            (non-config) conform plans.

        """
        result_type = r[
            tuple[
                m.Infra.MiseToolchainWorkspaceLayout,
                m.Infra.MiseToolchainWorkspacePlan,
                t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
                t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState],
                t.VariadicTuple[m.Infra.CodegenStagedFile],
                t.VariadicTuple[m.Infra.CodegenFilePlan],
            ]
        ]
        transaction_id = secrets.token_hex(16)
        topology = self._validated_generation_topology(
            scope_root,
            config_plans,
            file_plans,
            transaction_id,
        )
        if topology.failure:
            return result_type.from_failure(topology)
        layout, transaction_directories, plan = topology.value
        sources = self._generation_source_barrier(file_plans, plan)
        if sources.failure:
            return result_type.from_failure(sources)
        opened = self._open_generation_journal(
            layout,
            plan,
            sources.value,
            transaction_id,
            transaction_directories,
        )
        if opened.failure:
            return result_type.from_failure(opened)
        registered = self._register_mise_staging(layout, plan, *opened.value)
        if registered.failure:
            return result_type.from_failure(registered)
        active_journal, active_state, mise_files = registered.value
        config_paths = {config_plan.path for config_plan in config_plans}
        ordinary = tuple(
            file_plan
            for file_plan in file_plans
            if file_plan.path not in config_paths
            and u.Infra.codegen_file_requires_effect(file_plan)
        )
        return result_type.ok((
            layout,
            plan,
            sources.value,
            (active_journal, active_state),
            mise_files,
            ordinary,
        ))

    def _validate_staged_configs(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        mise_files: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[bool]:
        """Re-validate every staged Mise configuration on its staged root.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for project in plan.projects:
            staged_config = next(
                item.replacement
                for item in mise_files
                if item.before.path == project.config.before.path
            )
            if staged_config is None:
                return r[bool].fail("Mise staging receipt has no configuration")
            # The staged set is complete and self-contained; its projection of
            # the runtime root is proven again on the published destinations.
            staged_root = staged_config.path.parent
            validated = self._owner.validate_artifacts(staged_root, staged_root)
            if validated.failure:
                return self._recover_failure(
                    layout,
                    validated.error or "Mise staged validation failed",
                )
        return r[bool].ok(value=True)

    def _bind_conform_publications(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        ordinary: t.VariadicTuple[m.Infra.CodegenFilePlan],
        mise_publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]:
        """Stage the ordinary conform files and bind every destination parent.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]``
            with the complete publication set (conform plus changed Mise files).

        """
        ordinary_staged = FlextInfraCodegenStaging.stage_file_plans(
            layout,
            "conform",
            ordinary,
        )
        if ordinary_staged.failure:
            return r[t.VariadicTuple[m.Infra.CodegenStagedFile]].from_failure(
                self._recover_failure(
                    layout,
                    ordinary_staged.error or "cannot stage conform files",
                ),
            )
        return state.bind_created_parents(
            journal.directories,
            (*ordinary_staged.value, *mise_publications),
        )

    def _prepare_generation_journal(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        all_sources: t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
        journal_state: t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState],
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Durably prepare the generation journal, then re-verify the barriers.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        active_journal, active_state = journal_state
        barriers = self._verified_prepublication_barriers(
            layout,
            plan,
            all_sources,
            publications,
        )
        if barriers.failure:
            return result_type.from_failure(barriers)
        prepared_journal = journal_io.append_prepared(
            plan,
            active_journal,
            publications,
            sources=all_sources,
        )
        if prepared_journal.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    prepared_journal.error or "cannot prepare generation journal",
                ),
            )
        manifested = journal_io.record_transaction_manifests(
            layout,
            prepared_journal.value,
        )
        if manifested.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    manifested.error or "cannot register generation staging tree",
                ),
            )
        prepared_state = self._write_journal(
            layout,
            manifested.value,
            expected=active_state,
        )
        if prepared_state.failure:
            return result_type.from_failure(
                self._handle_journal_write_failure(
                    layout,
                    prepared_state.error
                    or "cannot publish prepared generation journal",
                ),
            )
        barriers = self._verified_prepublication_barriers(
            layout,
            plan,
            all_sources,
            publications,
        )
        if barriers.failure:
            return result_type.from_failure(barriers)
        return result_type.ok((manifested.value, prepared_state.value))

    def _publish_prepared_generation(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
        mise_publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Publish the staged set and prove publication and real-consumer liveness.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]`` with the written
            files.

        """
        published = FlextInfraMisePublication.publish(publications)
        if published.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    layout,
                    published.error or "generation publication failed",
                ),
            )
        publication_state = verify.publications_live(publications)
        if publication_state.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    layout,
                    publication_state.error
                    or "generation publication identity changed",
                ),
            )
        live = verify.live(self._owner, plan, mise_publications)
        if live.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    layout,
                    live.error or "Mise real-consumer validation failed",
                ),
            )
        return published

    def _publish_generation_transaction(
        self,
        settled: tuple[
            m.Infra.MiseToolchainWorkspaceLayout,
            m.Infra.MiseToolchainWorkspacePlan,
            t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState],
            t.VariadicTuple[m.Infra.CodegenStagedFile],
            t.VariadicTuple[m.Infra.CodegenFilePlan],
        ],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Validate staged configs, prepare the journal, and publish.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionSession]``.

        """
        result_type = r[m.Infra.CodegenTransactionSession]
        layout, plan, all_sources, journal_state, mise_files, ordinary = settled
        validated = self._validate_staged_configs(layout, plan, mise_files)
        if validated.failure:
            return result_type.from_failure(validated)
        mise_publications = tuple(
            item
            for item in mise_files
            if item.replacement is not None
            and u.Infra.atomic_file_state_differs(
                item.before,
                desired_content=item.replacement.content,
                desired_mode=item.replacement.mode,
            )
        )
        publications = self._bind_conform_publications(
            layout,
            journal_state[0],
            ordinary,
            mise_publications,
        )
        if publications.failure:
            return result_type.from_failure(publications)
        prepared = self._prepare_generation_journal(
            layout,
            plan,
            all_sources,
            journal_state,
            publications.value,
        )
        if prepared.failure:
            return result_type.from_failure(prepared)
        manifested, prepared_state = prepared.value
        finalized = self._publish_prepared_generation(
            layout,
            plan,
            publications.value,
            mise_publications,
        )
        if finalized.failure:
            return result_type.from_failure(finalized)
        return result_type.ok(
            m.Infra.CodegenTransactionSession(
                plan=plan,
                journal=manifested,
                journal_state=prepared_state,
                written_files=finalized.value,
            ),
        )

    def append_phase_locked(
        self,
        session: m.Infra.CodegenTransactionSession,
        phase: str,
        plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Append, durably authorize, then publish one dependent generated phase.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionSession]``.

        """
        result_type = r[m.Infra.CodegenTransactionSession]
        changed = tuple(
            plan for plan in plans if u.Infra.codegen_file_requires_effect(plan)
        )
        if not changed:
            return result_type.ok(session)
        authorized = self._authorize_phase_destinations(session, phase, changed, plans)
        if authorized.failure:
            return result_type.from_failure(authorized)
        staged = self._stage_authorized_phase(authorized.value, phase, changed)
        if staged.failure:
            return result_type.from_failure(staged)
        persisted = self._persist_phase_journal(authorized.value, phase, staged.value)
        if persisted.failure:
            return result_type.from_failure(persisted)
        published = self._publish_verified_phase(
            authorized.value[0].plan.layout,
            phase,
            staged.value,
        )
        if published.failure:
            return result_type.from_failure(published)
        journal, journal_state = persisted.value
        return result_type.ok(
            m.Infra.CodegenTransactionSession(
                plan=authorized.value[0].plan,
                journal=journal,
                journal_state=journal_state,
                written_files=(*session.written_files, *published.value),
            ),
        )

    def _authorize_phase_destinations(
        self,
        session: m.Infra.CodegenTransactionSession,
        phase: str,
        changed: t.VariadicTuple[m.Infra.CodegenFilePlan],
        plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[
        t.Triple[
            m.Infra.CodegenTransactionSession,
            t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
            t.VariadicTuple[m.Cli.AtomicFileState],
        ]
    ]:
        """Authorize the journal and prove the phase's sources unchanged.

        Returns:
            The resulting ``p.Result[t.Triple[m.Infra.CodegenTransactionSession,
                t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
                t.VariadicTuple[m.Cli.AtomicFileState]]]`` carrying the aligned
            session, the tagged sources, and their bare states.

        """
        result_type = r[
            t.Triple[
                m.Infra.CodegenTransactionSession,
                t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
                t.VariadicTuple[m.Cli.AtomicFileState],
            ]
        ]
        aligned = FlextInfraCodegenPreconditions.unchanged_journal(
            session,
            "generation journal changed between phases",
        )
        if aligned.failure:
            return result_type.from_failure(aligned)
        session = aligned.value
        layout = session.plan.layout
        existing_paths = {entry.path for entry in session.journal.entries}
        for plan in changed:
            relative = files.transaction_relative(layout, plan.path)
            if relative.failure:
                return result_type.from_failure(relative)
            if relative.value in existing_paths:
                return result_type.from_failure(
                    self._recover_failure(
                        layout,
                        "multiple generation phases own one destination: "
                        f"{relative.value}",
                    ),
                )
        sources = FlextInfraCodegenPreconditions.phase_sources(phase, plans)
        if sources.failure:
            return result_type.from_failure(
                self._recover_failure(layout, sources.error or "invalid phase sources"),
            )
        source_states = tuple(source for _phase, source in sources.value)
        source_barrier = verify.states_current(
            FlextInfraCodegenPreconditions.unique_states(source_states),
            journal=session.journal,
        )
        if source_barrier.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    source_barrier.error or f"{phase} sources changed",
                ),
            )
        return result_type.ok((session, sources.value, source_states))

    def _stage_authorized_phase(
        self,
        authorized: t.Triple[
            m.Infra.CodegenTransactionSession,
            t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
            t.VariadicTuple[m.Cli.AtomicFileState],
        ],
        phase: str,
        changed: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]:
        """Stage the phase's files, bind parents, and prove destinations stable.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenStagedFile]]``.

        """
        session = authorized[0]
        layout = session.plan.layout
        staged = FlextInfraCodegenStaging.stage_file_plans(layout, phase, changed)
        if staged.failure:
            return r[t.VariadicTuple[m.Infra.CodegenStagedFile]].from_failure(
                self._recover_failure(
                    layout,
                    staged.error or f"cannot stage {phase} phase",
                ),
            )
        bound = state.bind_created_parents(session.journal.directories, staged.value)
        if bound.failure:
            return r[t.VariadicTuple[m.Infra.CodegenStagedFile]].from_failure(
                self._recover_failure(
                    layout,
                    bound.error or f"cannot bind {phase} destination parents",
                ),
            )
        destination_barrier = verify.states_current(
            tuple(item.before for item in bound.value),
        )
        if destination_barrier.failure:
            return r[t.VariadicTuple[m.Infra.CodegenStagedFile]].from_failure(
                self._recover_failure(
                    layout,
                    destination_barrier.error or f"{phase} destinations changed",
                ),
            )
        return bound

    def _persist_phase_journal(
        self,
        authorized: t.Triple[
            m.Infra.CodegenTransactionSession,
            t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
            t.VariadicTuple[m.Cli.AtomicFileState],
        ],
        phase: str,
        staged: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Append, manifest, and durably persist the phase, then re-verify barriers.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        session, tagged_sources, source_states = authorized
        layout = session.plan.layout
        extended = journal_io.append_prepared(
            session.plan,
            session.journal,
            staged,
            sources=tagged_sources,
        )
        if extended.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    extended.error or f"cannot append {phase} journal phase",
                ),
            )
        manifested = journal_io.record_transaction_manifests(layout, extended.value)
        if manifested.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    manifested.error or f"cannot register {phase} staging tree",
                ),
            )
        persisted = self._write_journal(
            layout,
            manifested.value,
            expected=session.journal_state,
        )
        if persisted.failure:
            return result_type.from_failure(
                self._handle_journal_write_failure(
                    layout,
                    persisted.error or f"cannot persist {phase} journal phase",
                ),
            )
        source_barrier = verify.states_current(
            FlextInfraCodegenPreconditions.unique_states(source_states),
            journal=manifested.value,
        )
        destination_barrier = verify.states_current(
            tuple(item.before for item in staged),
        )
        if source_barrier.failure or destination_barrier.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    source_barrier.error
                    or destination_barrier.error
                    or f"{phase} prepublication barrier failed",
                ),
            )
        return result_type.ok((manifested.value, persisted.value))

    def _publish_verified_phase(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        phase: str,
        staged: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Publish the verified staged set and prove it live.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]`` with the written
            files.

        """
        published = FlextInfraMisePublication.publish(staged)
        if published.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    layout,
                    published.error or f"cannot publish {phase} phase",
                ),
            )
        live = verify.publications_live(staged)
        if live.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    layout,
                    live.error or f"{phase} publication changed",
                ),
            )
        return published

    def append_directories_locked(
        self,
        session: m.Infra.CodegenTransactionSession,
        phase: str,
        directories: t.VariadicTuple[Path],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Authorize missing generated directories durably, then create them.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenTransactionSession]``.

        """
        result_type = r[m.Infra.CodegenTransactionSession]
        planned = state.plan_directories(
            session.plan.layout,
            phase=phase,
            requested=directories,
            disposition="generated",
        )
        if planned.failure:
            return result_type.from_failure(
                self._recover_failure(
                    session.plan.layout,
                    planned.error or f"cannot plan {phase} directories",
                ),
            )
        if not planned.value:
            return result_type.ok(session)
        materialized = self._persist_directories(session, phase, planned.value)
        if materialized.failure:
            return result_type.from_failure(materialized)
        recorded, recorded_state = materialized.value
        return result_type.ok(
            m.Infra.CodegenTransactionSession(
                plan=session.plan,
                journal=recorded,
                journal_state=recorded_state,
                written_files=session.written_files,
            ),
        )

    def _persist_directories(
        self,
        session: m.Infra.CodegenTransactionSession,
        phase: str,
        planned: t.VariadicTuple[m.Infra.CodegenJournalDirectory],
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Authorize the journal, append the directories, and materialize them.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        layout = session.plan.layout
        unchanged = FlextInfraCodegenPreconditions.unchanged_journal(
            session,
            "generation journal changed before directories",
        )
        if unchanged.failure:
            return result_type.from_failure(unchanged)
        session = unchanged.value
        extended = journal_io.append_directories(session.journal, planned)
        if extended.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    extended.error or f"cannot append {phase} directories",
                ),
            )
        persisted = self._write_journal(
            layout,
            extended.value,
            expected=session.journal_state,
        )
        if persisted.failure:
            return result_type.from_failure(
                self._handle_journal_write_failure(
                    layout,
                    persisted.error or f"cannot persist {phase} directories",
                ),
            )
        return self._materialize_directories(layout, extended.value, persisted.value)

    def commit_locked(
        self,
        session: m.Infra.CodegenTransactionSession,
        validator: Callable[[], p.Result[bool]],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Validate final reality while recoverable, then commit and clean up.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        exact = verify.journal_destinations_live(session.plan.layout, session.journal)
        if exact.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    session.plan.layout,
                    exact.error or "publication identity changed",
                ),
            )
        validated = validator()
        if validated.failure or not validated.value:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    session.plan.layout,
                    validated.error or "generation fixed-point validation failed",
                ),
            )
        committed = self._verified_commit(session)
        if committed.failure:
            return r[t.VariadicTuple[Path]].from_failure(committed)
        cleaned = journal_io.cleanup(
            session.plan.layout,
            committed.value[0],
            committed.value[1],
        )
        if cleaned.failure:
            return r[t.VariadicTuple[Path]].from_failure(cleaned)
        self._journal_receipts.pop(session.plan.layout.journal_path, None)
        return r[t.VariadicTuple[Path]].ok(session.written_files)

    def _verified_commit(
        self,
        session: m.Infra.CodegenTransactionSession,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Re-prove the journal, commit it, and durably persist the commit.

        Returns:
            The resulting ``p.Result[t.Pair[m.Infra.CodegenTransactionJournal,
                m.Cli.AtomicFileState]]``.

        """
        result_type = r[
            t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]
        ]
        layout = session.plan.layout
        unchanged = FlextInfraCodegenPreconditions.unchanged_journal(
            session,
            "generation journal changed before commit",
        )
        if unchanged.failure:
            return result_type.from_failure(unchanged)
        session = unchanged.value
        exact = verify.journal_destinations_live(layout, session.journal)
        if exact.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    exact.error or "publication identity changed before commit",
                ),
            )
        committed = journal_io.commit(session.journal)
        if committed.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    committed.error or "cannot validate generation commit",
                ),
            )
        committed_state = self._write_journal(
            layout,
            committed.value,
            expected=session.journal_state,
        )
        if committed_state.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    committed_state.error or "cannot persist generation commit",
                ),
            )
        return result_type.ok((committed.value, committed_state.value))

    def abort_locked(
        self,
        session: m.Infra.CodegenTransactionSession,
        failure: str,
    ) -> p.Result[bool]:
        """Recover the complete prepared transaction and preserve the cause.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return self._recover_failure(session.plan.layout, failure)

    def publish_prepared_locked[T](
        self,
        session: m.Infra.CodegenTransactionSession,
        operation: Callable[[m.Infra.CodegenTransactionSession], p.Result[T]],
    ) -> p.Result[T]:
        """Run every phase after ``begin_locked`` without stranding its journal.

        A phase that fails or raises after the journal was prepared recovers
        that journal here, while the lease is still held, and keeps the cause:
        a failure is returned unchanged and an exception escapes unchanged.
        A failure whose owner already attempted or refused recovery (it carries
        ``recovery_error``) is returned as-is, never recovered twice.

        Returns:
            The resulting ``p.Result[T]``.

        """
        layout = session.plan.layout
        try:
            outcome = operation(session)
        except Exception as exc:
            recovered = self._recover_prepared(layout)
            if recovered.failure:
                exc.add_note(f"generation recovery failed: {recovered.error}")
            raise
        if outcome.success or (
            outcome.error_data is not None and "recovery_error" in outcome.error_data
        ):
            return outcome
        recovered = self._recover_prepared(layout)
        if recovered.failure:
            return r[T].fail(
                outcome.error or "generation phase failed",
                error_data={
                    **(outcome.error_data or {}),
                    "recovery_error": recovered.error,
                },
            )
        return outcome


__all__: list[str] = ["FlextInfraCodegenTransaction"]
