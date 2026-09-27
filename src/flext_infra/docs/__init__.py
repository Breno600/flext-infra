# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.docs package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from ._auditor_checks import FlextInfraDocAuditorChecksMixin
    from ._auditor_report import FlextInfraDocAuditorReportMixin
    from ._generator_bundle import FlextInfraDocGeneratorBundleMixin
    from .auditor import FlextInfraDocAuditor
    from .auditor_mixin import FlextInfraDocAuditorMixin
    from .base import FlextInfraDocServiceBase
    from .builder import FlextInfraDocBuilder
    from .collector import FlextInfraDocCollector
    from .fixer import FlextInfraDocFixer
    from .formatter import FlextInfraDocFormatter
    from .generator import FlextInfraDocGenerator
    from .server import FlextInfraDocServer
    from .validator import FlextInfraDocValidator


__all__: tuple[str, ...] = (
    "FlextInfraDocAuditor",
    "FlextInfraDocAuditorChecksMixin",
    "FlextInfraDocAuditorMixin",
    "FlextInfraDocAuditorReportMixin",
    "FlextInfraDocBuilder",
    "FlextInfraDocCollector",
    "FlextInfraDocFixer",
    "FlextInfraDocFormatter",
    "FlextInfraDocGenerator",
    "FlextInfraDocGeneratorBundleMixin",
    "FlextInfraDocServer",
    "FlextInfraDocServiceBase",
    "FlextInfraDocValidator",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            "._auditor_checks": ("FlextInfraDocAuditorChecksMixin",),
            "._auditor_report": ("FlextInfraDocAuditorReportMixin",),
            "._generator_bundle": ("FlextInfraDocGeneratorBundleMixin",),
            ".auditor": ("FlextInfraDocAuditor",),
            ".auditor_mixin": ("FlextInfraDocAuditorMixin",),
            ".base": ("FlextInfraDocServiceBase",),
            ".builder": ("FlextInfraDocBuilder",),
            ".collector": ("FlextInfraDocCollector",),
            ".fixer": ("FlextInfraDocFixer",),
            ".formatter": ("FlextInfraDocFormatter",),
            ".generator": ("FlextInfraDocGenerator",),
            ".server": ("FlextInfraDocServer",),
            ".validator": ("FlextInfraDocValidator",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
