"""Lazy-init constants for the codegen package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsCodegenLazy:
    """Lazy-init and export-policy constants for codegen."""

    MANIFEST_API_VERSION: ClassVar[str] = "flext-infra/projections-lock/v1"
    "Version tag of the projected ``.agents/projections.lock.json`` contract."
    MANIFEST_FILENAME: ClassVar[str] = "projections.lock.json"
    "Projection lock filename emitted beside the lazy-init projections."
    PROJECTED_ROOTS: ClassVar[frozenset[str]] = frozenset({".agents", ".codex"})
    "Roots whose projected files carry a manifest entry."
    MAX_ALIAS_LENGTH: ClassVar[int] = 2
    "Maximum length of a public facade alias."
    AUTOGEN_HEADER: ClassVar[str] = "# AUTO-GENERATED FILE — Regenerate with: make gen"
    "Header prepended to every auto-generated ``__init__.py`` file."
    AUTOGEN_HEADERS: ClassVar[t.Pair[str, str]] = (
        AUTOGEN_HEADER,
        "# @generated AUTO-GENERATED FILE — Regenerate with: make gen",
    )
    "Current and former generated initializer headers accepted during migration."
    ROOT_EXPORTS_FILENAME: ClassVar[str] = "_exports.py"
    "Root public ABI contract module consumed by lazy-init planning."
    ROOT_EXPORTS_DIR: ClassVar[str] = "_constants"
    "Directory under each package where lazy-init registries must live."
    GENERATED_EXPORT_SIDECAR_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?:_exports(?:_lazy(?:_part_[0-9]+)?)?|_lazy_exports)\.py$",
    )
    "Regex matching every generated lazy-export sidecar filename "
    "(``_exports.py``, ``_exports_lazy.py``, ``_exports_lazy_part_N.py``, "
    "``_lazy_exports.py``); legacy variants are excluded from discovery and cleanup."
    OBSOLETE_ROOT_SUPPORT_NAMES: ClassVar[frozenset[str]] = frozenset({
        "_root_exports",
        "_root_exports_parts",
        "_root_typing",
        "_root_typing_parts",
    })
    "Closed set of retired root registry module and package names."
    LAZY_BOOTSTRAP_HELPERS: ClassVar[t.VariadicTuple[str]] = (
        "build_lazy_import_map",
        "install_lazy_exports",
    )
    "Lazy helpers every initializer imports; the bootstrap root publishes them."
    ROOT_TEMPLATE_BINDINGS: ClassVar[frozenset[str]] = frozenset({
        "MappingProxyType",
        "TYPE_CHECKING",
        *LAZY_BOOTSTRAP_HELPERS,
    })
    "Names the root initializer template binds; only the helpers are ever published."
    TEST_ONLY_SOURCE_MODULE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?:_?test(?:_[A-Za-z0-9_]+)?|[A-Za-z0-9_]+_tests?)\.py$",
    )
    "Test-module filenames forbidden from installable package export maps."
    # Cleanup is the only owner of retired init artifacts.
    OBSOLETE_GENERATED_INIT_FILES: ClassVar[t.StrSequence] = ("__unit__.py",)
    "Generated initializer artifacts removed during every codegen pass."
    INIT_PYI: ClassVar[str] = "__init__.pyi"
    "Typing stub paired with generated thin package initializers."
    ROOT_PUBLIC_EXPORTS_SUFFIX: ClassVar[str] = "_PUBLIC_EXPORTS"
    "Suffix for tuple constants that declare frozen public root exports."
    ALL_SCAN_PATTERNS: ClassVar[t.StrSequence] = (
        "src/**/__init__.py",
        "tests/**/__init__.py",
        "examples/**/__init__.py",
    )
    """Glob patterns for all directories the lazy-init generator scans.

    ``scripts/`` is deliberately absent: its modules are entry points, each
    owning its own ``main``, not a package whose names a generated initializer
    should re-export.
    """
    NON_PUBLIC_LAZY_ROOTS: ClassVar[frozenset[str]] = frozenset({
        "examples",
        "scripts",
        "tests",
    })
    "Root import surfaces generated as private lazy plumbing, not public ABI."
    WRAPPER_NAMESPACE_DEPTH: ClassVar[int] = 2
    "Dotted depth of a namespace package under a governed wrapper surface."
    # Pytest must register fixture plugins before importing
    # them, so their private package initializer is always side-effect free.
    # Real cycle exceptions are the bootstrap packages imported while
    # ``flext_core.lazy`` initializes; importing them with a lazy facade would
    # re-enter the partially-initialized module and fail.
    BOOTSTRAP_CYCLE_EXCEPTION_SEGMENTS: ClassVar[frozenset[str]] = frozenset({
        "_lazy_parts",
        "_typings",
    })
    "Package segments whose initializer must remain empty to avoid bootstrap cycles."

    # The bootstrap-owning distribution's generated initializers open with
    # `from flext_core.lazy import ...`, so a package that `flext_core.lazy`
    # itself reaches at module scope cannot carry one: importing it would
    # re-enter the module that is still initializing and fail with "cannot
    # import name 'build_lazy_import_map' from partially initialized module
    # 'flext_core.lazy'". `flext_core.lazy` pulls `._lazy_parts`, which pulls
    # `._typings`, which reaches the other private facets, so the whole private
    # surface of the bootstrap-owning distribution keeps side-effect-free
    # initializers. Every OTHER distribution imports the helpers from the
    # `flext_core` root, which publishes them, never from its submodule.
    LAZY_BOOTSTRAP_ROOT_PACKAGE: ClassVar[str] = "flext_core"
    LAZY_BOOTSTRAP_MODULE: ClassVar[str] = "flext_core.lazy"
    "Module defining the lazy helpers; only the bootstrap owner imports it directly."

    BARE_IMPORT_FROM_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^from\s+import\s",
        re.MULTILINE,
    )
    "Regex: malformed ``from import`` statement (missing module name)."

    LINT_TOOLS: ClassVar[t.StrSequencePairTuple] = (
        # Ruff runs with NO --select override: the project's pyproject.toml
        # (select=ALL + narrow whitelist + preview) is the ONLY rule policy.
        ("ruff", ("ruff", "check", "{file}", "--no-fix")),
        ("pyright", ("pyright", "{file}")),
        ("mypy", ("mypy", "{file}", "--no-error-summary")),
        ("pyrefly", ("pyrefly", "check", "{file}")),
    )
    "Lint tool names and their CLI command templates for validation."
    LOCAL_INFERRED_SEGMENTS: ClassVar[frozenset[str]] = frozenset({
        "_constants",
        "_exceptions",
        "_models",
        "_protocols",
        "_typings",
        "_utilities",
        "constants",
        "exceptions",
        "models",
        "protocols",
        "typings",
        "utilities",
        "services",
        "docs",
        "tools",
    })
    "Module segments recognized as local inferred imports in lazy-load chain."
    PUBLIC_ROOT_MODULE_EXPORTS: ClassVar[frozenset[str]] = frozenset()
    "Internal child packages exported at the root as module objects only."
    INFRA_ONLY_EXPORTS: ClassVar[frozenset[str]] = frozenset({
        "cleanup_submodule_namespace",
        "lazy_getattr",
        "logger",
        "merge_lazy_imports",
        "output",
        "output_reporting",
        "pytest_addoption",
        "pytest_collect_file",
        "pytest_collection_modifyitems",
        "pytest_configure",
        "pytest_runtest_setup",
        "pytest_runtest_teardown",
        "pytest_sessionfinish",
        "pytest_sessionstart",
        "pytest_terminal_summary",
        "pytest_warning_recorded",
    })
    "Exports excluded from package __init__.py auto-export."
    PUBLISHED_ALL_EXCLUDE: ClassVar[frozenset[str]] = frozenset({
        "lazy",
        "normalize_lazy_imports",
    })
    # These remain direct inline lazy imports without
    # widening the explicit wildcard contract or requiring root sidecars.
    "Public-module symbols withheld from generated root-facade __all__."
    PUBLIC_ROOT_ALIAS_ORDER: ClassVar[t.StrSequence] = (
        "c",
        "t",
        "p",
        "m",
        "u",
        "d",
        "e",
        "h",
        "r",
        "s",
        "x",
        "infra",
        "main",
    )
    "Canonical dependency order for public aliases and operational entry points."
    ROOT_WRAPPER_SEGMENTS: ClassVar[frozenset[str]] = frozenset({
        "docs",
        "src",
        "tests",
        "examples",
        "scripts",
    })
    "Directory segments recognized as project-root wrapper paths."
    TEST_RUNTIME_ALIAS_TARGETS: ClassVar[t.MappingKV[str, t.StrPair]] = (
        MappingProxyType({
            "c": ("flext_tests", "c"),
            "d": ("flext_tests", "d"),
            "e": ("flext_tests", "e"),
            "h": ("flext_tests", "h"),
            "m": ("flext_tests", "m"),
            "p": ("flext_tests", "p"),
            "r": ("flext_tests", "r"),
            "s": ("flext_tests", "s"),
            "t": ("flext_tests", "t"),
            "td": ("flext_tests", "td"),
            "tf": ("flext_tests", "tf"),
            "tk": ("flext_tests", "tk"),
            "tm": ("flext_tests", "tm"),
            "u": ("flext_tests", "u"),
            "x": ("flext_tests", "x"),
        })
    )
    "Mapping of test-only aliases to flext-tests runtime targets."


__all__: list[str] = ["FlextInfraConstantsCodegenLazy"]
