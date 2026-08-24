"""Tests for FlextInfraSkillValidator — core validation and helpers.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from flext_infra.validate.skill_validator import FlextInfraSkillValidator
from flext_tests import tm
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import m, t


class TestSafeLoadYaml:
    """Test u.Infra.yaml_load_infra_mapping helper function."""

    def test_valid_yaml(self, tmp_path: Path) -> None:
        """Valid YAML file loads correctly."""
        f = tmp_path / "test.yml"
        f.write_text("key: value\nlist:\n  - item1\n  - item2")
        result = u.Cli.yaml_load_mapping(f)
        tm.that(result.get("key"), eq="value")
        list_value = result.get("list")
        tm.that(list_value, is_=list)
        tm.that(list_value, eq=["item1", "item2"])

    def test_empty_and_null(self, tmp_path: Path) -> None:
        """Empty/null YAML returns empty dict."""
        (tmp_path / "empty.yml").write_text("")
        tm.that(dict(u.Cli.yaml_load_mapping(tmp_path / "empty.yml")), eq={})
        (tmp_path / "null.yml").write_text("null")
        tm.that(dict(u.Cli.yaml_load_mapping(tmp_path / "null.yml")), eq={})

    def test_non_dict_returns_empty_mapping(self, tmp_path: Path) -> None:
        """Non-mapping YAML normalizes to an empty mapping."""
        (tmp_path / "list.yml").write_text("- item1\n- item2")
        tm.that(dict(u.Cli.yaml_load_mapping(tmp_path / "list.yml")), eq={})
        (tmp_path / "str.yml").write_text("just a string")
        tm.that(dict(u.Cli.yaml_load_mapping(tmp_path / "str.yml")), eq={})


class TestStringList:
    """Test u.Infra.string_list helper function."""

    def test_none_returns_empty(self) -> None:
        """None returns empty list."""
        tm.that(u.Infra.string_list(None), empty=True)

    def test_valid_list(self) -> None:
        """Valid string list passes through."""
        tm.that(u.Infra.string_list(["a", "b", "c"]), eq=["a", "b", "c"])

    def test_string_wraps_to_list(self) -> None:
        """Bare string is wrapped into a single-element list."""
        tm.that(u.Infra.string_list("not a list"), eq=["not a list"])

    def test_invalid_input_raises(self) -> None:
        """Non-string items and non-list values raise."""
        with pytest.raises(TypeError):
            u.Infra.string_list(["a", 123, "c"])
        with pytest.raises(TypeError, match="expected list"):
            u.Infra.string_list({"key": "value"})


class TestSkillValidatorCore:
    """Core validation tests for FlextInfraSkillValidator."""

    def test_validate_missing_rules_yml(self, tmp_path: Path) -> None:
        """Missing rules.yml returns not-passed report."""
        validator = FlextInfraSkillValidator(skill="test-skill")
        skills = tmp_path / c.Infra.SKILLS_DIR / "test-skill"
        skills.mkdir(parents=True)
        report: m.Infra.ValidationReport = tm.ok(
            validator.build_report(tmp_path, "test-skill")
        )
        tm.that(not report.passed, eq=True)
        tm.that(report.summary, contains="no rules.yml")

    def test_validate_invalid_scan_targets(self, tmp_path: Path) -> None:
        """Non-dict scan_targets returns failure."""
        validator = FlextInfraSkillValidator(skill="test-skill")
        skill = tmp_path / c.Infra.SKILLS_DIR / "test-skill"
        skill.mkdir(parents=True)
        (skill / "rules.yml").write_text("scan_targets: [item1, item2]")
        tm.fail(validator.build_report(tmp_path, "test-skill"), has="scan_targets")

    def test_validate_invalid_rules_not_list(self, tmp_path: Path) -> None:
        """Non-list rules returns failure."""
        validator = FlextInfraSkillValidator(skill="test-skill")
        skill = tmp_path / c.Infra.SKILLS_DIR / "test-skill"
        skill.mkdir(parents=True)
        (skill / "rules.yml").write_text("rules: {not: a_list}")
        tm.fail(
            validator.build_report(tmp_path, "test-skill"), has="rules must be a list"
        )

    def test_validate_non_dict_rule_skipped(self, tmp_path: Path) -> None:
        """Non-dict rule objects are skipped."""
        validator = FlextInfraSkillValidator(skill="test-skill")
        skill = tmp_path / c.Infra.SKILLS_DIR / "test-skill"
        skill.mkdir(parents=True)
        (skill / "rules.yml").write_text("rules:\n  - not_a_dict\n  - another_string")
        report: m.Infra.ValidationReport = tm.ok(
            validator.build_report(tmp_path, "test-skill")
        )
        tm.that(report.passed, eq=True)

    def test_validate_scalar_rules_yml_yields_empty_success(
        self, tmp_path: Path
    ) -> None:
        """Scalar rules.yml content yields an empty successful report."""
        validator = FlextInfraSkillValidator(skill="test-skill")
        skill = tmp_path / c.Infra.SKILLS_DIR / "test-skill"
        skill.mkdir(parents=True)
        (skill / "rules.yml").write_text("just a plain string")
        report: m.Infra.ValidationReport = tm.ok(
            validator.build_report(tmp_path, "test-skill")
        )
        tm.that(report.passed, eq=True)
        tm.that(report.violations, empty=True)


class TestSkillValidatorAstGrepRules:
    """Public build_report coverage for ast-grep rule counting."""

    @staticmethod
    def _write_skill(root: Path, rules_yml: str) -> None:
        skill = root / c.Infra.SKILLS_DIR / "test-skill"
        skill.mkdir(parents=True)
        (skill / "rule.yaml").write_text(
            "id: t\nlanguage: python\nrule: {pattern: 'forbidden_token'}\n",
            encoding="utf-8",
        )
        (skill / "rules.yml").write_text(rules_yml, encoding="utf-8")

    @staticmethod
    def _write_target(root: Path, source: str) -> None:
        package_root = root / "demo" / "src" / "demo"
        package_root.mkdir(parents=True)
        (package_root / "m.py").write_text(source, encoding="utf-8")

    def test_empty_ast_grep_rule_file_fails_closed(self, tmp_path: Path) -> None:
        """An ast-grep rule with an empty file is invalid configuration."""
        self._write_skill(
            tmp_path, 'rules:\n  - id: t\n    type: ast-grep\n    file: ""\n'
        )
        tm.fail(
            FlextInfraSkillValidator(skill="test-skill").build_report(
                tmp_path, "test-skill", mode=c.Infra.OperationMode.STRICT
            ),
            has="non-empty file",
        )

    def test_missing_ast_grep_rule_file_fails_closed(self, tmp_path: Path) -> None:
        """An ast-grep rule pointing at a missing file is invalid configuration."""
        self._write_skill(
            tmp_path,
            'rules:\n  - id: t\n    type: ast-grep\n    file: "nonexistent.yml"\n',
        )
        tm.fail(
            FlextInfraSkillValidator(skill="test-skill").build_report(
                tmp_path, "test-skill", mode=c.Infra.OperationMode.STRICT
            ),
            has="does not exist",
        )

    def test_matching_ast_grep_rule_reports_violation(self, tmp_path: Path) -> None:
        """A matching ast-grep rule over include globs surfaces a violation."""
        self._write_skill(
            tmp_path,
            'scan_targets:\n  include: ["**/*.py"]\n'
            'rules:\n  - id: t\n    type: ast-grep\n    file: "rule.yaml"\n',
        )
        self._write_target(tmp_path, "forbidden_token = 1\n")
        report = tm.ok(
            FlextInfraSkillValidator(skill="test-skill").build_report(
                tmp_path, "test-skill", mode=c.Infra.OperationMode.STRICT
            )
        )
        tm.that(report.passed, eq=False)
        tm.that(report.summary, has="1 violations")

    def test_missing_custom_script_fails_closed(self, tmp_path: Path) -> None:
        """A custom rule pointing at a missing script is invalid configuration."""
        self._write_skill(
            tmp_path,
            'rules:\n  - id: t\n    type: custom\n    script: "nonexistent.py"\n',
        )
        tm.fail(
            FlextInfraSkillValidator(skill="test-skill").build_report(
                tmp_path, "test-skill", mode=c.Infra.OperationMode.STRICT
            ),
            has="does not exist",
        )


class TestSkillValidatorBaselineTemplate:
    """Public build_report coverage for {skill} baseline path templating."""

    def test_relative_baseline_path_resolves_with_skill_name(
        self, tmp_path: Path
    ) -> None:
        """A relative baseline file template is resolved under the workspace."""
        skill_dir = tmp_path / c.Infra.SKILLS_DIR / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "rule.yaml").write_text(
            "id: t\nlanguage: python\nrule: {pattern: 'forbidden_token'}\n",
            encoding="utf-8",
        )
        (skill_dir / "rules.yml").write_text(
            'scan_targets:\n  include: ["**/*.py"]\n'
            'baseline:\n  strategy: total\n  file: ".reports/{skill}/baseline.json"\n'
            'rules:\n  - id: t\n    type: ast-grep\n    file: "rule.yaml"\n',
            encoding="utf-8",
        )
        package_root = tmp_path / "demo" / "src" / "demo"
        package_root.mkdir(parents=True)
        (package_root / "m.py").write_text("forbidden_token = 1\n", encoding="utf-8")
        baseline_path = tmp_path / ".reports" / "test-skill" / "baseline.json"
        baseline_path.parent.mkdir(parents=True)
        baseline_path.write_text(json.dumps({"counts": {"t": 0}}), encoding="utf-8")

        report = tm.ok(
            FlextInfraSkillValidator(skill="test-skill").build_report(
                tmp_path, "test-skill", mode=c.Infra.OperationMode.BASELINE
            )
        )

        # Resolved templated baseline (counts.t=0) disallows the 1 real match.
        tm.that(report.passed, eq=False)


__all__: t.StrSequence = []
