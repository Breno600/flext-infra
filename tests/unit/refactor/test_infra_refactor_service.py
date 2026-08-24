"""Unit tests for FlextInfraRefactorService rule dispatch and project scanning."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c
from flext_infra.refactor.service import FlextInfraRefactorService
from flext_tests import tm

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRefactorInfraRefactorService:
    """Behavior contract for test_infra_refactor_service."""

    def test_rule_dispatch_prefers_fix_action_metadata(self, tmp_path: Path) -> None:
        """Resolve enabled rules from their explicit fix-action metadata."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir(parents=True)
        config_path = tmp_path / "settings.yml"
        config_path.write_text("session: test\n", encoding="utf-8")
        (rules_dir / "rules.yml").write_text(
            (
                "\nrules:\n"
                "  - id: custom-rule-a\n"
                "    enabled: true\n"
                "    fix_action: remove\n"
                "  - id: custom-rule-b\n"
                "    enabled: true\n"
                "    fix_action: replace_with_alias\n"
                "  - id: custom-rule-c\n"
                "    enabled: true\n"
                "    fix_action: reorder_methods\n"
                "  - id: custom-rule-d2\n"
                "    enabled: true\n"
                "    fix_action: migrate_to_class_mro\n"
                "  - id: custom-rule-e\n"
                "    enabled: true\n"
                "    fix_action: ensure_future_annotations\n"
                "  - id: custom-rule-f\n"
                "    enabled: true\n"
                "    fix_action: propagate_symbol_renames\n"
                "    import_symbol_renames:\n"
                "      Old: New\n"
                "  - id: custom-rule-g\n"
                "    enabled: true\n"
                "    fix_action: propagate_signature_migrations\n"
                "    signature_migrations:\n"
                "      - id: migrate-keyword\n"
                "        enabled: true\n"
                "        target_simple_names:\n"
                "          - run\n"
                "        keyword_renames:\n"
                "          old: new\n"
                "  - id: custom-rule-h\n"
                "    enabled: true\n"
                "    fix_action: convert_dict_to_mapping_annotations\n"
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        service = FlextInfraRefactorService(config_path=config_path)
        result = service.load_rules()
        tm.ok(result)
        tm.that(len(service.rule_loader.rules), eq=8)
        tm.that(
            [rule_kind for rule_kind, _settings in service.rule_loader.rules],
            eq=[
                c.Infra.RefactorRuleKind.LEGACY_REMOVAL,
                c.Infra.RefactorRuleKind.IMPORT_MODERNIZER,
                c.Infra.RefactorRuleKind.CLASS_RECONSTRUCTOR,
                c.Infra.RefactorRuleKind.MRO_CLASS_MIGRATION,
                c.Infra.RefactorRuleKind.FUTURE_ANNOTATIONS,
                c.Infra.RefactorRuleKind.SYMBOL_PROPAGATION,
                c.Infra.RefactorRuleKind.SIGNATURE_PROPAGATION,
                c.Infra.RefactorRuleKind.PATTERN_CORRECTIONS,
            ],
        )

    def test_rule_dispatch_fails_on_invalid_pattern_rule_config(
        self, tmp_path: Path
    ) -> None:
        """Reject incomplete pattern-rule configuration at load time."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir(parents=True)
        config_path = tmp_path / "settings.yml"
        config_path.write_text("session: test\n", encoding="utf-8")
        (rules_dir / "rules.yml").write_text(
            (
                "\nrules:\n"
                "  - id: custom-pattern-rule\n"
                "    enabled: true\n"
                "    fix_action: remove_redundant_casts\n"
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        service = FlextInfraRefactorService(config_path=config_path)
        result = service.load_rules()
        tm.fail(result)
        tm.that(result.error, none=False)
        tm.that(result.error, has="redundant_type_targets")

    def test_rule_dispatch_ignores_unknown_rule_mapping(self, tmp_path: Path) -> None:
        """Ignore unknown declarative rule identifiers without dispatching them."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir(parents=True)
        config_path = tmp_path / "settings.yml"
        config_path.write_text("session: test\n", encoding="utf-8")
        (rules_dir / "rules.yml").write_text(
            "\nrules:\n  - id: custom-unknown-rule\n    enabled: true\n".strip() + "\n",
            encoding="utf-8",
        )
        service = FlextInfraRefactorService(config_path=config_path)
        result = service.load_rules()
        tm.ok(result)
        tm.that(service.rule_loader.rules, eq=[])

    def test_service_keeps_file_rules_declarative(self, tmp_path: Path) -> None:
        """Keep file-rule selection in the declarative loader contract."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir(parents=True)
        config_path = tmp_path / "settings.yml"
        config_path.write_text("session: test\n", encoding="utf-8")
        (rules_dir / "rules.yml").write_text(
            (
                "\nrules:\n"
                "  - id: custom-import-rule\n"
                "    enabled: true\n"
                "    fix_action: replace_with_alias\n"
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        service = FlextInfraRefactorService(config_path=config_path)
        service.set_rule_filters(["custom-import-rule"])
        result = service.load_rules()
        tm.ok(result)
        tm.that(service.rule_loader.file_rules, eq=[])

    def test_rule_dispatch_drops_legacy_id_fallback_mapping(
        self, tmp_path: Path
    ) -> None:
        """Do not infer a rule action from a legacy identifier."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir(parents=True)
        config_path = tmp_path / "settings.yml"
        config_path.write_text("session: test\n", encoding="utf-8")
        (rules_dir / "rules.yml").write_text(
            "\nrules:\n  - id: modernize-import-fallback\n    enabled: true\n".strip()
            + "\n",
            encoding="utf-8",
        )
        service = FlextInfraRefactorService(config_path=config_path)
        result = service.load_rules()
        tm.ok(result)
        tm.that(service.rule_loader.rules, eq=[])

    def test_refactor_project_scans_tests_and_scripts_dirs(
        self, tmp_path: Path
    ) -> None:
        """Scan every directory explicitly owned by refactor configuration."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "rules.yml").write_text(
            (
                "\nrules:\n"
                "  - id: ensure-future-annotations\n"
                "    enabled: true\n"
                "    fix_action: ensure_future_annotations\n"
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        config_path = tmp_path / "settings.yml"
        config_path.write_text(
            "\nrefactor:\n  project_scan_dirs:\n    - tests\n    - scripts\n".strip()
            + "\n",
            encoding="utf-8",
        )
        project_root = tmp_path / "sample"
        tests_dir = project_root / "tests"
        scripts_dir = project_root / "scripts"
        tests_dir.mkdir(parents=True)
        scripts_dir.mkdir(parents=True)
        (tests_dir / "test_sample.py").write_text("import os\n", encoding="utf-8")
        (scripts_dir / "task.py").write_text("import sys\n", encoding="utf-8")
        service = FlextInfraRefactorService(config_path=config_path)
        loaded = service.load_rules()
        tm.ok(loaded)
        results = service.refactor_project(project_root, apply_safety=False)
        file_results = [
            result for result in results if result.file_path != project_root
        ]
        tm.that(len(file_results), eq=2)
        tm.that(
            {result.file_path.name for result in file_results},
            eq={"task.py", "test_sample.py"},
        )
        tm.that(all(result.success for result in file_results), eq=True)
        tm.that(all(result.modified for result in file_results), eq=True)

    def test_refactor_files_skips_non_python_inputs(self, tmp_path: Path) -> None:
        """Return an explicit successful skip result for non-Python inputs."""
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "rules.yml").write_text(
            (
                "\nrules:\n"
                "  - id: ensure-future-annotations\n"
                "    enabled: true\n"
                "    fix_action: ensure_future_annotations\n"
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        config_path = tmp_path / "settings.yml"
        config_path.write_text('refactor:\n  project_scan_dirs: ["src"]\n')
        py_file = tmp_path / "sample.py"
        py_file.write_text("import os\n", encoding="utf-8")
        md_file = tmp_path / "README.md"
        md_file.write_text("# doc\n", encoding="utf-8")
        service = FlextInfraRefactorService(config_path=config_path)
        loaded = service.load_rules()
        tm.ok(loaded)
        results = service.refactor_files([py_file, md_file], dry_run=True)
        tm.that(len(results), eq=2)
        md_result = next(item for item in results if item.file_path == md_file)
        tm.that(md_result.success, eq=True)
        tm.that(md_result.modified, eq=False)
        tm.that(md_result.changes, has="Skipped non-Python file")
