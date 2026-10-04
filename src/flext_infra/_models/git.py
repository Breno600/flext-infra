"""Typed Git request/report contracts for flext-infra public Git API.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from flext_cli import m

from flext_infra import t
from flext_infra._models._git.identity import FlextInfraModelsGitIdentity
from flext_infra._models._git.worktree_facts import FlextInfraModelsGitWorktreeFacts
from flext_infra._models._git.worktree_state import FlextInfraModelsGitWorktreeState


class FlextInfraModelsGit(
    FlextInfraModelsGitIdentity,
    FlextInfraModelsGitWorktreeFacts,
    FlextInfraModelsGitWorktreeState,
):
    """Declaration-only models for Git facade and FlextInfraGitService.

    Composed via FLEXT with FlextInfraModelsGitIdentity (GitIdentityReport).
    """

    class GitRepoRequest(m.ContractModel):
        """One repository path for a monomorphic Git query."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]

    class GitStatusRequest(m.ContractModel):
        """Request porcelain status for one repository."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]

    class GitStatusReport(m.ContractModel):
        """Porcelain status snapshot for one repository."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        porcelain: Annotated[
            str,
            m.Field(description="Raw git status --porcelain output"),
        ]
        dirty: Annotated[bool, m.Field(description="Whether the worktree is dirty")]

    class GitPrimaryRootReport(m.ContractModel):
        """Resolved primary worktree root."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        primary_root: Annotated[
            Path,
            m.Field(description="Canonical primary worktree root"),
        ]

    class GitRootReport(m.ContractModel):
        """Resolved workspace or superproject root."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repository_root: Annotated[
            Path,
            m.Field(description="Workspace or superproject root"),
        ]

    class GitOidReport(m.ContractModel):
        """Resolved Git object id."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        oid: Annotated[t.NonEmptyStr, m.Field(description="Git object id (hex)")]

    class GitTextReport(m.ContractModel):
        """Captured Git stdout text for one semantic operation."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        text: Annotated[str, m.Field(description="Captured stdout text")]

    class GitBytesReport(m.ContractModel):
        """Captured Git stdout bytes for one semantic operation."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        payload: Annotated[bytes, m.Field(description="Captured stdout bytes")]

    class GitBoolReport(m.ContractModel):
        """Boolean outcome for one semantic Git predicate."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        value: Annotated[bool, m.Field(description="Predicate result")]

    class GitWorktreeEntry(m.ContractModel):
        """One registered worktree checkout from Git's canonical registry."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        path: Annotated[Path, m.Field(description="Registered worktree root")]
        head: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Checked-out commit oid; absent for a bare worktree"),
        ] = None
        branch: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Checked-out branch short name; absent when detached"),
        ] = None
        detached: Annotated[bool, m.Field(description="Whether HEAD is detached")] = (
            False
        )
        bare: Annotated[
            bool,
            m.Field(description="Whether this is the bare main worktree"),
        ] = False
        locked: Annotated[
            bool,
            m.Field(description="Whether the worktree is locked"),
        ] = False

    class GitWorktreeListReport(m.ContractModel):
        """Git's worktree registry, parsed once, plus its raw porcelain contract."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        root: Annotated[
            Path,
            m.Field(description="Repository the registry was read for"),
        ]
        entries: Annotated[
            t.VariadicTuple[FlextInfraModelsGit.GitWorktreeEntry],
            m.Field(description="Every registered worktree, primary first"),
        ]
        porcelain: Annotated[
            str,
            m.Field(description="Raw git worktree list --porcelain output"),
        ]

    class GitBranchRequest(m.ContractModel):
        """Repository plus branch name for branch-scoped operations."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        branch: Annotated[t.NonEmptyStr, m.Field(description="Branch name")]

    class GitRefRequest(m.ContractModel):
        """Repository plus exact Git ref name."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        reference: Annotated[t.NonEmptyStr, m.Field(description="Exact Git ref")]

    class GitSubmoduleConfigRequest(m.ContractModel):
        """One ``.gitmodules`` section key of a declared submodule."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Superproject worktree root")]
        section: Annotated[
            t.NonEmptyStr,
            m.Field(description="Section, e.g. submodule.flext-core"),
        ]
        key: Annotated[t.NonEmptyStr, m.Field(description="Key inside the section")]

    class GitCommitishRequest(m.ContractModel):
        """Repository plus commit-ish for resolve/ancestor/merge ops."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        commitish: Annotated[t.NonEmptyStr, m.Field(description="Commit-ish")]

    class GitAncestryRequest(m.ContractModel):
        """Repository plus the ancestor and descendant an ancestry proof relates.

        ``descendant`` defaults to ``HEAD``, so the HEAD-bound proof every
        existing consumer relied on is the same single owner generalized to an
        arbitrary pair; there is no separate pair verb.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        ancestor: Annotated[t.NonEmptyStr, m.Field(description="Candidate ancestor")]
        descendant: Annotated[
            t.NonEmptyStr,
            m.Field(default="HEAD", description="Candidate descendant"),
        ] = "HEAD"

    class GitPathPairRequest(m.ContractModel):
        """Repository plus source/target relative paths."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        source: Annotated[t.NonEmptyStr, m.Field(description="Source path relative")]
        target: Annotated[t.NonEmptyStr, m.Field(description="Target path relative")]

    class GitRelativePathRequest(m.ContractModel):
        """Repository plus one relative path."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        relative_path: Annotated[
            t.NonEmptyStr,
            m.Field(description="Path relative to repo root"),
        ]

    class GitDeleteRefRequest(m.ContractModel):
        """Delete a ref when it still points at an expected oid."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        reference: Annotated[t.NonEmptyStr, m.Field(description="Exact Git ref")]
        expected_oid: Annotated[
            t.NonEmptyStr,
            m.Field(description="Expected tip oid for CAS delete"),
        ]

    class GitPushRequest(m.ContractModel):
        """Push a local commit-ish (HEAD by default) to a remote branch ref."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        remote: Annotated[t.NonEmptyStr, m.Field(description="Remote name")] = "origin"
        branch: Annotated[t.NonEmptyStr, m.Field(description="Branch to publish")]
        source: Annotated[
            t.NonEmptyStr,
            m.Field(description="Local commit-ish pushed to the remote branch"),
        ] = "HEAD"

    class GitRemoteRequest(m.ContractModel):
        """One repository plus one remote name."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        remote: Annotated[t.NonEmptyStr, m.Field(description="Remote name")] = "origin"

    class GitRemoteBranchRequest(GitRemoteRequest):
        """One remote branch, optionally bound to its expected tip oid."""

        branch: Annotated[t.NonEmptyStr, m.Field(description="Remote branch name")]
        expected_oid: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Remote tip the mutation is leased on"),
        ] = None

    class GitRefHeadsRequest(m.ContractModel):
        """List every ref below one namespace.

        Namespaces include ``refs/heads`` and ``refs/remotes/origin``.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        namespace: Annotated[t.NonEmptyStr, m.Field(description="Ref namespace")]

    class GitRefHeadsReport(m.ContractModel):
        """Short ref names below one namespace mapped to their tip oids."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        heads: Annotated[
            t.StrMapping,
            m.Field(description="Name relative to the namespace -> tip oid"),
        ]

    class GitOidListReport(m.ContractModel):
        """Ordered Git object ids."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        oids: Annotated[t.StrSequence, m.Field(description="Object ids in order")]

    class GitBranchCreateRequest(m.ContractModel):
        """Create one branch at a start point, optionally switching to it."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        branch: Annotated[t.NonEmptyStr, m.Field(description="New branch name")]
        start: Annotated[
            t.NonEmptyStr,
            m.Field(description="Commit-ish the branch starts at"),
        ] = "HEAD"
        switch: Annotated[
            bool,
            m.Field(description="Switch the worktree to it, carrying local changes"),
        ] = False

    class GitStashDropRequest(m.ContractModel):
        """Drop the stash entry whose commit is exactly ``oid``."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        oid: Annotated[t.NonEmptyStr, m.Field(description="Stash commit oid")]

    class GitMergeProbeRequest(m.ContractModel):
        """Ask whether merging ``commitish`` into ``base`` would change nothing."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        base: Annotated[t.NonEmptyStr, m.Field(description="Merge target commit-ish")]
        commitish: Annotated[t.NonEmptyStr, m.Field(description="Merged commit-ish")]

    class GitTimestampReport(m.ContractModel):
        """One Unix timestamp in seconds."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        epoch_seconds: Annotated[
            t.NonNegativeInt,
            m.Field(description="Seconds since the Unix epoch"),
        ]

    class GitWorktreeAddRequest(m.ContractModel):
        """Add a development worktree lane."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Primary repository root")]
        lane: Annotated[Path, m.Field(description="Absolute lane worktree path")]
        branch: Annotated[t.NonEmptyStr, m.Field(description="Lane branch name")]
        base: Annotated[
            t.NonEmptyStr,
            m.Field(description="Base commit-ish when creating branch"),
        ]
        track_remote: Annotated[
            bool,
            m.Field(description="Track origin/<branch> when creating"),
        ] = False
        local_branch_exists: Annotated[
            bool,
            m.Field(description="Whether refs/heads/<branch> already exists"),
        ] = False

    class GitNumstatReport(m.ContractModel):
        """HEAD commit subject plus parent..HEAD numstat text."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        subject: Annotated[str, m.Field(description="HEAD commit subject")]
        numstat: Annotated[str, m.Field(description="git diff --numstat HEAD~1 HEAD")]

    class GitFingerprintInputsReport(m.ContractModel):
        """Byte-exact inputs for workspace fingerprinting."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        paths_z: Annotated[
            bytes,
            m.Field(description="NUL-delimited ls-files path list"),
        ]
        index_z: Annotated[
            bytes,
            m.Field(description="NUL-delimited ls-files --stage list"),
        ]
        head: Annotated[bytes, m.Field(description="HEAD oid bytes or UNBORN")]

    class GitUpdateIndexGitlinkRequest(m.ContractModel):
        """Stage one gitlink (mode 160000) into the index."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        oid: Annotated[t.NonEmptyStr, m.Field(description="Gitlink commit oid")]
        relative_path: Annotated[
            t.NonEmptyStr,
            m.Field(description="Gitlink path relative to repo"),
        ]

    class GitPathsRequest(m.ContractModel):
        """Repository plus multiple relative paths for add/restore operations."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        paths: Annotated[
            t.SequenceOf[t.NonEmptyStr],
            m.Field(description="Relative paths to operate on"),
        ]

    class GitCommitRequest(m.ContractModel):
        """Repository plus commit message for staging a commit."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        message: Annotated[t.NonEmptyStr, m.Field(description="Commit message")]

    class GitRemoteUrlRequest(m.ContractModel):
        """Repository plus optional remote name for URL resolution."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        remote: Annotated[t.NonEmptyStr, m.Field(description="Remote name")] = "origin"

    class GitSubmoduleContractRequest(m.ContractModel):
        """Superproject plus one declared submodule path for contract reads."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Superproject worktree root")]
        member_path: Annotated[
            t.NonEmptyStr,
            m.Field(description="Submodule path relative to the superproject root"),
        ]

    class GitSubmoduleContractReport(m.ContractModel):
        """Declared ``.gitmodules`` URL and branch for one submodule path."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        url: Annotated[t.NonEmptyStr, m.Field(description="Declared submodule URL")]
        branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Declared submodule branch"),
        ]

    class GitLaneRequest(m.ContractModel):
        """One publication lane: ``branch`` carried from ``base`` to a pull request."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        branch: Annotated[t.NonEmptyStr, m.Field(description="Lane branch")]
        base: Annotated[
            t.NonEmptyStr,
            m.Field(description="Integration branch the lane starts from and targets"),
        ]
        subject: Annotated[
            t.NonEmptyStr,
            m.Field(description="Commit subject and pull-request title"),
        ]
        body_file: Annotated[Path, m.Field(description="Pull-request body file")]

    class GitCheckoutPathsRequest(m.ContractModel):
        """Repository plus optional paths for checkout/restore operations."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_root: Annotated[Path, m.Field(description="Repository worktree root")]
        paths: Annotated[
            t.SequenceOf[t.NonEmptyStr],
            m.Field(description="Relative paths to restore; empty restores all"),
        ] = ()


__all__: list[str] = ["FlextInfraModelsGit"]
