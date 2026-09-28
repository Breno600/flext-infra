"""Typed contracts for isolated worktree command transactions."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, ClassVar, Literal

from flext_cli import m

from .. import t


class FlextInfraModelsWorktree:
    """Declaration-only models for transactional fix and codegen execution."""

    class LintSnapshot(m.ContractModel):
        """Captured diagnostics from one lint tool invocation."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        tool: Annotated[t.NonEmptyStr, m.Field(description="Canonical tool name")]
        exit_code: Annotated[int, m.Field(description="Tool process exit code")]
        errors: Annotated[
            t.NonNegativeInt, m.Field(description="Detected error count")
        ] = 0
        warnings: Annotated[
            t.NonNegativeInt, m.Field(description="Detected warning count")
        ] = 0
        output: Annotated[str, m.Field(description="Combined captured tool output")] = (
            ""
        )

    class RepositoryDelta(m.ContractModel):
        """Operation-only patch for one repository in a workspace transaction."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        relative_path: Annotated[
            t.NonEmptyStr,
            m.Field(description="Repository path relative to the repository root"),
        ]
        source_root: Annotated[
            Path, m.Field(description="Original repository worktree root")
        ]
        worktree_root: Annotated[
            Path, m.Field(description="Temporary repository worktree root")
        ]
        checkpoint_sha: Annotated[
            t.NonEmptyStr, m.Field(description="Synthetic dirty-state checkpoint SHA")
        ]
        changed_files: Annotated[
            t.StrSequence, m.Field(description="Files changed by the isolated command")
        ] = ()
        patch: Annotated[
            bytes,
            m.Field(b"", description="Binary Git patch relative to the checkpoint"),
        ] = b""

    class RepositoryWorktree(m.ContractModel):
        """One source repository paired with its isolated worktree checkpoint."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        relative_path: Annotated[
            t.NonEmptyStr,
            m.Field(description="Repository path relative to the repository root"),
        ]
        source_root: Annotated[
            Path, m.Field(description="Original repository worktree root")
        ]
        worktree_root: Annotated[
            Path, m.Field(description="Temporary detached repository worktree root")
        ]
        checkpoint_sha: Annotated[
            t.NonEmptyStr, m.Field(description="Current isolated checkpoint SHA")
        ]

    class WorktreeFactsPolicy(m.ContractModel):
        """Worktree-layout facts the canonical primitive consumes.

        Every pattern is policy-owned: the primitive hardcodes no internal
        layout or dependency directory name, and empty tuples make collection
        a no-op that reports nothing.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        tool_internal: Annotated[
            t.StrSequence,
            m.Field(description="Path fragments classifying tool-internal worktrees"),
        ] = ()
        deps_dirs: Annotated[
            t.StrSequence,
            m.Field(description="Rebuildable dependency directories inside a worktree"),
        ] = ()

    class WorktreeFactsQuery(m.ContractModel):
        """One worktree facts request: the roots, policy, clock, and evidence.

        The query carries everything the primitive needs, so callers state the
        scan once and correlation evidence stays optional and boundary-typed.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        repo_roots: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Repository roots whose registry is scanned"),
        ]
        policy: Annotated[
            FlextInfraModelsWorktree.WorktreeFactsPolicy,
            m.Field(description="Layout and dependency vocabulary to apply"),
        ]
        now: Annotated[float, m.Field(description="Current epoch seconds")]
        activity_window_days: Annotated[
            int, m.Field(ge=0, description="Staleness window in days")
        ]
        bead_rows: Annotated[
            t.VariadicTuple[t.JsonMapping],
            m.Field(description="Optional bead rows for correlation"),
        ] = ()
        actor_evidence: Annotated[
            t.MappingKV[str, t.Pair[str, str]] | None,
            m.Field(description="Optional worktree-path to (actor, session) evidence"),
        ] = None

    class WorktreeCandidate(m.ContractModel):
        """One registered worktree paired with its owning repository and branch."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        path: Annotated[Path, m.Field(description="Worktree checkout root")]
        repo: Annotated[Path, m.Field(description="Owning repository root")]
        branch: Annotated[str, m.Field(description="HEAD-derived branch")] = ""

    class WorktreeFact(m.ContractModel):
        """One registered worktree measured for the facts report."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        name: Annotated[t.NonEmptyStr, m.Field(description="Worktree directory name")]
        path: Annotated[Path, m.Field(description="Worktree checkout root")]
        repo: Annotated[Path, m.Field(description="Owning repository root")]
        kind: Annotated[
            Literal["sibling", "tool_internal"],
            m.Field(description="Layout kind of the registered worktree"),
        ]
        bytes: Annotated[t.NonNegativeInt, m.Field(description="Total tree bytes")] = 0
        deps_bytes: Annotated[
            t.NonNegativeInt, m.Field(description="Rebuildable deps bytes")
        ] = 0
        stale_days: Annotated[
            float, m.Field(ge=0, description="Days since the newest mtime")
        ] = 0.0
        exact: Annotated[
            bool, m.Field(description="Whether the measurement hit no bound")
        ] = True
        branch: Annotated[str, m.Field(description="HEAD-derived branch")] = ""
        bead: Annotated[str, m.Field(description="Correlated bead id")] = ""
        pr_number: Annotated[
            int | None, m.Field(description="Correlated pull request number")
        ] = None
        actor: Annotated[str, m.Field(description="Last known actor")] = ""
        session_id: Annotated[str, m.Field(description="Attributed session id")] = ""
        retire_candidate: Annotated[
            bool,
            m.Field(description="Retirement candidate; execution never happens here"),
        ] = False

    class PruneAction(m.ContractModel):
        """One planned mutation, fully described before any execution."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        kind: Annotated[
            Literal[
                "cache-expire",
                "cache-lru",
                "log-truncate",
                "tmp-expire",
                "trash-empty",
                "quarantine-expire",
                "junk-remove",
                "dir-move",
                "file-move",
                "dir-remove",
                "contents-remove",
            ],
            m.Field(description="Mutation strategy for the subject path"),
        ]
        path: Annotated[Path, m.Field(description="Mutation subject")]
        reason: Annotated[
            t.NonEmptyStr, m.Field(description="Why the action is planned")
        ]
        owner: Annotated[t.NonEmptyStr, m.Field(description="Owning surface")]
        reclaim_bytes: Annotated[
            t.NonNegativeInt, m.Field(description="Bytes the action reclaims")
        ] = 0

    class PrunePlan(m.ContractModel):
        """The full action plan rendered before anything is written."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        generated_at: Annotated[datetime, m.Field(description="UTC plan instant")]
        mode: Annotated[str, m.Field(description="Detected execution mode")]
        apply: Annotated[bool, m.Field(description="Whether this plan will execute")]
        actions: Annotated[
            t.VariadicTuple[FlextInfraModelsWorktree.PruneAction],
            m.Field(description="Planned actions in stable order"),
        ] = ()
        total_reclaim_bytes: Annotated[
            t.NonNegativeInt, m.Field(description="Total bytes the plan reclaims")
        ] = 0

    class WorktreesReport(m.ContractModel):
        """The worktree facts report: measured facts plus the planned actions."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        facts: Annotated[
            t.VariadicTuple[FlextInfraModelsWorktree.WorktreeFact],
            m.Field(description="Every measured registered worktree"),
        ] = ()
        plan: Annotated[
            FlextInfraModelsWorktree.PrunePlan | None,
            m.Field(description="Planned stale-deps pruning, when any"),
        ] = None


__all__: list[str] = ["FlextInfraModelsWorktree"]
