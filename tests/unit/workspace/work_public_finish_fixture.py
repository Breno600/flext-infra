"""Typed remote-epic operations for public FINISH scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Self

import pytest

from flext_infra import FlextInfraWorkService, c, m, u
from flext_tests import tm
from tests import u as test_u
from tests.unit.workspace.work_public_service_fixture import WorkPublicServiceFixture


@dataclass(frozen=True, slots=True)
class ChildFinishState:
    epic_bead: str
    child_bead: str
    epic_branch: str
    child_branch: str
    epic_lane: Path
    child_lane: Path
    child_oid: str


@dataclass(frozen=True, slots=True)
class WorkInvocation:
    operation: c.Infra.WorkOperation
    bead: str
    name: str | None = None
    base: str | None = None
    epic: str | None = None


@dataclass(frozen=True, slots=True)
class WorkPublicFinishFixture:
    boundary: WorkPublicServiceFixture

    @classmethod
    def create(cls, root: Path, monkeypatch: pytest.MonkeyPatch) -> Self:
        return cls(WorkPublicServiceFixture.create(root, monkeypatch))

    @property
    def repository(self) -> Path:
        return self.boundary.repository

    def start_and_land(self) -> ChildFinishState:
        epic_bead, child_bead = "mro-finish-epic", "mro-finish-child"
        self.boundary.add_issue(epic_bead, issue_type="epic")
        self.boundary.add_issue(child_bead, issue_type="task", parent=epic_bead)
        self._execute(
            WorkInvocation(
                c.Infra.WorkOperation.START, epic_bead, name="finish-epic", base="HEAD"
            )
        )
        self._execute(
            WorkInvocation(
                c.Infra.WorkOperation.START,
                child_bead,
                name="finish-child",
                epic=epic_bead,
            )
        )
        epic = self.ready_metadata(epic_bead)
        child = self.ready_metadata(child_bead)
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "push", "origin", epic.branch], cwd=epic.worktree
            )
        )
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "commit", "--allow-empty", "-m", "child change"],
                cwd=child.worktree,
            )
        )
        self._execute(WorkInvocation(c.Infra.WorkOperation.LAND, child_bead))
        child = self.ready_metadata(child_bead)
        return ChildFinishState(
            epic_bead,
            child_bead,
            epic.branch,
            child.branch,
            epic.worktree,
            child.worktree,
            self.oid(child.worktree, "HEAD"),
        )

    def advance_remote_epic_with_child(self, state: ChildFinishState) -> str:
        tm.ok(
            test_u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "push",
                    "origin",
                    f"{state.child_oid}:refs/heads/{state.epic_branch}",
                ],
                cwd=state.child_lane,
            )
        )
        return state.child_oid

    def advance_local_epic(self, state: ChildFinishState) -> str:
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "commit", "--allow-empty", "-m", "local epic advance"],
                cwd=state.epic_lane,
            )
        )
        return self._persist_epic_head(state)

    def fast_forward_local_epic(self, state: ChildFinishState, oid: str) -> None:
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "merge", "--ff-only", oid], cwd=state.epic_lane
            )
        )
        self._persist_epic_head(state)

    def mark_pr_merged(self, state: ChildFinishState) -> None:
        self.boundary.set_merged_pr(head=state.child_branch)

    def ready_metadata(self, bead_id: str) -> m.Infra.ReadyLaneMetadata:
        metadata = self.boundary.issue(bead_id).metadata
        assert isinstance(metadata, m.Infra.ReadyLaneMetadata)
        return metadata

    def oid(self, repository: Path, commitish: str) -> str:
        report: m.Infra.GitOidReport = tm.ok(
            u.Infra.git_rev_parse(
                m.Infra.GitCommitishRequest(repo_root=repository, commitish=commitish)
            )
        )
        return report.oid

    def parent_count(self, repository: Path, oid: str) -> int:
        output = tm.ok(
            u.Cli.capture(
                (c.Infra.GIT, "show", "-s", "--format=%P", oid), cwd=repository
            )
        )
        return len(output.split())

    def is_ancestor(self, repository: Path, ancestor: str, descendant: str) -> bool:
        result = u.Cli.run_raw(
            (c.Infra.GIT, "merge-base", "--is-ancestor", ancestor, descendant),
            cwd=repository,
        )
        return tm.ok(result).exit_code == 0

    def epic_update_precedes_child_retirement(self, state: ChildFinishState) -> bool:
        events = self.boundary.update_events()
        epic_index = next(
            index
            for index, event in enumerate(events)
            if event.get("bead") == state.epic_bead
            and event.get("head_oid") == self.oid(state.epic_lane, "HEAD")
        )
        child_index = next(
            index
            for index, event in enumerate(events)
            if event.get("bead") == state.child_bead
            and event.get("worktree") == "removed"
        )
        return epic_index < child_index

    def _persist_epic_head(self, state: ChildFinishState) -> str:
        metadata = self.ready_metadata(state.epic_bead)
        oid = self.oid(state.epic_lane, "HEAD")
        tm.ok(
            u.Infra.beads_update_lane(
                state.epic_bead,
                metadata=metadata.model_copy(update={"head_oid": oid}),
                root=self.repository,
            )
        )
        return oid

    def _execute(self, invocation: WorkInvocation) -> None:
        tm.ok(
            FlextInfraWorkService(
                workspace_root=self.repository,
                operation=invocation.operation,
                bead=invocation.bead,
                name=invocation.name,
                base=invocation.base,
                epic=invocation.epic,
                apply_changes=True,
            ).execute()
        )


__all__: tuple[str, ...] = (
    "ChildFinishState",
    "WorkInvocation",
    "WorkPublicFinishFixture",
)
