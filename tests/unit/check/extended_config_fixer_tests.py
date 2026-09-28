"""Tests for FlextInfraConfigFixer — process_file, run, find, fix methods.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import config
from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
from flext_infra.deps.fix_pyrefly_config import FlextInfraConfigFixer
from tests import t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraExtendedConfigFixer:
    @staticmethod
    def _extra_paths_manager(repository_root: Path) -> FlextInfraExtraPathsManager:
        return FlextInfraExtraPathsManager(repository_root=repository_root)

    class TestConfigFixerProcessFile:
        """Test FlextInfraConfigFixer.process_file."""

        def test_process_file_missing_file(self, tmp_path: Path) -> None:
            """Return a typed failure when the pyproject is missing."""
            fixer = FlextInfraConfigFixer(repository_root=tmp_path)
            tm.fail(fixer.process_file(tmp_path / "missing.toml"), has="not found")

        def test_process_file_invalid_toml(self, tmp_path: Path) -> None:
            """Return a typed failure for invalid TOML input."""
            fixer = FlextInfraConfigFixer(repository_root=tmp_path)
            pyproject = tmp_path / "pyproject.toml"
            pyproject.write_text("invalid [[[")
            tm.fail(fixer.process_file(pyproject), has="TOML parse failed")

        def test_process_file_no_pyrefly_section(self, tmp_path: Path) -> None:
            """Leave documents without a Pyrefly table unchanged."""
            fixer = FlextInfraConfigFixer(repository_root=tmp_path)
            pyproject = tmp_path / "pyproject.toml"
            pyproject.write_text("[tool]\nother = true\n")
            result = fixer.process_file(pyproject)
            tm.ok(result)
            tm.that(result.value, empty=True)

        def test_process_file_dry_run_no_write(self, tmp_path: Path) -> None:
            """Keep the source file unchanged during dry-run."""
            fixer = FlextInfraConfigFixer(repository_root=tmp_path)
            pyproject = tmp_path / "pyproject.toml"
            original = "[tool.pyrefly]\nsearch-path = []\n"
            pyproject.write_text(original)
            result = fixer.process_file(pyproject, dry_run=True)
            tm.ok(result)
            tm.that(pyproject.read_text(), eq=original)

        def test_process_file_syncs_search_path_from_public_manager(
            self, tmp_path: Path
        ) -> None:
            """Synchronize search paths through the public manager."""
            (tmp_path / "typings" / "generated").mkdir(parents=True)
            pyproject = tmp_path / "pyproject.toml"
            pyproject.write_text("[tool.pyrefly]\nsearch-path = []\n", encoding="utf-8")

            result = FlextInfraConfigFixer(repository_root=tmp_path).process_file(
                pyproject
            )

            tm.ok(result)
            tm.that(result.value, has="synchronized search-path from YAML rules")
            pyrefly = u.Tests.toml_table_at(
                pyproject.read_text(encoding="utf-8"), "tool", "pyrefly"
            )
            tm.that(
                pyrefly["search-path"],
                eq=TestsFlextInfraExtendedConfigFixer._extra_paths_manager(
                    tmp_path
                ).pyrefly_search_paths(project_dir=tmp_path, is_root=True),
            )

        def test_process_file_keeps_all_existing_tracked_project_includes(
            self, tmp_path: Path
        ) -> None:
            """Keep every existing tracked Python root in project includes."""
            u.Tests.write_project_beads_config(tmp_path, "tmp")
            (tmp_path / "src").mkdir()
            (tmp_path / "src" / "package.py").write_text(
                "VALUE = 1\n", encoding="utf-8"
            )
            (tmp_path / "tests").mkdir()
            (tmp_path / "tests" / "test_package.py").write_text(
                "def test_package() -> None:\n    pass\n", encoding="utf-8"
            )
            pyproject = tmp_path / "pyproject.toml"
            pyproject.write_text(
                (
                    "[tool.pyright]\n"
                    "include = ['src']\n\n"
                    "[tool.pyrefly]\n"
                    "search-path = ['src']\n"
                    "project-includes = ['src/**/*.py*', 'tests/**/*.py*']\n"
                ),
                encoding="utf-8",
            )

            result = FlextInfraConfigFixer(repository_root=tmp_path).process_file(
                pyproject
            )

            tm.ok(result)
            tm.that(result.value, lacks="synchronized project-includes from YAML rules")
            pyrefly = u.Tests.toml_table_at(
                pyproject.read_text(encoding="utf-8"), "tool", "pyrefly"
            )
            tm.that(pyrefly["project-includes"], eq=["src/**/*.py*", "tests/**/*.py*"])

        def test_process_file_preserves_unrelated_toml_comments_and_formatting(
            self, tmp_path: Path
        ) -> None:
            """Preserve unrelated TOML trivia while changing Pyrefly keys."""
            pyproject = tmp_path / "pyproject.toml"
            pyproject.write_text(
                (
                    "[project]\n"
                    "name = 'sample'\n"
                    "# keep dependency context\n"
                    "dependencies = [\n"
                    "    # keep dependency item comment\n"
                    "    'flext-core',\n"
                    "]\n\n"
                    "[tool.ruff]\n"
                    "line-length = 120\n\n"
                    "[tool.pyrefly]\n"
                    "search-path = []\n"
                    "project-excludes = []\n\n"
                    "[tool.pyrefly.errors]\n"
                    'bad-return = "error"\n\n'
                    "# [MANAGED] pyright\n"
                    "[tool.pyright]\n"
                    "include = ['src']\n"
                ),
                encoding="utf-8",
            )

            result = FlextInfraConfigFixer(repository_root=tmp_path).process_file(
                pyproject
            )

            tm.ok(result)
            updated = pyproject.read_text(encoding="utf-8")
            tm.that(updated, contains="# keep dependency context")
            tm.that(updated, contains="# keep dependency item comment")
            tm.that(updated, contains="line-length = 120")
            tm.that(updated, contains="# [MANAGED] pyright")
            tm.that(result.value, has="synchronized search-path from YAML rules")

        def test_process_file_removes_ignored_sub_configs_via_public_api(
            self, tmp_path: Path
        ) -> None:
            """Remove ignored Pyrefly sub-configurations through the public API."""
            pyproject = tmp_path / "pyproject.toml"
            pyproject.write_text(
                (
                    "[tool.pyrefly]\n"
                    'search-path = ["src"]\n'
                    "sub-settings = [\n"
                    '  { matches = "*.py", ignore = true },\n'
                    '  { matches = "*.pyi", ignore = false },\n'
                    "]\n"
                ),
                encoding="utf-8",
            )

            result = FlextInfraConfigFixer(repository_root=tmp_path).process_file(
                pyproject
            )

            tm.ok(result)
            tm.that(result.value, has="removed ignore=true sub-settings for '*.py'")
            pyrefly = u.Tests.toml_table_at(
                pyproject.read_text(encoding="utf-8"), "tool", "pyrefly"
            )
            expected_sub_settings: t.JsonList = [{"matches": "*.pyi", "ignore": False}]
            tm.that(pyrefly["sub-settings"], eq=expected_sub_settings)

        def test_process_file_syncs_root_project_excludes_via_public_api(
            self, tmp_path: Path
        ) -> None:
            """Synchronize root exclusions from the validated config singleton."""
            pyproject = tmp_path / "pyproject.toml"
            pyproject.write_text(
                ('[tool.pyrefly]\nsearch-path = ["src"]\nproject-excludes = []\n'),
                encoding="utf-8",
            )

            fixer = FlextInfraConfigFixer(repository_root=tmp_path)
            result = fixer.process_file(pyproject)

            tm.ok(result)
            tm.that(result.value, has="synchronized project-excludes from YAML rules")
            pyrefly = u.Tests.toml_table_at(
                pyproject.read_text(encoding="utf-8"), "tool", "pyrefly"
            )
            tm.that(
                pyrefly["project-excludes"],
                eq=sorted(
                    set(config.Infra.tooling.tools.pyrefly.project_exclude_globs)
                ),
            )

    class TestConfigFixerRun:
        """Test FlextInfraConfigFixer.run."""

        def test_run_with_empty_projects(self, tmp_path: Path) -> None:
            """Accept an empty project selection."""
            fixer = FlextInfraConfigFixer(repository_root=tmp_path)
            result = fixer.run([])
            tm.ok(result)
            tm.that(len(result.value), gte=0)

        def test_run_with_nonexistent_projects(self, tmp_path: Path) -> None:
            """Fail closed when an explicit project selection is inaccessible."""
            u.Tests.reject_inaccessible_config_project(tmp_path)

        def test_run_with_dry_run_flag(self, tmp_path: Path) -> None:
            """Execute the workspace runner in dry-run mode."""
            fixer = FlextInfraConfigFixer(repository_root=tmp_path)
            tm.ok(fixer.run([], dry_run=True))

        def test_run_with_verbose_flag(self, tmp_path: Path) -> None:
            """Execute the workspace runner with verbose reporting."""
            fixer = FlextInfraConfigFixer(repository_root=tmp_path)
            tm.ok(fixer.run([], verbose=True))

    class TestConfigFixerExecute:
        """Test FlextInfraConfigFixer.execute method."""

        def test_execute_returns_failure(self, tmp_path: Path) -> None:
            """Require the typed command entry point for execution."""
            fixer = FlextInfraConfigFixer(repository_root=tmp_path)
            tm.fail(fixer.execute(), has="Use execute_command() directly")

    class TestConfigFixerToArray:
        """Test u.Cli.toml_array."""

        def test_to_array_creates_array(self) -> None:
            """Create a TOML array from typed string items."""
            items = ["a", "b", "c"]
            arr = u.Cli.toml_array(items)
            tm.that(len(arr), eq=3)
            tm.that(list(arr), has="a")
