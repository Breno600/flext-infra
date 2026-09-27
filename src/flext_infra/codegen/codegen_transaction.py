"""Single extensible transaction coordinator for complete project generation."""

from __future__ import annotations

import secrets
from collections.abc import Callable, Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t, u
from flext_infra.codegen.mise_artifacts_workspace import FlextInfraMiseWorkspacePlanner

from ._codegen_staging import stage_file_plans
from ._mise_artifacts_files import FlextInfraMiseArtifactsFiles as files
from ._mise_artifacts_journal import FlextInfraMiseArtifactsJournal as journal_io
from ._mise_artifacts_publication import publish
from ._mise_artifacts_recovery import FlextInfraMiseRecovery
from ._mise_artifacts_staging import FlextInfraMiseStaging
from ._mise_artifacts_state import FlextInfraMiseArtifactsState as state
from ._mise_artifacts_verification import FlextInfraMiseArtifactsVerification as verify
from .codegen_preconditions import FlextInfraCodegenPreconditions

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenTransaction:
    """Keep every generation phase recoverable until one final fixed point."""

    def __init__(self, owner: p.Infra.MiseArtifactsOwner) -> None:
        """Initialize the transaction with its configured Mise artifact owner."""
        self._owner = owner
        self._planner = FlextInfraMiseWorkspacePlanner(owner)
        self._recovery = FlextInfraMiseRecovery()
        self._mise_staging = FlextInfraMiseStaging()
        self._file_leases: dict[Path, m.Infra.CodegenFileParticipant] = {}
        self._journal_receipts: dict[Path, m.Cli.AtomicFileState] = {}

    def run_files_locked[T](
        self, roots: t.MappingKV[str, Path], operation: Callable[[Path], p.Result[T]]
    ) -> p.Result[T]:
        """Hold Git and shared destination leases before planning or recovery."""
        identity = self._planner.scope_identity()
        if identity.failure:
            return r[T].from_failure(identity)
        proposed = self._planner.file_layout(
            identity.value.repo_root, roots, transaction_id=secrets.token_hex(16)
        )
        if proposed.failure:
            return r[T].from_failure(proposed)
        with u.Infra.codegen_transaction_lease(
            self._planner.journal_path(identity.value)
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
                            "file capability identity changed before recovery"
                        )
                    participants[participant.root] = participant
            with self._lease_file_participants(tuple(participants.values())):
                return self._run_locked_operation(
                    identity.value, prepare=True, operation=operation
                )

    @contextmanager
    def _lease_file_participants(
        self, participants: t.VariadicTuple[m.Infra.CodegenFileParticipant]
    ) -> Generator[None]:
        """Serialize shared destinations across worktrees in stable path order."""
        for participant in participants:
            physical = files.physical_directory_identity(participant.root).unwrap()
            if physical != (participant.device, participant.inode):
                msg = f"file publication root changed before lease: {participant.root}"
                raise ValueError(msg)
        acquired: set[Path] = set()
        try:
            with ExitStack() as stack:
                for participant in sorted(
                    participants, key=lambda item: str(item.root)
                ):
                    if participant.root in self._file_leases:
                        continue
                    # The lease is regenerable transaction state: it lives in
                    # the root's ignored state directory, never beside tracked
                    # content where it would surface as an untracked entry.
                    lease_directory = (
                        participant.root / c.Infra.TRANSACTION_STATE_DIRNAME
                    )
                    if lease_directory.is_symlink() or lease_directory.exists():
                        files.physical_directory_identity(lease_directory).unwrap()
                    lease_path = lease_directory / c.Infra.JOURNAL_NAME
                    u.Cli.atomic_read_binary_file_state(
                        lease_path.with_name(f"{lease_path.name}.lock"), required=False
                    ).unwrap()
                    stack.enter_context(u.Infra.codegen_transaction_lease(lease_path))
                    files.physical_directory_identity(lease_directory).unwrap()
                    acquired.add(participant.root)
                    self._file_leases[participant.root] = participant
                    physical = files.physical_directory_identity(
                        participant.root
                    ).unwrap()
                    if physical != (participant.device, participant.inode):
                        msg = f"file publication root changed during lease: {participant.root}"
                        raise ValueError(msg)
                yield
        finally:
            for root in acquired:
                self._file_leases.pop(root)

    def begin_files_locked(
        self,
        scope_root: Path,
        roots: t.MappingKV[str, Path],
        inputs: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Create a durable file-only cursor using the existing journal lifecycle."""
        result_type = r[m.Infra.CodegenTransactionSession]
        if set(roots.values()) - self._file_leases.keys():
            return result_type.fail("file session requires every destination lease")
        transaction_id = secrets.token_hex(16)
        prepared = self._planner.file_layout(
            scope_root, roots, transaction_id=transaction_id
        )
        if prepared.failure:
            return result_type.from_failure(prepared)
        layout = prepared.value
        for participant in layout.file_participants:
            leased = self._file_leases[participant.root]
            if (participant.device, participant.inode) != (leased.device, leased.inode):
                return result_type.fail(
                    "file capability root changed after lease acquisition"
                )
        plan = m.Infra.CodegenFileSessionPlan(layout=layout)
        observed = state.journal_state(layout)
        if observed.failure:
            return result_type.from_failure(observed)
        before = state.journal_snapshot(observed.value)
        if before is None or before.content is not None:
            return result_type.fail(
                "file transaction journal is not absent after recovery"
            )
        if state.transaction_residue(layout):
            return result_type.fail("file transaction has unowned staging residue")
        stable = verify.states_current(inputs)
        if stable.failure:
            return result_type.from_failure(stable)
        directories = state.plan_transaction_directories(layout)
        if directories.failure:
            return result_type.from_failure(directories)
        journal = journal_io.begin(
            plan,
            transaction_id=transaction_id,
            sources=tuple(("docs", source) for source in inputs),
            directories=directories.value,
        )
        if journal.failure:
            return result_type.from_failure(journal)
        persisted = self._write_journal(layout, journal.value, expected=before)
        if persisted.failure:
            return result_type.from_failure(persisted)
        materialized = self._materialize_directories(
            layout, journal.value, persisted.value
        )
        if materialized.failure:
            return result_type.from_failure(materialized)
        recorded, recorded_state = materialized.value
        prepared_journal = journal_io.append_prepared(plan, recorded, ())
        if prepared_journal.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, prepared_journal.error or "file preparation failed"
                )
            )
        ready = self._write_journal(
            layout, prepared_journal.value, expected=recorded_state
        )
        if ready.failure:
            return result_type.from_failure(
                self._handle_journal_write_failure(
                    layout, ready.error or "file cursor persistence failed"
                )
            )
        return result_type.ok(
            m.Infra.CodegenTransactionSession(
                plan=plan, journal=prepared_journal.value, journal_state=ready.value
            )
        )

    def publish_file_phase_locked(
        self,
        scope_root: Path,
        roots: t.MappingKV[str, Path],
        analysis: m.Infra.CodegenPhaseAnalysis,
        directories: t.VariadicTuple[Path],
        validator: Callable[[], p.Result[bool]],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Compose file publication through the same durable phase lifecycle."""
        result_type = r[t.VariadicTuple[Path]]
        started = self.begin_files_locked(scope_root, roots, analysis.inputs)
        if started.failure:
            return result_type.from_failure(started)
        prepared = self.append_directories_locked(
            started.value, analysis.phase, directories
        )
        if prepared.failure:
            return result_type.from_failure(prepared)
        published = self.append_phase_locked(
            prepared.value, analysis.phase, analysis.files
        )
        if published.failure:
            return result_type.from_failure(published)
        return self.commit_locked(published.value, validator)

    def validate(
        self, config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan] = ()
    ) -> p.Result[bool]:
        """Validate a coherent committed Mise snapshot under the generation lock."""
        return self.run_locked(
            prepare=False,
            operation=lambda scope_root: self.validate_locked(scope_root, config_plans),
        )

    def validate_locked(
        self,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan] = (),
    ) -> p.Result[bool]:
        """Reject pending recovery/residue, then exercise real Mise consumers."""
        layout_result = (
            self._planner.layout_for_config_plans(scope_root, config_plans)
            if config_plans
            else self._planner.layout(scope_root)
        )
        if layout_result.failure:
            return r[bool].from_failure(layout_result)
        selected = self._planner.select_layout(layout_result.value, config_plans)
        if selected.failure:
            return r[bool].from_failure(selected)
        layout = selected.value
        journal = state.journal_state(layout)
        if journal.failure:
            return r[bool].from_failure(journal)
        journal_snapshot = state.journal_snapshot(journal.value)
        if journal_snapshot is not None and journal_snapshot.content is not None:
            return r[bool].fail(
                "pending generation transaction requires apply-mode recovery"
            )
        residue = state.transaction_residue(layout)
        if residue:
            return r[bool].fail(
                f"generation staging has no journal authority: {residue[0]}"
            )
        plan = self._planner.snapshot(layout, config_plans)
        if plan.failure:
            return r[bool].from_failure(plan)
        return verify.live(self._owner, plan.value)

    @staticmethod
    def validate_phase_analysis_locked(
        analysis: m.Infra.CodegenPhaseAnalysis,
    ) -> p.Result[bool]:
        """Validate a published phase from its immutable planning receipt."""
        return verify.phase_analysis_live(analysis)

    def run_locked[T](
        self, *, prepare: bool, operation: Callable[[Path], p.Result[T]]
    ) -> p.Result[T]:
        """Own the shared journal before recovery through final publication cleanup."""
        identity = self._planner.scope_identity()
        if identity.failure:
            return r[T].from_failure(identity)
        with u.Infra.codegen_transaction_lease(
            self._planner.journal_path(identity.value)
        ):
            return self._run_locked_operation(
                identity.value, prepare=prepare, operation=operation
            )

    def _run_locked_operation[T](
        self,
        identity: m.Infra.GitIdentityReport,
        *,
        prepare: bool,
        operation: Callable[[Path], p.Result[T]],
    ) -> p.Result[T]:
        """Reauthenticate and reconcile after the descriptor lock is held."""
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
        """Publish conform+Mise as the first fully journaled prepared phase."""
        result_type = r[m.Infra.CodegenTransactionSession]
        transaction_id = secrets.token_hex(16)
        layout_result = self._planner.layout_for_config_plans(
            scope_root, config_plans, transaction_id=transaction_id
        )
        if layout_result.failure:
            return result_type.from_failure(layout_result)
        layout = layout_result.value
        residue = state.transaction_residue(layout)
        if residue:
            return result_type.fail(
                f"generation residue has no journal authority: {residue[0]}"
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
        journal_before = state.journal_state(layout)
        if journal_before.failure:
            return result_type.from_failure(journal_before)
        journal_before_snapshot = state.journal_snapshot(journal_before.value)
        if journal_before_snapshot is None:
            return result_type.fail("generation journal state is unavailable")
        if journal_before_snapshot.content is not None:
            return result_type.fail("generation journal appeared after locked recovery")
        config_paths = {config_plan.path for config_plan in config_plans}
        ordinary = tuple(
            file_plan
            for file_plan in file_plans
            if file_plan.path not in config_paths
            and u.Infra.codegen_file_requires_effect(file_plan)
        )
        source_states = FlextInfraCodegenPreconditions.phase_sources(
            "conform", file_plans
        )
        if source_states.failure:
            return result_type.from_failure(source_states)
        mise_sources = tuple(
            ("mise", source)
            for project in plan.value.projects
            for source in project.config.sources
        )
        all_sources = (*source_states.value, *mise_sources)
        source_barrier = verify.states_current(
            FlextInfraCodegenPreconditions.unique_states(
                tuple(source for _phase, source in all_sources)
            )
        )
        if source_barrier.failure:
            return result_type.from_failure(source_barrier)
        staging_journal = journal_io.begin(
            plan.value,
            transaction_id=transaction_id,
            sources=all_sources,
            directories=transaction_directories.value,
        )
        if staging_journal.failure:
            return result_type.from_failure(staging_journal)
        staging_state = self._write_journal(
            layout, staging_journal.value, expected=journal_before_snapshot
        )
        if staging_state.failure:
            return result_type.from_failure(staging_state)
        materialized = self._materialize_directories(
            layout, staging_journal.value, staging_state.value
        )
        if materialized.failure:
            return result_type.from_failure(materialized)
        active_journal, active_state = materialized.value
        mise_staged = self._mise_staging.stage(plan.value)
        if mise_staged.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, mise_staged.error or "cannot stage Mise artifacts"
                )
            )
        mise_files, mise_directories = mise_staged.value
        staged_manifest = verify.register_transaction_manifests(
            layout,
            active_journal,
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
        recorded = journal_io.record_directories(active_journal, staged_manifest.value)
        if recorded.failure:
            return result_type.from_failure(recorded)
        persisted = self._write_journal(layout, recorded.value, expected=active_state)
        if persisted.failure:
            return result_type.from_failure(persisted)
        active_journal, active_state = recorded.value, persisted.value
        for project in plan.value.projects:
            staged_config = next(
                item.replacement
                for item in mise_files
                if item.before.path == project.config.before.path
            )
            if staged_config is None:
                return result_type.fail("Mise staging receipt has no configuration")
            validated = self._owner.validate_artifacts(staged_config.path.parent)
            if validated.failure:
                return result_type.from_failure(
                    self._recover_failure(
                        layout, validated.error or "Mise staged validation failed"
                    )
                )
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
        ordinary_staged = stage_file_plans(layout, "conform", ordinary)
        if ordinary_staged.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, ordinary_staged.error or "cannot stage conform files"
                )
            )
        bound = state.bind_created_parents(
            active_journal.directories, (*ordinary_staged.value, *mise_publications)
        )
        if bound.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, bound.error or "cannot bind generation destination parents"
                )
            )
        publications = bound.value
        barriers = self._verified_prepublication_barriers(
            layout, plan.value, all_sources, publications
        )
        if barriers.failure:
            return result_type.from_failure(barriers)
        prepared_journal = journal_io.append_prepared(
            plan.value, active_journal, publications, sources=all_sources
        )
        if prepared_journal.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    prepared_journal.error or "cannot prepare generation journal",
                )
            )
        manifested = journal_io.record_transaction_manifests(
            layout, prepared_journal.value
        )
        if manifested.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    manifested.error or "cannot register generation staging tree",
                )
            )
        prepared_state = self._write_journal(
            layout, manifested.value, expected=active_state
        )
        if prepared_state.failure:
            return result_type.from_failure(
                self._handle_journal_write_failure(
                    layout,
                    prepared_state.error
                    or "cannot publish prepared generation journal",
                )
            )
        barriers = self._verified_prepublication_barriers(
            layout, plan.value, all_sources, publications
        )
        if barriers.failure:
            return result_type.from_failure(barriers)
        published = publish(publications)
        if published.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, published.error or "generation publication failed"
                )
            )
        publication_state = verify.publications_live(publications)
        if publication_state.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    publication_state.error
                    or "generation publication identity changed",
                )
            )
        live = verify.live(self._owner, plan.value, mise_publications)
        if live.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, live.error or "Mise real-consumer validation failed"
                )
            )
        return result_type.ok(
            m.Infra.CodegenTransactionSession(
                plan=plan.value,
                journal=manifested.value,
                journal_state=prepared_state.value,
                written_files=published.value,
            )
        )

    def append_phase_locked(
        self,
        session: m.Infra.CodegenTransactionSession,
        phase: str,
        plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Append, durably authorize, then publish one dependent generated phase."""
        result_type = r[m.Infra.CodegenTransactionSession]
        changed = tuple(
            plan for plan in plans if u.Infra.codegen_file_requires_effect(plan)
        )
        if not changed:
            return result_type.ok(session)
        aligned = FlextInfraCodegenPreconditions.unchanged_journal(
            session, "generation journal changed between phases"
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
                    )
                )
        sources = FlextInfraCodegenPreconditions.phase_sources(phase, plans)
        if sources.failure:
            return result_type.from_failure(
                self._recover_failure(layout, sources.error or "invalid phase sources")
            )
        source_states = tuple(source for _phase, source in sources.value)
        source_barrier = verify.states_current(
            FlextInfraCodegenPreconditions.unique_states(source_states),
            journal=session.journal,
        )
        if source_barrier.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, source_barrier.error or f"{phase} sources changed"
                )
            )
        staged = stage_file_plans(layout, phase, changed)
        if staged.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, staged.error or f"cannot stage {phase} phase"
                )
            )
        staged = state.bind_created_parents(session.journal.directories, staged.value)
        if staged.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, staged.error or f"cannot bind {phase} destination parents"
                )
            )
        destination_barrier = verify.states_current(
            tuple(item.before for item in staged.value)
        )
        if destination_barrier.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, destination_barrier.error or f"{phase} destinations changed"
                )
            )
        extended = journal_io.append_prepared(
            session.plan, session.journal, staged.value, sources=sources.value
        )
        if extended.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, extended.error or f"cannot append {phase} journal phase"
                )
            )
        manifested = journal_io.record_transaction_manifests(layout, extended.value)
        if manifested.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, manifested.error or f"cannot register {phase} staging tree"
                )
            )
        persisted = self._write_journal(
            layout, manifested.value, expected=session.journal_state
        )
        if persisted.failure:
            return result_type.from_failure(
                self._handle_journal_write_failure(
                    layout, persisted.error or f"cannot persist {phase} journal phase"
                )
            )
        source_barrier = verify.states_current(
            FlextInfraCodegenPreconditions.unique_states(source_states),
            journal=manifested.value,
        )
        destination_barrier = verify.states_current(
            tuple(item.before for item in staged.value)
        )
        if source_barrier.failure or destination_barrier.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout,
                    source_barrier.error
                    or destination_barrier.error
                    or f"{phase} prepublication barrier failed",
                )
            )
        published = publish(staged.value)
        if published.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, published.error or f"cannot publish {phase} phase"
                )
            )
        live = verify.publications_live(staged.value)
        if live.failure:
            return result_type.from_failure(
                self._recover_failure(
                    layout, live.error or f"{phase} publication changed"
                )
            )
        return result_type.ok(
            m.Infra.CodegenTransactionSession(
                plan=session.plan,
                journal=manifested.value,
                journal_state=persisted.value,
                written_files=(*session.written_files, *published.value),
            )
        )

    def append_directories_locked(
        self,
        session: m.Infra.CodegenTransactionSession,
        phase: str,
        directories: t.VariadicTuple[Path],
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Authorize missing generated directories durably, then create them."""
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
                )
            )
        if not planned.value:
            return result_type.ok(session)
        unchanged = FlextInfraCodegenPreconditions.unchanged_journal(
            session, "generation journal changed before directories"
        )
        if unchanged.failure:
            return result_type.from_failure(unchanged)
        session = unchanged.value
        extended = journal_io.append_directories(session.journal, planned.value)
        if extended.failure:
            return result_type.from_failure(
                self._recover_failure(
                    session.plan.layout,
                    extended.error or f"cannot append {phase} directories",
                )
            )
        persisted = self._write_journal(
            session.plan.layout, extended.value, expected=session.journal_state
        )
        if persisted.failure:
            return result_type.from_failure(
                self._handle_journal_write_failure(
                    session.plan.layout,
                    persisted.error or f"cannot persist {phase} directories",
                )
            )
        materialized = self._materialize_directories(
            session.plan.layout, extended.value, persisted.value
        )
        if materialized.failure:
            return result_type.from_failure(materialized)
        recorded, recorded_state = materialized.value
        return result_type.ok(
            m.Infra.CodegenTransactionSession(
                plan=session.plan,
                journal=recorded,
                journal_state=recorded_state,
                written_files=session.written_files,
            )
        )

    def commit_locked(
        self,
        session: m.Infra.CodegenTransactionSession,
        validator: Callable[[], p.Result[bool]],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Validate final reality while recoverable, then commit and clean up."""
        exact = verify.journal_destinations_live(session.plan.layout, session.journal)
        if exact.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    session.plan.layout, exact.error or "publication identity changed"
                )
            )
        validated = validator()
        if validated.failure or not validated.value:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    session.plan.layout,
                    validated.error or "generation fixed-point validation failed",
                )
            )
        unchanged = FlextInfraCodegenPreconditions.unchanged_journal(
            session, "generation journal changed before commit"
        )
        if unchanged.failure:
            return r[t.VariadicTuple[Path]].from_failure(unchanged)
        session = unchanged.value
        exact = verify.journal_destinations_live(session.plan.layout, session.journal)
        if exact.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    session.plan.layout,
                    exact.error or "publication identity changed before commit",
                )
            )
        committed = journal_io.commit(session.journal)
        if committed.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    session.plan.layout,
                    committed.error or "cannot validate generation commit",
                )
            )
        committed_state = self._write_journal(
            session.plan.layout, committed.value, expected=session.journal_state
        )
        if committed_state.failure:
            return r[t.VariadicTuple[Path]].from_failure(
                self._recover_failure(
                    session.plan.layout,
                    committed_state.error or "cannot persist generation commit",
                )
            )
        cleaned = journal_io.cleanup(
            session.plan.layout, committed.value, committed_state.value
        )
        if cleaned.failure:
            return r[t.VariadicTuple[Path]].from_failure(cleaned)
        self._journal_receipts.pop(session.plan.layout.journal_path, None)
        return r[t.VariadicTuple[Path]].ok(session.written_files)

    def _materialize_directories(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        journal_state: m.Cli.AtomicFileState,
    ) -> p.Result[t.Pair[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]:
        """Create and durably bind one directory identity at a time."""
        result_type = r[tuple[m.Infra.CodegenTransactionJournal, m.Cli.AtomicFileState]]
        current_journal = journal
        current_state = journal_state
        for intent in current_journal.directories:
            if intent.created is not None:
                continue
            created = state.create_journaled_directory(
                layout, current_journal.directories, intent
            )
            if created.failure:
                return result_type.from_failure(
                    self._recover_failure(
                        layout,
                        created.error or f"cannot create directory {intent.path}",
                    )
                )
            directories = tuple(
                created.value if entry.path == intent.path else entry
                for entry in current_journal.directories
            )
            recorded = journal_io.record_directories(current_journal, directories)
            if recorded.failure:
                failed = self._compensate_directory_persistence(
                    layout,
                    created.value,
                    recorded.error or f"cannot record directory {intent.path}",
                    journal_write=False,
                )
                return result_type.from_failure(failed)
            persisted = self._write_journal(
                layout, recorded.value, expected=current_state
            )
            if persisted.failure:
                failed = self._compensate_directory_persistence(
                    layout,
                    created.value,
                    persisted.error or f"cannot persist directory {intent.path}",
                    journal_write=True,
                )
                return result_type.from_failure(failed)
            current_journal = recorded.value
            current_state = persisted.value
        manifested = journal_io.record_transaction_manifests(layout, current_journal)
        if manifested.failure:
            return result_type.from_failure(manifested)
        for previous, recorded in zip(
            current_journal.directories, manifested.value.directories, strict=True
        ):
            if (
                previous.manifest is None
                and recorded.manifest is not None
                and recorded.manifest.entries
            ):
                return result_type.fail(
                    f"new transaction tree contains unregistered entries: {recorded.path}"
                )
        persisted = self._write_journal(
            layout, manifested.value, expected=current_state
        )
        if persisted.failure:
            return result_type.from_failure(persisted)
        return result_type.ok((manifested.value, persisted.value))

    def _compensate_directory_persistence(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        created: m.Infra.CodegenJournalDirectory,
        failure: str,
        *,
        journal_write: bool,
    ) -> p.Result[bool]:
        """Compensate only this invocation's exact empty-directory effect."""
        compensated = state.compensate_created_directory(created)
        if compensated.failure:
            return r[bool].fail(
                f"{failure}; created-directory compensation failed: {compensated.error}"
            )
        if journal_write:
            return self._handle_journal_write_failure(layout, failure)
        return self._recover_failure(layout, failure)

    def abort_locked(
        self, session: m.Infra.CodegenTransactionSession, failure: str
    ) -> p.Result[bool]:
        """Recover the complete prepared transaction and preserve the cause."""
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

    def _recover_prepared(
        self, layout: m.Infra.MiseToolchainWorkspaceLayout
    ) -> p.Result[bool]:
        """Recover only the latest journal receipt written by this transaction."""
        expected = self._journal_receipts.get(layout.journal_path)
        if expected is None:
            observed = state.journal_state(layout)
            if observed.failure:
                return r[bool].from_failure(observed)
            snapshot = state.journal_snapshot(observed.value)
            if snapshot is not None and snapshot.content is None:
                return r[bool].ok(False)
            return r[bool].fail("generation recovery has no invocation journal receipt")
        return self._recover(layout, expected=expected)

    def _reconcile(self, identity: m.Infra.GitIdentityReport) -> p.Result[bool]:
        layout = self._planner.journal_layout(identity)
        if layout.failure:
            return r[bool].from_failure(layout)
        journal = state.journal_state(layout.value)
        if journal.failure:
            return r[bool].from_failure(journal)
        journal_snapshot = state.journal_snapshot(journal.value)
        if journal_snapshot is not None and journal_snapshot.content is not None:
            return self._recover(layout.value)
        residue = state.transaction_residue(layout.value)
        if residue:
            return r[bool].fail(
                f"generation residue has no journal authority: {residue[0]}"
            )
        return r[bool].ok(True)

    def _handle_journal_write_failure(
        self, layout: m.Infra.MiseToolchainWorkspaceLayout, failure: str
    ) -> p.Result[bool]:
        observed = state.journal_state(layout)
        if observed.failure:
            return r[bool].fail(
                f"{failure}; journal inspection failed: {observed.error}"
            )
        observed_snapshot = state.journal_snapshot(observed.value)
        if observed_snapshot is None or observed_snapshot.content is None:
            return r[bool].fail(f"{failure}; durable journal disappeared")
        return self._recover_failure(layout, failure)

    def _verified_prepublication_barriers(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        plan: m.Infra.MiseToolchainWorkspacePlan,
        all_sources: t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]],
        publications: t.VariadicTuple[m.Infra.CodegenStagedFile],
    ) -> p.Result[bool]:
        """Re-verify every pre-publication barrier, recovering on the first breach."""
        barriers = FlextInfraCodegenPreconditions.prepublication_barriers(
            plan,
            tuple(source for _phase, source in all_sources),
            tuple(item.before for item in publications),
        )
        if barriers.failure:
            return r[bool].from_failure(
                self._recover_failure(
                    layout, barriers.error or "generation barrier failed"
                )
            )
        return r[bool].ok(True)

    def _recover_failure(
        self, layout: m.Infra.MiseToolchainWorkspaceLayout, failure: str
    ) -> p.Result[bool]:
        recovered = self._recover_prepared(layout)
        if recovered.failure:
            # Recovery must never replace the failure that initiated it.
            return r[bool].fail(failure, error_data={"recovery_error": recovered.error})
        return r[bool].fail(failure)

    def _write_journal(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        journal: m.Infra.CodegenTransactionJournal,
        *,
        expected: m.Cli.AtomicFileState,
    ) -> p.Result[m.Cli.AtomicFileState]:
        """Retain the exact owned receipt for in-session failure recovery."""
        written = journal_io.write(layout, journal, expected=expected)
        if written.success:
            self._journal_receipts[layout.journal_path] = written.value
        return written

    def _recover(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        *,
        expected: m.Cli.AtomicFileState | None = None,
    ) -> p.Result[bool]:
        loaded = journal_io.read(layout)
        if loaded.failure:
            return r[bool].from_failure(loaded)
        journal, journal_state = loaded.value
        if expected is not None and journal_state != expected:
            return r[bool].fail(
                "generation recovery journal changed from owned receipt"
            )
        if journal.file_participants:
            if journal.projects:
                return r[bool].fail(
                    "mixed Mise and file-only recovery requires explicit composition"
                )
            recovery_layout = self._planner.file_layout(
                layout.scope_root,
                {item.selector: item.root for item in journal.file_participants},
                transaction_id=journal.transaction_id,
            )
            if recovery_layout.failure:
                return r[bool].from_failure(recovery_layout)
            if recovery_layout.value.journal_path != layout.journal_path:
                return r[bool].fail("file journal identity changed during recovery")
            with self._lease_file_participants(journal.file_participants):
                recovered = self._recovery.execute(
                    recovery_layout.value, journal, journal_state
                )
            if recovered.success:
                self._journal_receipts.pop(layout.journal_path, None)
            return recovered
        selectors = tuple(project.selector for project in journal.projects)
        recovery_layout = self._planner.layout_from_selectors(
            layout.scope_root, selectors, transaction_id=journal.transaction_id
        )
        if recovery_layout.failure:
            return r[bool].from_failure(recovery_layout)
        if recovery_layout.value.journal_path != layout.journal_path:
            return r[bool].fail("generation journal identity changed during recovery")
        recovered = self._recovery.execute(
            recovery_layout.value, journal, journal_state
        )
        if recovered.success:
            self._journal_receipts.pop(layout.journal_path, None)
        return recovered


__all__: list[str] = ["FlextInfraCodegenTransaction"]
