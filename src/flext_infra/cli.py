"""CLI entrypoint for the canonical flext-infra command surface."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, override

from flext_infra import c, t

from .services.cli_dispatch import CliDispatchService

if TYPE_CHECKING:
    from flext_infra import m


class FlextInfraCli(CliDispatchService):
    """Single CLI entry surface for every flext-infra command group."""

    @classmethod
    @override
    def route_table_for(cls, group: str) -> t.VariadicTuple[m.Cli.ResultCommandRoute]:
        """Compose the check facade at the transport root."""
        if group != c.Infra.CLI_GROUP_CHECK:
            return super().route_table_for(group)
        from flext_infra import m

        from .api import infra
        from .deps.fix_pyrefly_config import FlextInfraConfigFixer
        from .fixers.orchestrator import FlextInfraEnforcementFixerOrchestrator
        from .services.cli_route_base import CliRouteBase

        return (
            m.Cli.ResultCommandRoute(
                name=c.Infra.VERB_RUN,
                help_text="Run workspace quality gates",
                model_cls=m.Infra.RunCommand,
                handler=CliRouteBase.result_handler(infra.check),
            ),
            m.Cli.ResultCommandRoute(
                name="fix-pyrefly-settings",
                help_text="Repair [tool.pyrefly] blocks",
                model_cls=m.Infra.FixPyreflyConfigCommand,
                handler=CliRouteBase.result_handler(
                    FlextInfraConfigFixer.execute_payload
                ),
            ),
            m.Cli.ResultCommandRoute(
                name="fix-enforcement",
                help_text="Auto-fix enforcement-catalog violations",
                model_cls=m.Infra.FixEnforcementCommand,
                handler=CliRouteBase.result_handler(
                    FlextInfraEnforcementFixerOrchestrator.execute_payload
                ),
            ),
        )


def main(args: t.StrSequence | None = None) -> int:
    """Run the canonical flext-infra CLI."""
    cli_args = list(args) if args is not None else sys.argv[1:]
    return FlextInfraCli().main(cli_args)


def docs_main(args: t.StrSequence | None = None) -> int:
    """Run the docs group directly (``flext-docs`` == ``flext-infra docs``)."""
    cli_args = list(args) if args is not None else sys.argv[1:]
    return FlextInfraCli().main([c.Infra.CLI_GROUP_DOCS, *cli_args])


__all__: list[str] = ["FlextInfraCli", "docs_main", "main"]
