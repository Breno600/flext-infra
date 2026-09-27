"""Public service execution tests for docs commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import config
from flext_infra.docs.auditor import FlextInfraDocAuditor
from flext_infra.docs.builder import FlextInfraDocBuilder
from flext_infra.docs.fixer import FlextInfraDocFixer
from flext_infra.docs.generator import FlextInfraDocGenerator
from flext_infra.docs.validator import FlextInfraDocValidator
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsMainCommands:
    """Public service execution tests for docs commands."""

    def test_auditor_execute_verdict_follows_configured_posture(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path)
        (workspace / "docs/README.md").write_text(
            "# Docs\n\n[Broken](missing.md)\n", encoding="utf-8"
        )

        result = FlextInfraDocAuditor(repository_root=workspace).execute()

        if "audit" in config.Infra.codegen.make.docs.warning_actions:
            tm.ok(result)
        else:
            tm.fail(result)

    def test_fixer_execute_applies_link_and_toc_updates(self, tmp_path: Path) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path, include_fixable_link=True)

        result = FlextInfraDocFixer(
            repository_root=workspace, apply_changes=True
        ).execute()

        tm.ok(result)
        content = (workspace / "docs/README.md").read_text(encoding="utf-8")
        tm.that(content, has="guides/setup.md")
        tm.that(content, has="<!-- TOC START -->")

    def test_fixer_execute_fails_on_unapplied_drift(self, tmp_path: Path) -> None:
        """The command boundary rejects fixable docs left unapplied."""
        workspace = u.Tests.create_docs_workspace(tmp_path, include_fixable_link=True)

        result = FlextInfraDocFixer(repository_root=workspace).execute()

        tm.fail(result)

    def test_generator_plans_root_and_selected_project(self, tmp_path: Path) -> None:
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            project_names=("flext-a", "flext-b"),
            selected_projects=["flext-a"],
        )
        plans = u.Tests.publish_docs_bundle(generator)

        planned_paths = {plan.path for plan in plans}
        tm.that(
            workspace / "docs/projects/generated/catalog.md" in planned_paths, eq=True
        )
        tm.that(workspace / "flext-a/README.md" in planned_paths, eq=True)
        tm.that(workspace / "flext-b/README.md" not in planned_paths, eq=True)

    def test_validator_execute_fails_before_generation_and_succeeds_after(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        before = FlextInfraDocValidator(
            repository_root=workspace, selected_projects=["flext-a"]
        ).execute()
        tm.fail(before)
        generator = FlextInfraDocGenerator(
            repository_root=workspace, selected_projects=["flext-a"]
        )
        _ = u.Tests.publish_docs_bundle(generator)
        after = FlextInfraDocValidator(
            repository_root=workspace, selected_projects=["flext-a"], apply_changes=True
        ).execute()
        tm.ok(after)
        tm.that(
            (workspace / "flext-a/.reports/docs/validate-report.md").exists(), eq=True
        )
        tm.that((workspace / "flext-a/TODOS.md").exists(), eq=False)

    def test_builder_execute_fails_when_mkdocs_is_missing(self, tmp_path: Path) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path)

        result = FlextInfraDocBuilder(repository_root=workspace).execute()

        tm.fail(result)
        tm.that((workspace / ".reports/docs/build-report.md").exists(), eq=True)

    def test_builder_execute_fails_with_invalid_mkdocs_config(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path)
        (workspace / "mkdocs.yml").write_text("site_name: [", encoding="utf-8")

        result = FlextInfraDocBuilder(repository_root=workspace).execute()

        tm.fail(result)

    def test_generate_fix_cycle_is_byte_identical_on_second_run(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path)
        generator = FlextInfraDocGenerator(repository_root=workspace)
        fixer = FlextInfraDocFixer(repository_root=workspace, apply_changes=True)

        first_bundle = generator.prepare_bundle()
        tm.ok(first_bundle)
        required = generator.required_directories(first_bundle.value)
        tm.ok(required)
        for directory in required.value:
            directory.mkdir(parents=True, exist_ok=True)
        tm.ok(
            u.Tests.materialize_codegen_plans(generator.plan_files(first_bundle.value))
        )
        tm.ok(fixer.execute())
        first_cycle = {
            path: path.read_bytes() for path in u.Infra.iter_markdown_files(workspace)
        }

        second_bundle = generator.prepare_bundle()
        tm.ok(second_bundle)
        tm.ok(
            u.Tests.materialize_codegen_plans(generator.plan_files(second_bundle.value))
        )
        tm.ok(fixer.execute())
        second_cycle = {
            path: path.read_bytes() for path in u.Infra.iter_markdown_files(workspace)
        }

        tm.that(second_cycle, eq=first_cycle)
