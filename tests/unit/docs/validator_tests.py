"""Public validation-workflow tests for docs services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.docs.generator import FlextInfraDocGenerator
from flext_infra.docs.validator import FlextInfraDocValidator
from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsValidator:
    """Public validation-workflow tests for docs services."""

    def test_validate_report_model_fields(self) -> None:
        report = m.Infra.DocsPhaseReport(
            phase="validate",
            scope="root",
            result="FAIL",
            message="Missing generated docs",
            missing_adr_skills=["rules-docs"],
            todo_written=False,
        )

        tm.that(report.result, eq="FAIL")
        tm.that(report.missing_adr_skills, eq=["rules-docs"])
        tm.that(report.todo_written, eq=False)

    def test_validate_workspace_fails_before_generated_files_exist(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        result = FlextInfraDocValidator().validate_workspace(
            m.Infra.DocsGenerateRequest(repository_root=workspace, projects=["flext-a"])
        )

        tm.ok(result)
        tm.that(any(report.result == "FAIL" for report in result.value), eq=True)

    def test_validate_workspace_passes_after_generation(self, tmp_path: Path) -> None:
        """Validation passes once the generated bundle is published."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        prepared = FlextInfraDocGenerator(
            repository_root=workspace, selected_projects=["flext-a"]
        ).prepare_bundle()
        tm.ok(prepared)
        generated = u.Tests.materialize_docs_bundle(prepared.value)
        tm.ok(generated)
        result = FlextInfraDocValidator().validate_workspace(
            m.Infra.DocsGenerateRequest(repository_root=workspace, projects=["flext-a"])
        )

        tm.ok(result)
        tm.that(all(report.result == "OK" for report in result.value), eq=True)

    def test_standalone_manifest_keeps_project_docs_and_validates(
        self, tmp_path: Path
    ) -> None:
        """A standalone repository carrying its manifest is not a workspace root.

        Regression: treating the manifest file's presence as topology made
        generate publish an empty root catalog ("Governed projects: 0") for a
        standalone repository and broke its gen fixed point. The scope label,
        derived from the manifest's typed role, is the only topology input.
        """
        repository = u.Tests.create_docs_workspace(tmp_path)
        u.Tests.write_standalone_workspace_manifest(repository, "workspace")

        prepared = FlextInfraDocGenerator(repository_root=repository).prepare_bundle()
        tm.ok(prepared)
        tm.ok(u.Tests.materialize_docs_bundle(prepared.value))
        result = FlextInfraDocValidator().validate_workspace(
            m.Infra.DocsGenerateRequest(repository_root=repository)
        )

        tm.ok(result)
        tm.that(all(report.result == "OK" for report in result.value), eq=True)
        tm.that((repository / "docs/projects/generated/catalog.md").exists(), eq=False)

    def test_validate_workspace_does_not_write_project_todo(
        self, tmp_path: Path
    ) -> None:
        """Read-only validation does not publish a project TODO ledger."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        prepared = FlextInfraDocGenerator(
            repository_root=workspace, selected_projects=["flext-a"]
        ).prepare_bundle()
        tm.ok(prepared)
        tm.ok(u.Tests.materialize_docs_bundle(prepared.value))
        result = FlextInfraDocValidator().validate_workspace(
            m.Infra.DocsGenerateRequest(repository_root=workspace, projects=["flext-a"])
        )

        tm.ok(result)
        tm.that((workspace / "flext-a/TODOS.md").exists(), eq=False)
