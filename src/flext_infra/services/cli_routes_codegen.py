"""Codegen, check, and dependency CLI route ownership."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, ClassVar

from flext_infra import c, m
from flext_infra.codegen.census import FlextInfraCodegenCensus
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.codegen.consolidator import FlextInfraCodegenConsolidator
from flext_infra.codegen.constants_quality_gate import FlextInfraCodegenQualityGate
from flext_infra.codegen.fixer import FlextInfraCodegenFixer
from flext_infra.codegen.layout import FlextInfraCodegenLayout
from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit
from flext_infra.codegen.make_bootstrap import FlextInfraCodegenMakeBootstrap
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts
from flext_infra.codegen.pipeline import FlextInfraCodegenPipeline
from flext_infra.codegen.project_new import FlextInfraCodegenProjectNew
from flext_infra.codegen.py_typed import FlextInfraCodegenPyTyped
from flext_infra.codegen.scaffolder import FlextInfraCodegenScaffolder
from flext_infra.codegen.version_file import FlextInfraCodegenVersionFile
from flext_infra.deps.detector import FlextInfraRuntimeDevDependencyDetector
from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
from flext_infra.deps.modernizer import FlextInfraPyprojectModernizer

from .cli_route_base import CliRouteBase

if TYPE_CHECKING:
    from flext_infra import t


class CodegenRoutes(CliRouteBase):
    """Own check, codegen, and dependency command routes."""

    codegen_routes: ClassVar[
        MutableMapping[str, t.VariadicTuple[m.Cli.ResultCommandRoute]]
    ] = {
        c.Infra.CLI_GROUP_CODEGEN: (
            m.Cli.ResultCommandRoute(
                name="conform",
                help_text="Conform generated project and workspace files",
                model_cls=m.Infra.CodegenConformRequest,
                handler=FlextInfraCodegenConform.execute_request,
                success_message="project conformance complete",
            ),
            *(
                m.Cli.ResultCommandRoute(
                    name=route_name,
                    help_text=help_text,
                    model_cls=model_cls,
                    handler=handler,
                    success_message=success_message,
                )
                for route_name, help_text, model_cls, handler, success_message in (
                    (
                        "new",
                        "Create a new FLEXT project from the canonical templates",
                        FlextInfraCodegenProjectNew,
                        CliRouteBase.result_handler(
                            FlextInfraCodegenProjectNew.execute
                        ),
                        "project created",
                    ),
                    (
                        "init",
                        "Bootstrap only the canonical generated Makefile",
                        FlextInfraCodegenMakeBootstrap,
                        CliRouteBase.result_handler(
                            FlextInfraCodegenMakeBootstrap.execute
                        ),
                        "Makefile bootstrap complete",
                    ),
                    (
                        "lazy-init",
                        (
                            "Regenerate PEP 562 lazy-import __init__.py files as "
                            "part of the continuous gen check/apply cycle (unlike "
                            "`init`, which only bootstraps a fresh, unprovisioned "
                            "repository)"
                        ),
                        FlextInfraCodegenLazyInit,
                        CliRouteBase.result_handler(FlextInfraCodegenLazyInit.execute),
                        "lazy-init complete",
                    ),
                    (
                        "census",
                        "Count namespace violations across workspace projects",
                        FlextInfraCodegenCensus,
                        CliRouteBase.result_handler(FlextInfraCodegenCensus.execute),
                        None,
                    ),
                    (
                        "scaffold",
                        "Generate missing base modules in src/ and tests/",
                        FlextInfraCodegenScaffolder,
                        CliRouteBase.result_handler(
                            FlextInfraCodegenScaffolder.execute
                        ),
                        None,
                    ),
                    (
                        "auto-fix",
                        "Auto-fix namespace violations (move Finals/TypeVars)",
                        FlextInfraCodegenFixer,
                        CliRouteBase.result_handler(FlextInfraCodegenFixer.execute),
                        None,
                    ),
                    (
                        "py-typed",
                        "Create/remove PEP 561 py.typed markers",
                        FlextInfraCodegenPyTyped,
                        CliRouteBase.result_handler(FlextInfraCodegenPyTyped.execute),
                        "py-typed markers updated",
                    ),
                    (
                        "pipeline",
                        "Run full codegen pipeline",
                        FlextInfraCodegenPipeline,
                        CliRouteBase.result_handler(FlextInfraCodegenPipeline.execute),
                        None,
                    ),
                    (
                        "constants-quality-gate",
                        "Run constants migration quality gate",
                        FlextInfraCodegenQualityGate,
                        CliRouteBase.result_handler(
                            FlextInfraCodegenQualityGate.execute
                        ),
                        "constants quality gate passed",
                    ),
                    (
                        "consolidate",
                        "Consolidate inline constants into c.Infra.* references",
                        FlextInfraCodegenConsolidator,
                        CliRouteBase.result_handler(
                            FlextInfraCodegenConsolidator.execute
                        ),
                        None,
                    ),
                    (
                        "layout",
                        "Check/apply the canonical project layout (SSOT-driven)",
                        FlextInfraCodegenLayout,
                        CliRouteBase.result_handler(FlextInfraCodegenLayout.execute),
                        "layout conformance complete",
                    ),
                    (
                        "mise-artifacts",
                        "Validate the generated Mise bundle read-only",
                        FlextInfraCodegenMiseArtifacts,
                        CliRouteBase.result_handler(
                            FlextInfraCodegenMiseArtifacts.execute
                        ),
                        "Mise artifact validation complete",
                    ),
                    (
                        "version-file",
                        "Generate __version__.py from project-metadata SSOT",
                        FlextInfraCodegenVersionFile,
                        CliRouteBase.result_handler(
                            FlextInfraCodegenVersionFile.execute
                        ),
                        "version-file generation complete",
                    ),
                )
            ),
        ),
        c.Infra.CLI_GROUP_DEPS: tuple(
            m.Cli.ResultCommandRoute(
                name=route_name,
                help_text=help_text,
                model_cls=model_cls,
                handler=CliRouteBase.result_handler(model_cls.execute),
            )
            for route_name, help_text, model_cls in (
                (
                    "detect",
                    "Detect runtime vs dev dependencies",
                    FlextInfraRuntimeDevDependencyDetector,
                ),
                (
                    "extra-paths",
                    "Synchronize pyright/mypy extraPaths",
                    FlextInfraExtraPathsManager,
                ),
                (
                    "modernize",
                    "Modernize workspace pyproject files",
                    FlextInfraPyprojectModernizer,
                ),
            )
        ),
    }


__all__: list[str] = ["CodegenRoutes"]
