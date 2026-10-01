"""Refactor CLI route ownership."""

from __future__ import annotations

import functools
from typing import ClassVar

from flext_infra import infra, m, p, t
from flext_infra.codegen.protocol_models import FlextInfraCodegenProtocolModels
from flext_infra.codemod.ast_scan import FlextInfraCodemodAstScan
from flext_infra.codemod.snapshot_refresh import FlextInfraCodemodSnapshotRefresh
from flext_infra.refactor.accessor_migration import (
    FlextInfraAccessorMigrationOrchestrator,
)
from flext_infra.refactor.census import FlextInfraRefactorCensus
from flext_infra.refactor.modernize_orchestrator import FlextInfraModernizeOrchestrator
from flext_infra.refactor.namespace_enforcer import FlextInfraNamespaceEnforcer
from flext_infra.refactor.signature_propagation import (
    FlextInfraRefactorSignaturePropagation,
)
from flext_infra.refactor.wrapper_root_namespace import (
    FlextInfraWrapperRootNamespaceRefactor,
)
from flext_infra.services.cli_route_base import FlextInfraCliRouteBase
from flext_infra.transformers.dataclass_modelizer import (
    FlextInfraRefactorDataclassModelizer,
)
from flext_infra.transformers.pydantic_modernizer import (
    FlextInfraRefactorPydanticModernizer,
)


class FlextInfraCliModProgress:
    """Render mod progress at the CLI transport boundary."""

    def emit(self, message: str) -> None:
        """Show the current canonical mod phase."""
        cli.display_text(message)

    def emit_rename(self, report: m.Infra.ApplyRenamesReport) -> None:
        """Show one completed CSV campaign."""
        cli.display_text(FlextInfraCliModProgress.render_rename(report))

    @staticmethod
    def render_rename(report: m.Infra.ApplyRenamesReport) -> str:
        """Render native published paths and pending edit spans."""
        return (
            f"{report.label}: {report.files_changed} published file(s), "
            f"{report.occurrences} pending source edit(s), "
            f"{report.files_scanned} scanned file(s)"
        )


class FlextInfraRefactorRoutes(FlextInfraCliRouteBase):
    """Own the complete refactor command tuple."""

    @staticmethod
    def execute_mod_text(
        request: m.Infra.ModTextCommand,
    ) -> p.Result[t.Cli.ResultValue]:
        """Replay the declared text rules without entering Rope or AST phases."""
        return infra.mod_text(request)

    @staticmethod
    def execute_mod_text_candidate(
        request: m.Infra.ModTextCommand,
    ) -> p.Result[t.Cli.ResultValue]:
        """Replay a manifest-declared candidate with the healthy provider."""
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
                FlextInfraNamespaceEnforcer.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="census",
            help_text="Run a Rope-only workspace census for Python objects",
            model_cls=FlextInfraRefactorCensus,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraRefactorCensus.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="accessor-migrate",
            help_text="Preview or apply automated get_/set_/is_ migration",
            model_cls=m.Infra.AccessorMigrationInput,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraAccessorMigrationOrchestrator.execute_payload
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
            name="propagate-signatures",
            help_text=(
                "Rewrite call sites from the declared signature migrations in "
                "config/rules/refactor/signature-propagation.yml"
            ),
            model_cls=m.Infra.ModernizeInput,
            handler=FlextInfraRefactorSignaturePropagation.execute_command,
        ),
        m.Cli.ResultCommandRoute(
            name="modernize-pydantic",
            help_text="Migrate Pydantic v1/legacy patterns to Pydantic v2",
            model_cls=m.Infra.ModernizeInput,
            handler=functools.partial(
                FlextInfraModernizeOrchestrator.execute_command,
                transformer_factory=FlextInfraRefactorPydanticModernizer,
                description="pydantic modernizer",
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="modernize-dataclass",
            help_text=(
                "Convert serializable frozen dataclasses to canonical "
                "m.FrozenModel contracts; catalog unsafe skips with reasons"
            ),
            model_cls=m.Infra.ModernizeInput,
            handler=functools.partial(
                FlextInfraModernizeOrchestrator.execute_command,
                transformer_factory=FlextInfraRefactorDataclassModelizer,
                description="dataclass modelizer",
            ),
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
                "Apply ast-grep rules, prove fixed point, then require Ruff, "
                "Pyrefly, and real LSP diagnostics"
            ),
            model_cls=m.Infra.ModCommand,
            handler=execute_mod,
        ),
        m.Cli.ResultCommandRoute(
            name="mod-text",
            help_text="Replay only authenticated declarative text rules",
            model_cls=m.Infra.ModCommand,
            handler=execute_mod_text,
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
