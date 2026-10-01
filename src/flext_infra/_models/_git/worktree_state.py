"""Durable, scoped Git worktree capture contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from flext_cli import m

from flext_infra import t


class FlextInfraModelsGitWorktreeState:
    """Declarations for independently recoverable index and working files."""

    class GitMutationScope(m.ContractModel):
        """Physical file scope and its optional validated Git worktree owner."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        root: Annotated[Path, m.Field(description="Physical requested mutation root")]
        git_dir: Annotated[
            Path | None,
            m.Field(
                description="Validated worktree Git directory, absent only for file scopes"
            ),
        ]

    class GitWorktreeCheckpointPublication(m.ContractModel):
        """Exact credential-free endpoint and durable remote checkpoint proof."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        remote_name: Annotated[
            str, m.Field(description="Configured remote used for publication")
        ]
        remote_url: Annotated[
            str,
            m.Field(description="Exact verified credential-free fetch and push URL"),
        ]
        checkpoint_ref: Annotated[
            str, m.Field(description="Published dedicated checkpoint reference")
        ]
        checkpoint_oid: Annotated[
            str, m.Field(description="Exact advertised checkpoint commit")
        ]

    class GitWorktreeStateRequest(m.ContractModel):
        """Literal repository-relative owned paths; directories select subtrees."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        retained_commits: Annotated[
            t.VariadicTuple[str],
            m.Field(
                description="Additional child commits referenced by owning gitlinks"
            ),
        ] = ()
        repo_root: Annotated[
            Path, m.Field(description="Source repository worktree root")
        ]
        paths: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Literal owned relative paths; empty selects nothing"),
        ]

    class GitWorktreeIndexEntry(m.ContractModel):
        """One stage-zero Git index entry."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        path: Annotated[Path, m.Field(description="Repository-relative index path")]
        mode: Annotated[str, m.Field(description="Git octal index entry mode")]
        oid: Annotated[
            str, m.Field(description="Index blob or gitlink object identifier")
        ]

    class GitWorktreeObservedFile(m.ContractModel):
        """The observed worktree layer of one file before a guarded effect.

        The guarded-effect precondition hashes these bytes itself (the hash
        is the comparison), so this is the pre-hash identity: raw content
        (symlink target text for links, ``None`` for an absent file), the
        git mode string, and the exact permission bits.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        content: Annotated[
            bytes | None,
            m.Field(
                description="Raw working bytes; link text for symlinks, None when absent"
            ),
        ]
        mode: Annotated[str, m.Field(description="Git mode for raw bytes or symlink")]
        permissions: Annotated[
            int, m.Field(description="Exact filesystem permission bits")
        ]

    class GitWorktreeFileState(m.ContractModel):
        """Exact working bytes and permissions, including symlink link text."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        path: Annotated[Path, m.Field(description="Repository-relative working path")]
        mode: Annotated[
            str, m.Field(description="Git mode for raw bytes, symlink or gitlink")
        ]
        permissions: Annotated[
            int,
            m.Field(description="Exact filesystem permission bits; zero for gitlinks"),
        ]
        oid: Annotated[
            str,
            m.Field(
                description="Object identifier for raw bytes or current gitlink HEAD"
            ),
        ]

    class GitWorktreeObservedContent(m.ContractModel):
        """Observed working bytes with their filesystem state before hashing."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        path: Annotated[Path, m.Field(description="Repository-relative working path")]
        content: Annotated[
            bytes | None,
            m.Field(description="Observed working bytes; absent means no file"),
        ]
        mode: Annotated[
            str, m.Field(description="Git mode the observed bytes classify as")
        ]
        permissions: Annotated[
            int,
            m.Field(description="Exact filesystem permission bits of the observation"),
        ]

    class GitWorktreeStateSnapshot(m.ContractModel):
        """Scoped source identity and both independently measured layers."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        retained_commits: Annotated[
            t.VariadicTuple[str],
            m.Field(
                description="Additional resolved commits retained by checkpoint ancestry"
            ),
        ] = ()
        head_entries: Annotated[
            t.VariadicTuple[FlextInfraModelsGitWorktreeState.GitWorktreeIndexEntry],
            m.Field(
                description="Original HEAD entries including deleted gitlink preimages"
            ),
        ]
        repo_root: Annotated[Path, m.Field(description="Original source worktree root")]
        common_dir: Annotated[
            Path, m.Field(description="Shared Git object storage identity")
        ]
        head: Annotated[
            str, m.Field(description="Original HEAD commit object identifier")
        ]
        paths: Annotated[
            t.VariadicTuple[Path], m.Field(description="Exact literal ownership scope")
        ]
        index_entries: Annotated[
            t.VariadicTuple[FlextInfraModelsGitWorktreeState.GitWorktreeIndexEntry],
            m.Field(description="Captured stage-zero index entries"),
        ]
        files: Annotated[
            t.VariadicTuple[FlextInfraModelsGitWorktreeState.GitWorktreeFileState],
            m.Field(description="Captured raw working files and gitlink heads"),
        ]

    class GitWorktreeStateCheckpoint(m.ContractModel):
        """Reachable commits retain both original layers after save and GC."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        snapshot: Annotated[
            FlextInfraModelsGitWorktreeState.GitWorktreeStateSnapshot,
            m.Field(description="Original immutable ownership and state evidence"),
        ]
        checkpoint_ref: Annotated[
            str, m.Field(description="Durable dedicated Git reference")
        ]
        index_commit: Annotated[
            str,
            m.Field(description="Reachable commit retaining the original index tree"),
        ]
        worktree_commit: Annotated[
            str,
            m.Field(
                description="Reachable commit retaining raw working bytes and snapshot metadata"
            ),
        ]


__all__: list[str] = ["FlextInfraModelsGitWorktreeState"]
