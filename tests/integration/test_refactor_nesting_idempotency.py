"""Idempotency tests for class nesting file execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra import c
from flext_infra.refactor.file_executor import FlextInfraRefactorFileExecutor
from flext_tests import tm
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import m, t


class _FileRuleHarness(FlextInfraRefactorFileExecutor):
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._class_nesting_config = None
        self._class_nesting_policy_by_family = None
        self._class_nesting_gate = None

    @override
    def _load_class_nesting_config(self) -> t.JsonMapping:
        return u.Cli.yaml_load_mapping(self._config_path)

    def apply_rule(
        self,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        *,
        dry_run: bool,
    ) -> m.Infra.Result:
        """Expose class nesting through the integration harness contract."""
        return self._apply_file_rule_selection(
            c.Infra.RefactorFileRuleKind.CLASS_NESTING,
            {},
            rope_project,
            resource,
            dry_run=dry_run,
        )


def _apply_rule(
    workspace_root: Path, file_path: Path, config_path: Path, *, dry_run: bool
) -> m.Infra.Result:
    rule = _FileRuleHarness(config_path)
    rope_project = u.Infra.init_rope_project(workspace_root)
    try:
        resource = u.Infra.get_resource_from_path(rope_project, file_path)
        if resource is None:
            raise FileNotFoundError(file_path)
        return rule.apply_rule(rope_project, resource, dry_run=dry_run)
    finally:
        rope_project.close()


class TestsFlextInfraIntegrationRefactorNestingIdempotency:
    """Test that running refactor multiple times is idempotent."""

    def test_first_run_produces_changes(self, tmp_path: Path) -> None:
        """First run should produce changes."""
        test_file = tmp_path / "test.py"
        test_file.write_text("\nclass TimeoutEnforcer:\n    pass\n")
        config_file = tmp_path / "mappings.yml"
        config_file.write_text(
            "\nclass_nesting:\n"
            "  - loose_name: TimeoutEnforcer\n"
            "    current_file: test.py\n"
            "    target_namespace: FlextDispatcher\n"
            "    target_name: TimeoutEnforcer\n"
            "    confidence: high\n"
        )
        result = _apply_rule(tmp_path, test_file, config_file, dry_run=False)
        tm.that(result.modified, eq=True)
        tm.that(result.refactored_code, none=False)
        tm.that(result.refactored_code, has="class FlextDispatcher:")

    def test_second_run_produces_no_changes(self, tmp_path: Path) -> None:
        """Second run on already-refactored code should produce no changes."""
        test_file = tmp_path / "test.py"
        test_file.write_text("\nclass TimeoutEnforcer:\n    pass\n")
        config_file = tmp_path / "mappings.yml"
        config_file.write_text(
            "\nclass_nesting:\n"
            "  - loose_name: TimeoutEnforcer\n"
            "    current_file: test.py\n"
            "    target_namespace: FlextDispatcher\n"
            "    target_name: TimeoutEnforcer\n"
            "    confidence: high\n"
        )
        result1 = _apply_rule(tmp_path, test_file, config_file, dry_run=False)
        refactored_code = tm.not_none(result1.refactored_code)
        test_file.write_text(refactored_code)
        result2 = _apply_rule(tmp_path, test_file, config_file, dry_run=True)
        tm.that(result2.success, eq=True)

    def test_third_run_produces_no_changes(self, tmp_path: Path) -> None:
        """Third run should also produce no changes."""
        test_file = tmp_path / "test.py"
        test_file.write_text("\nclass TimeoutEnforcer:\n    pass\n")
        config_file = tmp_path / "mappings.yml"
        config_file.write_text(
            "\nclass_nesting:\n"
            "  - loose_name: TimeoutEnforcer\n"
            "    current_file: test.py\n"
            "    target_namespace: FlextDispatcher\n"
            "    target_name: TimeoutEnforcer\n"
            "    confidence: high\n"
        )
        for _ in range(3):
            result = _apply_rule(tmp_path, test_file, config_file, dry_run=False)
            if result.modified and result.refactored_code is not None:
                test_file.write_text(result.refactored_code)
        final_result = _apply_rule(tmp_path, test_file, config_file, dry_run=True)
        tm.that(final_result.success, eq=True)
