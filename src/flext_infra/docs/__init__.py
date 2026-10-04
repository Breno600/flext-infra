# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra.docs package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
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

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraDocAuditor": (".auditor", "FlextInfraDocAuditor"),
        "FlextInfraDocAuditorChecksMixin": (
            "._auditor_checks",
            "FlextInfraDocAuditorChecksMixin",
        ),
        "FlextInfraDocAuditorMixin": (".auditor_mixin", "FlextInfraDocAuditorMixin"),
        "FlextInfraDocAuditorReportMixin": (
            "._auditor_report",
            "FlextInfraDocAuditorReportMixin",
        ),
        "FlextInfraDocBuilder": (".builder", "FlextInfraDocBuilder"),
        "FlextInfraDocCollector": (".collector", "FlextInfraDocCollector"),
        "FlextInfraDocFixer": (".fixer", "FlextInfraDocFixer"),
        "FlextInfraDocFormatter": (".formatter", "FlextInfraDocFormatter"),
        "FlextInfraDocGenerator": (".generator", "FlextInfraDocGenerator"),
        "FlextInfraDocGeneratorBundleMixin": (
            "._generator_bundle",
            "FlextInfraDocGeneratorBundleMixin",
        ),
        "FlextInfraDocServer": (".server", "FlextInfraDocServer"),
        "FlextInfraDocServiceBase": (".base", "FlextInfraDocServiceBase"),
        "FlextInfraDocValidator": (".validator", "FlextInfraDocValidator"),
    }),
    public_exports=__all__,
)
