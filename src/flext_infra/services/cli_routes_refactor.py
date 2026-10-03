"""Refactor CLI route ownership.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import ClassVar

from flext_cli import cli

from flext_core import r
from flext_infra import infra, m, p, t
from flext_infra.codegen.protocol_models import FlextInfraCodegenProtocolModels
from flext_infra.codemod.ast_scan import FlextInfraCodemodAstScan
from flext_infra.codemod.snapshot_refresh import FlextInfraCodemodSnapshotRefresh
from flext_infra.refactor.accessor_migration import (
    FlextInfraAccessorMigrationOrchestrator,
)
from flext_infra.refactor.census import FlextInfraRefactorCensus
from flext_infra.refactor.namespace_enforcer import FlextInfraNamespaceEnforcer
from flext_infra.refactor.wrapper_root_namespace import (
    FlextInfraWrapperRootNamespaceRefactor,
)
from flext_infra.services.cli_route_base import FlextInfraCliRouteBase


class FlextInfraCliModProgress:
    """Render mod progress at the CLI transport boundary."""

    @staticmethod
    def emit(message: str) -> None:
        """Show the current canonical mod phase."""
        cli.display_text(message)

    @staticmethod
    def emit_rename(report: m.Infra.ApplyRenamesReport) -> None:
        """Show one completed CSV campaign."""
        cli.display_text(FlextInfraCliModProgress.render_rename(report))

    @staticmethod
    def render_rename(report: m.Infra.ApplyRenamesReport) -> str:
        """Render native published paths and pending edit spans.

        Returns:
            The resulting ``str``.

        """
        return (
            f"{report.label}: {report.files_changed} published file(s), "
            f"{report.occurrences} pending source edit(s), "
            f"{report.files_scanned} scanned file(s)"
        )


class FlextInfraRefactorRoutes(FlextInfraCliRouteBase):
    """Own the complete refactor command tuple."""

    @staticmethod
    def execute_apply_renames(
        request: m.Infra.ApplyRenamesInput,
    ) -> p.Result[t.Cli.ResultValue]:
        """Display the real rename result and preserve pending-work failure.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        result = infra.apply_renames(request)
        if result.failure:
            return r[t.Cli.ResultValue].from_failure(result)
        report = result.value
        cli.display_text(FlextInfraCliModProgress.render_rename(report))
        if report.occurrences:
            return r[t.Cli.ResultValue].fail(
                f"{report.occurrences} pending source edits",
            )
        return r[t.Cli.ResultValue].ok(True)

    @staticmethod
    def execute_mod(request: m.Infra.ModCommand) -> p.Result[t.Cli.ResultValue]:
        """Compose the mod use case and pass through its first failure.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        return infra.mod(request, FlextInfraCliModProgress())

    @staticmethod
    def execute_mod_text(
        request: m.Infra.ModTextCommand,
    ) -> p.Result[t.Cli.ResultValue]:
        """Replay the declared text rules without entering Rope or AST phases.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        return infra.mod_text(request)

    @staticmethod
    def execute_mod_text_candidate(
        request: m.Infra.ModTextCommand,
    ) -> p.Result[t.Cli.ResultValue]:
        """Replay a manifest-declared candidate with the healthy provider.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        return infra.mod_text_candidate(request)

    refactor_routes: ClassVar[t.VariadicTuple[m.Cli.ResultCommandRoute]] = (
        m.Cli.ResultCommandRoute(
            name="apply-renames",
            help_text="Check or apply an old,new CSV rename list",
            model_cls=m.Infra.ApplyRenamesInput,
            handler=execute_apply_renames,
        ),
        m.Cli.ResultCommandRoute(
            name="namespace-enforce",
            help_text="Scan workspace for namespace governance violations",
            model_cls=m.Infra.RefactorNamespaceEnforceInput,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraNamespaceEnforcer.execute_command,
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="census",
            help_text="Run a Rope-only workspace census for Python objects",
            model_cls=FlextInfraRefactorCensus,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraRefactorCensus.execute_command,
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="accessor-migrate",
            help_text="Preview or apply automated get_/set_/is_ migration",
            model_cls=m.Infra.AccessorMigrationInput,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraAccessorMigrationOrchestrator.execute_payload,
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="wrapper-root-namespace",
            help_text=(
                "Normalize wrapper alias imports to wrapper root and "
                "flatten *.Core.Tests paths"
            ),
            model_cls=FlextInfraWrapperRootNamespaceRefactor,
            handler=FlextInfraWrapperRootNamespaceRefactor.execute,
        ),
        m.Cli.ResultCommandRoute(
            name="protocol-models",
            help_text=(
                "Assemble the member's generated structural protocols from "
                "its validated models; dry-run reports drift"
            ),
            model_cls=FlextInfraCodegenProtocolModels,
            handler=FlextInfraCodegenProtocolModels.execute_command,
        ),
        m.Cli.ResultCommandRoute(
            name="mod",
            help_text=(
                "Apply ast-grep, semantic and text rules to a proven fixed point; "
                "make check owns the lint and type verdicts"
            ),
            model_cls=m.Infra.ModCommand,
            handler=execute_mod,
        ),
        m.Cli.ResultCommandRoute(
            name="mod-text",
            help_text="Replay only authenticated declarative text rules",
            model_cls=m.Infra.ModTextCommand,
            handler=execute_mod_text,
        ),
        m.Cli.ResultCommandRoute(
            name="mod-text-candidate",
            help_text="Replay text rules in the declared candidate worktree",
            model_cls=m.Infra.ModTextCommand,
            handler=execute_mod_text_candidate,
        ),
        m.Cli.ResultCommandRoute(
            name="mod-snapshots",
            help_text=(
                "Regenerate the owned ast-grep rule-test snapshots from their "
                "tests; dry-run fails while any snapshot differs"
            ),
            model_cls=FlextInfraCodemodSnapshotRefresh,
            handler=FlextInfraCodemodSnapshotRefresh.execute_command,
        ),
        m.Cli.ResultCommandRoute(
            name="ast",
            help_text=(
                "Run the ast engine standalone: ast-grep cascade plus "
                "sed-by-list cascade (scan report; --apply reaches the "
                "mechanical fixed point)"
            ),
            model_cls=FlextInfraCodemodAstScan,
            handler=FlextInfraCodemodAstScan.execute_command,
        ),
    )


__all__: list[str] = ["FlextInfraRefactorRoutes"]
