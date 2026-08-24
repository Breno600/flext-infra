"""Centralized constants for the workspace subpackage."""

from __future__ import annotations

from enum import StrEnum, unique
from typing import TYPE_CHECKING, Final

from flext_infra._constants.codegen_project import FlextInfraConstantsCodegenProject

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsWorkspace:
    """Workspace infrastructure constants."""

    @unique
    class WorktreeOperation(StrEnum):
        """Private Git worktree primitives composed by the work saga."""

        LIST = "list"
        ADD = "add"
        UPDATE = "update"
        REMOVE = "remove"

    @unique
    class WorkOperation(StrEnum):
        """Public make work saga operations."""

        START = "start"
        STATUS = "status"
        LAND = "land"
        FINISH = "finish"

    @unique
    class WorkKind(StrEnum):
        """GitFlow lane kinds owned by configuration policy."""

        EPIC = "epic"
        FEATURE = "feature"
        BUGFIX = "bugfix"
        HOTFIX = "hotfix"
        RELEASE = "release"

    @unique
    class WorkBranchNamespace(StrEnum):
        EPIC = "epic"
        FEATURE = "feature"
        BUGFIX = "bugfix"
        HOTFIX = "hotfix"
        RELEASE = "release"

    @unique
    class WorkLaneRole(StrEnum):
        """Topology role one registered lane holds inside an epic program."""

        PLAIN = "plain"
        EPIC = "epic"
        CHILD = "child"

    @unique
    class WorkProvisioningState(StrEnum):
        """Lifecycle state persisted for one work-lane reservation."""

        PENDING = "pending"
        READY = "ready"
        FAILED = "failed"

    @unique
    class WorkRecoveryCategory(StrEnum):
        """Recovery action supported for a failed work-lane reservation."""

        RETRY_SETUP = "retry-setup"

    @unique
    class WorkProvisioningError(StrEnum):
        """Provisioning stage that failed after lane reservation."""

        SETUP = "setup"

    @unique
    class BeadIssueStatus(StrEnum):
        """Beads issue states relevant to live lane ownership."""

        OPEN = "open"
        IN_PROGRESS = "in_progress"
        BLOCKED = "blocked"
        CLOSED = "closed"

    WORK_ACTIVE_ISSUE_STATUSES: Final[frozenset[BeadIssueStatus]] = frozenset({
        BeadIssueStatus.OPEN,
        BeadIssueStatus.IN_PROGRESS,
        BeadIssueStatus.BLOCKED,
    })

    WORK_FORBIDDEN_SLUGS: Final[frozenset[str]] = frozenset({
        "teste",
        "ajuste",
        "correcao",
        "temp",
        "nova-branch",
    })
    WORK_BEADS_METADATA_KEYS: Final[t.StrSequence] = (
        "branch",
        "namespace",
        "worktree",
        "kind",
        "slug",
        "integration_base",
        "head_oid",
        "pr_number",
        "pr_url",
        "provisioning",
        "recovery",
        "error_category",
        "role",
        "epic_bead",
        "epic_branch",
        "epic_worktree",
        "child_slug",
    )

    @unique
    class WorkspaceMode(StrEnum):
        """Workspace execution mode enumeration."""

        WORKSPACE = "workspace"
        WORKSPACE_MEMBER = "workspace-member"
        STANDALONE = "standalone"

    @unique
    class WorkspaceProjectRole(StrEnum):
        """Role of one discovered project relative to the uv workspace root."""

        WORKSPACE_MEMBER = "member"
        ATTACHED = "attached"

    EXTERNAL_WORKSPACE_SIBLING_PATTERNS: Final[t.StrSequence] = (
        ".ai-hub",
        "algar-*",
        "gruponos-*",
    )
    "Sibling directory patterns for FLEXT-managed external workspaces."

    PERSISTENT_STATE_ARTIFACT_NAMES: Final[frozenset[str]] = frozenset({
        ".beads",
        ".code-review-graph",
        ".codegraph",
        ".serena",
    })
    "Persistent-state artifact basenames owned only by the workspace root."

    MAKEFILE_REPLACEMENTS: Final[t.VariadicTuple[t.StrPair]] = (
        (
            'python3 "$(BASE_MK_DIR)/scripts/mode.py"',
            "python -m flext_infra workspace detect",
        ),
        (
            'python "$(WORKSPACE_ROOT)/scripts/check/fix_pyrefly_config.py"',
            "python -m flext_infra check fix-pyrefly-settings",
        ),
        (
            'python "$(WORKSPACE_ROOT)/scripts/check/workspace_check.py"',
            "python -m flext_infra check run",
        ),
        (
            '$(VENV_PYTHON) "$(BASE_MK_DIR)/scripts/core/pytest_diag_extract.py"',
            "$(VENV_PYTHON) -m flext_infra validate pytest-diag",
        ),
        (
            'python3 "$(WORKSPACE_ROOT)/scripts/github/pr_manager.py"',
            "python3 -m flext_infra github pr",
        ),
    )
    # NOTE (mro-jnm1.2): the .gitignore body is derived from the artifact SSOT
    # (config/codegen.yaml artifacts -> CodegenConfigSpec.gitignore_sections)
    # and written only by codegen conform; the old REQUIRED_GITIGNORE_ENTRIES,
    # GITIGNORE_REMOVE_EXACT and GITIGNORE_MANAGED_HEADER append-paths were
    # removed with the migrator/sync parallel writers.
    WORKTREES_DIRNAME: Final[str] = ".worktrees"
    WORKTREE_NAMESPACE_DIGEST_LENGTH: Final[int] = 12
    VSCODE_DIRNAME: Final[str] = ".vscode"
    VSCODE_SETTINGS_FILENAME: Final[str] = "settings.json"
    VSCODE_PYTHON_ENVS_SEARCH_PATHS_KEY: Final[str] = "python-envs.workspaceSearchPaths"
    CODEGEN_OWNER_VSCODE: Final[str] = "vscode"
    # Canonical VS Code settings content lives in config/codegen.yaml (vscode:).
    # Recursive "**" venv search globs are forbidden: they make the Python
    # Environments locator (pet) walk entire trees and hang discovery.
    MAKEFILE_INCLUDE_OLD: Final[str] = (
        'ifneq ("$(wildcard ../base.mk)", "")\n'
        "include ../base.mk\n"
        "else\n"
        "include base.mk\n"
        "endif"
    )

    MAKEFILE_GENERATED_MARKER: Final[str] = (
        "# @generated by: flext_infra codegen conform"
    )
    "Comment marker inserted into generated Makefiles."
    TEMPLATE_GENERATED_MARKER: Final[str] = "Generated by flext_infra codegen"
    "Header marker every rendered project template carries."
    MAKEFILE_CUSTOM_INCLUDE: Final[str] = (
        f"-include {FlextInfraConstantsCodegenProject.CUSTOM_MAKE_FILENAME}"
    )
    "Makefile include for user customization overrides."

    # Workspace environment sync (public `infra` facade): generated-file
    # detection and canonical filenames for direnv/mise artifacts. Old marker
    # kept for migration: files written by the retired workspace sync module
    # must still be recognized as generated and upgradable in place.
    ENVRC_FILENAME: Final[str] = ".envrc"
    MISE_TOML_FILENAME: Final[str] = ".mise.toml"
    WORKSPACE_ENV_FILES: Final[t.StrSequence] = (ENVRC_FILENAME, MISE_TOML_FILENAME)
    WORKSPACE_ENV_GENERATED_MARKERS: Final[t.StrSequence] = (
        "# @generated by: flext_infra workspace sync",
        "# Generated by `flext-infra codegen conform`.",
        "# Generated by `flext_infra codegen conform`.",
    )
    # Tools that must never appear under mise: linters/type-checkers come from
    # the locked pyproject dependency groups into .venv (gates invoke them via
    # python -m), and go is not a workspace runtime. Sync prunes any drift.
    WORKSPACE_MISE_REMOVED_TOOLS: Final[t.StrSequence] = (
        "mypy",
        "pyright",
        "pyrefly",
        "ruff",
        "go",
    )


__all__: list[str] = ["FlextInfraConstantsWorkspace"]
