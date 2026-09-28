"""Real Git + shim bd behavior for make work saga."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService
from tests import c, t, u

if TYPE_CHECKING:
    from pathlib import Path as PathType


from tests.unit.workspace.work_service_fixture import WorkServiceFixture


class TestsWorkServiceTopology(WorkServiceFixture):
    """Exercise the public work service lifecycle through real Git."""

    @pytest.mark.parametrize(
        ("issue_type", "expected_branch"),
        [
            ("epic", "epic/derived-kind"),
            ("feature", "feature/derived-kind"),
            ("bug", "bugfix/derived-kind"),
        ],
    )
    def test_start_derives_kind_from_issue_type(
        self,
        tmp_path: PathType,
        monkeypatch: pytest.MonkeyPatch,
        issue_type: str,
        expected_branch: str,
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = f"mro-{issue_type}-kind"
        shim_dir = self._install_bd_shim(
            tmp_path, bead_id, issue_types={bead_id: issue_type}
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                name="derived-kind",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has=f"BRANCH={expected_branch}")

    def test_start_refuses_explicit_gitflow_kind_for_epic_issue(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-epic-explicit-kind"
        shim_dir = self._install_bd_shim(
            tmp_path, bead_id, issue_types={bead_id: "epic"}
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="epic-explicit-kind",
            base="HEAD",
            apply_changes=True,
        ).execute()

        tm.fail(result, has="epic issue derives the epic branch namespace")

    def test_start_refuses_missing_issue_type_without_kind_override(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-missing-kind"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            name="missing-kind",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="missing issue_type")

    def _started_epic_lane(
        self,
        tmp_path: PathType,
        repository: PathType,
        epic_bead: str,
        child_bead: str,
        *,
        child_name: str = "child-one",
    ) -> tuple[PathType, PathType]:
        """Start one epic lane and one child lane nested below it."""
        store_path = tmp_path / "beads-store.json"
        store = t.json_dict_adapter().validate_python(
            u.Cli.json_loads(store_path.read_text(encoding="utf-8")).unwrap()
        )
        epic_issue = t.json_dict_adapter().validate_python(store[epic_bead])
        child_issue = t.json_dict_adapter().validate_python(store[child_bead])
        epic_issue["issue_type"] = "epic"
        child_issue["parent"] = epic_bead
        store[epic_bead] = epic_issue
        store[child_bead] = child_issue
        store_path.write_text(u.Cli.json_dumps(store).unwrap(), encoding="utf-8")
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=epic_bead,
                name="epic-alpha",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=child_bead,
                kind=c.Infra.WorkKind.FEATURE,
                name=child_name,
                epic=epic_bead,
                apply_changes=True,
            ).execute()
        )
        return (
            Path(self._metadata(tmp_path, epic_bead)["worktree"]),
            Path(self._metadata(tmp_path, child_bead)["worktree"]),
        )

    def test_start_child_nests_under_the_registered_epic(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A child lane derives its base and its container from its epic."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic"
        child_bead = "mro-test-child"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "task"},
            parents={child_bead: epic_bead},
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=epic_bead,
                name="epic-alpha",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        epic_lane = Path(self._metadata(tmp_path, epic_bead)["worktree"])

        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=child_bead,
                kind=c.Infra.WorkKind.FEATURE,
                name="child-one",
                epic=epic_bead,
                apply_changes=True,
            ).execute()
        )

        tm.that(started, has=f"EPIC={epic_bead}")
        tm.that(started, has="BASE=epic/epic-alpha")
        child = self._metadata(tmp_path, child_bead)
        tm.that(child["role"], eq=c.Infra.WorkLaneRole.CHILD.value)
        tm.that(child["epic_bead"], eq=epic_bead)
        tm.that(child["epic_branch"], eq="epic/epic-alpha")
        tm.that(child["epic_worktree"], eq=str(epic_lane))
        tm.that(child["child_slug"], eq="child-one")
        tm.that(child["integration_base"], eq="epic/epic-alpha")
        container = epic_lane / c.Infra.WORKTREES_DIRNAME
        tm.that(Path(child["worktree"]), eq=container / "child-one")
        tm.that(
            self._metadata(tmp_path, epic_bead)["role"],
            eq=c.Infra.WorkLaneRole.EPIC.value,
        )
        tm.that(
            tm.ok(FlextInfraWorktreeService.registered_children(repository, epic_lane)),
            eq=(Path(child["worktree"]),),
        )

    def test_start_child_refuses_a_literal_base_beside_its_epic(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The epic alone decides where a child branches from."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-base"
        child_bead = "mro-test-child-base"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "task"},
            parents={child_bead: epic_bead},
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=epic_bead,
                name="epic-alpha",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=child_bead,
            kind=c.Infra.WorkKind.FEATURE,
            name="child-one",
            epic=epic_bead,
            base="HEAD",
            apply_changes=True,
        ).execute()

        tm.fail(result, has="drop --base")

    def test_start_child_refuses_an_epic_that_owns_no_lane(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A child never precedes the epic lane it must nest under."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-absent"
        child_bead = "mro-test-child-absent"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "task"},
            parents={child_bead: epic_bead},
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=child_bead,
            kind=c.Infra.WorkKind.FEATURE,
            name="child-one",
            epic=epic_bead,
            apply_changes=True,
        ).execute()

        tm.fail(result, has=f"epic bead {epic_bead} lane is not ready")

    def test_status_reports_the_registered_epic_topology(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Status proves the recorded topology against Git's registry."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-status"
        child_bead = "mro-test-child-status"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "feature"},
            parents={child_bead: epic_bead},
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        epic_lane, child_lane = self._started_epic_lane(
            tmp_path, repository, epic_bead, child_bead
        )

        epic_status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=epic_bead,
                apply_changes=False,
            ).execute()
        )
        child_status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=child_bead,
                apply_changes=False,
            ).execute()
        )

        tm.that(epic_status, has=f"epic_topology: epic children=1 {child_lane}")
        tm.that(child_status, has=f"epic_topology: child of {epic_lane}")

    def test_status_of_a_plain_lane_reports_no_epic_topology(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A lane without an epic keeps the exact status it always had."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-plain-status"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="plain-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )

        status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=bead_id,
                apply_changes=False,
            ).execute()
        )

        assert "epic_topology" not in status
        assert "metadata.role" not in status

    # Why (suite budget): builds an epic lane plus a nested child worktree with
    # real git submodule scans; the per-case wall only holds on an idle CPU.
    @pytest.mark.slow
    def test_finish_refuses_the_epic_until_its_child_is_finished(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A child lane pins its epic lane, and finishing the child frees it."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-finish"
        child_bead = "mro-test-child-finish"
        shim_dir = self._install_bd_shim(tmp_path, epic_bead, child_bead)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        epic_lane, child_lane = self._started_epic_lane(
            tmp_path, repository, epic_bead, child_bead
        )
        for bead_id, pr_number in ((epic_bead, "1"), (child_bead, "2")):
            self._update_root_matrix_entry(tmp_path, bead_id, pr_number=pr_number)

        refused = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=epic_bead,
            apply_changes=True,
        ).execute()

        tm.fail(refused, has="while children are registered")
        tm.fail(refused, has=str(child_lane))
        tm.that(epic_lane.is_dir(), where=bool)

        tm.that(
            tm.ok(
                FlextInfraWorkService(
                    workspace_root=repository,
                    operation=c.Infra.WorkOperation.FINISH,
                    bead=child_bead,
                    apply_changes=True,
                ).execute()
            ),
            has="FINISHED BRANCH=feature/child-one",
        )
        tm.that(
            tm.ok(
                FlextInfraWorkService(
                    workspace_root=repository,
                    operation=c.Infra.WorkOperation.FINISH,
                    bead=epic_bead,
                    apply_changes=True,
                ).execute()
            ),
            has="FINISHED BRANCH=epic/epic-alpha",
        )
        assert not epic_lane.exists()

    def test_finish_refuses_a_child_lane_outside_its_epic_namespace(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recorded child metadata never overrides the real lane topology."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-escape"
        child_bead = "mro-test-child-escape"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "feature"},
            parents={child_bead: epic_bead},
        )
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=epic_bead,
                name="epic-alpha",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        epic_lane = Path(self._metadata(tmp_path, epic_bead)["worktree"])
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=child_bead,
                kind=c.Infra.WorkKind.FEATURE,
                name="outside-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, child_bead)
        record["metadata"] |= {
            "role": c.Infra.WorkLaneRole.CHILD.value,
            "epic_bead": epic_bead,
            "epic_branch": "epic/epic-alpha",
            "epic_worktree": str(epic_lane),
            "child_slug": "outside-lane",
        }
        self._set_record(tmp_path, child_bead, record)

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=child_bead,
            apply_changes=True,
        ).execute()

        tm.fail(result, has="is not nested under epic lane")
        tm.fail(result, has=str(epic_lane))
