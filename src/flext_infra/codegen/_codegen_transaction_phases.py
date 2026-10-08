"""Dependent-phase append, directory authorization, and commit mixin.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m, t, u
from flext_infra.codegen._codegen_transaction_recovery import (
    FlextInfraCodegenTransactionRecovery,
)
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)
from flext_infra.codegen._mise_artifacts_journal import (
    FlextInfraMiseArtifactsJournal as journal_io,
)
from flext_infra.codegen._mise_artifacts_state import (
    FlextInfraMiseArtifactsState as state,
)
from flext_infra.codegen._mise_artifacts_verification import (
    FlextInfraMiseArtifactsVerification as verify,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenTransactionPhases(FlextInfraCodegenTransactionRecovery):
    """Append dependent phases and directories, then commit the journal."""

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
        from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions
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
        from flext_infra.codegen._codegen_staging import FlextInfraCodegenStaging
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
        from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions
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
        from flext_infra.codegen._mise_artifacts_publication import FlextInfraMisePublication
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
        from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions
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
        from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions
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


__all__: list[str] = ["FlextInfraCodegenTransactionPhases"]
