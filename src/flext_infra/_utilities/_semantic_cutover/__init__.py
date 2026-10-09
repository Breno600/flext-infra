# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Semantic Cutover package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports
from flext_infra._utilities._semantic_cutover.alias_cst import (
    FlextInfraUtilitiesSemanticCutoverAliasCst,
)
from flext_infra._utilities._semantic_cutover.aliases import (
    FlextInfraUtilitiesSemanticCutoverAliases,
)
from flext_infra._utilities._semantic_cutover.base import (
    FlextInfraUtilitiesSemanticCutoverBase,
)
from flext_infra._utilities._semantic_cutover.bindings import (
    FlextInfraUtilitiesSemanticCutoverBindings,
)
from flext_infra._utilities._semantic_cutover.dynamic_environment import (
    FlextInfraUtilitiesSemanticCutoverDynamicEnvironment,
)
from flext_infra._utilities._semantic_cutover.edits import (
    FlextInfraUtilitiesSemanticCutoverEdits,
)
from flext_infra._utilities._semantic_cutover.facade_base_cst import (
    FlextInfraUtilitiesSemanticCutoverFacadeBaseCst,
)
from flext_infra._utilities._semantic_cutover.facade_bases import (
    FlextInfraUtilitiesSemanticCutoverFacadeBases,
)
from flext_infra._utilities._semantic_cutover.facade_owners import (
    FlextInfraUtilitiesSemanticCutoverFacadeOwners,
)
from flext_infra._utilities._semantic_cutover.family_flatten import (
    FlextInfraUtilitiesSemanticFamilyFlatten,
)
from flext_infra._utilities._semantic_cutover.family_references import (
    FlextInfraUtilitiesSemanticFamilyReferences,
)
from flext_infra._utilities._semantic_cutover.family_type_references import (
    FlextInfraUtilitiesSemanticFamilyTypeReferences,
)
from flext_infra._utilities._semantic_cutover.helper_references import (
    FlextInfraUtilitiesSemanticHelperReferences,
)
from flext_infra._utilities._semantic_cutover.model_fields import (
    FlextInfraUtilitiesSemanticCutoverModelFields,
)
from flext_infra._utilities._semantic_cutover.model_fields_bindings import (
    FlextInfraUtilitiesSemanticCutoverModelFieldsBindings,
)
from flext_infra._utilities._semantic_cutover.module_layout import (
    FlextInfraUtilitiesSemanticCutoverModuleLayout,
)
from flext_infra._utilities._semantic_cutover.nesting import (
    FlextInfraUtilitiesSemanticCutoverNesting,
)
from flext_infra._utilities._semantic_cutover.nesting_cst import (
    FlextInfraUtilitiesSemanticCutoverNestingCst,
)
from flext_infra._utilities._semantic_cutover.nesting_module_aliases import (
    FlextInfraUtilitiesSemanticCutoverNestingModuleAliases,
)
from flext_infra._utilities._semantic_cutover.nesting_owner import (
    FlextInfraUtilitiesSemanticCutoverNestingOwner,
)
from flext_infra._utilities._semantic_cutover.nesting_references import (
    FlextInfraUtilitiesSemanticCutoverNestingReferences,
)
from flext_infra._utilities._semantic_cutover.nesting_types import (
    FlextInfraUtilitiesSemanticNestingTypes,
)
from flext_infra._utilities._semantic_cutover.private_import_cst import (
    FlextInfraUtilitiesSemanticCutoverPrivateImportCst,
)
from flext_infra._utilities._semantic_cutover.private_imports import (
    FlextInfraUtilitiesSemanticCutoverPrivateImports,
)
from flext_infra._utilities._semantic_cutover.self_facade import (
    FlextInfraUtilitiesSemanticCutoverSelfFacade,
)

__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesSemanticCutoverAliasCst",
    "FlextInfraUtilitiesSemanticCutoverAliases",
    "FlextInfraUtilitiesSemanticCutoverBase",
    "FlextInfraUtilitiesSemanticCutoverBindings",
    "FlextInfraUtilitiesSemanticCutoverDynamicEnvironment",
    "FlextInfraUtilitiesSemanticCutoverEdits",
    "FlextInfraUtilitiesSemanticCutoverFacadeBaseCst",
    "FlextInfraUtilitiesSemanticCutoverFacadeBases",
    "FlextInfraUtilitiesSemanticCutoverFacadeOwners",
    "FlextInfraUtilitiesSemanticCutoverModelFields",
    "FlextInfraUtilitiesSemanticCutoverModelFieldsBindings",
    "FlextInfraUtilitiesSemanticCutoverModuleLayout",
    "FlextInfraUtilitiesSemanticCutoverNesting",
    "FlextInfraUtilitiesSemanticCutoverNestingCst",
    "FlextInfraUtilitiesSemanticCutoverNestingModuleAliases",
    "FlextInfraUtilitiesSemanticCutoverNestingOwner",
    "FlextInfraUtilitiesSemanticCutoverNestingReferences",
    "FlextInfraUtilitiesSemanticCutoverPrivateImportCst",
    "FlextInfraUtilitiesSemanticCutoverPrivateImports",
    "FlextInfraUtilitiesSemanticCutoverSelfFacade",
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
            ".bindings": ("FlextInfraUtilitiesSemanticCutoverBindings",),
            ".dynamic_environment": (
                "FlextInfraUtilitiesSemanticCutoverDynamicEnvironment",
            ),
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
            ".model_fields": ("FlextInfraUtilitiesSemanticCutoverModelFields",),
            ".model_fields_bindings": (
                "FlextInfraUtilitiesSemanticCutoverModelFieldsBindings",
            ),
            ".module_layout": ("FlextInfraUtilitiesSemanticCutoverModuleLayout",),
            ".nesting": ("FlextInfraUtilitiesSemanticCutoverNesting",),
            ".nesting_cst": ("FlextInfraUtilitiesSemanticCutoverNestingCst",),
            ".nesting_module_aliases": (
                "FlextInfraUtilitiesSemanticCutoverNestingModuleAliases",
            ),
            ".nesting_owner": ("FlextInfraUtilitiesSemanticCutoverNestingOwner",),
            ".nesting_references": (
                "FlextInfraUtilitiesSemanticCutoverNestingReferences",
            ),
            ".nesting_types": ("FlextInfraUtilitiesSemanticNestingTypes",),
            ".private_import_cst": (
                "FlextInfraUtilitiesSemanticCutoverPrivateImportCst",
            ),
            ".private_imports": ("FlextInfraUtilitiesSemanticCutoverPrivateImports",),
            ".self_facade": ("FlextInfraUtilitiesSemanticCutoverSelfFacade",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
