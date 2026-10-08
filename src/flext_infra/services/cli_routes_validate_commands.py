"""Validate-command CLI route ownership.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import ClassVar

from flext_infra import m, p, r, t
from flext_infra.api import infra
from flext_infra.services.cli_route_base import FlextInfraCliRouteBase
from flext_infra.validate.cprofile_report import FlextInfraCProfileReport
from flext_infra.validate.fresh_import import FlextInfraValidateFreshImport
from flext_infra.validate.inventory import FlextInfraInventoryService
from flext_infra.validate.lazy_map_freshness import FlextInfraValidateLazyMapFreshness
from flext_infra.validate.pytest_diag import FlextInfraPytestDiagExtractor
from flext_infra.validate.runtime_census import FlextInfraRuntimeCensusValidator
from flext_infra.validate.scanner import FlextInfraTextPatternScanner
from flext_infra.validate.skill_validator import FlextInfraSkillValidator
from flext_infra.validate.stub_chain import FlextInfraStubSupplyChain


class FlextInfraValidationCommandRoutes(FlextInfraCliRouteBase):
    """Own the complete validate command tuple."""

    @staticmethod
    def _validate_namespace_command(
        request: m.Infra.NamespaceValidateCommand,
    ) -> p.Result[m.Infra.ValidationReport]:
        """Run namespace validation through the rule engine.

        Returns:
            The resulting ``p.Result[m.Infra.ValidationReport]``.

        """
        result = infra.validate_namespace(request)
        if result.failure:
            return r[m.Infra.ValidationReport].from_failure(result)
        report = result.unwrap()
        if report.passed:
            return r[m.Infra.ValidationReport].ok(report)
        details = "\n".join((report.summary, *report.violations))
        return r[m.Infra.ValidationReport].fail(details)

    validate_command_routes: ClassVar[t.VariadicTuple[m.Cli.ResultCommandRoute]] = (
        tuple(
            m.Cli.ResultCommandRoute(
                name=route_name,
                help_text=help_text,
                model_cls=model_cls,
                handler=handler,
            )
            for route_name, help_text, model_cls, handler in (
                (
                    "cprofile-report",
                    "Render a bounded cProfile report",
                    FlextInfraCProfileReport,
                    FlextInfraCliRouteBase.result_handler(
                        FlextInfraCProfileReport.execute,
                    ),
                ),
                (
                    "inventory",
                    "Generate scripts inventory",
                    FlextInfraInventoryService,
                    FlextInfraCliRouteBase.result_handler(
                        FlextInfraInventoryService.execute,
                    ),
                ),
                (
                    "runtime-census",
                    "Post-import Beartype enforcement census for flext_* modules",
                    FlextInfraRuntimeCensusValidator,
                    FlextInfraCliRouteBase.result_handler(
                        FlextInfraRuntimeCensusValidator.execute,
                    ),
                ),
                (
                    "pytest-diag",
                    "Extract pytest diagnostics",
                    FlextInfraPytestDiagExtractor,
                    FlextInfraCliRouteBase.result_handler(
                        FlextInfraPytestDiagExtractor.execute,
                    ),
                ),
                (
                    "scan",
                    "Scan text files for patterns",
                    FlextInfraTextPatternScanner,
                    FlextInfraCliRouteBase.result_handler(
                        FlextInfraTextPatternScanner.execute,
                    ),
                ),
                (
                    "skill-validate",
                    "Validate a skill",
                    FlextInfraSkillValidator,
                    FlextInfraCliRouteBase.result_handler(
                        FlextInfraSkillValidator.execute,
                    ),
                ),
                (
                    "stub-validate",
                    "Validate stub supply chain",
                    FlextInfraStubSupplyChain,
                    FlextInfraCliRouteBase.result_handler(
                        FlextInfraStubSupplyChain.execute,
                    ),
                ),
                (
                    "fresh-import",
                    "Guard 7: fresh-process import smoke test",
                    FlextInfraValidateFreshImport,
                    FlextInfraCliRouteBase.result_handler(
                        FlextInfraValidateFreshImport.execute,
                    ),
                ),
                (
                    "lazy-map-freshness",
                    "Guard 2/3: lazy-map freshness validator",
                    FlextInfraValidateLazyMapFreshness,
                    FlextInfraCliRouteBase.result_handler(
                        FlextInfraValidateLazyMapFreshness.execute,
                    ),
                ),
                (
                    "namespace",
                    "Guard: namespace laws of the rule catalog",
                    m.Infra.NamespaceValidateCommand,
                    FlextInfraCliRouteBase.result_handler(_validate_namespace_command),
                ),
            )
        )
    )


__all__: list[str] = ["FlextInfraValidationCommandRoutes"]
