"""The Beads adapter is the sole untrusted JSON parsing boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from flext_infra import c, config, m, u
from flext_tests import tm

from tests import u as test_u


class TestsFlextInfraBeadsLaneTypedBoundary:
    """Exercise the public Beads lane boundary through typed lifecycle states."""

    def test_work_lane_models_keep_type_aliases_inside_nested_classes(self) -> None:
        """Reject loose declarations outside the governed model hierarchy."""
        source = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "flext_infra"
            / "_models"
            / "work_lane.py"
        ).read_text(encoding="utf-8")
        loose_aliases = [
            statement
            for statement in u.Infra.logical_statements(source)
            if statement.category == c.Infra.StatementCategory.TYPE_ALIAS
            and statement.enclosing_kind == c.Infra.RopeScopeKind.MODULE
        ]
        module_classes = [
            u.Infra.header_name(statement)
            for statement in u.Infra.logical_statements(source)
            if statement.category == c.Infra.StatementCategory.CLASS_DEF
            and statement.enclosing_kind == c.Infra.RopeScopeKind.MODULE
        ]

        tm.that(loose_aliases, eq=[])
        tm.that(module_classes, eq=["FlextInfraModelsWorkLane"])

    def test_work_lane_model_tests_keep_behavior_inside_test_class(self) -> None:
        """Reject loose helpers and tests outside the governed test class."""
        source = (
            Path(__file__).resolve().parent / "test_work_lane_models.py"
        ).read_text(encoding="utf-8")
        statements = u.Infra.logical_statements(source)
        loose_functions = [
            u.Infra.header_name(statement)
            for statement in statements
            if statement.category == c.Infra.StatementCategory.FUNC_DEF
            and statement.enclosing_kind == c.Infra.RopeScopeKind.MODULE
        ]
        module_classes = [
            u.Infra.header_name(statement)
            for statement in statements
            if statement.category == c.Infra.StatementCategory.CLASS_DEF
            and statement.enclosing_kind == c.Infra.RopeScopeKind.MODULE
        ]

        tm.that(loose_functions, eq=[])
        tm.that(module_classes, eq=["TestsFlextInfraWorkLaneModels"])

    @staticmethod
    def _repository(tmp_path: Path) -> Path:
        repository = tmp_path / "repository"
        repository.mkdir()
        test_u.Tests.declare_workspace_ledger(repository, "mro")
        test_u.Tests.initialize_git_repo(repository)
        return repository

    @staticmethod
    def _integration_branch(repository: Path) -> str:
        manifest = u.Cli.yaml_load_mapping(repository / "config" / "workspace.yaml")
        workspace = m.Infra.WorkspaceSpec.model_validate(manifest)
        provider = next(
            item
            for item in config.Infra.codegen.providers
            if item.name == workspace.repository.provider
        )
        return u.Infra.resolve_integration_branch(workspace, provider)

    @staticmethod
    def _install_bd(
        tmp_path: Path, payload: str, *, argv_log: Path | None = None
    ) -> Path:
        shim_dir = tmp_path / "bin"
        shim_dir.mkdir()
        shim = shim_dir / "bd"
        shim.write_text(
            "#!/usr/bin/env python3\n"
            "from __future__ import annotations\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"PAYLOAD = {payload!r}\n"
            f"ARGV_LOG = {str(argv_log)!r}\n"
            "args = sys.argv[1:]\n"
            "if 'show' in args or 'list' in args:\n"
            "    print(PAYLOAD)\n"
            "    raise SystemExit(0)\n"
            "if 'update' in args and ARGV_LOG:\n"
            "    Path(ARGV_LOG).write_text(json.dumps(args), encoding='utf-8')\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit('unsupported')\n",
            encoding="utf-8",
        )
        shim.chmod(0o755)
        return shim_dir

    @staticmethod
    def _activate_bd(monkeypatch: pytest.MonkeyPatch, shim_dir: Path) -> None:
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )

    def test_beads_show_rejects_malformed_payload(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        shim_dir = self._install_bd(
            tmp_path, '[{"id": "mro-test", "metadata": {"provisioning": "ready"}}]'
        )
        self._activate_bd(monkeypatch, shim_dir)

        result = u.Infra.beads_show("mro-test", root=repository)

        tm.fail(result, has="validation")

    def test_beads_list_returns_only_typed_reservations(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        integration_branch = self._integration_branch(repository)
        records = [
            {
                "id": "mro-ready",
                "status": "open",
                "issue_type": "feature",
                "parent": None,
                "metadata": {
                    "branch": "feature/ready-lane",
                    "namespace": "feature",
                    "worktree": "ready-lane",
                    "kind": "feature",
                    "slug": "ready-lane",
                    "integration_base": integration_branch,
                    "role": "plain",
                    "provisioning": "ready",
                    "head_oid": "abc",
                },
            },
            {
                "id": "mro-pending",
                "status": "open",
                "issue_type": "feature",
                "parent": None,
                "metadata": {
                    "branch": "feature/pending-lane",
                    "namespace": "feature",
                    "worktree": "pending-lane",
                    "kind": "feature",
                    "slug": "pending-lane",
                    "integration_base": integration_branch,
                    "role": "plain",
                    "provisioning": "pending",
                    "matrix": {
                        "entries": [
                            {
                                "project": ".",
                                "branch": "feature/pending-lane",
                                "head_oid": "def",
                                "state": "started",
                            }
                        ]
                    },
                },
            },
        ]
        shim_dir = self._install_bd(tmp_path, json.dumps(records))
        self._activate_bd(monkeypatch, shim_dir)

        reservations = tm.ok(u.Infra.beads_list_reservations(root=repository))

        assert len(reservations) == 2
        ready_metadata = reservations[0].metadata
        assert isinstance(ready_metadata, m.Infra.ReadyLaneMetadata)
        assert ready_metadata.matrix is None
        assert reservations[1].metadata is not None
        assert (
            reservations[1].metadata.provisioning
            == c.Infra.WorkProvisioningState.PENDING
        )

    def test_pending_retry_ignores_stale_failed_state_fields(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        integration_branch = self._integration_branch(repository)
        record = {
            "id": "mro-retry",
            "status": "in_progress",
            "issue_type": "epic",
            "metadata": {
                "branch": "epic/tracker-governance",
                "namespace": "epic",
                "worktree": str(repository),
                "slug": "tracker-governance",
                "integration_base": integration_branch,
                "role": "epic",
                "epic_bead": "mro-retry",
                "provisioning": "pending",
                "recovery": "retry-setup",
                "error_category": "setup",
            },
        }
        shim_dir = self._install_bd(tmp_path, json.dumps([record]))
        self._activate_bd(monkeypatch, shim_dir)

        issue = tm.ok(u.Infra.beads_show("mro-retry", root=repository))

        assert isinstance(issue.metadata, m.Infra.PendingLaneReservation)

    def test_pending_update_removes_stale_failed_state_fields(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        integration_branch = self._integration_branch(repository)
        argv_log = tmp_path / "argv.json"
        shim_dir = self._install_bd(tmp_path, "[]", argv_log=argv_log)
        self._activate_bd(monkeypatch, shim_dir)
        metadata = m.Infra.PendingLaneReservation(
            branch="feature/retry",
            namespace=c.Infra.WorkBranchNamespace.FEATURE,
            worktree=repository,
            kind=c.Infra.WorkKind.FEATURE,
            slug="retry",
            integration_base=integration_branch,
            topology=m.Infra.PlainLaneTopology(role=c.Infra.WorkLaneRole.PLAIN),
            provisioning=c.Infra.WorkProvisioningState.PENDING,
        )

        tm.ok(
            u.Infra.beads_update_lane("mro-retry", metadata=metadata, root=repository)
        )

        argv = json.loads(argv_log.read_text(encoding="utf-8"))
        unset_fields = {
            argv[index + 1]
            for index, argument in enumerate(argv[:-1])
            if argument == "--unset-metadata"
        }
        assert unset_fields == {
            "recovery",
            "error_category",
            "pr_number",
            "pr_url",
            "matrix",
        }

    def test_legacy_ready_without_matrix_fails_closed_when_start_requests_adoption(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        integration_branch = self._integration_branch(repository)
        bead_id = "mro-test"
        record = {
            "id": bead_id,
            "status": "open",
            "issue_type": "epic",
            "metadata": {
                "worktree": "typed-lane",
                "kind": "epic",
                "slug": "typed-lane",
                "integration_base": integration_branch,
            },
        }
        shim_dir = self._install_bd(tmp_path, json.dumps([record]))
        self._activate_bd(monkeypatch, shim_dir)

        tm.fail(
            u.Infra.beads_show(bead_id, root=repository, adopt_legacy_ready=True),
            has="matrix",
        )

    @pytest.mark.parametrize("decoded", [False, True])
    def test_start_adopts_live_legacy_epic_matrix_payload(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, decoded: bool
    ) -> None:
        repository = self._repository(tmp_path)
        integration_branch = self._integration_branch(repository)
        epic_bead_id = "mro-fixture-epic"
        entries = [
            {
                "project": "." if index == 0 else f"flext-member-{index}",
                "branch": "epic/tracker-governance",
                "head_oid": f"{index + 1:040x}",
                "pr_number": "",
                "pr_url": "",
                "state": "started",
            }
            for index in range(32)
        ]
        matrix = {"entries": entries}
        record = {
            "id": epic_bead_id,
            "status": "in_progress",
            "issue_type": "epic",
            "metadata": {
                "integration_base": integration_branch,
                "kind": "epic",
                "matrix": matrix if decoded else json.dumps(matrix),
                "slug": "tracker-governance",
                "worktree": str(repository),
            },
        }
        shim_dir = self._install_bd(tmp_path, json.dumps([record]))
        self._activate_bd(monkeypatch, shim_dir)

        adopted = tm.ok(
            u.Infra.beads_show(epic_bead_id, root=repository, adopt_legacy_ready=True)
        )

        assert isinstance(adopted.metadata, m.Infra.ReadyLaneMetadata)
        assert adopted.metadata.matrix is not None
        assert adopted.metadata.branch == "epic/tracker-governance"
        assert adopted.metadata.namespace == c.Infra.WorkBranchNamespace.EPIC
        assert adopted.metadata.kind is None
        assert len(adopted.metadata.matrix.entries) == 32
        assert adopted.metadata.matrix.entries == tuple(
            m.Infra.WorkLaneEntry.model_validate(entry) for entry in entries
        )

    def test_start_ignores_unrelated_metadata_that_only_contains_matrix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        record = {
            "id": "mro-test",
            "status": "open",
            "issue_type": "feature",
            "metadata": {
                "matrix": {
                    "entries": [
                        {
                            "project": ".",
                            "branch": "feature/unrelated",
                            "head_oid": "abc",
                            "state": "started",
                        }
                    ]
                }
            },
        }
        shim_dir = self._install_bd(tmp_path, json.dumps([record]))
        self._activate_bd(monkeypatch, shim_dir)

        issue = tm.ok(
            u.Infra.beads_show("mro-test", root=repository, adopt_legacy_ready=True)
        )

        assert issue.metadata is None


__all__: tuple[str, ...] = ()
"""The Beads adapter is the sole untrusted JSON parsing boundary."""
