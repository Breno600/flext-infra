"""Real Git + shim bd behavior for make work saga."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path as PathType


from tests.unit.workspace.work_service_fixture import WorkServiceFixture


class TestsFlextInfraWorkService(WorkServiceFixture):
    """Exercise the public work service lifecycle through real Git."""

    def test_start_registers_lane_and_status_reports_metadata(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-work"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="example-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has="BRANCH=feature/example-lane")
        tm.that(started, has="WORKTREE=")
        status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=bead_id,
                apply_changes=False,
            ).execute()
        )
        tm.that(status, has="metadata.branch: feature/example-lane")
        tm.that(status, has="metadata.worktree:")

    def test_start_rejects_matrixless_ready_before_mutation(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-matrixless-ready"
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
                name="matrixless-ready",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        record["metadata"].pop("matrix")
        self._set_record(tmp_path, bead_id, record)
        before_record = self._record(tmp_path, bead_id)
        before_worktrees = tm.ok(
            FlextInfraWorktreeService(
                repository_root=repository, operation=c.Infra.WorktreeOperation.LIST
            ).execute()
        )

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="matrixless-ready",
            base="HEAD",
            apply_changes=True,
        ).execute()

        tm.fail(result, has="ready lane start requires matrix metadata")
        assert self._record(tmp_path, bead_id) == before_record
        assert (
            tm.ok(
                FlextInfraWorktreeService(
                    repository_root=repository, operation=c.Infra.WorktreeOperation.LIST
                ).execute()
            )
            == before_worktrees
        )

    def test_status_renders_matrixless_ready_without_matrix_lines(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-matrixless-status"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "feature/matrixless-status",
                "namespace": "feature",
                "worktree": str(tmp_path / "matrixless-status"),
                "kind": "feature",
                "slug": "matrixless-status",
                "integration_base": "HEAD",
                "head_oid": "abc",
                "provisioning": "ready",
                "role": "plain",
            },
        )

        status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=bead_id,
                apply_changes=False,
            ).execute()
        )

        tm.that(status, has="metadata.branch: feature/matrixless-status")
        assert "matrix:" not in status

    def test_finish_refuses_primary_checkout(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-primary"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "feature/primary-abuse",
                "namespace": "feature",
                "worktree": str(repository),
                "kind": "feature",
                "slug": "primary-abuse",
                "integration_base": "HEAD",
                "head_oid": tm.ok(
                    u.Infra.git_repository_head(
                        m.Infra.GitRepoRequest(repo_root=repository)
                    )
                ).oid,
                "provisioning": "ready",
                "role": "plain",
            },
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="refuses the primary worktree")

    def test_start_requires_bead(self, tmp_path: PathType) -> None:
        repository = self._repository(tmp_path)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            kind=c.Infra.WorkKind.FEATURE,
            name="no-bead",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="requires --bead")

    def test_beads_resolve_reads_the_governing_workspace_manifest(
        self, tmp_path: PathType
    ) -> None:
        """The governing manifest owns the ledger for the workspace and members."""
        workspace = self._repository(tmp_path)
        member = self._member(tmp_path, workspace, "member")

        resolved = tm.ok(u.Infra.beads_resolve_root(member))
        assert str(resolved) == str(workspace.resolve())
        resolved_workspace = tm.ok(u.Infra.beads_resolve_root(workspace))
        assert str(resolved_workspace) == str(workspace.resolve())

    def test_beads_resolve_ignores_a_member_local_tracker_file(
        self, tmp_path: PathType
    ) -> None:
        """A member never outranks the governing workspace it belongs to.

        mro-tvc03: resolution used to walk candidates positionally and return
        the first `.beads/config.yaml` it found, so a member carrying that file
        captured the lane and `bd` bound to the wrong ledger. Ownership is a
        typed declaration on the governing manifest, never a file on disk.
        """
        workspace = self._repository(tmp_path)
        member = self._member(tmp_path, workspace, "member")
        member_beads = member / ".beads"
        member_beads.mkdir()
        (member_beads / "config.yaml").write_text(
            'issue-prefix: "member-local"\n', encoding="utf-8"
        )

        resolved = tm.ok(u.Infra.beads_resolve_root(member))
        assert str(resolved) == str(workspace.resolve())

    def test_finish_removes_lane_and_updates_metadata(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has="BRANCH=bugfix/finish-lane")
        record = self._record(tmp_path, bead_id)
        lane = record["metadata"]["worktree"]
        head = record["metadata"]["head_oid"]
        matrix = m.Infra.WorkLaneMatrix.model_validate_json(
            record["metadata"]["matrix"]
        )
        record["metadata"]["matrix"] = matrix.model_copy(
            update={
                "entries": tuple(
                    entry.model_copy(update={"pr_number": "1"})
                    if entry.project == "."
                    else entry
                    for entry in matrix.entries
                )
            }
        ).model_dump_json()
        record["metadata"]["pr_number"] = "1"
        self._set_record(tmp_path, bead_id, record)
        finished = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.FINISH,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        tm.that(finished, has="FINISHED BRANCH=bugfix/finish-lane")
        assert not Path(lane).exists()
        updated = self._metadata(tmp_path, bead_id)
        assert updated["worktree"] == "removed"
        assert updated["head_oid"] == head

    def test_finish_cas_mismatch_fails(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-cas"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="cas-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(
            tmp_path, bead_id, head_oid="0" * 40, pr_number="1"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="CAS failed")

    def test_land_refuses_permanent_branch(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-perm"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "main",
                "worktree": str(tmp_path / "fake-lane"),
                "kind": "feature",
                "slug": "main",
                "integration_base": "HEAD",
                "head_oid": "a" * 40,
                "provisioning": "ready",
                "role": "plain",
            },
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="metadata.ready.namespace")

    def test_land_requires_head_oid(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-oid"
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
                name="land-oid",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        record["metadata"]["head_oid"] = ""
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="metadata.ready.head_oid")

    def test_land_refuses_metadata_worktree_mismatch(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-bind"
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
                name="land-bind",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        poison = tmp_path / "poison-tree"
        poison.mkdir()
        (poison / "README.md").write_text("poison\n", encoding="utf-8")
        u.Tests.initialize_git_repo(poison)
        record = self._record(tmp_path, bead_id)
        record["metadata"]["worktree"] = str(poison)
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="does not match registered lane")

    def test_finish_requires_head_oid(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-oid"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-oid",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        record["metadata"]["head_oid"] = ""
        record["metadata"]["pr_number"] = "1"
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="metadata.ready.head_oid")

    def test_finish_refuses_permanent_branch_via_config_integration(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        # Why (mro-tvc03): the manifest is the tracker SSOT the fixture already
        # wrote, so the integration branch is ADDED to it. Overwriting the file
        # with a fragment produced a manifest without version/name/repository
        # and the lane could no longer resolve its own ledger.
        manifest = repository / "config" / "workspace.yaml"
        declared = u.Cli.yaml_load_mapping(manifest)
        tm.ok(
            u.Cli.yaml_dump(
                manifest,
                {
                    **declared,
                    "integration": {"provider": "flext-sh", "branch": "0.12.0-dev"},
                },
            )
        )
        bead_id = "mro-test-finish-perm"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "0.12.0-dev",
                "worktree": str(tmp_path / "fake-lane"),
                "kind": "feature",
                "slug": "integration",
                "integration_base": "0.12.0-dev",
                "head_oid": "a" * 40,
                "provisioning": "ready",
                "role": "plain",
            },
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="metadata.ready.namespace")

    def test_finish_accepts_already_removed(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-removed"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "bugfix/gone",
                "namespace": "bugfix",
                "worktree": "removed",
                "kind": "bugfix",
                "slug": "gone",
                "integration_base": "HEAD",
                "head_oid": "a" * 40,
                "provisioning": "ready",
                "role": "plain",
            },
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.that(tm.ok(result), has="receipt.worktree=removed")

    def test_status_reports_after_start(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-status-detail"
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
                name="status-detail",
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
        tm.that(status, has="branch: feature/status-detail")
        tm.that(status, has="primary_checkout:")

    def test_finish_refuses_metadata_worktree_mismatch(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-bind"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-bind",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        poison = tmp_path / "poison-finish"
        poison.mkdir()
        (poison / "README.md").write_text("poison\n", encoding="utf-8")
        u.Tests.initialize_git_repo(poison)
        record = self._record(tmp_path, bead_id)
        record["metadata"]["worktree"] = str(poison)
        record["metadata"]["pr_number"] = "1"
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="does not match registered lane")

    def test_start_rejects_invalid_slug(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-bad-slug"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="Not_Kebab",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="kebab-case required")

    def test_start_rejects_forbidden_slug(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-forbidden-slug"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="temp",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="forbidden work slug")

    def test_start_requires_apply(self, tmp_path: PathType) -> None:
        repository = self._repository(tmp_path)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead="mro-test-start-apply",
            kind=c.Infra.WorkKind.FEATURE,
            name="needs-apply",
            base="HEAD",
            apply_changes=False,
        ).execute()
        tm.fail(result, has="requires --apply")

    def test_land_requires_apply(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-apply"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=False,
        ).execute()
        tm.fail(result, has="requires --apply")

    def test_land_cas_mismatch_fails(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-cas"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-cas",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(tmp_path, bead_id, head_oid="0" * 40)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="CAS failed")

    def test_land_refuses_dirty_lane(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-dirty"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="land-dirty",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        lane = Path(self._metadata(tmp_path, bead_id)["worktree"])
        (lane / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="clean lane worktree")

    def test_finish_refuses_missing_lane(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-missing"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-missing",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        lane = Path(record["metadata"]["worktree"])
        record["metadata"]["pr_number"] = "1"
        self._set_record(tmp_path, bead_id, record)
        for child in sorted(lane.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        lane.rmdir()
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="lane worktree missing")
        assert self._metadata(tmp_path, bead_id)["worktree"] != "removed"

    def test_finish_fails_when_pr_list_errors(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-gh-fail"
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
                name="finish-gh-fail",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        gh = shim_dir / "gh"
        gh.write_text(
            "#!/usr/bin/env python3"
            + chr(10)
            + "import sys"
            + chr(10)
            + "raise SystemExit('gh unavailable')"
            + chr(10),
            encoding="utf-8",
        )
        gh.chmod(0o755)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="gh unavailable")

    def test_finish_refuses_pr_head_mismatch(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-pr-head"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-pr-head",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(tmp_path, bead_id, pr_number="9")
        gh = shim_dir / "gh"
        gh.write_text(
            "#!/usr/bin/env python3"
            + chr(10)
            + "import json, sys"
            + chr(10)
            + "print(json.dumps({'state': 'MERGED', 'mergedAt': '2026-08-03T00:00:00Z', 'headRefName': 'feature/other'}))"
            + chr(10),
            encoding="utf-8",
        )
        gh.chmod(0o755)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="does not match lane branch")

    def test_land_refuses_integration_base_drift(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        # Why (mro-tvc03): add the integration branch to the manifest the
        # fixture already declared; replacing it with a fragment removed the
        # tracker identity the lane resolves its ledger from.
        manifest = repository / "config" / "workspace.yaml"
        declared = u.Cli.yaml_load_mapping(manifest)
        tm.ok(
            u.Cli.yaml_dump(
                manifest,
                {
                    **declared,
                    "integration": {"provider": "flext-sh", "branch": "0.12.0-dev"},
                },
            )
        )
        bead_id = "mro-test-land-base-drift"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-base-drift",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        record["metadata"]["integration_base"] = "attacker-base"
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="integration_base drift")

    def test_start_idempotent_same_lane_refreshes_head(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-running start on a bound bead refreshes CAS instead of failing."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-start-idempotent"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        first = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="idempotent-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(first, has="receipt.operation=start")
        lane = Path(self._metadata(tmp_path, bead_id)["worktree"])
        stale_head = self._metadata(tmp_path, bead_id)["head_oid"]
        self._commit_in(lane, "lane work")
        second = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="idempotent-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        refreshed = self._metadata(tmp_path, bead_id)
        assert refreshed["worktree"] == str(lane)
        assert refreshed["head_oid"] != stale_head
        tm.that(second, has=f"receipt.head_oid={refreshed['head_oid']}")
        tm.that(second, has=f"receipt.worktree={lane}")
        assert lane.is_dir()
