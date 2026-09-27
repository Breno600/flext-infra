"""Workspace/parser helper tests for deps modernizer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPyprojectModernizer, config, main, u as infra_u
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraDepsModernizerWorkspace:
    """Validate helper behavior through public utilities and entrypoints."""

    @staticmethod
    def _reject_external_selector(
        modernizer_workspace: Path,
        selector: str,
        external_pyproject: Path,
        original: str,
    ) -> None:
        """Run the modernizer on an undeclared selector and prove no mutation."""
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=modernizer_workspace,
            selected_projects=[selector],
            apply_changes=True,
            skip_check=True,
            skip_comments=True,
        )

        tm.that(modernizer.run(), eq=2)
        tm.that(external_pyproject.read_text(encoding="utf-8"), eq=original)

    def test_taplo_formats_toml_through_public_utility(self, tmp_path: Path) -> None:
        config_path = tmp_path / ".taplo.toml"
        config_path.write_text('include = ["**/*.toml"]\n', encoding="utf-8")
        formatter = infra_u.Infra.format_toml_source
        taplo_version = config.Infra.codegen.toolchain.taplo_version
        process_timeout_seconds = (
            config.Infra.tooling.tools.tomlsort.process_timeout_seconds
        )
        source = 'name="demo"\n'

        formatted = tm.ok(
            formatter(
                source,
                path=tmp_path / "first" / "pyproject.toml",
                toolchain_root=tmp_path,
                taplo_version=taplo_version,
                process_timeout_seconds=process_timeout_seconds,
            )
        )
        config_path.write_text('include = ["pyproject.toml"]\n', encoding="utf-8")
        reformatted = tm.ok(
            formatter(
                source,
                path=tmp_path / "first" / "pyproject.toml",
                toolchain_root=tmp_path,
                taplo_version=taplo_version,
                process_timeout_seconds=process_timeout_seconds,
            )
        )
        # Why (flext-50qh0): the wrapper returns Taplo's stdout unchanged and
        # a formatted TOML document ends with the canonical trailing newline.
        tm.that(formatted, eq='name = "demo"\n')
        tm.that(reformatted, eq=formatted)

    def test_taplo_uses_nearest_existing_root_for_scaffold_path(
        self, tmp_path: Path
    ) -> None:
        future_root = tmp_path / "future" / "project"

        formatted = tm.ok(
            infra_u.Infra.format_toml_source(
                'name="demo"\n',
                path=future_root / "pyproject.toml",
                toolchain_root=future_root,
                taplo_version=config.Infra.codegen.toolchain.taplo_version,
                process_timeout_seconds=(
                    config.Infra.tooling.tools.tomlsort.process_timeout_seconds
                ),
            )
        )

        # Why (flext-50qh0): the wrapper returns Taplo's stdout unchanged and
        # a formatted TOML document ends with the canonical trailing newline.
        tm.that(formatted, eq='name = "demo"\n')

    @pytest.mark.parametrize(
        ("content", "exists", "expected"),
        [
            pytest.param('key = "value"\n', True, True, id="valid"),
            pytest.param("invalid toml content [[[", True, False, id="invalid"),
            pytest.param("", False, False, id="missing"),
        ],
    )
    def test_toml_read_handles_public_file_cases(
        self, tmp_path: Path, content: str, *, exists: bool, expected: bool
    ) -> None:
        """Verify toml read handles public file cases."""
        toml_file = tmp_path / "test.toml"
        if exists:
            toml_file.write_text(content, encoding="utf-8")
        with u.structlog().testing.capture_logs() as log_entries:
            result = u.Cli.toml_read(toml_file)
        tm.that(result is not None, eq=expected)
        if exists and not expected:
            tm.that(log_entries, len=1)
            tm.that(log_entries[0].get("log_level"), eq="warning")
        else:
            tm.that(log_entries, empty=True)

    def test_repository_root_returns_explicit_path(self, tmp_path: Path) -> None:
        """Verify repository root returns explicit path."""
        explicit = tmp_path / "explicit"
        explicit.mkdir()
        result = u.Infra.resolve_repository_root_or_cwd(explicit)
        tm.that(str(result), eq=str(explicit.resolve()))

    def test_repository_root_fallback_returns_non_empty_path(
        self, tmp_path: Path
    ) -> None:
        """Verify repository root fallback returns non empty path."""
        deep_path = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep_path.mkdir(parents=True, exist_ok=True)
        result = u.Infra.resolve_repository_root_or_cwd(deep_path)
        tm.that(str(result), ne="")

    @pytest.mark.parametrize(
        ("description", "sort_first"),
        [
            pytest.param("Config-owned metadata", None, id="config-owner"),
            pytest.param(
                "Portable process runner",
                ("project", "dependency-groups"),
                id="project-first",
            ),
            pytest.param(
                "Typed metadata: punctuation-safe.",
                ("dependency-groups", "project"),
                id="groups-first",
            ),
        ],
    )
    def test_conform_preserves_explicit_project_table_boundary(
        self, tmp_path: Path, description: str, sort_first: t.StrSequence | None
    ) -> None:
        """Keep project scalars explicit for arbitrary valid top-level orders."""
        pyproject = tmp_path / c.PYPROJECT_FILENAME
        package_init = tmp_path / "src" / "flext_example" / "__init__.py"
        package_init.parent.mkdir(parents=True)
        package_init.write_text("", encoding="utf-8")
        expected_order = (
            config.Infra.tooling.tools.tomlsort.sort_first
            if sort_first is None
            else sort_first
        )
        source = (
            "[project]\n"
            'name = "flext-example"\n'
            'version = "0.1.0"\n'
            f'description = "{description}"\n'
            "\n[dependency-groups]\n"
            'dev = ["pytest"]\n'
        )
        modernizer = (
            FlextInfraPyprojectModernizer(
                repository_root=tmp_path, skip_check=True, skip_comments=True
            )
            if sort_first is None
            else FlextInfraPyprojectModernizer(
                repository_root=tmp_path,
                skip_check=True,
                skip_comments=True,
                tomlsort_sort_first=sort_first,
            )
        )
        rendered = tm.ok(modernizer.conform_source(source, path=pyproject))
        tm.that(rendered.count("[project]"), eq=1)
        payload = u.Cli.toml_mapping_from_text(rendered)
        tm.that(payload, none=False)
        if payload is None:
            pytest.fail("conformed pyproject must remain valid TOML")
        project = u.Cli.toml_mapping_child(payload, c.Infra.PROJECT)
        tm.that(project, none=False)
        if project is None:
            pytest.fail("conformed pyproject must retain [project]")
        tm.that(project.get("description"), eq=description)
        groups = u.Cli.toml_mapping_child(payload, "dependency-groups")
        tm.that(groups, none=False)
        if groups is None:
            pytest.fail("conformed pyproject must retain [dependency-groups]")
        tm.that(u.Cli.json_as_sequence(groups.get(c.Infra.DEV)), eq=["pytest"])
        tm.that(list(payload)[: len(expected_order)], eq=list(expected_order))

    def test_main_applies_only_selected_projects(
        self, modernizer_workspace_with_projects: Path
    ) -> None:
        """Verify main applies only selected projects."""
        selected_pyproject = (
            modernizer_workspace_with_projects / "selected" / c.PYPROJECT_FILENAME
        )
        ignored_pyproject = (
            modernizer_workspace_with_projects / "ignored" / c.PYPROJECT_FILENAME
        )
        tm.that(
            main([
                "deps",
                "modernize",
                "--repository-root",
                str(modernizer_workspace_with_projects),
                "--apply",
                "--skip-check",
                "--projects",
                "selected",
            ]),
            eq=0,
        )
        tm.that(
            selected_pyproject.read_text(encoding="utf-8"),
            has='build-backend = "hatchling.build"',
        )
        tm.that(ignored_pyproject.read_text(encoding="utf-8"), has='name = "ignored"')

    def test_modernizer_selects_configured_member_by_declared_name(
        self, tmp_path: Path
    ) -> None:
        """Resolve a configured member through its canonical project name."""
        workspace = tmp_path / "workspace"
        member = workspace / "member-dir"
        member.mkdir(parents=True)
        (workspace / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "workspace"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (workspace / ".gitmodules").write_text(
            '[submodule "declared-name"]\n\tpath = member-dir\n'
            "\turl = https://github.com/flext-sh/declared-name.git\n",
            encoding="utf-8",
        )
        (member / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "declared-name"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        u.Tests.write_beads_project(
            member,
            workspace="workspace",
            database="declared_name",
            issue_prefix="declared-name",
        )

        modernizer = FlextInfraPyprojectModernizer(
            repository_root=workspace,
            selected_projects=["declared-name"],
            apply_changes=False,
            skip_check=True,
            skip_comments=True,
        )

        tm.that(modernizer.run(), eq=0)

    def test_modernizer_accepts_workspace_only_root_without_constraint_rewrite(
        self, tmp_path: Path
    ) -> None:
        """Do not require root project metadata for member-only modernization."""
        workspace = tmp_path / "workspace"
        member = workspace / "member"
        member.mkdir(parents=True)
        (workspace / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "workspace"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (workspace / ".gitmodules").write_text(
            '[submodule "member"]\n\tpath = member\n'
            "\turl = https://github.com/flext-sh/member.git\n",
            encoding="utf-8",
        )
        (member / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "member"\nversion = "0.1.0"\n', encoding="utf-8"
        )

        modernizer = FlextInfraPyprojectModernizer(
            repository_root=workspace,
            selected_projects=["member"],
            apply_changes=False,
            skip_check=True,
            skip_comments=True,
            rewrite_constraints=False,
        )

        tm.that(modernizer.run(), eq=0)

    def test_modernizer_rejects_ambiguous_configured_member_alias(
        self, tmp_path: Path
    ) -> None:
        """Fail loud when one canonical project name selects multiple members."""
        workspace = tmp_path / "workspace"
        (workspace / "first-dir").mkdir(parents=True)
        (workspace / "second-dir").mkdir()
        (workspace / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "workspace"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (workspace / ".gitmodules").write_text(
            '[submodule "first"]\n\tpath = first-dir\n'
            "\turl = https://github.com/flext-sh/first.git\n"
            '[submodule "second"]\n\tpath = second-dir\n'
            "\turl = https://github.com/flext-sh/second.git\n",
            encoding="utf-8",
        )
        for member_name in ("first-dir", "second-dir"):
            (workspace / member_name / c.PYPROJECT_FILENAME).write_text(
                '[project]\nname = "shared-name"\nversion = "0.1.0"\n', encoding="utf-8"
            )

        ambiguous = FlextInfraPyprojectModernizer(
            repository_root=workspace,
            selected_projects=["shared-name"],
            apply_changes=False,
            skip_check=True,
            skip_comments=True,
        )
        exact = FlextInfraPyprojectModernizer(
            repository_root=workspace,
            selected_projects=["first-dir"],
            apply_changes=False,
            skip_check=True,
            skip_comments=True,
        )

        tm.that(ambiguous.run(), eq=2)
        tm.that(exact.run(), eq=0)

    @pytest.mark.parametrize("member_kind", ["absolute", "parent-relative", "symlink"])
    def test_modernizer_rejects_configured_members_outside_workspace(
        self, modernizer_workspace: Path, member_kind: str
    ) -> None:
        """Reject configured members resolving outside root without mutation."""
        external_project = modernizer_workspace.parent / "external"
        external_project.mkdir()
        external_pyproject = external_project / c.PYPROJECT_FILENAME
        original = '[project]\nname = "external"\nversion = "0.1.0"\n'
        external_pyproject.write_text(original, encoding="utf-8")
        if member_kind == "absolute":
            selector = str(external_project)
        elif member_kind == "parent-relative":
            selector = "../external"
        else:
            selector = "linked-external"
            (modernizer_workspace / selector).symlink_to(
                external_project, target_is_directory=True
            )
        (modernizer_workspace / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "workspace"\nversion = "0.1.0"\n'
            f'\n[tool.uv.workspace]\nmembers = ["{selector}"]\n',
            encoding="utf-8",
        )

        TestsFlextInfraDepsModernizerWorkspace._reject_external_selector(
            modernizer_workspace, selector, external_pyproject, original
        )

    @pytest.mark.parametrize("selector_kind", ["absolute", "parent-relative"])
    def test_modernizer_rejects_undeclared_project_paths(
        self, modernizer_workspace: Path, selector_kind: str
    ) -> None:
        """Reject selectors outside declared workspace projects without mutation."""
        external_project = modernizer_workspace.parent / "external"
        external_project.mkdir()
        external_pyproject = external_project / c.PYPROJECT_FILENAME
        original = '[project]\nname = "external"\nversion = "0.1.0"\n'
        external_pyproject.write_text(original, encoding="utf-8")
        selector = (
            str(external_project) if selector_kind == "absolute" else "../external"
        )

        TestsFlextInfraDepsModernizerWorkspace._reject_external_selector(
            modernizer_workspace, selector, external_pyproject, original
        )
