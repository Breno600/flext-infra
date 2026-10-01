# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.validate package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from . import _namespace_rules, _pytest_runner
    from ._namespace_rules.base import FlextInfraNamespaceRulesBase
    from ._namespace_rules.contracts import FlextInfraNamespaceRulesContracts
    from ._namespace_rules.imports import FlextInfraNamespaceRulesImports
    from ._namespace_rules.structure import FlextInfraNamespaceRulesStructure
    from ._pytest_diag_xml import FlextInfraPytestDiagXmlMixin
    from ._pytest_runner.base import FlextInfraPytestRunnerBase
    from ._pytest_runner.command import FlextInfraPytestRunnerCommand
    from ._pytest_runner.execution import FlextInfraPytestRunnerExecution
    from ._pytest_runner.reports import FlextInfraPytestRunnerReports
    from ._skill_rule_runner import FlextInfraSkillRuleRunnerMixin
    from .cprofile_report import FlextInfraCProfileReport
    from .fresh_import import FlextInfraValidateFreshImport
    from .import_cycles import FlextInfraValidateImportCycles
    from .inventory import FlextInfraInventoryService
    from .lazy_map_freshness import FlextInfraValidateLazyMapFreshness
    from .loc_delta import FlextInfraLocDeltaValidator
    from .manual_command import FlextInfraManualCommandValidator
    from .namespace_rules import FlextInfraNamespaceRules
    from .namespace_validator import FlextInfraNamespaceValidator
    from .pytest_diag import FlextInfraPytestDiagExtractor
    from .pytest_runner import FlextInfraPytestRunner
    from .runtime_census import FlextInfraRuntimeCensusValidator
    from .scanner import FlextInfraTextPatternScanner
    from .skill_validator import FlextInfraSkillValidator
    from .stub_chain import FlextInfraStubSupplyChain
    from .testmon_db import FlextInfraTestmonDbInspector


__all__: tuple[str, ...] = (
    "FlextInfraCProfileReport",
    "FlextInfraInventoryService",
    "FlextInfraLocDeltaValidator",
    "FlextInfraManualCommandValidator",
    "FlextInfraNamespaceRules",
    "FlextInfraNamespaceRulesBase",
    "FlextInfraNamespaceRulesContracts",
    "FlextInfraNamespaceRulesImports",
    "FlextInfraNamespaceRulesStructure",
    "FlextInfraNamespaceValidator",
    "FlextInfraPytestDiagExtractor",
    "FlextInfraPytestDiagXmlMixin",
    "FlextInfraPytestRunner",
    "FlextInfraPytestRunnerBase",
    "FlextInfraPytestRunnerCommand",
    "FlextInfraPytestRunnerExecution",
    "FlextInfraPytestRunnerReports",
    "FlextInfraRuntimeCensusValidator",
    "FlextInfraSkillRuleRunnerMixin",
    "FlextInfraSkillValidator",
    "FlextInfraStubSupplyChain",
    "FlextInfraTestmonDbInspector",
    "FlextInfraTextPatternScanner",
    "FlextInfraValidateFreshImport",
    "FlextInfraValidateImportCycles",
    "FlextInfraValidateLazyMapFreshness",
    "_namespace_rules",
    "_pytest_runner",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._namespace_rules": ("_namespace_rules",),
            "._namespace_rules.base": ("FlextInfraNamespaceRulesBase",),
            "._namespace_rules.contracts": ("FlextInfraNamespaceRulesContracts",),
            "._namespace_rules.imports": ("FlextInfraNamespaceRulesImports",),
            "._namespace_rules.structure": ("FlextInfraNamespaceRulesStructure",),
            "._pytest_diag_xml": ("FlextInfraPytestDiagXmlMixin",),
            "._pytest_runner": ("_pytest_runner",),
            "._pytest_runner.base": ("FlextInfraPytestRunnerBase",),
            "._pytest_runner.command": ("FlextInfraPytestRunnerCommand",),
            "._pytest_runner.execution": ("FlextInfraPytestRunnerExecution",),
            "._pytest_runner.reports": ("FlextInfraPytestRunnerReports",),
            "._skill_rule_runner": ("FlextInfraSkillRuleRunnerMixin",),
            ".cprofile_report": ("FlextInfraCProfileReport",),
            ".fresh_import": ("FlextInfraValidateFreshImport",),
            ".import_cycles": ("FlextInfraValidateImportCycles",),
            ".inventory": ("FlextInfraInventoryService",),
            ".lazy_map_freshness": ("FlextInfraValidateLazyMapFreshness",),
            ".loc_delta": ("FlextInfraLocDeltaValidator",),
            ".manual_command": ("FlextInfraManualCommandValidator",),
            ".namespace_rules": ("FlextInfraNamespaceRules",),
            ".namespace_validator": ("FlextInfraNamespaceValidator",),
            ".pytest_diag": ("FlextInfraPytestDiagExtractor",),
            ".pytest_runner": ("FlextInfraPytestRunner",),
            ".runtime_census": ("FlextInfraRuntimeCensusValidator",),
            ".scanner": ("FlextInfraTextPatternScanner",),
            ".skill_validator": ("FlextInfraSkillValidator",),
            ".stub_chain": ("FlextInfraStubSupplyChain",),
            ".testmon_db": ("FlextInfraTestmonDbInspector",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
