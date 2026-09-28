"""Validate-command CLI route ownership."""

from __future__ import annotations

from typing import ClassVar

from flext_core import r
from flext_infra import m, p, t
from flext_infra.api import infra
from flext_infra.services.cli_route_base import FlextInfraCliRouteBase
from flext_infra.validate.cprofile_report import FlextInfraCProfileReport
from flext_infra.validate.fresh_import import FlextInfraValidateFreshImport
from flext_infra.validate.import_cycles import FlextInfraValidateImportCycles
from flext_infra.validate.inventory import FlextInfraInventoryService
from flext_infra.validate.lazy_map_freshness import FlextInfraValidateLazyMapFreshness
from flext_infra.validate.metadata_discipline import (
    FlextInfraValidateMetadataDiscipline,
)
from flext_infra.validate.pytest_diag import FlextInfraPytestDiagExtractor
from flext_infra.validate.runtime_census import FlextInfraRuntimeCensusValidator
from flext_infra.validate.scanner import FlextInfraTextPatternScanner
from flext_infra.validate.silent_failure import FlextInfraSilentFailureValidator
from flext_infra.validate.skill_validator import FlextInfraSkillValidator
from flext_infra.validate.stub_chain import FlextInfraStubSupplyChain
from flext_infra.validate.tier_whitelist import FlextInfraValidateTierWhitelist


def _validate_namespace_command(
    request: m.Infra.NamespaceValidateCommand,
) -> p.Result[m.Infra.ValidationReport]:
    """Run namespace validation through the facade-owned Rope composition."""
    result = infra.validate_namespace(request)
    if result.failure:
        return r[m.Infra.ValidationReport].from_failure(result)
    report = result.unwrap()
    if report.passed:
        return r[m.Infra.ValidationReport].ok(report)
    details = "\n".join((report.summary, *report.violations))
    return r[m.Infra.ValidationReport].fail(details)


class FlextInfraValidationCommandRoutes(FlextInfraCliRouteBase):
    """Own the complete validate command tuple."""

    validate_command_routes: ClassVar[t.VariadicTuple[m.Cli.ResultCommandRoute]] = (
        m.Cli.ResultCommandRoute(
            name="cprofile-report",
            help_text="Render a bounded cProfile report",
            model_cls=FlextInfraCProfileReport,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraCProfileReport.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="inventory",
            help_text="Generate scripts inventory",
            model_cls=FlextInfraInventoryService,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraInventoryService.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="runtime-census",
            help_text="Post-import Beartype enforcement census for flext_* modules",
            model_cls=FlextInfraRuntimeCensusValidator,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraRuntimeCensusValidator.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="pytest-diag",
            help_text="Extract pytest diagnostics",
            model_cls=FlextInfraPytestDiagExtractor,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraPytestDiagExtractor.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="scan",
            help_text="Scan text files for patterns",
            model_cls=FlextInfraTextPatternScanner,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraTextPatternScanner.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="skill-validate",
            help_text="Validate a skill",
            model_cls=FlextInfraSkillValidator,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraSkillValidator.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="silent-failure",
            help_text="Validate silent failure sentinel returns",
            model_cls=FlextInfraSilentFailureValidator,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraSilentFailureValidator.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="stub-validate",
            help_text="Validate stub supply chain",
            model_cls=FlextInfraStubSupplyChain,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraStubSupplyChain.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="fresh-import",
            help_text="Guard 7: fresh-process import smoke test",
            model_cls=FlextInfraValidateFreshImport,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraValidateFreshImport.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="import-cycles",
            help_text="Guard 1: ROPE-backed import cycle detector",
            model_cls=FlextInfraValidateImportCycles,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraValidateImportCycles.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="lazy-map-freshness",
            help_text="Guard 2/3: lazy-map freshness validator",
            model_cls=FlextInfraValidateLazyMapFreshness,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraValidateLazyMapFreshness.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="namespace",
            help_text="Guard: static namespace rules (NS-000..003) via rope",
            model_cls=m.Infra.NamespaceValidateCommand,
            handler=FlextInfraCliRouteBase.result_handler(
                _validate_namespace_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="tier-whitelist",
            help_text="Guard 5: tier-whitelist/abstraction-boundary enforcer",
            model_cls=FlextInfraValidateTierWhitelist,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraValidateTierWhitelist.execute_command
            ),
        ),
        m.Cli.ResultCommandRoute(
            name="metadata-discipline",
            help_text="Guard 8: centralized metadata parser discipline",
            model_cls=FlextInfraValidateMetadataDiscipline,
            handler=FlextInfraCliRouteBase.result_handler(
                FlextInfraValidateMetadataDiscipline.execute_command
            ),
        ),
    )


__all__: list[str] = ["FlextInfraValidationCommandRoutes"]
