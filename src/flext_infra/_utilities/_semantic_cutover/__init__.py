# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Semantic Cutover package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
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
    from flext_infra._utilities._semantic_cutover.class_scope import (
        FlextInfraUtilitiesSemanticCutoverClassScope,
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
    "FlextInfraUtilitiesSemanticCutoverClassScope",
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

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraUtilitiesSemanticCutoverAliasCst": (
            ".alias_cst",
            "FlextInfraUtilitiesSemanticCutoverAliasCst",
        ),
        "FlextInfraUtilitiesSemanticCutoverAliases": (
            ".aliases",
            "FlextInfraUtilitiesSemanticCutoverAliases",
        ),
        "FlextInfraUtilitiesSemanticCutoverBase": (
            ".base",
            "FlextInfraUtilitiesSemanticCutoverBase",
        ),
        "FlextInfraUtilitiesSemanticCutoverBindings": (
            ".bindings",
            "FlextInfraUtilitiesSemanticCutoverBindings",
        ),
        "FlextInfraUtilitiesSemanticCutoverClassScope": (
            ".class_scope",
            "FlextInfraUtilitiesSemanticCutoverClassScope",
        ),
        "FlextInfraUtilitiesSemanticCutoverDynamicEnvironment": (
            ".dynamic_environment",
            "FlextInfraUtilitiesSemanticCutoverDynamicEnvironment",
        ),
        "FlextInfraUtilitiesSemanticCutoverEdits": (
            ".edits",
            "FlextInfraUtilitiesSemanticCutoverEdits",
        ),
        "FlextInfraUtilitiesSemanticCutoverFacadeBaseCst": (
            ".facade_base_cst",
            "FlextInfraUtilitiesSemanticCutoverFacadeBaseCst",
        ),
        "FlextInfraUtilitiesSemanticCutoverFacadeBases": (
            ".facade_bases",
            "FlextInfraUtilitiesSemanticCutoverFacadeBases",
        ),
        "FlextInfraUtilitiesSemanticCutoverFacadeOwners": (
            ".facade_owners",
            "FlextInfraUtilitiesSemanticCutoverFacadeOwners",
        ),
        "FlextInfraUtilitiesSemanticCutoverModelFields": (
            ".model_fields",
            "FlextInfraUtilitiesSemanticCutoverModelFields",
        ),
        "FlextInfraUtilitiesSemanticCutoverModelFieldsBindings": (
            ".model_fields_bindings",
            "FlextInfraUtilitiesSemanticCutoverModelFieldsBindings",
        ),
        "FlextInfraUtilitiesSemanticCutoverModuleLayout": (
            ".module_layout",
            "FlextInfraUtilitiesSemanticCutoverModuleLayout",
        ),
        "FlextInfraUtilitiesSemanticCutoverNesting": (
            ".nesting",
            "FlextInfraUtilitiesSemanticCutoverNesting",
        ),
        "FlextInfraUtilitiesSemanticCutoverNestingCst": (
            ".nesting_cst",
            "FlextInfraUtilitiesSemanticCutoverNestingCst",
        ),
        "FlextInfraUtilitiesSemanticCutoverNestingModuleAliases": (
            ".nesting_module_aliases",
            "FlextInfraUtilitiesSemanticCutoverNestingModuleAliases",
        ),
        "FlextInfraUtilitiesSemanticCutoverNestingOwner": (
            ".nesting_owner",
            "FlextInfraUtilitiesSemanticCutoverNestingOwner",
        ),
        "FlextInfraUtilitiesSemanticCutoverNestingReferences": (
            ".nesting_references",
            "FlextInfraUtilitiesSemanticCutoverNestingReferences",
        ),
        "FlextInfraUtilitiesSemanticCutoverPrivateImportCst": (
            ".private_import_cst",
            "FlextInfraUtilitiesSemanticCutoverPrivateImportCst",
        ),
        "FlextInfraUtilitiesSemanticCutoverPrivateImports": (
            ".private_imports",
            "FlextInfraUtilitiesSemanticCutoverPrivateImports",
        ),
        "FlextInfraUtilitiesSemanticCutoverSelfFacade": (
            ".self_facade",
            "FlextInfraUtilitiesSemanticCutoverSelfFacade",
        ),
        "FlextInfraUtilitiesSemanticFamilyFlatten": (
            ".family_flatten",
            "FlextInfraUtilitiesSemanticFamilyFlatten",
        ),
        "FlextInfraUtilitiesSemanticFamilyReferences": (
            ".family_references",
            "FlextInfraUtilitiesSemanticFamilyReferences",
        ),
        "FlextInfraUtilitiesSemanticFamilyTypeReferences": (
            ".family_type_references",
            "FlextInfraUtilitiesSemanticFamilyTypeReferences",
        ),
        "FlextInfraUtilitiesSemanticHelperReferences": (
            ".helper_references",
            "FlextInfraUtilitiesSemanticHelperReferences",
        ),
        "FlextInfraUtilitiesSemanticNestingTypes": (
            ".nesting_types",
            "FlextInfraUtilitiesSemanticNestingTypes",
        ),
    }),
    public_exports=__all__,
)
