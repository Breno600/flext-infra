"""Tests for scanner helper methods.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import u as infra_u
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraScannerHelpers:
    """Tests for scanner helper methods."""

    def test_iter_matching_files_glob_patterns(self, tmp_path: Path) -> None:
        """Canonical file selection respects include/exclude glob patterns."""
        u.Tests.git_bootstrap(tmp_path, ("init",))
        (tmp_path / "file1.py").write_text("")
        (tmp_path / "file2.txt").write_text("")
        (tmp_path / "file3.py").write_text("")
        (tmp_path / "test.py").write_text("")
        included = u.Infra.iter_matching_files(tmp_path, includes=["*.py"])
        tm.that(len(included), eq=3)
        excluded = u.Infra.iter_matching_files(
            tmp_path, includes=["*.py"], excludes=["test*"]
        )
        tm.that(len(excluded), eq=2)

    def test_iter_matching_files_skips_directories(self, tmp_path: Path) -> None:
        """Canonical file selection skips directories."""
        u.Tests.git_bootstrap(tmp_path, ("init",))
        (tmp_path / "file.txt").write_text("")
        (tmp_path / "subdir").mkdir()
        files = u.Infra.iter_matching_files(tmp_path, includes=["*"])
        tm.that(len(files), eq=1)

    def test_iter_matching_files_prefers_git_tracked_files(
        self, tmp_path: Path
    ) -> None:
        """Canonical file selection prefers tracked files when Git is active."""
        u.Tests.git_bootstrap(tmp_path, ("init",))
        u.Tests.configure_git_identity(tmp_path)
        tracked_file = tmp_path / "tracked.py"
        tracked_file.write_text("")
        untracked_file = tmp_path / "untracked.py"
        untracked_file.write_text("")
        add_result = u.Cli.run_raw(["git", "add", "tracked.py"], cwd=tmp_path)
        tm.ok(add_result)
        tm.that(u.Cli.process_succeeded(add_result.value.outcome), eq=True)

        files = u.Infra.iter_matching_files(tmp_path, includes=["*.py"])

        tm.that(files, eq=[tracked_file, untracked_file])

    def test_iter_matching_files_excludes_git_ignored_explicit_scope(
        self, tmp_path: Path
    ) -> None:
        """An ignored nested scope cannot bypass its ancestor repository policy."""
        init_result = u.Cli.run_raw(["git", "init"], cwd=tmp_path)
        tm.ok(init_result)
        tm.that(u.Cli.process_succeeded(init_result.value.outcome), eq=True)
        (tmp_path / ".gitignore").write_text("scratch/\n", encoding="utf-8")
        scope = tmp_path / "scratch" / "project"
        scope.mkdir(parents=True)
        explicit_file = scope / "README.md"
        explicit_file.write_text("# explicit scope\n", encoding="utf-8")

        files = u.Infra.iter_matching_files(scope, includes=["*.md"])

        tm.that(files, eq=[])

    def test_tracked_scope_refreshes_dirty_files_between_scans(
        self, tmp_path: Path
    ) -> None:
        """A long-running pipeline observes files created after its first scan."""
        init_result = u.Cli.run_raw(["git", "init"], cwd=tmp_path)
        tm.ok(init_result)
        tm.that(u.Cli.process_succeeded(init_result.value.outcome), eq=True)
        source = tmp_path / "src"
        source.mkdir()
        first = source / "first.py"
        first.write_text("", encoding="utf-8")
        tm.that(infra_u.Infra.git_tracked_scope_paths(source), eq=[first])

        second = source / "second.py"
        second.write_text("", encoding="utf-8")

        tm.that(infra_u.Infra.git_tracked_scope_paths(source), eq=[first, second])

    def test_tracked_scope_refreshes_repository_identity_after_git_init(
        self, tmp_path: Path
    ) -> None:
        """A process observes repository identity created after its first scan."""
        source = tmp_path / "src"
        source.mkdir()
        unmanaged = source / "unmanaged.py"
        unmanaged.write_text("", encoding="utf-8")
        tm.that(infra_u.Infra.git_tracked_scope_paths(source), eq=None)

        init_result = u.Cli.run_raw(["git", "init"], cwd=tmp_path)
        tm.ok(init_result)
        tm.that(u.Cli.process_succeeded(init_result.value.outcome), eq=True)

        tm.that(infra_u.Infra.git_tracked_scope_paths(source), eq=[unmanaged])

    def test_empty_git_scope_does_not_fall_back_to_filesystem_scan(
        self, tmp_path: Path
    ) -> None:
        """A valid empty Git scope stays distinct from an external scope."""
        init_result = u.Cli.run_raw(["git", "init"], cwd=tmp_path)
        tm.ok(init_result)
        tm.that(u.Cli.process_succeeded(init_result.value.outcome), eq=True)
        scope = tmp_path / "empty"
        scope.mkdir()

        tm.that(infra_u.Infra.git_tracked_scope_paths(scope), eq=[])
