"""Read-only publication-plan contracts for generated documentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.docs.generator import FlextInfraDocGenerator
from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsGeneratorPlan:
    """Read-only publication-plan contracts for generated documentation."""

    def _prepare_generated_parents(self, workspace: Path, project_name: str) -> None:
        """Materialize only parents until the directory transaction owns creation."""
        for path in (
            workspace
            / "docs/api-reference/generated/projects"
            / project_name
            / "modules",
            workspace / "docs/projects/generated",
            workspace / project_name / "docs/api-reference/generated/modules",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def test_required_directories_are_unique_parent_first_and_read_only(
        self, tmp_path: Path
    ) -> None:
        """Plan arbitrary nested target parents without materializing any directory."""
        project = tmp_path / "project"
        project.mkdir()
        source = project / "pyproject.toml"
        source.write_text("[project]\nname = 'docs-fixture'\n", encoding="utf-8")
        target = project / "docs/api-reference/generated/modules/api/v1/public.md"
        sibling = project / "docs/api-reference/generated/modules/api/v1/private.md"
        source_state = u.Cli.atomic_read_binary_file_state(source, required=True)
        tm.ok(source_state)
        bundle = m.Infra.DocsGenerationBundle(
            scopes=(
                m.Infra.DocsScopeArtifacts(
                    scope=m.Infra.DocScope(
                        name="docs-fixture",
                        path=project,
                        report_dir=project / ".reports/docs",
                    ),
                    artifacts=(
                        m.Infra.DocsRenderedArtifact(
                            relative_path=target.relative_to(project),
                            desired_content=b"# Public\n",
                            desired_mode=0o644,
                        ),
                        m.Infra.DocsRenderedArtifact(
                            relative_path=sibling.relative_to(project),
                            desired_content=b"# Private\n",
                            desired_mode=0o644,
                        ),
                    ),
                ),
            ),
            source_states=(source_state.value,),
            repository_root=project,
        )

        result = u.Infra.docs_required_directories(bundle)

        tm.ok(result)
        tm.that(
            result.value,
            eq=(
                project / "docs",
                project / "docs/api-reference",
                project / "docs/api-reference/generated",
                project / "docs/api-reference/generated/modules",
                project / "docs/api-reference/generated/modules/api",
                project / "docs/api-reference/generated/modules/api/v1",
            ),
        )
        tm.that(all(not path.exists() for path in result.value), eq=True)

    def test_required_directories_reject_duplicate_targets(
        self, tmp_path: Path
    ) -> None:
        """Fail before effects when two rendered artifacts claim one target."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))

        generator = FlextInfraDocGenerator(
            repository_root=workspace, selected_projects=["flext-a", "flext-a"]
        )
        prepared = generator.prepare_bundle()

        tm.fail(prepared)
        tm.that(prepared.error or "", has="duplicate docs publication target")

    def test_required_directories_match_final_file_plan_targets(
        self, tmp_path: Path
    ) -> None:
        """Keep the pre-snapshot directory plan bound to the final artifact owner."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path, project_names=("flext-a",), selected_projects=["flext-a"]
        )
        # `rglob` never yields the root it walks, and a scope root always exists,
        # so it is a directory the plan writes into and never has to create.

        def _directories() -> set[Path]:
            return {
                workspace,
                *(path for path in workspace.rglob("*") if path.is_dir()),
            }

        directories_before = _directories()

        prepared = generator.prepare_bundle()
        tm.ok(prepared)
        required = generator.required_directories(prepared.value)

        tm.ok(required)
        tm.that(_directories(), eq=directories_before)
        tm.that(any(not directory.exists() for directory in required.value), eq=True)
        for directory in required.value:
            if not directory.exists():
                directory.mkdir()
        planned = generator.plan_files(prepared.value)
        tm.ok(planned)
        planned_new_parents = {
            plan.path.parent
            for plan in planned.value
            if plan.desired_content is not None
            and plan.path.parent not in directories_before
        }
        tm.that(planned_new_parents.difference(required.value), eq=set())

    def test_plan_files_returns_exact_read_only_docs_plans(
        self, tmp_path: Path
    ) -> None:
        """Describe generated artifacts without changing the workspace."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        self._prepare_generated_parents(workspace, "flext-a")
        before = {
            path: path.read_bytes() for path in workspace.rglob("*") if path.is_file()
        }

        generator = FlextInfraDocGenerator(
            repository_root=workspace, selected_projects=["flext-a"]
        )
        plans = u.Tests.plan_docs_bundle(generator)

        tm.that(plans, empty=False)
        tm.that(all(plan.desired_mode == 0o644 for plan in plans), eq=True)
        tm.that(all(plan.source_states for plan in plans), eq=True)
        tm.that(
            {
                path: path.read_bytes()
                for path in workspace.rglob("*")
                if path.is_file()
            },
            eq=before,
        )
        tm.that((workspace / ".reports").exists(), eq=False)

    def test_generate_publishes_and_reaches_an_unchanged_second_run(
        self, tmp_path: Path
    ) -> None:
        """The public fixed-effect command writes and converges without a mode flag."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        generator = FlextInfraDocGenerator(repository_root=workspace)
        plans = u.Tests.plan_docs_bundle(generator)
        changed = next(
            plan
            for plan in plans
            if plan.desired_content is not None
            and u.Infra.codegen_file_requires_effect(plan)
        )
        request = m.Infra.DocsGenerateRequest(repository_root=workspace)
        first = generator.generate(request)
        tm.ok(first)
        tm.that(any(report.generated for report in first.value), eq=True)
        tm.that(changed.path.read_bytes(), eq=changed.desired_content)
        second = generator.generate(request)
        tm.ok(second)
        tm.that(
            all(report.changed_files == 0 and report.passed for report in second.value),
            eq=True,
        )

    def test_stale_generated_markdown_becomes_delete_plan(self, tmp_path: Path) -> None:
        """Represent stale generated cleanup as a journalable delete plan."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        self._prepare_generated_parents(workspace, "flext-a")
        stale = workspace / "flext-a/docs/api-reference/generated/stale.md"
        stale.write_text("stale\n", encoding="utf-8")

        generator = FlextInfraDocGenerator(
            repository_root=workspace, selected_projects=["flext-a"]
        )
        plans = u.Tests.plan_docs_bundle(generator)

        stale_plan = next(plan for plan in plans if plan.path == stale)
        tm.that(stale_plan.desired_content, eq=None)
        tm.that(u.Infra.codegen_file_requires_effect(stale_plan), eq=True)
        tm.that(
            tm.ok(u.Infra.codegen_file_before_state(stale_plan)).content, eq=b"stale\n"
        )
        tm.that(stale.exists(), eq=True)

    def test_scope_failure_is_not_normalized_to_empty_aggregate(
        self, tmp_path: Path
    ) -> None:
        """Propagate malformed workspace topology instead of rendering an empty root."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        (workspace / ".gitmodules").write_text(
            '[submodule "broken"]\n\tpath = ../outside\n', encoding="utf-8"
        )

        generator = FlextInfraDocGenerator(repository_root=workspace)
        prepared = generator.prepare_bundle()

        tm.fail(prepared)
        tm.that(prepared.error or "", has="invalid Git submodule path")
