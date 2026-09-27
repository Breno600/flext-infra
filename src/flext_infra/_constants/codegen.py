"""Centralized constants for the codegen package.

All constants used across codegen modules are defined here to avoid
duplication and ensure single-source-of-truth for configuration values.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from enum import StrEnum, unique
from typing import TYPE_CHECKING, ClassVar

from .._constants.codegen_detection import FlextInfraConstantsCodegenDetection
from .._constants.codegen_lazy import FlextInfraConstantsCodegenLazy
from .._constants.codegen_render_names import FlextInfraConstantsCodegenRenderNames
from .workspace import FlextInfraConstantsWorkspace

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsCodegen(
    FlextInfraConstantsCodegenLazy,
    FlextInfraConstantsCodegenDetection,
    FlextInfraConstantsCodegenRenderNames,
):
    """Namespace for all codegen-related constants."""

    ARTIFACT_SPECS: ClassVar[t.VariadicTuple[t.Pair[str, int]]] = (
        ("bin/mise", 0o755),
        ("bin/mise.cmd", 0o644),
    )

    CONFIG_SPEC: ClassVar[t.Pair[str, int]] = (
        FlextInfraConstantsWorkspace.MISE_TOML_FILENAME,
        0o644,
    )

    PUBLICATION_SPECS: ClassVar[t.VariadicTuple[t.Pair[str, int]]] = (
        CONFIG_SPEC,
        *ARTIFACT_SPECS,
    )

    ARTIFACT_NAMES: ClassVar[t.VariadicTuple[str]] = tuple(
        name for name, _mode in ARTIFACT_SPECS
    )

    JOURNAL_NAME: ClassVar[str] = "flext-infra-codegen-transaction-journal.json"

    JOURNAL_MODE: ClassVar[int] = 0o600

    JOURNAL_LEASE_WAIT_SECONDS: ClassVar[float] = 1800.0
    """Bounded polite wait for a held lease before failing loud.

    A legitimate fleet ``make gen`` holds the lease for minutes; an immediate
    non-blocking refusal turned ordinary multi-agent traffic into a spurious
    ``JournalLeaseTimeoutError`` (flext-c2kp3). The wait is bounded so a truly
    wedged holder still fails loud instead of hanging forever.
    """

    JOURNAL_LEASE_POLL_SECONDS: ClassVar[float] = 1.0
    """Polling interval while waiting for a held journal lease."""

    TRANSACTION_DIR_PREFIX: ClassVar[str] = "transaction-"

    TRANSACTION_ID_LENGTH: ClassVar[int] = 32

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
    "Base module definitions for tests/: (filename, class_suffix, base_class, docstring)."
    # flext-wkii.14 (agent: codegen) — canonical root config/settings pair: a
    # private `_config.py`/`_settings.py` module exporting the singleton.
    # Consumed by the scaffold generator (flext-wkii.10).
    RUNTIME_MODULES: ClassVar[t.VariadicTuple[t.Quad[str, str, str, str]]] = (
        ("_config.py", "Config", "FlextConfig", "Runtime config"),
        ("_settings.py", "Settings", "FlextSettings", "Runtime settings"),
    )
    "Runtime singleton modules for src/: (filename, class_suffix, base_class, docstring)."
    VIOLATION_PATTERN: ClassVar[t.RegexPattern] = re.compile(
        r"\[(?P<rule>NS-(?:[A-Z]+|\d{3}))-\d{3}\]\s+"
        r"(?P<module>[^:]+):(?P<line>\d+)\s+\u2014\s+(?P<message>.+)"
    )
    "Regex to parse violation strings: [NS-RULE-NNN] path:line — message."
    MISE_RELEASE_COMPONENT_COUNT: ClassVar[int] = 3
    "Number of numeric components in a generated Mise release version."
    MISE_LAUNCHER_DIRECTORY: ClassVar[str] = "bin"
    "Directory that owns generated runtime Mise launchers."
    MISE_UNIX_LAUNCHER_FILENAME: ClassVar[str] = "mise"
    "Canonical Unix Mise launcher filename."
    MISE_WINDOWS_LAUNCHER_FILENAME: ClassVar[str] = "mise.cmd"
    "Canonical Windows Mise launcher filename."
    "UTC basic stamp for `{filename}.{stamp}.bak` written before gen apply."
    CODEGEN_TRANSACTION_LOCK_FILENAME: ClassVar[str] = "flext-infra-codegen.lock"
    "Worktree-specific administrative lock for complete generation."
    CODEGEN_TRANSACTION_LOCK_MODE: ClassVar[int] = 0o600
    "Owner-private mode required for the generation lock."
    MISE_BOOTSTRAP_SEED_DIRECTORY: ClassVar[str] = "templates/bootstrap"
    "Package-local bootstrap seed directory for the authenticated launcher."
    MISE_UNLOCKED_RESOLUTION_URL: ClassVar[str] = (
        "https://github.com/jdx/mise/releases/latest"
    )
    "Upstream resolution endpoint the unlocked launcher must carry."
    MISE_UNLOCKED_FAIL_LOUD_CLAUSE: ClassVar[str] = (
        "could not resolve the latest mise release"
    )
    "Fail-loud clause emitted when the releases/latest resolution fails."
    MISE_UNLOCKED_CHECKSUM_URI: ClassVar[str] = "SHASUMS256.txt"
    "Release checksum payload the unlocked launcher always verifies."
    MISE_BOOTSTRAP_STORAGE_ROOT_VARIABLE: ClassVar[str] = "MISE_DATA_DIR"
    "Required caller-owned persistent root for generated Mise setup."
    MISE_BOOTSTRAP_FIXED_ENVIRONMENT: ClassVar[t.VariadicTuple[t.Pair[str, str]]] = (
        ("GIT_CONFIG_NOSYSTEM", "1"),
        ("GIT_TERMINAL_PROMPT", "0"),
        ("LANG", "C"),
        ("LC_ALL", "C"),
        ("MISE_SAFE", "1"),
        ("MISE_PARANOID", "true"),
        ("MISE_QUIET", "1"),
        ("MISE_NO_ENV", "1"),
        ("MISE_NO_HOOKS", "1"),
        ("MISE_AUTO_ENV", "false"),
        ("MISE_AUTO_INSTALL", "false"),
        ("MISE_EXEC_AUTO_INSTALL", "false"),
        ("MISE_TASK_RUN_AUTO_INSTALL", "false"),
        ("MISE_AUTO_UPDATE", "false"),
        ("MISE_HTTP_RETRIES", "0"),
        ("MISE_NETRC", "false"),
        ("MISE_NOT_FOUND_AUTO_INSTALL", "false"),
        ("MISE_NOT_FOUND_SYSTEM_FALLBACK", "false"),
        ("MISE_OVERRIDE_CONFIG_FILENAMES", ".mise.toml"),
        ("MISE_OVERRIDE_TOOL_VERSIONS_FILENAMES", "none"),
        ("MISE_GITHUB_GH_CLI_TOKENS", "false"),
        ("MISE_GITHUB_USE_GIT_CREDENTIALS", "false"),
        ("MISE_GITHUB_OAUTH_CLIENT_ID", ""),
        ("MISE_GITHUB_OAUTH_EXPORT_ENV", ""),
        ("MISE_GITHUB_OAUTH_OPEN_BROWSER", "false"),
    )
    "Fixed fail-closed settings shared by every generated Mise invocation."
    MISE_BOOTSTRAP_TRANSIENT_ENVIRONMENT: ClassVar[
        t.VariadicTuple[t.Pair[str, str]]
    ] = (
        ("HOME", "home"),
        ("USERPROFILE", "home"),
        ("APPDATA", "appdata"),
        ("LOCALAPPDATA", "appdata"),
        ("XDG_CONFIG_HOME", "xdg-config"),
        ("XDG_DATA_HOME", "xdg-data"),
        ("XDG_CACHE_HOME", "xdg-cache"),
        ("XDG_STATE_HOME", "xdg-state"),
        ("NETRC", "netrc"),
        ("GIT_CONFIG_GLOBAL", "gitconfig"),
        ("MISE_NETRC_FILE", "netrc"),
        ("MISE_GLOBAL_CONFIG_FILE", "global-config.toml"),
        ("MISE_CONFIG_DIR", "config"),
        ("MISE_TMP_DIR", "tmp"),
        ("MISE_GLOBAL_CONFIG_ROOT", "."),
        ("MISE_SYSTEM_CONFIG_DIR", "system-config"),
        ("MISE_SYSTEM_CONFIG_FILE", "system-config/config.toml"),
        ("MISE_SYSTEM_DATA_DIR", "system-data"),
        ("MISE_SYSTEM_INSTALLS_DIR", "system-installs"),
        ("MISE_SYSTEM_SHIMS_DIR", "system-shims"),
        ("TMPDIR", "tmp"),
        ("TMP", "tmp"),
        ("TEMP", "tmp"),
    )
    "Environment paths rooted in one invocation-local private directory."
    MISE_BOOTSTRAP_PERSISTENT_ENVIRONMENT: ClassVar[
        t.VariadicTuple[t.Pair[str, str]]
    ] = (
        ("MISE_DATA_DIR", "."),
        ("MISE_CACHE_DIR", "cache"),
        ("MISE_STATE_DIR", "state"),
        ("MISE_INSTALLS_DIR", "installs"),
        ("MISE_SHIMS_DIR", "shims"),
        ("UV_CACHE_DIR", "uv-cache"),
    )
    "Tool and package caches rooted in the required persistent storage directory."
    MISE_BOOTSTRAP_EMPTY_FILES: ClassVar[t.VariadicTuple[str]] = (
        "global-config.toml",
        "system-config/config.toml",
        "gitconfig",
        "netrc",
    )
    "Private empty files that disable ambient configuration and netrc discovery."
    MISE_BOOTSTRAP_PASSTHROUGH_ENVIRONMENT: ClassVar[t.VariadicTuple[str]] = (
        "PATH",
        "COMSPEC",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        # Credential and network-policy keys the lock-time provenance fetch
        # requires: without them the shared-host GitHub rate limit fails the
        # lock generation closed. Reinjection stays explicit (allowlist).
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "MISE_GITHUB_TOKEN",
        "MISE_GITHUB_CREDENTIAL_COMMAND",
        "MISE_HTTP_TIMEOUT",
        # Launcher pin knob: hosts whose curl resolves through Mise shims
        # cannot resolve "latest" inside the sanitized bootstrap env; an
        # explicit MISE_VERSION skips that resolution entirely.
        "MISE_VERSION",
    )
    "Only host environment keys eligible for explicit reinjection."

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
    QG_CHECK_FLEXT_VALIDITY: ClassVar[str] = "flext_validity"
    QG_CHECK_IMPORT_RESOLUTION: ClassVar[str] = "import_resolution"
    QG_CHECK_LAYER_COMPLIANCE: ClassVar[str] = "layer_compliance"
    QG_CHECK_DUPLICATION_REDUCTION: ClassVar[str] = "duplication_reduction"
    QG_CHECK_TYPE_SAFETY: ClassVar[str] = "type_safety"
    QG_CHECK_LINT_CLEAN: ClassVar[str] = "lint_clean"


__all__: list[str] = ["FlextInfraConstantsCodegen"]
