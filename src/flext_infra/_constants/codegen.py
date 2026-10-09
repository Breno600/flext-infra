"""Centralized constants for the codegen package.

All constants used across codegen modules are defined here to avoid
duplication and ensure single-source-of-truth for configuration values.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from enum import StrEnum, unique
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from flext_infra._constants.codegen_detection import FlextInfraConstantsCodegenDetection
from flext_infra._constants.codegen_lazy import FlextInfraConstantsCodegenLazy
from flext_infra._constants.codegen_render_names import (
    FlextInfraConstantsCodegenRenderNames,
)
from flext_infra._constants.workspace import FlextInfraConstantsWorkspace

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsCodegen(
    FlextInfraConstantsCodegenLazy,
    FlextInfraConstantsCodegenDetection,
    FlextInfraConstantsCodegenRenderNames,
):
    """Namespace for all codegen-related constants."""

    MISE_ARTIFACTS_STATE_DIRECTORY: ClassVar[Path] = Path(".state") / "mise-artifacts"

    CONFIG_SPEC: ClassVar[t.Pair[str, int]] = (
        FlextInfraConstantsWorkspace.MISE_TOML_FILENAME,
        0o644,
    )

    JOURNAL_NAME: ClassVar[str] = "flext-infra-codegen-transaction-journal.json"

    JOURNAL_MODE: ClassVar[int] = 0o600

    JOURNAL_LEASE_WAIT_SECONDS: ClassVar[float] = 1800.0
    """Bounded polite wait for a held lease before failing loud.

    A legitimate fleet ``make gen`` holds the lease for minutes; an immediate
    non-blocking refusal turned ordinary concurrent traffic into a spurious
    ``JournalLeaseTimeoutError``. The wait is bounded so a truly
    wedged holder still fails loud instead of hanging forever.
    """

    JOURNAL_LEASE_POLL_SECONDS: ClassVar[float] = 1.0
    """Polling interval while waiting for a held journal lease."""

    TRANSACTION_DIR_PREFIX: ClassVar[str] = "transaction-"

    TRANSACTION_ID_LENGTH: ClassVar[int] = 32

    FACADE_MODULE_PARTS: ClassVar[int] = 2
    """Dotted parts of the ``package.module`` a type facade destination names."""

    SRC_MODULES: ClassVar[t.VariadicTuple[t.Quad[str, str, str, str]]] = (
        ("constants.py", "Constants", "FlextConstants", "Constants"),
        ("typings.py", "Types", "FlextTypes", "Type aliases"),
        ("protocols.py", "Protocols", "FlextProtocols", "Protocol definitions"),
        ("models.py", "Models", "FlextModels", "Domain models"),
        ("utilities.py", "Utilities", "FlextUtilities", "Utility functions"),
    )
    "Base module definitions for src/: (filename, class_suffix, base_class, docstring)."
    TESTS_MODULES: ClassVar[t.VariadicTuple[t.Quad[str, str, str, str]]] = (
        ("constants.py", "Constants", "FlextTestsConstants", "Test constants"),
        ("typings.py", "Types", "FlextTestsTypes", "Test type aliases"),
        ("protocols.py", "Protocols", "FlextTestsProtocols", "Test protocols"),
        ("models.py", "Models", "FlextTestsModels", "Test models"),
        ("utilities.py", "Utilities", "FlextTestsUtilities", "Test utilities"),
    )
    "Base module definitions for tests/: (filename, class_suffix, base_class, doc)."
    # Canonical root config/settings pair: a
    # private `_config.py`/`_settings.py` module exporting the singleton.
    # Consumed by the scaffold generator.
    RUNTIME_MODULES: ClassVar[t.VariadicTuple[t.Quad[str, str, str, str]]] = (
        ("_config.py", "Config", "FlextConfig", "Runtime config"),
        ("_settings.py", "Settings", "FlextSettings", "Runtime settings"),
    )
    "Runtime singleton modules for src/: (filename, class_suffix, base_class, doc)."
    VIOLATION_PATTERN: ClassVar[t.RegexPattern] = re.compile(
        r"\[(?P<rule>[a-z0-9][a-z0-9-]*)\]\s+"
        r"(?P<module>[^:]+):(?P<line>\d+)\s+\u2014\s+(?P<message>.+)",
    )
    "Regex to parse violation strings: [rule-id] path:line — message."
    PROTOCOL_MODEL_MINIMAL_BODY_LINES: ClassVar[int] = 3
    "Header lines of a generated protocol class; at or below it the body is empty."
    MISE_RELEASE_COMPONENT_COUNT: ClassVar[int] = 3
    "Number of numeric components in a generated Mise release version."
    MISE_RELEASE_PATTERN: ClassVar[str] = (
        rf"[0-9]+(\.[0-9]+){{{MISE_RELEASE_COMPONENT_COUNT - 1}}}"
    )
    "Resolved-release grammar consumed by Python and generated shell boundaries."
    CODEGEN_TRANSACTION_LOCK_FILENAME: ClassVar[str] = "flext-infra-codegen.lock"
    "Worktree-specific administrative lock for complete generation."
    CODEGEN_TRANSACTION_LOCK_MODE: ClassVar[int] = 0o600
    "Owner-private mode required for the generation lock."

    # --- Pipeline stage StrEnum (was: class Pipeline plain strings) ---
    @unique
    class PipelineStage(StrEnum):
        """Canonical codegen pipeline stage identifiers."""

        DISCOVER = "discover"
        TOOLCHAIN = "toolchain"
        PY_TYPED = "py_typed"
        CENSUS_BEFORE = "census_before"
        SCAFFOLD = "scaffold"
        AUTO_FIX = "auto_fix"
        DEPS = "deps"
        LAZY_INIT = "lazy_init"
        CENSUS_AFTER = "census_after"

    PIPELINE_STAGE_ORDER: ClassVar[t.VariadicTuple[PipelineStage]] = (
        PipelineStage.DISCOVER,
        PipelineStage.TOOLCHAIN,
        PipelineStage.PY_TYPED,
        PipelineStage.CENSUS_BEFORE,
        PipelineStage.SCAFFOLD,
        PipelineStage.AUTO_FIX,
        PipelineStage.DEPS,
        PipelineStage.LAZY_INIT,
        PipelineStage.CENSUS_AFTER,
    )
    "Ordered sequence of pipeline stage identifiers."
    PIPELINE_KEY_DRY_RUN: ClassVar[str] = "dry_run"
    "Config key for pipeline dry-run mode."

    # --- Quality gate constants (was: class QualityGate) ---
    QG_REPORT_DIR: ClassVar[str] = ".reports/codegen/constants-quality-gate"
    "Report directory for constants quality gate."
    QG_CHECK_NAMESPACE_COMPLIANCE: ClassVar[str] = "namespace_compliance"
    QG_CHECK_DUPLICATION_REDUCTION: ClassVar[str] = "duplication_reduction"
    QG_CHECK_TYPE_SAFETY: ClassVar[str] = "type_safety"
    QG_CHECK_LINT_CLEAN: ClassVar[str] = "lint_clean"


__all__: list[str] = ["FlextInfraConstantsCodegen"]
