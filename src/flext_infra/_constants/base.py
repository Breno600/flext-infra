"""Base constants for flext-infra project.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from enum import StrEnum, unique
from typing import TYPE_CHECKING, ClassVar

from .make import FlextInfraConstantsMake
from .source_code import FlextInfraConstantsSourceCode
from .validate import FlextInfraConstantsSharedInfra

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsBase(
    FlextInfraConstantsSharedInfra,
    FlextInfraConstantsMake,
    FlextInfraConstantsSourceCode,
):
    """Base constants for flext-infra project."""

    @unique
    class DependencyGroup(StrEnum):
        """Canonical pyproject dependency-group names."""

        DEV = "dev"
        DOCS = "docs"
        SECURITY = "security"
        TEST = "test"
        TYPINGS = "typings"

    @unique
    class ScopeLevel(StrEnum):
        """Scope-resolution granularity enum for refactor selectors."""

        MODULE = "module"
        NAMESPACE = "namespace"
        PROJECT = "project"
        PROJECTS = "projects"
        FILES = "files"
        WORKSPACE = "workspace"

    # TOML section/key names for pyproject.toml parsing

    TOOL: ClassVar[str] = "tool"
    "Top-level [tool] section key."
    POETRY: ClassVar[str] = "poetry"
    "Poetry tool subsection key."
    PROJECT: ClassVar[str] = "project"
    "Top-level [project] section key."
    DEPENDENCIES: ClassVar[str] = "dependencies"
    "Dependencies key within project or poetry sections."
    DEPENDENCY_GROUPS: ClassVar[str] = "dependency-groups"
    "PEP 735 dependency-groups table key."
    OPTIONAL_DEPENDENCIES: ClassVar[str] = "optional-dependencies"
    "Optional dependencies key within [project]."
    GROUP: ClassVar[str] = "group"
    "Poetry group key for dependency groups."
    NAME: ClassVar[str] = "name"
    "Project/package name key."
    VERSION: ClassVar[str] = "version"
    "Project release version key within [project]."
    PACKAGE_IMPORT_NAME: ClassVar[str] = "flext_infra"
    "Canonical import package name for flext-infra itself."
    WORKSPACE_FINGERPRINT_READ_CHUNK_BYTES: ClassVar[int] = 1024 * 1024
    "Bounded read size used while hashing workspace files."
    PYREFLY: ClassVar[str] = "pyrefly"
    "Pyrefly tool section key."
    MYPY: ClassVar[str] = "mypy"
    "Mypy tool section key."
    PYRIGHT: ClassVar[str] = "pyright"
    "Pyright tool section key."
    PYRIGHT_LANGSERVER: ClassVar[str] = "pyright-langserver"
    "Pyright Language Server Protocol executable."
    PYTEST: ClassVar[str] = "pytest"
    "Pytest tool section key."
    RUFF: ClassVar[str] = "ruff"
    "Ruff tool section key."
    DEPTRY: ClassVar[str] = "deptry"
    "Deptry tool section key."
    ISORT: ClassVar[str] = "isort"
    "Isort tool section key (ruff.lint.isort)."
    INI_OPTIONS: ClassVar[str] = "ini_options"
    "Pytest ini_options subsection key."
    LINT_SECTION: ClassVar[str] = "lint"
    "Ruff lint subsection key."
    SEARCH_PATH: ClassVar[str] = "search-path"
    "Pyrefly search-path settings key."
    PROJECT_EXCLUDES: ClassVar[str] = "project-excludes"
    "Pyrefly project-excludes settings key."
    SUB_CONFIG: ClassVar[str] = "sub-settings"
    "Pyrefly sub-settings key."
    EXTRA_PATHS: ClassVar[str] = "extraPaths"
    "Pyright extra paths settings key."
    REPORT_PRIVATE_USAGE: ClassVar[str] = "reportPrivateUsage"
    "Pyright execution-environment private-usage settings key."
    VENV_PATH: ClassVar[str] = "venvPath"
    "Pyright virtualenv base path settings key."
    PYTHON_VERSION_HYPHEN: ClassVar[str] = "python-version"
    "Pyrefly/pyright python-version settings key (hyphenated)."
    PYTHON_VERSION_FILENAME: ClassVar[str] = ".python-version"
    "Interpreter-selection file consumed by pyenv/asdf/mise."
    TAPLO_CONFIG_FILENAME: ClassVar[str] = ".taplo.toml"
    "Taplo workspace formatting configuration filename."
    PYTHON_VERSION_UNDERSCORE: ClassVar[str] = "python_version"
    "Mypy python_version settings key (underscored)."
    EXTEND: ClassVar[str] = "extend"
    "Ruff extend settings key."
    KNOWN_FIRST_PARTY_HYPHEN: ClassVar[str] = "known-first-party"
    "Ruff isort known-first-party key (hyphenated)."
    KNOWN_FIRST_PARTY_UNDERSCORE: ClassVar[str] = "known_first_party"
    "Ruff isort known_first_party key (underscored)."
    MINVERSION: ClassVar[str] = "minversion"
    "Pytest minversion settings key."
    FLEXT_SLOW_TIMEOUT_SECONDS: ClassVar[str] = "flext_slow_timeout_seconds"
    "Enforcement-plugin ini key carrying the config-owned slow-item budget."
    ASYNCIO_DEFAULT_FIXTURE_LOOP_SCOPE: ClassVar[str] = (
        "asyncio_default_fixture_loop_scope"
    )
    "Pytest-asyncio ini key selecting the asynchronous fixture event-loop scope."
    PYTHON_CLASSES: ClassVar[str] = "python_classes"
    "Pytest python_classes settings key."
    PYTHON_FILES: ClassVar[str] = "python_files"
    "Pytest python_files settings key."
    ADDOPTS: ClassVar[str] = "addopts"
    "Pytest addopts settings key."
    MARKERS: ClassVar[str] = "markers"
    "Pytest markers settings key."
    PLUGINS: ClassVar[str] = "plugins"
    "Mypy plugins settings key."
    DISABLE_ERROR_CODE: ClassVar[str] = "disable_error_code"
    "Mypy disable_error_code settings key."
    IGNORE: ClassVar[str] = "ignore"
    "Pyrefly/sub-settings ignore key."
    INCLUDE: ClassVar[str] = "include"
    "Generic include key."
    EXCLUDE: ClassVar[str] = "exclude"
    "Generic exclude key."
    PROJECT_INCLUDES: ClassVar[str] = "project-includes"
    "Pyrefly project-includes settings key."
    PATH: ClassVar[str] = "path"
    "Path key within dependency entries."
    ERROR: ClassVar[str] = "error"
    "Deptry JSON error field key."
    CODE: ClassVar[str] = "code"
    "Deptry JSON code field key."
    MODULE: ClassVar[str] = "module"
    "Deptry JSON module field key."
    DEV: ClassVar[DependencyGroup] = DependencyGroup.DEV
    "Development dependency group name."
    DOCS: ClassVar[DependencyGroup] = DependencyGroup.DOCS
    "Documentation dependency group name."
    SECURITY: ClassVar[DependencyGroup] = DependencyGroup.SECURITY
    "Security dependency group name."
    TEST: ClassVar[DependencyGroup] = DependencyGroup.TEST
    "Test dependency group name."
    TYPINGS: ClassVar[DependencyGroup] = DependencyGroup.TYPINGS
    "Typing stubs dependency group name."
    TYPING_LIBRARIES: ClassVar[str] = "typing_libraries"
    "Project limits typing_libraries key."
    MODULE_TO_PACKAGE: ClassVar[str] = "module_to_package"
    "Typing libraries module_to_package mapping key."
    PYTHON: ClassVar[str] = "python"
    "Python settings subsection key (in limits)."

    CANONICAL_DEV_DEPENDENCY_GROUPS: ClassVar[t.VariadicTuple[DependencyGroup]] = (
        DEV,
        DOCS,
        SECURITY,
        TEST,
        TYPINGS,
    )
    LEGACY_DEV_DEPENDENCY_GROUPS: ClassVar[t.VariadicTuple[DependencyGroup]] = (
        DOCS,
        SECURITY,
        TEST,
        TYPINGS,
    )

    # ANSI color codes and terminal symbols (SSOT for output styling).

    RESET: ClassVar[str] = "\x1b[0m"
    RED: ClassVar[str] = "\x1b[31m"
    GREEN: ClassVar[str] = "\x1b[32m"
    YELLOW: ClassVar[str] = "\x1b[33m"
    BLUE: ClassVar[str] = "\x1b[34m"
    CYAN: ClassVar[str] = "\x1b[36m"
    BOLD: ClassVar[str] = "\x1b[1m"

    # Unicode/ASCII symbols
    OK: ClassVar[str] = "✓"
    FAIL: ClassVar[str] = "✗"
    WARN: ClassVar[str] = "⚠"
    SKIP: ClassVar[str] = "–"

    # CLI tool binary names
    GIT: ClassVar[str] = "git"
    "Git version control binary."
    UV: ClassVar[str] = "uv"
    "uv package manager binary."
    GITLEAKS: ClassVar[str] = "gitleaks"
    "Gitleaks secret scanner binary."
    GITLEAKS_LEAK_EXIT_CODE: ClassVar[int] = 42
    "Gitleaks exit code reserved for detected secrets."
    GITLEAKS_POLICY_ENV_KEYS: ClassVar[t.StrSequence] = (
        "GITLEAKS_CONFIG",
        "GITLEAKS_CONFIG_TOML",
    )
    "Ambient Gitleaks policy variables removed from release scans."
    SOURCE_DATE_EPOCH: ClassVar[str] = "SOURCE_DATE_EPOCH"
    "Reproducible-build timestamp environment variable."
    TRANSACTION_STATE_DIRNAME: ClassVar[str] = ".state"
    "Root of regenerable codegen transaction state; never repository content."
    RELEASE_GITLEAKS_CONFIG_PATH: ClassVar[str] = "config/gitleaks-release.toml"
    "Workspace-relative trusted release secret-scan configuration."
    PYPI_SIMPLE_INDEX_URL: ClassVar[str] = "https://pypi.org/simple"
    "Canonical public package index used by isolated release builds."
    RELEASE_UV_BUILD_ARGS: ClassVar[t.StrSequence] = (
        UV,
        "build",
        "--force-pep517",
        "--no-config",
        "--no-sources",
        "--no-python-downloads",
        "--no-create-gitignore",
        "--no-progress",
        "--color",
        "never",
        "--default-index",
        PYPI_SIMPLE_INDEX_URL,
        "--require-hashes",
    )
    "Fail-closed isolated build of one release artifact from staged source."
    JSON_RPC_VERSION: ClassVar[str] = "2.0"
    "Canonical JSON-RPC protocol version used by LSP transports."
    GATE_ATTESTATION_SCHEMA: ClassVar[str] = "https://flext.sh/attestations/gates/v1"
    "Canonical schema identifier for signed gate attestations."
    UV_HTTP_CONNECT_TIMEOUT: ClassVar[str] = "UV_HTTP_CONNECT_TIMEOUT"
    "uv HTTP connection timeout environment key."
    UV_HTTP_TIMEOUT: ClassVar[str] = "UV_HTTP_TIMEOUT"
    "uv HTTP read timeout environment key."
    UV_HTTP_RETRIES: ClassVar[str] = "UV_HTTP_RETRIES"
    "uv HTTP retry-count environment key."
    UV_RELEASE_HTTP_CONNECT_TIMEOUT: ClassVar[str] = "10"
    "Release-build connection timeout in seconds."
    UV_RELEASE_HTTP_TIMEOUT: ClassVar[str] = "30"
    "Release-build read timeout in seconds."
    UV_RELEASE_HTTP_RETRIES: ClassVar[str] = "3"
    "Release-build HTTP retry count."
    UV_RELEASE_POLICY_ENV_KEYS: ClassVar[t.StrSequence] = (
        "UV_BUILD_CONSTRAINT",
        "UV_CONFIG_FILE",
        "UV_EXTRA_INDEX_URL",
        "UV_FIND_LINKS",
        "UV_INDEX",
        "UV_INDEX_URL",
        "UV_NO_BUILD_ISOLATION",
        "UV_NO_VERIFY_HASHES",
    )
    "Ambient uv variables removed before a policy-bound release build."
    SG: ClassVar[str] = "ast-grep"
    "Canonical ast-grep binary."
    SG_CONFIG_FLAG: ClassVar[str] = "--config"
    "Canonical ast-grep configuration-file option."
    SG_FILTER_FLAG: ClassVar[str] = "--filter"
    "Canonical ast-grep rule-ID filter option."
    SG_GLOBS_FLAG: ClassVar[str] = "--globs"
    "Canonical ast-grep include/exclude glob option."
    SG_UPDATE_ALL: ClassVar[str] = "--update-all"
    "ast-grep fixture and rewrite update flag."
    BANDIT: ClassVar[str] = "bandit"
    "Bandit security linter binary."
    RUMDL: ClassVar[str] = "rumdl"
    "uv-managed Markdown linter console script."
    OUTPUT_JSON: ClassVar[str] = "json"
    "Common CLI output format flag value."
    SCAN: ClassVar[str] = "scan"
    "ast-grep scan subcommand."
    MAKE: ClassVar[str] = "make"
    "Make build tool binary."
    "AI Hub code-review-graph analysis binary."

    CHECK: ClassVar[str] = "check"
    "Generic check command/subcommand identifier."

    @unique
    class TomlMergeMode(StrEnum):
        """SSOT merge strategies for TOML list synchronization."""

        REPLACE = "replace"
        ADDITIVE = "additive"
        MERGE = "merge"

    @unique
    class ResultStatus(StrEnum):
        """SSOT status values for reports and gate summaries."""

        PASSED = "PASS"
        FAIL = "FAIL"
        OK = "OK"
        WARN = "WARN"

    @unique
    class MatchMode(StrEnum):
        """SSOT scanner match mode values."""

        PRESENT = "present"
        ABSENT = "absent"

    @unique
    class LazyInitAction(StrEnum):
        """SSOT lazy-init action values."""

        WRITE = "write"
        REMOVE = "remove"
        SKIP = "skip"

    @unique
    class TomlOperationKind(StrEnum):
        """SSOT TOML phase operation kinds."""

        SET = "set"
        LIST = "list"
        REMOVE = "remove"

    @unique
    class OperationMode(StrEnum):
        """SSOT operation mode values."""

        BASELINE = "baseline"
        STRICT = "strict"

    @unique
    class SeverityLevel(StrEnum):
        """SSOT severity levels."""

        ERROR = "error"
        WARNING = "warning"
        NOTE = "note"
        LOW = "low"
        SKIP = "skip"

    DEFAULT_UNKNOWN: ClassVar[str] = "unknown"
    DEFAULT_UNNAMED: ClassVar[str] = "unnamed"

    RK_STATUS: ClassVar[str] = "status"
    RK_FILE: ClassVar[str] = "file"
    RK_MESSAGE: ClassVar[str] = "message"
    RK_SUMMARY: ClassVar[str] = "summary"
    RK_TOTAL: ClassVar[str] = "total"
    RK_RULES: ClassVar[str] = "rules"
    RK_RELEASE: ClassVar[str] = "release"
    RK_ACTION: ClassVar[str] = "action"
    RK_SCOPE: ClassVar[str] = "scope"
    RK_VIOLATIONS: ClassVar[str] = "violations"
    RK_VIOLATIONS_COUNT: ClassVar[str] = "violations_count"
    RK_RULE_ID: ClassVar[str] = "rule_id"
    RK_OK: ClassVar[str] = "ok"
    RK_ENABLED: ClassVar[str] = "enabled"
    RK_PROJECTS: ClassVar[str] = "projects"
    RK_WORKSPACE: ClassVar[str] = "workspace"
    RK_ROOT: ClassVar[str] = "root"
    ROOT_PROJECT_SELECTOR: ClassVar[str] = "."
    "Project selector naming the repository root itself."
    RK_ID: ClassVar[str] = "id"
    RK_URL: ClassVar[str] = "url"
    RK_CONFIDENCE: ClassVar[str] = "confidence"
    RK_FIX_ACTION: ClassVar[str] = "fix_action"
    RK_DESCRIPTION: ClassVar[str] = "description"
    RK_SEVERITY: ClassVar[str] = "severity"

    CLI_APPLY_OPTION_DECLS: ClassVar[t.StrSequence] = ("--apply/--dry-run",)
    "Typer dual-flag declarations for --apply/--dry-run option."

    @unique
    class FacadeFamily(StrEnum):
        """Facade family enumeration."""

        C = "c"
        T = "t"
        P = "p"
        M = "m"
        U = "u"

    SAFE_EXECUTION_BAK_SUFFIX: ClassVar[str] = ".bak"
    "File backup suffix for copy-on-write safety."
    ENV_VAR_FORCE_COLOR: ClassVar[str] = "FORCE_COLOR"
    "Color-forcing variable: its mere presence makes ruff emit ANSI sequences."

    ENV_VAR_STANDALONE: ClassVar[str] = "FLEXT_STANDALONE"
    ENV_VAR_REPOSITORY_ROOT: ClassVar[str] = "FLEXT_REPOSITORY_ROOT"
    ENV_VAR_USE_HTTPS: ClassVar[str] = "FLEXT_USE_HTTPS"
    ENV_VAR_GITHUB_ACTIONS: ClassVar[str] = "GITHUB_ACTIONS"
    ENV_VAR_GITHUB_HEAD_REF: ClassVar[str] = "GITHUB_HEAD_REF"
    ENV_VAR_GITHUB_REF_NAME: ClassVar[str] = "GITHUB_REF_NAME"
    ENV_DEFAULT_STANDALONE: ClassVar[bool] = False
    ENV_DEFAULT_USE_HTTPS: ClassVar[bool] = False
    ENV_DEFAULT_GITHUB_ACTIONS: ClassVar[bool] = False

    @unique
    class ExecutionMode(StrEnum):
        """Execution mode for commands that modify files."""

        DRY_RUN = "dry-run"
        "Preview changes without writing."
        CHECK_ONLY = "check-only"
        "Detect violations without fixing."
        APPLY_SAFE = "apply-safe"
        "Apply with backup, validate, rollback on failure."
        APPLY_FORCE = "apply-force"
        "Apply without post-validation."


__all__: list[str] = ["FlextInfraConstantsBase"]
