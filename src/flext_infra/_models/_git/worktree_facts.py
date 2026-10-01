"""Worktree facts models — nested container for FLEXT composition."""

from __future__ import annotations

from typing import Annotated, ClassVar

from flext_cli import m


class FlextInfraModelsGitWorktreeFacts:
    """Measured facts about one repository's registered worktrees."""

    class GitTreeStats(m.ContractModel):
        """Bounded tree measurement for one directory."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        total_bytes: Annotated[int, m.Field(ge=0, description="Sum of file sizes")]
        newest_mtime: Annotated[
            float, m.Field(ge=0, description="Newest file mtime as epoch seconds"),
        ]
        exact: Annotated[
            bool, m.Field(description="Whether the walk completed without skipping"),
        ]


__all__: list[str] = ["FlextInfraModelsGitWorktreeFacts"]
