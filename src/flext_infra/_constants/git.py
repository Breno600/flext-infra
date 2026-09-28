"""Git constants for flext-infra project.

Centralizes git mode/stage/remote/sha constants consumed by the
``_utilities/_git/`` facet so the GitPython-backed operations never
hardcode magic numbers or strings.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from enum import StrEnum, unique
from typing import ClassVar


class FlextInfraConstantsGit:
    """Git-specific constants for the GitPython-backed facet."""

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
    GIT_CACHEINFO_GITLINK: ClassVar[str] = "160000"
    "Submodule gitlink mode string for ``git update-index --cacheinfo``."

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
