"""Worktree facts models — nested container for FLEXT composition."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal

from flext_cli import m

from flext_infra import t


class FlextInfraModelsGitWorktreeFacts:
    """Measured facts about one repository's registered worktrees."""

    class GitTreeStats(m.ContractModel):
        """Bounded tree measurement for one directory."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        total_bytes: Annotated[int, m.Field(ge=0, description="Sum of file sizes")]
        newest_mtime: Annotated[
            float, m.Field(ge=0, description="Newest file mtime as epoch seconds")
        ]
        exact: Annotated[
            bool, m.Field(description="Whether the walk completed without skipping")
        ]

    class WorktreeFact(m.ContractModel):
        """One registered worktree with measured size and staleness facts."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        name: Annotated[t.NonEmptyStr, m.Field(description="Worktree directory name")]
        path: Annotated[Path, m.Field(description="Worktree root")]
        repo: Annotated[Path, m.Field(description="Owning repository root")]
        kind: Annotated[
            Literal["sibling", "tool_internal"],
            m.Field(description="Sibling checkout or tool-internal agent worktree"),
        ]
        bytes: Annotated[int, m.Field(ge=0, default=0, description="Total tree bytes")]
        deps_bytes: Annotated[
            int, m.Field(ge=0, default=0, description="Rebuildable dependency bytes")
        ]
        stale_days: Annotated[
            float, m.Field(ge=0, default=0.0, description="Days since newest mtime")
        ]
        exact: Annotated[
            bool, m.Field(default=True, description="Whether measurement completed")
        ]
        branch: Annotated[str, m.Field(default="", description="Checked-out branch")]
        retire_candidate: Annotated[
            bool, m.Field(default=False, description="Stale beyond the activity window")
        ]

    class WorktreesReport(m.ContractModel):
        """Facts for every registered worktree of one repository."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        facts: Annotated[
            t.VariadicTuple[FlextInfraModelsGitWorktreeFacts.WorktreeFact],
            m.Field(default=(), description="One fact per registered worktree"),
        ]


__all__: list[str] = ["FlextInfraModelsGitWorktreeFacts"]
