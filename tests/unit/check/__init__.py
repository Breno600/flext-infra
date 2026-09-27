# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests.unit.check package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .abstraction_boundary_gate_tests import TestsFlextInfraAbstractionBoundaryGate
    from .direnv_gate_tests import TestsFlextInfraDirenvGate
    from .duplication_gate_tests import TestsFlextInfraDuplicationGate
    from .enforcement_fixer_orchestrator_tests import (
        TestsFlextInfraEnforcementFixerOrchestrator,
    )
    from .extended_cli_entry_tests import TestsFlextInfraExtendedCliEntry
    from .extended_config_fixer_errors_tests import (
        TestsFlextInfraExtendedConfigFixerErrors,
    )
    from .extended_config_fixer_tests import TestsFlextInfraExtendedConfigFixer
    from .extended_error_reporting_tests import TestsFlextInfraGateErrorReporting
    from .extended_gate_bandit_markdown_tests import (
        TestsFlextInfraBanditAndMarkdownGates,
    )
    from .extended_gate_markdown_format_code_tests import (
        TestsFlextInfraMarkdownFormatAndCodeGates,
    )
    from .extended_gate_mypy_pyright_tests import TestsFlextInfraTypeGates
    from .extended_models_tests import TestsFlextInfraModels
    from .extended_project_runners_tests import TestsFlextInfraExtendedProjectRunners
    from .extended_resolve_gates_tests import (
        TestsFlextInfraWorkspaceCheckerResolveGates,
    )
    from .extended_run_projects_tests import TestsFlextInfraRunProjects
    from .extended_runners_ruff_tests import TestsFlextInfraRealGateRunners
    from .extended_workspace_init_tests import TestsFlextInfraWorkspaceInit
    from .fix_pyrefly_config_tests import TestsFlextInfraFixPyreflyConfig
    from .gate_registry_tests import TestsFlextInfraGateRegistry
    from .global_enforcement_tests import TestsFlextInfraGlobalEnforcement
    from .init_tests import TestsFlextInfraCheck
    from .loc_cap_gate_tests import TestsFlextInfraLocCapGate
    from .main_tests import TestsFlextInfraCheckMain
    from .pyrefly_tests import TestsFlextInfraConfigFixer
    from .silent_failure_gate_tests import TestsFlextInfraSilentFailureGate
    from .smells_gate_tests import TestsFlextInfraSmellsGate
    from .test_cli import TestsFlextInfraWorkspaceCheckCli
    from .tests_workspace_check import TestsFlextInfraWorkspaceCheckModule
    from .workspace_tests import TestsFlextInfraWorkspaceChecker


__all__: tuple[str, ...] = (
    "TestsFlextInfraAbstractionBoundaryGate",
    "TestsFlextInfraBanditAndMarkdownGates",
    "TestsFlextInfraCheck",
    "TestsFlextInfraCheckMain",
    "TestsFlextInfraConfigFixer",
    "TestsFlextInfraDirenvGate",
    "TestsFlextInfraDuplicationGate",
    "TestsFlextInfraEnforcementFixerOrchestrator",
    "TestsFlextInfraExtendedCliEntry",
    "TestsFlextInfraExtendedConfigFixer",
    "TestsFlextInfraExtendedConfigFixerErrors",
    "TestsFlextInfraExtendedProjectRunners",
    "TestsFlextInfraFixPyreflyConfig",
    "TestsFlextInfraGateErrorReporting",
    "TestsFlextInfraGateRegistry",
    "TestsFlextInfraGlobalEnforcement",
    "TestsFlextInfraLocCapGate",
    "TestsFlextInfraMarkdownFormatAndCodeGates",
    "TestsFlextInfraModels",
    "TestsFlextInfraRealGateRunners",
    "TestsFlextInfraRunProjects",
    "TestsFlextInfraSilentFailureGate",
    "TestsFlextInfraSmellsGate",
    "TestsFlextInfraTypeGates",
    "TestsFlextInfraWorkspaceCheckCli",
    "TestsFlextInfraWorkspaceCheckModule",
    "TestsFlextInfraWorkspaceChecker",
    "TestsFlextInfraWorkspaceCheckerResolveGates",
    "TestsFlextInfraWorkspaceInit",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".abstraction_boundary_gate_tests": (
                "TestsFlextInfraAbstractionBoundaryGate",
            ),
            ".direnv_gate_tests": ("TestsFlextInfraDirenvGate",),
            ".duplication_gate_tests": ("TestsFlextInfraDuplicationGate",),
            ".enforcement_fixer_orchestrator_tests": (
                "TestsFlextInfraEnforcementFixerOrchestrator",
            ),
            ".extended_cli_entry_tests": ("TestsFlextInfraExtendedCliEntry",),
            ".extended_config_fixer_errors_tests": (
                "TestsFlextInfraExtendedConfigFixerErrors",
            ),
            ".extended_config_fixer_tests": ("TestsFlextInfraExtendedConfigFixer",),
            ".extended_error_reporting_tests": ("TestsFlextInfraGateErrorReporting",),
            ".extended_gate_bandit_markdown_tests": (
                "TestsFlextInfraBanditAndMarkdownGates",
            ),
            ".extended_gate_markdown_format_code_tests": (
                "TestsFlextInfraMarkdownFormatAndCodeGates",
            ),
            ".extended_gate_mypy_pyright_tests": ("TestsFlextInfraTypeGates",),
            ".extended_models_tests": ("TestsFlextInfraModels",),
            ".extended_project_runners_tests": (
                "TestsFlextInfraExtendedProjectRunners",
            ),
            ".extended_resolve_gates_tests": (
                "TestsFlextInfraWorkspaceCheckerResolveGates",
            ),
            ".extended_run_projects_tests": ("TestsFlextInfraRunProjects",),
            ".extended_runners_ruff_tests": ("TestsFlextInfraRealGateRunners",),
            ".extended_workspace_init_tests": ("TestsFlextInfraWorkspaceInit",),
            ".fix_pyrefly_config_tests": ("TestsFlextInfraFixPyreflyConfig",),
            ".gate_registry_tests": ("TestsFlextInfraGateRegistry",),
            ".global_enforcement_tests": ("TestsFlextInfraGlobalEnforcement",),
            ".init_tests": ("TestsFlextInfraCheck",),
            ".loc_cap_gate_tests": ("TestsFlextInfraLocCapGate",),
            ".main_tests": ("TestsFlextInfraCheckMain",),
            ".pyrefly_tests": ("TestsFlextInfraConfigFixer",),
            ".silent_failure_gate_tests": ("TestsFlextInfraSilentFailureGate",),
            ".smells_gate_tests": ("TestsFlextInfraSmellsGate",),
            ".test_cli": ("TestsFlextInfraWorkspaceCheckCli",),
            ".tests_workspace_check": ("TestsFlextInfraWorkspaceCheckModule",),
            ".workspace_tests": ("TestsFlextInfraWorkspaceChecker",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
