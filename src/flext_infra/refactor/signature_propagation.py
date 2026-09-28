"""Call-site propagation driven by the declared signature-migration catalogue."""

from __future__ import annotations

from flext_cli import p, r

from flext_infra import m, t, u
from flext_infra.refactor.modernize_orchestrator import FlextInfraModernizeOrchestrator
from flext_infra.transformers.signature_propagator import (
    FlextInfraRefactorSignaturePropagator,
)


class FlextInfraRefactorSignaturePropagation:
    """Drive the signature propagator from the repository's declared catalogue.

    The transformer and the declarative rule kind existed already but nothing
    read a catalogue or dispatched to them, so a parameter rename stayed a hand
    sweep across every consumer. This is the verb that makes the capability
    reachable: one declaration, every call site rewritten, the same orchestrator
    the other modernizers use.
    """

    @classmethod
    def execute_command(
        cls, payload: m.Infra.ModernizeInput
    ) -> p.Result[t.Cli.ResultValue]:
        """Apply every declared migration across the governed project set."""
        declared = u.Infra.load(payload.repository_root)
        if declared.failure:
            return r[t.Cli.ResultValue].from_failure(declared)
        migrations = declared.value
        if not migrations:
            # An empty catalogue is the normal steady state: migrations are
            # declared for one cutover and removed once applied. Reporting is
            # the honest answer; inventing a rewrite would not be.
            return r[t.Cli.ResultValue].ok(
                "signature propagation: no migration declared"
            )
        return FlextInfraModernizeOrchestrator.execute_command(
            payload,
            transformer_factory=lambda: FlextInfraRefactorSignaturePropagator(
                migrations=migrations
            ),
            description=f"signature propagation ({len(migrations)} migration(s))",
        )


__all__: list[str] = ["FlextInfraRefactorSignaturePropagation"]
