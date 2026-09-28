"""Composed semantic cutover planner exposing one parameterized entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING, assert_never

from flext_infra import c, m, t

from .aliases import FlextInfraUtilitiesSemanticCutoverAliases
from .facade_bases import FlextInfraUtilitiesSemanticCutoverFacadeBases
from .nesting import FlextInfraUtilitiesSemanticCutoverNesting
from .private_imports import FlextInfraUtilitiesSemanticCutoverPrivateImports

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverBase(
    FlextInfraUtilitiesSemanticCutoverNesting,
    FlextInfraUtilitiesSemanticCutoverAliases,
    FlextInfraUtilitiesSemanticCutoverPrivateImports,
    FlextInfraUtilitiesSemanticCutoverFacadeBases,
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
        """
        root = rope_workspace.repository_root
        rule_id = c.Infra.SEMANTIC_CUTOVER_RULE_IDS.get(phase)
        selected = tuple(finding for finding in findings if finding.rule_id == rule_id)
        match phase:
            case c.Infra.SemanticCutoverPhase.CLASS_NESTING:
                return cls._plan_class_nesting(rope_workspace, sources)
            case c.Infra.SemanticCutoverPhase.COMPAT_ALIAS:
                return cls._plan_api_aliases(root, sources, selected)
            case c.Infra.SemanticCutoverPhase.PRIVATE_IMPORT:
                return cls._plan_private_imports(root, sources, selected)
            case c.Infra.SemanticCutoverPhase.FACADE_BASE:
                return cls._plan_facade_bases(root, sources, selected)
            case _:
                assert_never(phase)


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverBase"]
