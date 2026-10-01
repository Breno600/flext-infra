"""Immutable source and journal preconditions for generation transactions."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m

from ._mise_artifacts_state import FlextInfraMiseArtifactsState
from ._mise_artifacts_verification import FlextInfraMiseArtifactsVerification

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraCodegenPreconditions:
    """Validate source consistency and receipt ownership before publishing."""

    @staticmethod
    def phase_sources(
        phase: str, plans: t.VariadicTuple[m.Infra.CodegenFilePlan]
    ) -> p.Result[t.VariadicTuple[t.Pair[str, m.Cli.AtomicFileState]]]:
        """Reject conflicting observations and tag each source with its phase."""
        result_type = r[tuple[tuple[str, m.Cli.AtomicFileState], ...]]
        sources: MutableMapping[Path, m.Cli.AtomicFileState] = {}
        for plan in plans:
            for source in plan.source_states:
                previous = sources.get(source.path)
                if previous is not None and previous != source:
                    return result_type.fail(
                        f"{phase} planner observed two states for {source.path}"
                    )
                sources[source.path] = source
        return result_type.ok(tuple((phase, source) for source in sources.values()))

    @staticmethod
    def unique_states(
        states: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> t.VariadicTuple[m.Cli.AtomicFileState]:
        """Coalesce repeated states by their publication path."""
        by_path: MutableMapping[Path, m.Cli.AtomicFileState] = {}
        for file_state in states:
            by_path[file_state.path] = file_state
        return tuple(by_path.values())

    @staticmethod
    def prepublication_barriers(
        plan: m.Infra.MiseToolchainWorkspacePlan,
        sources: t.VariadicTuple[m.Cli.AtomicFileState],
        destinations: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> p.Result[bool]:
        """Require unchanged source and destination identities before writing."""
        source_barrier = FlextInfraMiseArtifactsVerification.states_current(
            FlextInfraCodegenPreconditions.unique_states(sources)
        )
        if source_barrier.failure:
            return source_barrier
        destination_barrier = FlextInfraMiseArtifactsVerification.states_current(
            destinations
        )
        if destination_barrier.failure:
            return destination_barrier
        return FlextInfraMiseArtifactsVerification.sources(plan)

    @staticmethod
    def unchanged_journal(
        session: m.Infra.CodegenTransactionSession, changed_error: str
    ) -> p.Result[m.Infra.CodegenTransactionSession]:
        """Require the complete journal receipt; a lease cannot authorize replacement."""
        result_type = r[m.Infra.CodegenTransactionSession]
        observed = FlextInfraMiseArtifactsState.journal_state(session.plan.layout)
        observed_snapshot = (
            None
            if observed.failure
            else FlextInfraMiseArtifactsState.journal_snapshot(observed.value)
        )
        expected = session.journal_state
        if observed.failure or observed_snapshot != expected:
            return result_type.fail(
                observed.error or changed_error,
                error_data={
                    "recovery_error": "journal authority no longer matches the session receipt"
                },
            )
        return result_type.ok(session)
