"""Adversarial real-Git operations for public work scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Self

import pytest

from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService, c, m, p, u
from flext_tests import tm
from tests import u as test_u
from tests.unit.workspace.work_public_finish_fixture import (
    ChildFinishState,
    WorkPublicFinishFixture,
)


@dataclass(frozen=True, slots=True)
class MetadataSnapshot:
    epic: m.Infra.ReadyLaneMetadata
    child: m.Infra.ReadyLaneMetadata


@dataclass(frozen=True, slots=True)
class WorkAdversarialFixture:
    finish: WorkPublicFinishFixture

    @classmethod
    def create(cls, root: Path, monkeypatch: pytest.MonkeyPatch) -> Self:
        fixture = WorkPublicFinishFixture.create(root, monkeypatch)
        manifest = fixture.repository / "config" / "workspace.yaml"
        tm.ok(
            u.Cli.files_write_text(
                manifest,
                manifest.read_text(encoding="utf-8")
                + "integration:\n  provider: fixture\n  branch: 0.12.0-dev\n",
            )
        )
        return cls(fixture)

    def divergent_finish_state(self) -> ChildFinishState:
        state = self.finish.start_and_land()
        self.finish.advance_remote_epic_with_child(state)
        self.finish.advance_local_epic(state)
        self.finish.mark_pr_merged(state)
        return state

    def conflicting_finish_state(self) -> ChildFinishState:
        state = self.finish.start_and_land()
        shared = state.epic_lane / "shared.txt"
        shared.write_text("base\n", encoding="utf-8")
        self._commit(state.epic_lane, "shared base")
        self._push(state.epic_lane, state.epic_branch)
        self._persist_epic(state)
        shared.write_text("local\n", encoding="utf-8")
        self._commit(state.epic_lane, "local conflict")
        self._persist_epic(state)
        remote = self.finish.boundary.root / "remote-epic"
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "clone", str(self.finish.boundary.origin), str(remote)],
                cwd=self.finish.boundary.root,
            )
        )
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "checkout", state.epic_branch], cwd=remote
            )
        )
        (remote / "shared.txt").write_text("remote\n", encoding="utf-8")
        self._commit(remote, "remote conflict")
        self._push(remote, state.epic_branch)
        self.finish.mark_pr_merged(state)
        return state

    def metadata_snapshot(self, state: ChildFinishState) -> MetadataSnapshot:
        return MetadataSnapshot(
            self.finish.ready_metadata(state.epic_bead),
            self.finish.ready_metadata(state.child_bead),
        )

    def finish_child(self, state: ChildFinishState) -> p.Result[str]:
        return FlextInfraWorkService(
            workspace_root=self.finish.repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=state.child_bead,
            apply_changes=True,
        ).execute()

    def land_parent(self, state: ChildFinishState) -> p.Result[str]:
        self.finish.boundary.pr_receipt.unlink(missing_ok=True)
        return FlextInfraWorkService(
            workspace_root=self.finish.repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=state.epic_bead,
            apply_changes=True,
        ).execute()

    def fail_updates_for(self, bead_id: str) -> None:
        self.finish.boundary.fail_updates_for(bead_id)

    def dirty_epic(self, state: ChildFinishState) -> None:
        (state.epic_lane / "dirty.txt").write_text("operator wip\n", encoding="utf-8")

    def remote_epic_oid(self, state: ChildFinishState) -> str:
        return self.finish.oid(
            self.finish.repository, f"refs/remotes/origin/{state.epic_branch}"
        )

    def both_lanes_registered(self, state: ChildFinishState) -> bool:
        return all(
            tm.ok(
                FlextInfraWorktreeService.registered_lane(
                    self.finish.repository, branch
                )
            )
            == lane
            for branch, lane in (
                (state.epic_branch, state.epic_lane),
                (state.child_branch, state.child_lane),
            )
        )

    def has_unmerged_paths(self, repository: Path) -> bool:
        return bool(
            tm.ok(
                u.Cli.capture(
                    (c.Infra.GIT, "diff", "--name-only", "--diff-filter=U"),
                    cwd=repository,
                )
            )
        )

    def registered_children(self, state: ChildFinishState) -> tuple[Path, ...]:
        return tm.ok(
            FlextInfraWorktreeService.registered_children(
                self.finish.repository, state.epic_lane
            )
        )

    def remote_parent_contains_child(self, state: ChildFinishState) -> bool:
        tm.ok(
            u.Infra.git_fetch_origin(
                m.Infra.GitRepoRequest(repo_root=self.finish.repository)
            )
        )
        return self.finish.is_ancestor(
            self.finish.repository,
            state.child_oid,
            f"refs/remotes/origin/{state.epic_branch}",
        )

    def _persist_epic(self, state: ChildFinishState) -> None:
        metadata = self.finish.ready_metadata(state.epic_bead)
        oid = self.finish.oid(state.epic_lane, "HEAD")
        tm.ok(
            u.Infra.beads_update_lane(
                state.epic_bead,
                metadata=metadata.model_copy(update={"head_oid": oid}),
                root=self.finish.repository,
            )
        )

    @staticmethod
    def _commit(repository: Path, message: str) -> None:
        tm.ok(test_u.Cli.run_checked([c.Infra.GIT, "add", "."], cwd=repository))
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "commit", "-m", message], cwd=repository
            )
        )

    @staticmethod
    def _push(repository: Path, branch: str) -> None:
        tm.ok(
            test_u.Cli.run_checked(
                [c.Infra.GIT, "push", "origin", branch], cwd=repository
            )
        )


__all__: tuple[str, ...] = ("MetadataSnapshot", "WorkAdversarialFixture")
