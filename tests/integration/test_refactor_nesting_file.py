"""Integration test for single-file class-nesting execution flow."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

import pytest

from flext_infra import c
from flext_infra.refactor.file_executor import FlextInfraRefactorFileExecutor
from flext_tests import tm
from tests import u

if TYPE_CHECKING:
    from tests import m, t

pytestmark = [pytest.mark.integration]


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


class TestsFlextInfraIntegrationRefactorNestingFile:
    """Behavior contract for test_refactor_nesting_file."""

    def test_class_nesting_refactor_single_file_end_to_end(
        self, tmp_path: Path
    ) -> None:
        """Verify class nesting refactor handles unknown module families gracefully."""
        fixture_file = (
            Path(__file__).parent.parent
            / "fixtures/namespace_validator/rule0_valid.pysrc"
        )
        source = fixture_file.read_text(encoding="utf-8")
        target_dir = tmp_path / "nonstandard_dir"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / "single_file_refactor_target.py"
        target_file.write_text(
            source
            + "\n\n"
            + "from pkg import ResultHelpers\n\n"
            + "class ResultHelpers:\n"
            + "    pass\n\n"
            + "def build(value: ResultHelpers) -> ResultHelpers:\n"
            + "    if isinstance(value, ResultHelpers):\n"
            + "        return ResultHelpers()\n"
            + "    return value\n",
            encoding="utf-8",
        )
        config_path = tmp_path / "class-nesting-mappings.yml"
        config_path.write_text(
            "confidence_threshold: low\n"
            "class_nesting:\n"
            "  - loose_name: ResultHelpers\n"
            f"    current_file: {target_file.as_posix()}\n"
            "    target_namespace: FlextUtilities\n"
            "    target_name: ResultHelpers\n"
            "    confidence: high\n"
            "helper_consolidation: []\n",
            encoding="utf-8",
        )
        result = _apply_rule(tmp_path, target_file, config_path, dry_run=False)
        # Module family policy treats unknown families as out-of-scope (no policy
        # to enforce against), so the refactor proceeds gracefully and the loose
        # ``ResultHelpers`` class is nested under ``FlextUtilities`` per the
        # mapping config.
        tm.that(result.success, eq=True)
        tm.that(result.modified, eq=True)
        tm.that(result.refactored_code, none=False)
        tm.that(result.refactored_code, has="class FlextUtilities:")
        tm.that(result.refactored_code, has="class ResultHelpers:")
