"""Public generation-workflow tests for docs services.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_core import r
from flext_infra import c, config, t
from flext_infra.docs.builder import FlextInfraDocBuilder
from flext_infra.docs.generator import FlextInfraDocGenerator
from flext_infra.docs.validator import FlextInfraDocValidator
from flext_infra.gates.markdown_format import FlextInfraMarkdownFormatGate
from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsGenerator:
    """Public generation-workflow tests for docs services."""

    @staticmethod
    def test_generate_returns_reports_for_root_and_selected_project(
        tmp_path: Path,
    ) -> None:
        """Return reports for the workspace root and selected project."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            project_names=("flext-a", "flext-b"),
            selected_projects=["flext-a"],
        )
        _ = u.Tests.plan_docs_bundle(generator)
        result = generator.generate(
            m.Infra.DocsGenerateRequest(
                repository_root=workspace,
                projects=["flext-a"],
            ),
        )

        tm.ok(result)
        tm.that([report.scope for report in result.value], eq=["root", "flext-a"])

    @staticmethod
    def test_standalone_root_mkdocs_publishes_canonical_site_title(
        tmp_path: Path,
    ) -> None:
        """A standalone repository's root MkDocs site carries no project suffix.

        The repository root publishes the canonical site identity its docs
        contract declares; the per-project ``" Documentation"`` suffix belongs
        to member project sites only (root title contract, c6db82fb2).
        """
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            selected_projects=["."],
        )
        _ = u.Tests.plan_docs_bundle(generator)
        result = generator.generate(
            m.Infra.DocsGenerateRequest(repository_root=workspace, projects=["."]),
        )

        tm.ok(result)
        mkdocs = (workspace / "mkdocs.yml").read_text(encoding="utf-8")
        tm.that("site_name: workspace\n" in mkdocs, eq=True)
        tm.that("site_name: workspace Documentation" in mkdocs, eq=False)

    @staticmethod
    def test_bundle_plans_root_and_selected_project_artifacts(
        tmp_path: Path,
    ) -> None:
        """Keep all selected artifacts in one transaction-owned bundle."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            project_names=("flext-a",),
            selected_projects=["flext-a"],
        )
        plans = u.Tests.plan_docs_bundle(generator)

        paths = {plan.path for plan in plans}
        tm.that(workspace / "docs/projects/generated/catalog.md" in paths, eq=True)
        tm.that(workspace / "flext-a/README.md" in paths, eq=True)
        tm.that(all(plan.owner == "docs" for plan in plans), eq=True)

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("selected_projects", [None, (".",), ("flext-a",)])
    @pytest.mark.parametrize("project_name", ["workspace", config.Infra.name])
    def test_workspace_package_api_and_member_docs_share_one_transaction(
        tmp_path: Path,
        selected_projects: t.StrSequence | None,
        project_name: str,
    ) -> None:
        """Publish root API and member aggregates together for every selection."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        (workspace / "pyproject.toml").write_text(
            f'[project]\nname = "{project_name}"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        package = workspace / "src/workspace_runtime"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            '"""Workspace fixture package."""\n',
            encoding="utf-8",
        )
        declared = ("api", "models")
        for module in declared:
            source = package / f"{module.replace('.', '/')}.py"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text('"""Public fixture module."""\n', encoding="utf-8")
        request = m.Infra.DocsGenerateRequest(
            repository_root=workspace,
            projects=selected_projects,
        )
        generator = FlextInfraDocGenerator(
            repository_root=workspace,
            selected_projects=selected_projects,
        )

        plans = u.Tests.publish_docs_bundle(generator)
        tm.that(len({plan.path for plan in plans}), eq=len(plans))
        generated = workspace / "docs/api-reference/generated"
        tm.that(
            (generated / "public-api.md").read_text(encoding="utf-8"),
            has=f"::: {package.name}\n",
        )
        modules = generated / "modules"
        tm.that((modules / "index.md").exists(), eq=True)
        tm.that(
            {path.relative_to(modules).as_posix() for path in modules.rglob("*.md")},
            eq={"index.md", *(f"{module.replace('.', '/')}.md" for module in declared)},
        )
        for module in declared:
            tm.that(
                (modules / f"{module.replace('.', '/')}.md").read_text(
                    encoding="utf-8",
                ),
                has=f"::: {package.name}.{module}\n",
            )
        preserved = {
            path: path.read_bytes()
            for path in (
                generated / "public-api.md",
                modules / "index.md",
                generated / "flext-a.md",
                generated / "projects/flext-a/modules/index.md",
                workspace / "docs/projects/generated/catalog.md",
            )
        }
        mkdocs = (workspace / "mkdocs.yml").read_text(encoding="utf-8")
        tm.that(mkdocs, has="- src\n")
        tm.that(mkdocs, has="- flext-a/src\n")
        stale = generated / "stale.md"
        stale.write_text("# Stale generated page\n", encoding="utf-8")

        _ = u.Tests.publish_docs_bundle(generator)
        tm.that(stale.exists(), eq=False)
        for path, content in preserved.items():
            tm.that(path.read_bytes(), eq=content)

        fixed_point = generator.generate(request)

        tm.ok(fixed_point)
        tm.that(all(report.changed_files == 0 for report in fixed_point.value), eq=True)

        bundle = u.Tests.prepare_docs_bundle(generator)
        # Mutate an authenticated source selected by the bundle itself.
        # Different project selections legitimately watch different sources.
        watched = next(
            state.path
            for state in bundle.source_states
            if workspace in state.path.parents
        )
        watched.write_text('"""Source changed after rendering."""\n', encoding="utf-8")
        tm.fail(generator.plan_files(bundle))

    @staticmethod
    def test_root_generated_catalog_survives_project_pass_and_required_indexes_validate(
        tmp_path: Path,
    ) -> None:
        """Preserve root output while leaving optional curated indexes unowned."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        request = m.Infra.DocsGenerateRequest(
            repository_root=workspace,
            projects=["flext-a"],
        )
        generator = FlextInfraDocGenerator(
            repository_root=workspace,
            selected_projects=["flext-a"],
        )

        _ = u.Tests.publish_docs_bundle(generator)
        catalog = workspace / "docs/projects/generated/catalog.md"
        tm.that(catalog.exists(), eq=True)

        _ = u.Tests.publish_docs_bundle(generator)
        tm.that(catalog.exists(), eq=True)

        for relative_path in (
            "docs/README.md",
            "docs/architecture/README.md",
            "docs/guides/README.md",
            "docs/projects/README.md",
        ):
            (workspace / relative_path).unlink()
        validation = FlextInfraDocValidator().validate_workspace(request)
        tm.ok(validation)
        tm.that(all(report.result == "OK" for report in validation.value), eq=True)

    @staticmethod
    def test_generated_collection_rules_pointer_stays_within_consumer_limit(
        tmp_path: Path,
    ) -> None:
        """Keep the generated Collection Rules pointer within the Markdown limit."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            project_names=("flext-a",),
            selected_projects=["flext-a"],
        )
        _ = u.Tests.publish_docs_bundle(generator)

        lines = (
            (workspace / "flext-a/docs/index.md")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        section_start = lines.index("## Collection Rules")
        section_end = next(
            index
            for index in range(section_start + 1, len(lines))
            if lines[index].startswith("## ")
        )
        collection_rules_lines = [
            line for line in lines[section_start:section_end] if line
        ]
        tm.that(max(map(len, collection_rules_lines)), lte=240)

    @staticmethod
    def test_governed_api_survives_generation_and_curated_paths_are_unowned(
        tmp_path: Path,
    ) -> None:
        """Publish standalone API without treating the sole scope as an aggregate."""
        workspace = (
            u.Tests.create_docs_workspace(
                tmp_path,
                project_names=("flext-infra-fixture",),
            )
            / "flext-infra-fixture"
        )
        u.Tests.write_standalone_workspace_manifest(workspace, "flext-infra-fixture")
        curated = workspace / "docs/README.md"
        curated_content = curated.read_bytes()
        request = m.Infra.DocsGenerateRequest(
            repository_root=workspace,
            projects=["flext-infra-fixture"],
        )
        generator = FlextInfraDocGenerator(
            repository_root=workspace,
            selected_projects=["flext-infra-fixture"],
        )

        plans = u.Tests.publish_docs_bundle(generator)
        tm.that(plans, empty=False)
        tm.that(len({plan.path for plan in plans}), eq=len(plans))
        tm.that(curated in {plan.path for plan in plans}, eq=False)

        result = generator.generate(request)
        tm.ok(result)
        tm.that(
            (workspace / "docs/api-reference/generated/public-api.md").is_file(),
            eq=True,
        )
        tm.that((workspace / "docs/projects/generated/catalog.md").exists(), eq=False)
        tm.that([report.scope for report in result.value], eq=["flext-infra-fixture"])
        for report in result.value:
            tm.that(report.changed_files, eq=0)
            tm.that(report.passed, eq=True)

        tm.that(curated.read_bytes(), eq=curated_content)
        tm.that(
            (workspace / "docs/api-reference/generated/public-api.md").read_text(
                encoding="utf-8",
            ),
            has=f"::: {u.Infra.project_package_name(workspace)}\n",
        )
        tm.that(
            (workspace / "docs/api-reference/generated/modules/index.md").exists(),
            eq=True,
        )

    @staticmethod
    def test_generate_preserves_declared_export_order_and_is_idempotent(
        tmp_path: Path,
    ) -> None:
        """Preserve declared export order across repeated generation."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        project = workspace / "flext-a"
        package = project / "src/flext_a"
        (package / "alpha.py").write_text(
            '"""Alpha exports."""\n\nclass FlextAAlpha:\n    """Alpha facade."""\n',
            encoding="utf-8",
        )
        (package / "beta.py").write_text(
            '"""Beta exports."""\n\nclass FlextABeta:\n    """Beta facade."""\n',
            encoding="utf-8",
        )
        (package / "__init__.py").write_text(
            "from flext_a.beta import FlextABeta\n"
            "from flext_a.alpha import FlextAAlpha\n\n"
            '__all__ = ["FlextAAlpha", "FlextABeta"]\n',
            encoding="utf-8",
        )
        generator = FlextInfraDocGenerator(
            repository_root=workspace,
            selected_projects=["flext-a"],
        )

        _ = u.Tests.publish_docs_bundle(generator)
        first_readme = (project / "README.md").read_text(encoding="utf-8")
        first_index = (project / "docs/index.md").read_text(encoding="utf-8")
        tm.that(first_readme, has=f"{c.Infra.GITHUB_REPO_URL}/blob/")
        tm.that(first_readme, lacks="](../AGENTS.md)")
        for generated_page in (first_readme, first_index):
            tm.that(generated_page, has="## Governance Pointer")
            tm.that(generated_page, has="- Skills index:")
            tm.that(generated_page, has=".agents/skills/")
            tm.that(generated_page, lacks="the agents_home `make-check` skill")
        tm.that(
            first_readme.index("FlextAAlpha") < first_readme.index("FlextABeta"),
            eq=True,
        )

        second = u.Tests.plan_docs_bundle(generator)
        tm.that(
            any(u.Infra.codegen_file_requires_effect(plan) for plan in second),
            eq=False,
        )
        tm.that((project / "README.md").read_text(encoding="utf-8"), eq=first_readme)

    @staticmethod
    def test_public_top_level_modules_own_generated_module_pages(
        tmp_path: Path,
    ) -> None:
        """Every public top-level module gets a page; private modules never do."""
        project_name = "flext-a"
        workspace = u.Tests.create_docs_workspace(
            tmp_path,
            project_names=(project_name,),
        )
        project = workspace / project_name
        package = project / "src" / project_name.replace("-", "_")
        public = ("api", "models")
        for module in (*public, "_internal"):
            (package / f"{module}.py").write_text(
                f'"""Fixture module {module}."""\n',
                encoding="utf-8",
            )

        generator = FlextInfraDocGenerator(
            repository_root=workspace,
            selected_projects=[project_name],
        )
        _ = u.Tests.publish_docs_bundle(generator)

        modules_root = project / "docs/api-reference/generated/modules"
        generated = {
            path.relative_to(modules_root).as_posix()
            for path in modules_root.rglob("*.md")
            if path.name != "index.md"
        }
        expected = {
            f"{path.stem}.md"
            for path in package.glob("*.py")
            if not path.stem.startswith("_")
        }
        tm.that(set(public) <= {name.removesuffix(".md") for name in expected}, eq=True)
        tm.that(generated, eq=expected)
        tm.that("_internal.md" in generated, eq=False)

    @staticmethod
    def test_generated_markdown_starts_with_level_one_heading(
        tmp_path: Path,
    ) -> None:
        """Test generated markdown starts with level one heading."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            project_names=("flext-a",),
            selected_projects=["flext-a"],
        )

        _ = u.Tests.publish_docs_bundle(generator)

        generated = (
            workspace / "flext-a/README.md",
            workspace / "flext-a/docs/index.md",
            workspace / "flext-a/docs/guides/README.md",
            workspace / "flext-a/docs/api-reference/README.md",
            workspace / "flext-a/docs/api-reference/generated/overview.md",
            workspace / "flext-a/docs/api-reference/generated/public-api.md",
            workspace / "flext-a/docs/api-reference/generated/modules/index.md",
        )
        for path in generated:
            first_line = path.read_text(encoding="utf-8").splitlines()[0]
            tm.that(first_line.startswith("# "), eq=True, msg=path.as_posix())

    @staticmethod
    def test_docs_policy_declares_cross_project_relative_link_pattern() -> None:
        """Test docs policy declares cross project relative link pattern."""
        tm.that(
            config.Infra.codegen.make.docs.cross_project_relative_link_pattern,
            empty=False,
        )

    @staticmethod
    def test_generated_mkdocstrings_directive_preserves_indented_options(
        tmp_path: Path,
    ) -> None:
        """Keep Mkdocstrings directives structural across generated pages."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            project_names=("flext-a",),
            selected_projects=["flext-a"],
        )

        _ = u.Tests.publish_docs_bundle(generator)
        page = (
            workspace / "flext-a/docs/api-reference/generated/public-api.md"
        ).read_text(encoding="utf-8")
        tm.that(
            page,
            has=(
                "::: flext_a\n\n"
                "    options:\n"
                "      show_root_heading: true\n"
                "      show_root_full_path: false\n"
                "      show_source: false\n"
            ),
        )
        tm.that(page, lacks="::: flext_a options:")

    @staticmethod
    @pytest.mark.slow
    def test_generated_directive_builds_with_real_mkdocstrings(
        tmp_path: Path,
    ) -> None:
        """The actual documentation engine consumes the generated directive options."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        package = workspace / "src/docs_example"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            '"""Documentation runtime contract."""\n',
            encoding="utf-8",
        )
        (workspace / "docs/index.md").write_text(
            u.Infra.docs_directive_page("Runtime API", "docs_example"),
            encoding="utf-8",
        )
        (workspace / "mkdocs.yml").write_text(
            "site_name: Documentation contract\ndocs_dir: docs\n"
            "exclude_docs: |\n  README.md\nplugins:\n  - autorefs\n"
            "  - mkdocstrings:\n      handlers:\n        python:\n"
            "          paths: [src]\n",
            encoding="utf-8",
        )

        result = FlextInfraDocBuilder(repository_root=workspace).execute()

        tm.ok(result)
        pages = tuple(workspace.rglob("index.html"))
        assert pages
        assert any('id="docs_example"' in page.read_text() for page in pages)

    @staticmethod
    def test_generated_bundle_is_accepted_by_real_markdown_formatter(
        tmp_path: Path,
        request: pytest.FixtureRequest,
    ) -> None:
        """Generated prose and directives already match the provisioned formatter."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            project_names=("flext-a",),
            selected_projects=["flext-a"],
        )
        _ = u.Tests.publish_docs_bundle(generator)
        project = workspace / "flext-a"
        config_path = project / c.Infra.PRETTIER_CONFIG_FILENAME
        config_path.write_text(
            (request.config.rootpath / c.Infra.PRETTIER_CONFIG_FILENAME).read_text(
                encoding="utf-8",
            ),
            encoding="utf-8",
        )
        result = u.Tests.run_gate_check(
            FlextInfraMarkdownFormatGate,
            workspace,
            project,
        )
        readme = project / "README.md"
        before = readme.read_text(encoding="utf-8")
        context = m.Infra.GateContext(
            repository_root=workspace,
            reports_dir=tmp_path,
            apply_fixes=True,
        )
        _ = FlextInfraMarkdownFormatGate(workspace).fix(project, context)
        assert before == readme.read_text(encoding="utf-8")
        assert result.result.passed, result.issues

    @staticmethod
    def test_generated_prose_wraps_without_reformatting_directive_blocks(
        tmp_path: Path,
    ) -> None:
        """Wrap prose at the canonical width while preserving directives."""
        scope = m.Infra.DocScope(
            name="flext-a",
            path=tmp_path,
            report_dir=tmp_path / ".reports/docs",
            project_class="library",
            package_name="flext_a",
        )
        contract = {"version": "1.0", "description": " ".join(["resilient"] * 20)}

        rendered = u.Infra.docs_project_index(scope, contract)

        description_lines = [
            line
            for line in rendered.splitlines()
            if line.startswith(("- Description:", "  resilient"))
        ]
        tm.that(
            max(map(len, description_lines)) <= u.Infra.docs_markdown_line_length(),
            eq=True,
        )
        tm.that(
            rendered,
            has=(
                "::: flext_a\n\n"
                "    options:\n"
                "      members: false\n"
                "      show_root_heading: false\n"
                "      show_root_toc_entry: false\n"
                "      show_source: false\n"
            ),
        )

    @staticmethod
    def test_file_plan_reports_real_drift_and_reaches_fixed_point(
        tmp_path: Path,
    ) -> None:
        """Report drift from one bundle and reach a byte-identical fixed point."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        generator = FlextInfraDocGenerator(repository_root=workspace)

        initial = u.Tests.plan_docs_bundle(generator)
        tm.that(
            any(u.Infra.codegen_file_requires_effect(plan) for plan in initial),
            eq=True,
        )
        published = u.Tests.materialize_codegen_plans(
            r[tuple[m.Infra.CodegenFilePlan, ...]].ok(initial),
        )
        tm.ok(published)

        fixed_point = u.Tests.plan_docs_bundle(generator)
        tm.that(
            any(u.Infra.codegen_file_requires_effect(plan) for plan in fixed_point),
            eq=False,
        )

    @staticmethod
    def test_stale_generated_file_drift_converges_through_file_plans(
        tmp_path: Path,
    ) -> None:
        """Plan stale removal, publish it via the transaction adapter, and converge."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            project_names=("flext-a",),
            selected_projects=["flext-a"],
        )
        _ = u.Tests.publish_docs_bundle(generator)
        stale = workspace / "flext-a/docs/api-reference/generated/stale.md"
        stale.write_text("stale\n", encoding="utf-8")

        stale_plans = u.Tests.plan_docs_bundle(generator)
        tm.that(stale.exists(), eq=True)
        tm.that(
            any(
                plan.path == stale and u.Infra.codegen_file_requires_effect(plan)
                for plan in stale_plans
            ),
            eq=True,
        )
        published = u.Tests.materialize_codegen_plans(
            r[tuple[m.Infra.CodegenFilePlan, ...]].ok(stale_plans),
        )
        tm.ok(published)
        tm.that(stale.exists(), eq=False)

        fixed_point = u.Tests.plan_docs_bundle(generator)
        tm.that(
            any(u.Infra.codegen_file_requires_effect(plan) for plan in fixed_point),
            eq=False,
        )

    @staticmethod
    def test_generated_file_model_is_frozen() -> None:
        """Keep generated-file report models immutable."""
        tm.that(m.Infra.GeneratedFile.model_config.get("frozen"), eq=True)

    @staticmethod
    def test_generate_report_tracks_written_files() -> None:
        """Track written files in generation phase reports."""
        report = m.Infra.DocsPhaseReport(
            phase="generate",
            scope="root",
            generated=2,
            applied=True,
            source="code-docstring-ssot",
            items=[
                m.Infra.DocsPhaseItemModel(
                    phase="generate",
                    path="docs/a.md",
                    written=True,
                ),
                m.Infra.DocsPhaseItemModel(
                    phase="generate",
                    path="docs/b.md",
                    written=False,
                ),
            ],
        )

        tm.that(report.generated, eq=2)
        tm.that(len(report.items), eq=2)

    @staticmethod
    def test_docs_url_scheme_rejects_http() -> None:
        """Test docs url scheme rejects http."""
        target = f"{c.Infra.DOCS_INSECURE_WEB_SCHEME}://example.invalid"

        with pytest.raises(ValueError, match="use HTTPS"):
            u.Infra.docs_url_scheme(target)
