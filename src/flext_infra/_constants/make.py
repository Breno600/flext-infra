"""Selector-free Make and project-tool constants."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from .._constants.check import FlextInfraConstantsCheck

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsMake:
    """One canonical vocabulary shared by generated Make and its services."""

    class PytestExecutionMode(StrEnum):
        """Public operations whose test scope and accounting are distinct."""

        INCREMENTAL = "incremental"
        FULL = "full"
        COVERAGE = "coverage"

    MAKE_ASSIGNMENT_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^[A-Za-z_][A-Za-z0-9_]*\s*(?::?:|\?|\+)?="
    )
    MAKE_DIRECTIVE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?:export|unexport|override|include|-include|sinclude|vpath)\b"
    )
    MAKE_CONDITIONAL_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?:else\b|endif\b|ifeq\b|ifneq\b|ifdef\b|ifndef\b)"
    )
    MAKE_REPOSITORY_ROOT: ClassVar[str] = "REPOSITORY_ROOT"
    "Make variable the workspace orchestrator passes to attached members."

    VERB_CHECK: ClassVar[str] = "check"
    VERB_TEST: ClassVar[str] = "test"
    VERB_CLEAN: ClassVar[str] = "clean"
    VERB_VALIDATE: ClassVar[str] = "validate"
    VERB_PUBLISH: ClassVar[str] = "publish"
    VERB_RUN: ClassVar[str] = "run"
    VERB_CHECKS: ClassVar[str] = "checks"
    VERB_SONARCLOUD_SYNC: ClassVar[str] = "sonarcloud-sync"

    CLI_GROUP_CHECK: ClassVar[str] = "check"
    CLI_GROUP_CODEGEN: ClassVar[str] = "codegen"
    CLI_GROUP_DEPS: ClassVar[str] = "deps"
    CLI_GROUP_DOCS: ClassVar[str] = "docs"
    CLI_GROUP_MAINTENANCE: ClassVar[str] = "maintenance"
    CLI_GROUP_REFACTOR: ClassVar[str] = "refactor"
    CLI_GROUP_RELEASE: ClassVar[str] = "release"
    CLI_ROUTE_RELEASE: ClassVar[str] = "release run"
    CLI_GROUP_VALIDATE: ClassVar[str] = "validate"
    CLI_ROUTE_MAINTENANCE: ClassVar[str] = "maintenance run"
    CLI_GROUP_WORKSPACE: ClassVar[str] = "workspace"

    MYPY_MEMORY_LIMIT_MB_ENV: ClassVar[str] = "MYPY_MEMORY_LIMIT_MB"
    MYPY_MEMORY_LIMIT_MB_DEFAULT: ClassVar[int] = 6144
    MYPY_TIMEOUT_SECONDS_ENV: ClassVar[str] = "MYPY_TIMEOUT_SECONDS"
    MYPY_TIMEOUT_SECONDS_DEFAULT: ClassVar[int] = 600
    MYPY_TIMEOUT_GRACE_SECONDS: ClassVar[int] = 10
    PRLIMIT_COMMAND: ClassVar[str] = "prlimit"
    PRLIMIT_ADDRESS_SPACE_OPTION: ClassVar[str] = "--as"
    TIMEOUT_COMMAND: ClassVar[str] = "timeout"
    TIMEOUT_KILL_AFTER_SECONDS: ClassVar[int] = 5

    # Every read-only gate this package implements, derived from the gate SSOT
    # (c.Infra.SARIF_TOOL_INFO) so registering a gate makes it reachable
    # through `make check` in the same edit and no second list can drift.
    # Mutating gates (`format`) are excluded: they rewrite files, so they are
    # owned by `make fmt` / `make fix` and a read-only verb
    # must never invoke them.
    CANONICAL_GATE_IDS: ClassVar[t.VariadicTuple[str]] = tuple(
        gate
        for gate in FlextInfraConstantsCheck.SARIF_TOOL_INFO
        if gate not in FlextInfraConstantsCheck.MUTATING_GATES
    )
    # markdown-code and markdown-format stay allowed and explicitly invocable
    # (`--gates markdown-code`), but are not default check gates: operator
    # ruling 2026-09-18 (flext-uz0dt for markdown-code; flext-v4fmn for
    # markdown-format) takes them out of the unset-CI default set pending
    # review. markdown-format is structurally contradictory on the current
    # generated docs: the gen render is not prettier-stable, so no commit can
    # satisfy both `gen fixed point` and `prettier --check`.
    CANONICAL_DEFAULT_GATE_IDS: ClassVar[t.VariadicTuple[str]] = tuple(
        gate
        for gate in CANONICAL_GATE_IDS
        if gate
        not in {
            FlextInfraConstantsCheck.MARKDOWN_CODE,
            FlextInfraConstantsCheck.MARKDOWN_FORMAT,
        }
    )
    CANONICAL_FIXABLE_GATE_IDS: ClassVar[t.VariadicTuple[str]] = (
        "lint",
        "markdown",
        "markdown-code",
        "canonical-alias",
        "smells",
    )
    # markdown-format is deliberately absent: prettier is a formatter, so the
    # gate's mutating side is owned by `make fmt` (check = `prettier --check`),
    # never by `make fix` — one operation per tool per verb, never repeated.
    ORCHESTRATED_VERBS: ClassVar[t.StrSequence] = (
        "build",
        "check",
        "clean",
        "docs",
        "fmt",
        "fix",
        "fix-enforcement",
        "sonarcloud-sync",
        "test",
        "test-full",
    )
    ORCHESTRATOR_REMOVE_ENV_KEYS: ClassVar[t.StrSequence] = (
        "GNUMAKEFLAGS",
        "MAKEFLAGS",
        "MAKEFILES",
        "MAKELEVEL",
        "MAKEOVERRIDES",
        "MISE_DIR",
        "MISE_EXE",
        "MISE_ORIG_PATH",
        "MISE_SESSION",
        "MISE_SHELL",
        "MISE_SHIMS",
        "MISE_VERBOSE",
        "MFLAGS",
        "MYPYPATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONPATH",
        "UV_PROJECT",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    )
    ORCHESTRATOR_ENV_NO_COLOR: ClassVar[str] = "NO_COLOR"
    ORCHESTRATOR_ENV_PATH: ClassVar[str] = "PATH"
    ORCHESTRATOR_ENV_PYTHONPATH: ClassVar[str] = "PYTHONPATH"
    ORCHESTRATOR_ENV_PATH_SEPARATOR: ClassVar[str] = ":"
    ORCHESTRATOR_ENV_MISE_SHIMS: ClassVar[str] = "MISE_SHIMS"
    ORCHESTRATOR_ENV_WORKSPACE_MISE_SHIMS: ClassVar[str] = "WORKSPACE_MISE_SHIMS"

    PYTEST_ENV_REPORTS: ClassVar[str] = "FLEXT_PYTEST_REPORTS_RAW"
    PYTEST_ENV_TARGET: ClassVar[str] = "FLEXT_PYTEST_TARGET_RAW"
    PYTEST_ENV_CI: ClassVar[str] = "CI"
    PYTEST_ENV_TESTMON_DATAFILE: ClassVar[str] = "TESTMON_DATAFILE"
    PYTEST_ENV_COLLECTION_MANIFEST: ClassVar[str] = "FLEXT_PYTEST_COLLECTION_MANIFEST"
    PYTEST_WARNING_EVENTS_SUFFIX: ClassVar[str] = ".warnings.jsonl"
    PYTEST_INHERITED_ENV_REMOVE_KEYS: ClassVar[t.StrSequence] = (
        "PYTEST_ADDOPTS",
        "PYTHONPATH",
        PYTEST_ENV_COLLECTION_MANIFEST,
    )


__all__: list[str] = ["FlextInfraConstantsMake"]
