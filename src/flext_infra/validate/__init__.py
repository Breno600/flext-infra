# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.validate package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from flext_infra.validate import _pytest_runner
    from flext_infra.validate._pytest_diag_xml import FlextInfraPytestDiagXmlMixin
    from flext_infra.validate._pytest_runner.base import FlextInfraPytestRunnerBase
    from flext_infra.validate._pytest_runner.command import (
        FlextInfraPytestRunnerCommand,
    )
    from flext_infra.validate._pytest_runner.execution import (
        FlextInfraPytestRunnerExecution,
    )
    from flext_infra.validate._pytest_runner.reports import (
        FlextInfraPytestRunnerReports,
    )
    from flext_infra.validate._skill_rule_runner import FlextInfraSkillRuleRunnerMixin
    from flext_infra.validate.cprofile_report import FlextInfraCProfileReport
    from flext_infra.validate.fresh_import import FlextInfraValidateFreshImport
    from flext_infra.validate.inventory import FlextInfraInventoryService
    from flext_infra.validate.lazy_map_freshness import (
        FlextInfraValidateLazyMapFreshness,
    )
    from flext_infra.validate.loc_delta import FlextInfraLocDeltaValidator
    from flext_infra.validate.manual_command import FlextInfraManualCommandValidator
    from flext_infra.validate.namespace_validator import FlextInfraNamespaceValidator
    from flext_infra.validate.pytest_diag import FlextInfraPytestDiagExtractor
    from flext_infra.validate.pytest_runner import FlextInfraPytestRunner
    from flext_infra.validate.runtime_census import FlextInfraRuntimeCensusValidator
    from flext_infra.validate.scanner import FlextInfraTextPatternScanner
    from flext_infra.validate.skill_validator import FlextInfraSkillValidator
    from flext_infra.validate.stub_chain import FlextInfraStubSupplyChain
    from flext_infra.validate.testmon_db import FlextInfraTestmonDbInspector

__all__: tuple[str, ...] = (
    "FlextInfraCProfileReport",
    "FlextInfraInventoryService",
    "FlextInfraLocDeltaValidator",
    "FlextInfraManualCommandValidator",
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
    "FlextInfraValidateLazyMapFreshness",
    "_pytest_runner",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._pytest_diag_xml": ("FlextInfraPytestDiagXmlMixin",),
            "._pytest_runner": ("_pytest_runner",),
            "._pytest_runner.base": ("FlextInfraPytestRunnerBase",),
            "._pytest_runner.command": ("FlextInfraPytestRunnerCommand",),
            "._pytest_runner.execution": ("FlextInfraPytestRunnerExecution",),
            "._pytest_runner.reports": ("FlextInfraPytestRunnerReports",),
            "._skill_rule_runner": ("FlextInfraSkillRuleRunnerMixin",),
            ".cprofile_report": ("FlextInfraCProfileReport",),
            ".fresh_import": ("FlextInfraValidateFreshImport",),
            ".inventory": ("FlextInfraInventoryService",),
            ".lazy_map_freshness": ("FlextInfraValidateLazyMapFreshness",),
            ".loc_delta": ("FlextInfraLocDeltaValidator",),
            ".manual_command": ("FlextInfraManualCommandValidator",),
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
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
