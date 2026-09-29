# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.transformers package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from ._canonical_t_import import FlextInfraEnsureCanonicalTImportMixin
    from ._import_facades import FlextInfraRefactorImportFacades
    from ._semantic_publication import (
        publish_semantic_file_plan,
        publish_semantic_file_plans,
    )
    from ._typing_rewrite import FlextInfraRefactorTypingUnifierRewriteMixin
    from .class_reconstructor import FlextInfraRefactorClassReconstructor
    from .compatibility_alias import FlextInfraRefactorCompatibilityAlias
    from .dataclass_modelizer import FlextInfraRefactorDataclassModelizer
    from .deprecated_remover import FlextInfraRefactorDeprecatedRemover
    from .future_import import FlextInfraRefactorFutureImport
    from .hardcoded_version import FlextInfraRefactorHardcodedVersion
    from .import_bypass_remover import FlextInfraRefactorImportBypassRemover
    from .import_modernizer import FlextInfraRefactorImportModernizer
    from .lazy_import_fixer import FlextInfraRefactorLazyImportFixer
    from .mro_remover import FlextInfraRefactorMroRemover
    from .open_encoding import FlextInfraRefactorOpenEncoding
    from .pydantic_modernizer import FlextInfraRefactorPydanticModernizer
    from .rope_transformer import FlextInfraRopeTransformer
    from .signature_propagator import FlextInfraRefactorSignaturePropagator
    from .symbol_propagator import FlextInfraRefactorSymbolPropagator
    from .typing_unifier import FlextInfraRefactorTypingUnifier


__all__: tuple[str, ...] = (
    "FlextInfraEnsureCanonicalTImportMixin",
    "FlextInfraRefactorClassReconstructor",
    "FlextInfraRefactorCompatibilityAlias",
    "FlextInfraRefactorDataclassModelizer",
    "FlextInfraRefactorDeprecatedRemover",
    "FlextInfraRefactorFutureImport",
    "FlextInfraRefactorHardcodedVersion",
    "FlextInfraRefactorImportBypassRemover",
    "FlextInfraRefactorImportFacades",
    "FlextInfraRefactorImportModernizer",
    "FlextInfraRefactorLazyImportFixer",
    "FlextInfraRefactorMroRemover",
    "FlextInfraRefactorOpenEncoding",
    "FlextInfraRefactorPydanticModernizer",
    "FlextInfraRefactorSignaturePropagator",
    "FlextInfraRefactorSymbolPropagator",
    "FlextInfraRefactorTypingUnifier",
    "FlextInfraRefactorTypingUnifierRewriteMixin",
    "FlextInfraRopeTransformer",
    "publish_semantic_file_plan",
    "publish_semantic_file_plans",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._canonical_t_import": ("FlextInfraEnsureCanonicalTImportMixin",),
            "._import_facades": ("FlextInfraRefactorImportFacades",),
            "._semantic_publication": (
                "publish_semantic_file_plan",
                "publish_semantic_file_plans",
            ),
            "._typing_rewrite": ("FlextInfraRefactorTypingUnifierRewriteMixin",),
            ".class_reconstructor": ("FlextInfraRefactorClassReconstructor",),
            ".compatibility_alias": ("FlextInfraRefactorCompatibilityAlias",),
            ".dataclass_modelizer": ("FlextInfraRefactorDataclassModelizer",),
            ".deprecated_remover": ("FlextInfraRefactorDeprecatedRemover",),
            ".future_import": ("FlextInfraRefactorFutureImport",),
            ".hardcoded_version": ("FlextInfraRefactorHardcodedVersion",),
            ".import_bypass_remover": ("FlextInfraRefactorImportBypassRemover",),
            ".import_modernizer": ("FlextInfraRefactorImportModernizer",),
            ".lazy_import_fixer": ("FlextInfraRefactorLazyImportFixer",),
            ".mro_remover": ("FlextInfraRefactorMroRemover",),
            ".open_encoding": ("FlextInfraRefactorOpenEncoding",),
            ".pydantic_modernizer": ("FlextInfraRefactorPydanticModernizer",),
            ".rope_transformer": ("FlextInfraRopeTransformer",),
            ".signature_propagator": ("FlextInfraRefactorSignaturePropagator",),
            ".symbol_propagator": ("FlextInfraRefactorSymbolPropagator",),
            ".typing_unifier": ("FlextInfraRefactorTypingUnifier",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
