# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.docs package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports
from flext_infra.docs._auditor_checks import FlextInfraDocAuditorChecksMixin
from flext_infra.docs._auditor_report import FlextInfraDocAuditorReportMixin
from flext_infra.docs._generator_bundle import FlextInfraDocGeneratorBundleMixin
from flext_infra.docs.auditor import FlextInfraDocAuditor
from flext_infra.docs.auditor_mixin import FlextInfraDocAuditorMixin
from flext_infra.docs.base import FlextInfraDocServiceBase
from flext_infra.docs.builder import FlextInfraDocBuilder
from flext_infra.docs.collector import FlextInfraDocCollector
from flext_infra.docs.fixer import FlextInfraDocFixer
from flext_infra.docs.formatter import FlextInfraDocFormatter
from flext_infra.docs.generator import FlextInfraDocGenerator
from flext_infra.docs.server import FlextInfraDocServer
from flext_infra.docs.validator import FlextInfraDocValidator

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
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
