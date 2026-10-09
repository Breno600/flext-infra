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
    from flext_infra._utilities._semantic_cutover.declaration_payload import (
        FlextInfraUtilitiesDeclarationPayload,
    )
    from flext_infra._utilities._semantic_cutover.declaration_relocation import (
        FlextInfraUtilitiesSemanticDeclarationRelocation,
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
    "FlextInfraUtilitiesDeclarationPayload",
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
    "FlextInfraUtilitiesSemanticDeclarationRelocation",
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
        "FlextInfraUtilitiesDeclarationPayload": ".declaration_payload",
        "FlextInfraUtilitiesSemanticCutoverAliasCst": ".alias_cst",
        "FlextInfraUtilitiesSemanticCutoverAliases": ".aliases",
        "FlextInfraUtilitiesSemanticCutoverBase": ".base",
        "FlextInfraUtilitiesSemanticCutoverBindings": ".bindings",
        "FlextInfraUtilitiesSemanticCutoverClassScope": ".class_scope",
        "FlextInfraUtilitiesSemanticCutoverDynamicEnvironment": ".dynamic_environment",
        "FlextInfraUtilitiesSemanticCutoverEdits": ".edits",
        "FlextInfraUtilitiesSemanticCutoverFacadeBaseCst": ".facade_base_cst",
        "FlextInfraUtilitiesSemanticCutoverFacadeBases": ".facade_bases",
        "FlextInfraUtilitiesSemanticCutoverFacadeOwners": ".facade_owners",
        "FlextInfraUtilitiesSemanticCutoverModelFields": ".model_fields",
        "FlextInfraUtilitiesSemanticCutoverModelFieldsBindings": (
            ".model_fields_bindings"
        ),
        "FlextInfraUtilitiesSemanticCutoverModuleLayout": ".module_layout",
        "FlextInfraUtilitiesSemanticCutoverNesting": ".nesting",
        "FlextInfraUtilitiesSemanticCutoverNestingCst": ".nesting_cst",
        "FlextInfraUtilitiesSemanticCutoverNestingModuleAliases": (
            ".nesting_module_aliases"
        ),
        "FlextInfraUtilitiesSemanticCutoverNestingOwner": ".nesting_owner",
        "FlextInfraUtilitiesSemanticCutoverNestingReferences": ".nesting_references",
        "FlextInfraUtilitiesSemanticCutoverPrivateImportCst": ".private_import_cst",
        "FlextInfraUtilitiesSemanticCutoverPrivateImports": ".private_imports",
        "FlextInfraUtilitiesSemanticCutoverSelfFacade": ".self_facade",
        "FlextInfraUtilitiesSemanticDeclarationRelocation": ".declaration_relocation",
        "FlextInfraUtilitiesSemanticFamilyFlatten": ".family_flatten",
        "FlextInfraUtilitiesSemanticFamilyReferences": ".family_references",
        "FlextInfraUtilitiesSemanticFamilyTypeReferences": ".family_type_references",
        "FlextInfraUtilitiesSemanticHelperReferences": ".helper_references",
        "FlextInfraUtilitiesSemanticNestingTypes": ".nesting_types",
    }),
    public_exports=__all__,
)
