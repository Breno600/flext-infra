"""Unit tests for FlextInfraRefactorSafetyManager integration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, overload, override

from flext_infra import r
from flext_infra.refactor.safety import FlextInfraRefactorSafetyManager
from flext_infra.refactor.service import FlextInfraRefactorService
from flext_tests import tm
from tests import u

if TYPE_CHECKING:
    from collections.abc import MutableSequence

    from flext_infra import t
    from tests import p


class RefactorSafetyStub(FlextInfraRefactorSafetyManager):
    """Test double for safety manager lifecycle operations."""

    def __init__(self) -> None:
        """Initialize call capture state for assertions."""
        super().__init__()
        self.calls: MutableSequence[str] = []
        self.kept_paths: t.SequenceOf[Path] = []

    @override
    def create_pre_transformation_checkpoint(
        self, workspace_root: Path, *, label: str = "flext-refactor-pre-transform"
    ) -> p.Result[str]:
        _ = workspace_root
        _ = label
        self.calls.append("checkpoint")
        return r[str].ok("checkpoint-ref")

    @override
    def save_checkpoint_state(
        self,
        workspace_root: Path,
        *,
        status: str,
        checkpoint_ref: str,
        processed_targets: t.StrSequence,
    ) -> p.Result[bool]:
        _ = workspace_root
        _ = status
        _ = checkpoint_ref
        _ = processed_targets
        self.calls.append("checkpoint-state")
        return r[bool].ok(True)

    @override
    def run_semantic_validation(self, workspace_root: Path) -> p.Result[bool]:
        _ = workspace_root
        self.calls.append("validate")
        return r[bool].ok(True)

    @override
    def clear_checkpoint(self, *, keep: t.SequenceOf[Path] = ()) -> p.Result[bool]:
        self.kept_paths = list(keep)
        self.calls.append("clear")
        return r[bool].ok(True)

    @override
    def request_emergency_stop(self, reason: str) -> None:
        _ = reason
        self.calls.append("stop")

    @overload
    def rollback(
        self, workspace_root: Path, checkpoint_ref: str = ""
    ) -> p.Result[bool]: ...

    @overload
    def rollback(self, workspace_root: str, /) -> None: ...

    @override
    def rollback(
        self, workspace_root: Path | str, checkpoint_ref: str = ""
    ) -> p.Result[bool] | None:
        _ = checkpoint_ref
        self.calls.append("rollback")
        if isinstance(workspace_root, Path):
            return r[bool].ok(True)
        return None

    @property
    @override
    def emergency_stop_requested(self) -> bool:
        self.calls.append("is_stop")
        return False


class TestsFlextInfraRefactorInfraRefactorSafety:
    """Behavior contract for test_infra_refactor_safety."""

    def test_refactor_project_integrates_safety_manager(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "rules.yml").write_text(
            "\nrules:\n  - id: ensure-future-annotations\n    enabled: true\n    fix_action: ensure_future_annotations\n".strip()
            + "\n",
            encoding="utf-8",
        )
        config_path = tmp_path / "settings.yml"
        config_path.write_text('refactor:\n  project_scan_dirs: ["src"]\n')
        src_dir = tmp_path / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "sample.py").write_text("import os\n", encoding="utf-8")
        service = FlextInfraRefactorService(config_path=config_path)
        stub = RefactorSafetyStub()
        service.orchestrator.safety_manager = stub
        loaded = service.load_rules()
        tm.ok(loaded)
        results = service.refactor_project(tmp_path, dry_run=False, apply_safety=True)
        tm.that(results, empty=False)
        tm.that(all(item.success for item in results), eq=True)
        tm.that(stub.calls, eq=["checkpoint", "checkpoint-state", "validate", "clear"])
        tm.that(stub.kept_paths, eq=[src_dir / "sample.py"])

    def test_clear_checkpoint_preserves_requested_backups(self, tmp_path: Path) -> None:
        keep_file = tmp_path / "keep.py"
        drop_file = tmp_path / "drop.py"
        keep_file.write_text("value = 1\n", encoding="utf-8")
        drop_file.write_text("value = 2\n", encoding="utf-8")
        manager = FlextInfraRefactorSafetyManager()
        created = manager.create_pre_transformation_checkpoint(tmp_path)
        tm.ok(created)

        cleared = manager.clear_checkpoint(keep=[keep_file])

        tm.ok(cleared)
        tm.that(keep_file.with_suffix(".py.bak").exists(), eq=True)
        tm.that(drop_file.with_suffix(".py.bak").exists(), eq=False)

    def test_create_pre_transformation_checkpoint_tracks_python_files(
        self, tmp_path: Path
    ) -> None:
        init_result = u.Cli.run_raw(["git", "init"], cwd=tmp_path)
        tm.ok(init_result)
        tm.that(init_result.value.exit_code, eq=0)
        email_result = u.Cli.run_raw(
            ["git", "config", "user.email", "test@example.com"], cwd=tmp_path
        )
        tm.ok(email_result)
        tm.that(email_result.value.exit_code, eq=0)
        name_result = u.Cli.run_raw(
            ["git", "config", "user.name", "Test User"], cwd=tmp_path
        )
        tm.ok(name_result)
        tm.that(name_result.value.exit_code, eq=0)
        tracked_file = tmp_path / "tracked.py"
        tracked_file.write_text("value = 1\n", encoding="utf-8")
        second_file = tmp_path / "second.py"
        second_file.write_text("value = 2\n", encoding="utf-8")
        add_result = u.Cli.run_raw(["git", "add", "tracked.py"], cwd=tmp_path)
        tm.ok(add_result)
        tm.that(add_result.value.exit_code, eq=0)
        manager = FlextInfraRefactorSafetyManager()

        created = manager.create_pre_transformation_checkpoint(tmp_path)

        tm.ok(created)
        tm.that(tracked_file.with_suffix(".py.bak").exists(), eq=True)
        tm.that(second_file.with_suffix(".py.bak").exists(), eq=True)
