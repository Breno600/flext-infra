"""Worktree checkpoint-state models — nested container for FLEXT composition."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, ClassVar

from flext_cli import m

from flext_infra import t

from .identity import FlextInfraModelsGitIdentity


class FlextInfraModelsGitWorktreeState:
    """Durable worktree checkpoint models, composed into m.Infra via FLEXT."""

    class GitWorktreeStateCheckpoint(m.ContractModel):
        """Non-destructive protection of one worktree's index and working blobs.

        The checkpoint commits live behind ``checkpoint_ref`` and never touch
        HEAD, the index, or the working tree; ``snapshot`` is the identity the
        checkpoint was taken from (its ``common_dir`` is the reconciliation
        key for linked worktrees).
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        snapshot: Annotated[
            FlextInfraModelsGitIdentity.GitIdentityReport,
            m.Field(
                description="Authenticated source Git state the checkpoint protects."
            ),
        ]
        checkpoint_ref: Annotated[
            t.NonEmptyStr,
            m.Field(description="Fully qualified ref holding the checkpoint commits."),
        ]
        checkpoint_commit: Annotated[
            t.NonEmptyStr, m.Field(description="Tip commit oid of the checkpoint ref.")
        ]
        created_at: Annotated[
            datetime, m.Field(description="UTC instant the checkpoint was recorded.")
        ]

    class GitWorktreeCheckpointPublication(m.ContractModel):
        """Record of one checkpoint ref published to its capture remote."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        checkpoint_ref: Annotated[
            t.NonEmptyStr,
            m.Field(description="Fully qualified ref that was published."),
        ]
        remote: Annotated[
            t.NonEmptyStr, m.Field(description="Remote name the ref was pushed to.")
        ]
        published_commit: Annotated[
            t.NonEmptyStr, m.Field(description="Remote tip commit oid after the push.")
        ]
        published_at: Annotated[
            datetime, m.Field(description="UTC instant the publication was recorded.")
        ]


__all__: list[str] = ["FlextInfraModelsGitWorktreeState"]
