"""Generation-phase staging, journal preparation, and publication mixin.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t, u
from flext_infra.codegen._codegen_staging import FlextInfraCodegenStaging
from flext_infra.codegen._codegen_transaction_recovery import (
    FlextInfraCodegenTransactionRecovery,
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


class FlextInfraCodegenTransactionGeneration(FlextInfraCodegenTransactionRecovery):
    """Stage, prepare, and publish the first conform+Mise generation phase."""

    def __init__(
        self,
        owner: p.Infra.MiseArtifactsOwner,
        *,
        participant_policy: m.Infra.CodegenParticipantPolicy | None = None,
    ) -> None:
        """Initialize the transaction with its configured Mise artifact owner."""
        super().__init__(owner, participant_policy=participant_policy)
        self._owner = owner
        self._mise_staging = FlextInfraMiseStaging()

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
            c.Infra.CodegenStagedFilePhase.CONFORM_BOOTSTRAP,
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
        recorded = journal_io.record_transaction_manifests(
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
            c.Infra.CodegenStagedFilePhase.CONFORM_BOOTSTRAP,
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


__all__: list[str] = ["FlextInfraCodegenTransactionGeneration"]
