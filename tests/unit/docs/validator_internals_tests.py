"""Public utility tests used by docs validation flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsValidatorInternals:
    """Public utility tests used by docs validation flows."""

    def test_docs_has_adr_reference_detects_marker(self, tmp_path: Path) -> None:
        skill = tmp_path / "SKILL.md"
        skill.write_text("# Skill\n\nADR: documented.\n", encoding="utf-8")

        tm.that(u.Infra.docs_has_adr_reference(skill), eq=True)

    def test_docs_load_required_skills_reads_architecture_config(
        self, tmp_path: Path
    ) -> None:
        settings = tmp_path / "docs/architecture/architecture_config.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(
            '{"docs_validation": {"required_skills": ["rules-docs", "readme-standardization"]}}',
            encoding="utf-8",
        )

        result = u.Infra.docs_load_required_skills(tmp_path)

        tm.ok(result)
        tm.that(result.value, eq=["rules-docs", "readme-standardization"])

    def test_docs_write_todo_writes_only_for_project_scopes(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        scopes = u.Infra.build_scopes(
            workspace, projects=["flext-a"], output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR
        )

        tm.ok(scopes)
        root_scope, project_scope = scopes.value
        root_result = u.Infra.docs_write_todo(root_scope, apply_mode=True)
        project_result = u.Infra.docs_write_todo(project_scope, apply_mode=True)
        tm.that(root_result.success, eq=True)
        tm.that(root_result.value is False, eq=True)
        tm.that(project_result.success, eq=True)
        tm.that(project_result.value is True, eq=True)
        tm.that((workspace / "flext-a/TODOS.md").exists(), eq=True)
