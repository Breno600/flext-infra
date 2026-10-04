# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.validate package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

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

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraCProfileReport": (".cprofile_report", "FlextInfraCProfileReport"),
        "FlextInfraInventoryService": (".inventory", "FlextInfraInventoryService"),
        "FlextInfraLocDeltaValidator": (".loc_delta", "FlextInfraLocDeltaValidator"),
        "FlextInfraManualCommandValidator": (
            ".manual_command",
            "FlextInfraManualCommandValidator",
        ),
        "FlextInfraNamespaceValidator": (
            ".namespace_validator",
            "FlextInfraNamespaceValidator",
        ),
        "FlextInfraPytestDiagExtractor": (
            ".pytest_diag",
            "FlextInfraPytestDiagExtractor",
        ),
        "FlextInfraPytestDiagXmlMixin": (
            "._pytest_diag_xml",
            "FlextInfraPytestDiagXmlMixin",
        ),
        "FlextInfraPytestRunner": (".pytest_runner", "FlextInfraPytestRunner"),
        "FlextInfraPytestRunnerBase": (
            "._pytest_runner.base",
            "FlextInfraPytestRunnerBase",
        ),
        "FlextInfraPytestRunnerCommand": (
            "._pytest_runner.command",
            "FlextInfraPytestRunnerCommand",
        ),
        "FlextInfraPytestRunnerExecution": (
            "._pytest_runner.execution",
            "FlextInfraPytestRunnerExecution",
        ),
        "FlextInfraPytestRunnerReports": (
            "._pytest_runner.reports",
            "FlextInfraPytestRunnerReports",
        ),
        "FlextInfraRuntimeCensusValidator": (
            ".runtime_census",
            "FlextInfraRuntimeCensusValidator",
        ),
        "FlextInfraSkillRuleRunnerMixin": (
            "._skill_rule_runner",
            "FlextInfraSkillRuleRunnerMixin",
        ),
        "FlextInfraSkillValidator": (".skill_validator", "FlextInfraSkillValidator"),
        "FlextInfraStubSupplyChain": (".stub_chain", "FlextInfraStubSupplyChain"),
        "FlextInfraTestmonDbInspector": (".testmon_db", "FlextInfraTestmonDbInspector"),
        "FlextInfraTextPatternScanner": (".scanner", "FlextInfraTextPatternScanner"),
        "FlextInfraValidateFreshImport": (
            ".fresh_import",
            "FlextInfraValidateFreshImport",
        ),
        "FlextInfraValidateLazyMapFreshness": (
            ".lazy_map_freshness",
            "FlextInfraValidateLazyMapFreshness",
        ),
        "_pytest_runner": ("._pytest_runner", ""),
    }),
    public_exports=__all__,
)
