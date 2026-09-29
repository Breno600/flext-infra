# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Semantic Cutover package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .alias_cst import FlextInfraUtilitiesSemanticCutoverAliasCst
    from .aliases import FlextInfraUtilitiesSemanticCutoverAliases
    from .base import FlextInfraUtilitiesSemanticCutoverBase
    from .edits import FlextInfraUtilitiesSemanticCutoverEdits
    from .facade_base_cst import FlextInfraUtilitiesSemanticCutoverFacadeBaseCst
    from .facade_bases import FlextInfraUtilitiesSemanticCutoverFacadeBases
    from .facade_owners import FlextInfraUtilitiesSemanticCutoverFacadeOwners
    from .family_flatten import FlextInfraUtilitiesSemanticFamilyFlatten
    from .family_references import FlextInfraUtilitiesSemanticFamilyReferences
    from .family_type_references import FlextInfraUtilitiesSemanticFamilyTypeReferences
    from .helper_references import FlextInfraUtilitiesSemanticHelperReferences
    from .nesting import FlextInfraUtilitiesSemanticCutoverNesting
    from .nesting_cst import FlextInfraUtilitiesSemanticCutoverNestingCst
    from .nesting_references import FlextInfraUtilitiesSemanticCutoverNestingReferences
    from .nesting_types import FlextInfraUtilitiesSemanticNestingTypes
    from .private_import_cst import FlextInfraUtilitiesSemanticCutoverPrivateImportCst
    from .private_imports import FlextInfraUtilitiesSemanticCutoverPrivateImports


__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesSemanticCutoverAliasCst",
    "FlextInfraUtilitiesSemanticCutoverAliases",
    "FlextInfraUtilitiesSemanticCutoverBase",
    "FlextInfraUtilitiesSemanticCutoverEdits",
    "FlextInfraUtilitiesSemanticCutoverFacadeBaseCst",
    "FlextInfraUtilitiesSemanticCutoverFacadeBases",
    "FlextInfraUtilitiesSemanticCutoverFacadeOwners",
    "FlextInfraUtilitiesSemanticCutoverNesting",
    "FlextInfraUtilitiesSemanticCutoverNestingCst",
    "FlextInfraUtilitiesSemanticCutoverNestingReferences",
    "FlextInfraUtilitiesSemanticCutoverPrivateImportCst",
    "FlextInfraUtilitiesSemanticCutoverPrivateImports",
    "FlextInfraUtilitiesSemanticFamilyFlatten",
    "FlextInfraUtilitiesSemanticFamilyReferences",
    "FlextInfraUtilitiesSemanticFamilyTypeReferences",
    "FlextInfraUtilitiesSemanticHelperReferences",
    "FlextInfraUtilitiesSemanticNestingTypes",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".alias_cst": ("FlextInfraUtilitiesSemanticCutoverAliasCst",),
            ".aliases": ("FlextInfraUtilitiesSemanticCutoverAliases",),
            ".base": ("FlextInfraUtilitiesSemanticCutoverBase",),
            ".edits": ("FlextInfraUtilitiesSemanticCutoverEdits",),
            ".facade_base_cst": ("FlextInfraUtilitiesSemanticCutoverFacadeBaseCst",),
            ".facade_bases": ("FlextInfraUtilitiesSemanticCutoverFacadeBases",),
            ".facade_owners": ("FlextInfraUtilitiesSemanticCutoverFacadeOwners",),
            ".family_flatten": ("FlextInfraUtilitiesSemanticFamilyFlatten",),
            ".family_references": ("FlextInfraUtilitiesSemanticFamilyReferences",),
            ".family_type_references": (
                "FlextInfraUtilitiesSemanticFamilyTypeReferences",
            ),
            ".helper_references": ("FlextInfraUtilitiesSemanticHelperReferences",),
            ".nesting": ("FlextInfraUtilitiesSemanticCutoverNesting",),
            ".nesting_cst": ("FlextInfraUtilitiesSemanticCutoverNestingCst",),
            ".nesting_references": (
                "FlextInfraUtilitiesSemanticCutoverNestingReferences",
            ),
            ".nesting_types": ("FlextInfraUtilitiesSemanticNestingTypes",),
            ".private_import_cst": (
                "FlextInfraUtilitiesSemanticCutoverPrivateImportCst",
            ),
            ".private_imports": ("FlextInfraUtilitiesSemanticCutoverPrivateImports",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
