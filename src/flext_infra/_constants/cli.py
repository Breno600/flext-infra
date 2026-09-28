"""CLI-related constants for flext-infra.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsCli:
    """Shared CLI flag vocabularies and route tables."""

    PROCESS_SUCCESS_EXIT_CODE: ClassVar[int] = 0
    "Exit code reported by a command group that completed successfully."
    PROCESS_TIMEOUT_EXIT_CODE: ClassVar[int] = 124
    "Exit code emitted by the canonical wall-time limiter."
    PROCESS_COMMAND_NOT_FOUND_EXIT_CODE: ClassVar[int] = 127
    "POSIX shell exit code for an executable that could not be located or started."
    PROCESS_SIGNAL_EXIT_OFFSET: ClassVar[int] = 128
    "POSIX shell offset used to encode a terminating signal."
    PROCESS_EXIT_ERROR_CODE: ClassVar[str] = "EXTERNAL_PROCESS_EXIT"
    "Stable result error code for non-zero external process exits."

    _SHARED_BOOL_FLAG_VALUES: ClassVar[t.VariadicTuple[str]] = (
        "--apply",
        "--check",
        "--check-only",
        "--dry-run",
        "--fail-fast",
        "--verbose",
        "--quiet",
        "--no-fail",
        "--typings",
        "--apply-typings",
        "--no-pip-check",
        "--skip-check",
        "--skip-comments",
        "--audit",
        "--rewrite-constraints",
    )
    _SHARED_VALUE_FLAG_VALUES: ClassVar[t.VariadicTuple[str]] = (
        "--checks",
        "--docstring-min",
        "--repository-root",
        "--projects",
        "--project",
        "--module",
        "--namespace",
        "--gates",
        "--what",
        "--format",
        "--output",
        "--report",
        "--output-dir",
        "--json-output",
        "--reports-dir",
        "--ruff-args",
        "--pyright-args",
        "--operation",
        "--branch",
        "--base",
        "--signer",
        "--allowed-signers",
        "--expected-gates",
        "--commit-sha",
        "--output",
    )
    SHARED_BOOL_FLAGS: ClassVar[frozenset[str]] = frozenset(_SHARED_BOOL_FLAG_VALUES)
    SHARED_VALUE_FLAGS: ClassVar[frozenset[str]] = frozenset(_SHARED_VALUE_FLAG_VALUES)
    CLI_GROUP_DESCRIPTIONS: ClassVar[t.StrMapping] = MappingProxyType({
        "check": "Lint gates and pyrefly settings management",
        "codegen": "Code generation and workspace standardization",
        "validate": "Infrastructure validators and diagnostics",
        "deps": "Dependency detection and modernization",
        "docs": "Documentation audit, fix, build, generate, validate",
        "maintenance": "Python version enforcement",
        "refactor": "Declarative refactoring and modernization",
        "release": "Release orchestration",
        "workspace": "Workspace detection and orchestration",
    })


__all__: t.VariadicTuple[str] = ("FlextInfraConstantsCli",)
