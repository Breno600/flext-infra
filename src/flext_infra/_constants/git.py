"""Git constants for flext-infra project.

Centralizes git mode/stage/remote/sha constants consumed by the
``_utilities/_git/`` facet so the GitPython-backed operations never
hardcode magic numbers or strings.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from enum import StrEnum, unique
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsGit:
    """Git-specific constants for the GitPython-backed facet."""

    GIT_UNBORN_HEAD_ERROR_CODE: ClassVar[str] = "GIT_UNBORN_HEAD"
    "Identity is unavailable because HEAD names a branch that has no ref yet."
    GIT_UNBORN_HEAD_MARKER: ClassVar[str] = "UNBORN"
    "Fingerprint input standing for HEAD when the current branch has no commit."
    GIT_REF_MISSING_EXIT_CODE: ClassVar[int] = 2
    "The documented git show-ref --exists result for an absent reference."

    @unique
    class GateAttestationSchema(StrEnum):
        """Supported signed gate-attestation schema identities."""

        V1 = "https://flext.sh/attestations/gates/v1"

    # --- Index entry modes (git mode field, not POSIX st_mode) ---

    GIT_MODE_FILE: ClassVar[int] = 0o100644
    "Normal tracked file index mode."
    GIT_MODE_EXECUTABLE: ClassVar[int] = 0o100755
    "Executable tracked file index mode."
    GIT_MODE_SYMLINK: ClassVar[int] = 0o120000
    "Symbolic link index mode."
    GIT_MODE_GITLINK: ClassVar[int] = 0o160000
    "Submodule gitlink index mode (used by BaseIndexEntry)."
    GIT_GITLINK_MODE_TEXT: ClassVar[str] = f"{GIT_MODE_GITLINK:o}"
    "Submodule gitlink mode as Git prints it in index, tree and diff records."
    GIT_LS_FILES_STAGE_FIELDS: ClassVar[int] = 4
    "Fields of one ``ls-files --stage`` record: mode, oid, stage and path."
    # --- Index stage values ---

    GIT_STAGE_NORMAL: ClassVar[int] = 0
    "Normal (non-conflict) index stage."

    # --- SHA lengths ---

    GIT_OID_HEX_LENGTH_SHA1: ClassVar[int] = 40
    "Hex length of a SHA-1 Git object id."
    GIT_OID_HEX_LENGTH_SHA256: ClassVar[int] = 64
    "Hex length of a SHA-256 Git object id."

    # --- Remote defaults ---

    GIT_DEFAULT_REMOTE: ClassVar[str] = "origin"
    "Canonical upstream remote name."
    GIT_EXIT_NEGATIVE: ClassVar[int] = 1
    "Exit status a Git predicate command documents for a negative answer."
    GIT_URL_SCHEME_PREFIX: ClassVar[str] = "git+"
    "PEP 508 direct-reference prefix that marks a Git dependency source."
    GIT_PORCELAIN_PATH_OFFSET: ClassVar[int] = 3
    "Column where the path starts in one ``git status --porcelain`` v1 line."
    GIT_REMOTE_SSH_SCHEMES: ClassVar[frozenset[str]] = frozenset({"ssh", "git+ssh"})
    "Remote URL schemes treated as SSH-style remote identifiers."
    GIT_REMOTE_SENSITIVE_QUERY_KEYS: ClassVar[frozenset[str]] = frozenset({
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "bearer",
        "client_secret",
        "id_token",
        "jwt",
        "key",
        "oauth_token",
        "password",
        "passwd",
        "private_key",
        "private_token",
        "refresh_token",
        "secret",
        "token",
    })
    "Remote query keys whose values are redacted from identity output."

    # --- Ref prefixes ---

    GIT_REFS_HEADS: ClassVar[str] = "refs/heads/"
    "Local branch ref prefix."

    GIT_REFS_REMOTES: ClassVar[str] = "refs/remotes/"
    "Remote-tracking ref prefix."

    GIT_REFS_TAGS: ClassVar[str] = "refs/tags/"
    "Tag ref prefix."

    GIT_REV_PARSE_ABSOLUTE_PATHS: ClassVar[str] = "--path-format=absolute"
    "``git rev-parse`` option that prints the path queries following it as absolute."

    # --- Lane hygiene audit (stashes, merged branches, orphan worktrees) ---

    @unique
    class LaneViolationKind(StrEnum):
        """Classes of lane accumulation the lane hygiene audit rejects."""

        STASH = "stash"
        MERGED_BRANCH = "merged-branch"
        TEMP_WORKTREE = "temp-worktree"
        MISSING_WORKTREE = "missing-worktree"
        MERGED_WORKTREE = "merged-worktree"
        DETACHED_WORKTREE = "detached-worktree"

    GIT_LANE_VIOLATION_REMEDY: ClassVar[t.MappingKV[LaneViolationKind, str]] = (
        MappingProxyType({
            LaneViolationKind.STASH: (
                "preserve every stash parent, index and untracked object; "
                "coordinate validated integration before authorized retirement"
            ),
            LaneViolationKind.MERGED_BRANCH: (
                "prove published integration ancestry, preservation and inactive "
                "ownership before authorizing retirement of {ref}"
            ),
            LaneViolationKind.TEMP_WORKTREE: (
                "adjudicate registered ownership and preserve all content at {ref}; "
                "temporary location alone never authorizes removal"
            ),
            LaneViolationKind.MISSING_WORKTREE: (
                "preserve registry and Git objects for {ref}; coordinator must "
                "prove recovery and integration before authorized registry retirement"
            ),
            LaneViolationKind.MERGED_WORKTREE: (
                "prove published ancestry, clean index/untracked content and "
                "inactive unlocked ownership before authorized retirement of {ref}"
            ),
            LaneViolationKind.DETACHED_WORKTREE: (
                "prove registered ownership and preserve detached content at {ref}; "
                "never infer permission to discard it"
            ),
        })
    )
    "Fix instruction per lane violation class; ``{ref}`` names the offender."

    # --- Linked-worktree registry (filesystem discovery, no Git subprocess) ---

    GIT_WORKTREES_DIRNAME: ClassVar[str] = "worktrees"
    "Directory under the repository's ``.git`` holding one registered entry."
    GIT_WORKTREE_SCAN_FILE_CAP: ClassVar[int] = 200_000
    "Maximum entries a bounded worktree tree walk visits before degrading."
    GIT_WORKTREE_SCAN_TIME_CAP_S: ClassVar[float] = 30.0
    "Maximum seconds a bounded worktree tree walk runs before degrading."
    SECONDS_PER_DAY: ClassVar[float] = 86400.0
    "Seconds in one day, the idle-time denominator for stale worktrees."


__all__: list[str] = ["FlextInfraConstantsGit"]
