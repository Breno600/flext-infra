"""Composed semantic cutover planner exposing one parameterized entry point.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING

from flext_infra import c, m, t
from flext_infra._utilities import (
    FlextInfraUtilitiesSemanticCutoverAliases,
    FlextInfraUtilitiesSemanticCutoverDynamicEnvironment,
    FlextInfraUtilitiesSemanticCutoverFacadeBases,
    FlextInfraUtilitiesSemanticCutoverModelFields,
    FlextInfraUtilitiesSemanticCutoverModuleLayout,
    FlextInfraUtilitiesSemanticCutoverNesting,
    FlextInfraUtilitiesSemanticCutoverPrivateImports,
    FlextInfraUtilitiesSemanticCutoverSelfFacade,
)
from flext_infra._utilities._semantic_cutover.declaration_relocation import (
    FlextInfraUtilitiesSemanticDeclarationRelocation,
)

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverBase(
    FlextInfraUtilitiesSemanticDeclarationRelocation,
    FlextInfraUtilitiesSemanticCutoverNesting,
    FlextInfraUtilitiesSemanticCutoverAliases,
    FlextInfraUtilitiesSemanticCutoverPrivateImports,
    FlextInfraUtilitiesSemanticCutoverFacadeBases,
    FlextInfraUtilitiesSemanticCutoverModelFields,
    FlextInfraUtilitiesSemanticCutoverSelfFacade,
    FlextInfraUtilitiesSemanticCutoverDynamicEnvironment,
    FlextInfraUtilitiesSemanticCutoverModuleLayout,
):
    """Plan every semantic ``make mod`` cutover through one typed contract."""

    @classmethod
    def plan_semantic_cutover(
        cls,
        phase: c.Infra.SemanticCutoverPhase,
        *,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding] = (),
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan one phase's edits without effects; every module failure is kept.

        ``rope_workspace`` supplies the repository root that reported findings
        are relative to and, for class nesting, the module ownership policy.
        Finding-driven phases select their own rule findings from ``findings``.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        """
        try:
            return cls._plan_dispatch(phase, rope_workspace, sources, findings)
        except Exception:
            traceback.print_exc()
            raise

    @classmethod
    def _plan_dispatch(
        cls,
        phase: c.Infra.SemanticCutoverPhase,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding] = (),
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        try:
            return cls._plan_phases(phase, rope_workspace, sources, findings)
        except Exception:
            traceback.print_exc()
            raise

    @classmethod
    def _plan_phases(
        cls,
        phase: c.Infra.SemanticCutoverPhase,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding] = (),
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        supported = isinstance(phase, c.Infra.SemanticCutoverPhase)
        if not supported:
            message = f"unsupported semantic cutover phase: {phase}"
            raise ValueError(message)
        root = rope_workspace.repository_root
        rule_id = c.Infra.SEMANTIC_CUTOVER_RULE_IDS.get(phase)
        selected = tuple(finding for finding in findings if finding.rule_id == rule_id)
        match phase:
            case (
                c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION
                | c.Infra.SemanticCutoverPhase.CLASS_NESTING
                | c.Infra.SemanticCutoverPhase.COMPAT_ALIAS
                | c.Infra.SemanticCutoverPhase.PRIVATE_IMPORT
                | c.Infra.SemanticCutoverPhase.FACADE_BASE
                | c.Infra.SemanticCutoverPhase.MODEL_FIELDS
            ):
                return cls._plan_selected_phase(
                    phase,
                    rope_workspace,
                    sources,
                    selected,
                )
            case (
                c.Infra.SemanticCutoverPhase.SELF_FACADE_IMPORT
                | c.Infra.SemanticCutoverPhase.DYNAMIC_ENVIRONMENT
                | c.Infra.SemanticCutoverPhase.MODULE_END
                | c.Infra.SemanticCutoverPhase.NOTICE_LAST
            ):
                return cls._plan_ordered_phase(phase, root, sources, selected)

    @classmethod
    def _plan_selected_phase(
        cls,
        phase: c.Infra.SemanticCutoverPhase,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
        selected: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan one finding-selected cutover phase.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        Raises:
            ValueError: When the phase is not finding-selected.

        """
        root = rope_workspace.repository_root
        match phase:
            case c.Infra.SemanticCutoverPhase.DECLARATION_RELOCATION:
                return cls._plan_declaration_relocation(rope_workspace, sources)
            case c.Infra.SemanticCutoverPhase.CLASS_NESTING:
                return cls._plan_class_nesting(rope_workspace, sources)
            case c.Infra.SemanticCutoverPhase.COMPAT_ALIAS:
                return cls._plan_api_aliases(root, sources, selected)
            case c.Infra.SemanticCutoverPhase.PRIVATE_IMPORT:
                return cls._plan_private_imports(root, sources, selected)
            case c.Infra.SemanticCutoverPhase.FACADE_BASE:
                return cls._plan_facade_bases(root, sources, selected)
            case c.Infra.SemanticCutoverPhase.MODEL_FIELDS:
                return cls._plan_model_fields(sources)
            case _:
                message = f"unsupported semantic cutover phase: {phase}"
                raise ValueError(message)

    @classmethod
    def _plan_ordered_phase(
        cls,
        phase: c.Infra.SemanticCutoverPhase,
        root: Path,
        sources: t.MappingKV[Path, str],
        selected: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan one order-driven cutover phase.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        Raises:
            ValueError: When the phase is not order-driven.

        """
        match phase:
            case c.Infra.SemanticCutoverPhase.SELF_FACADE_IMPORT:
                return cls._plan_self_facade_imports(root, sources, selected)
            case c.Infra.SemanticCutoverPhase.DYNAMIC_ENVIRONMENT:
                return cls._plan_dynamic_environment(root, sources, selected)
            case c.Infra.SemanticCutoverPhase.MODULE_END:
                return cls._plan_module_end(root, sources, selected)
            case c.Infra.SemanticCutoverPhase.NOTICE_LAST:
                return cls._plan_notice_last(root, sources, selected)
            case _:
                message = f"unsupported semantic cutover phase: {phase}"
                raise ValueError(message)


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverBase"]
