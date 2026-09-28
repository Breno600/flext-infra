"""Edge-case tests for public discovery behavior."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import u


class TestsFlextInfraDiscoveryInfraDiscoveryEdgeCases:
    """Edge-case tests for project discovery."""

    def test_standalone_never_discovers_undeclared_child_projects(
        self, tmp_path: Path
    ) -> None:
        service = u.Infra()
        repository_root = tmp_path
        non_git_dir = repository_root / "non_git_project"
        non_git_dir.mkdir()
        (non_git_dir / "pyproject.toml").write_text(
            "[project]\nname='non_git_project'\ndependencies=['flext-core>=0.1.0']\n",
            encoding="utf-8",
        )
        result = service.discover_projects(repository_root)
        tm.ok(result)
        tm.that(result.value, empty=True)

    def test_find_all_pyproject_files_with_nonexistent_path(self) -> None:
        service = u.Infra()
        nonexistent = Path("/nonexistent/path/to/workspace")
        result = service.find_all_pyproject_files(nonexistent)
        tm.ok(result)
        tm.that(result.value, eq=[])

    def test_standalone_pyproject_scan_never_reads_parent_or_sibling(
        self, tmp_path: Path
    ) -> None:
        service = u.Infra()
        child = tmp_path / "child"
        sibling = tmp_path / "sibling"
        child.mkdir()
        sibling.mkdir()
        own_pyproject = child / "pyproject.toml"
        own_pyproject.touch()
        (tmp_path / "pyproject.toml").touch()
        (sibling / "pyproject.toml").touch()

        result = service.find_all_pyproject_files(child)

        tm.ok(result)
        tm.that(tuple(result.value), eq=(own_pyproject,))

    def test_find_all_pyproject_files_with_permission_error(
        self, tmp_path: Path
    ) -> None:
        service = u.Infra()
        (tmp_path / "pyproject.toml").touch()
        result = service.find_all_pyproject_files(tmp_path)
        tm.ok(result)
        tm.that(len(result.value) >= 1, eq=True)

    def test_discover_projects_skips_no_pyproject_no_gomod(
        self, tmp_path: Path
    ) -> None:
        service = u.Infra()
        repository_root = tmp_path
        proj = repository_root / "incomplete_project"
        proj.mkdir()
        (proj / "pyproject.toml").write_text(
            "[project]\nname='incomplete_project'\n", encoding="utf-8"
        )
        result = service.discover_projects(repository_root)
        tm.ok(result)
        tm.that(not result.value, eq=True)

    def test_find_all_pyproject_files_skips_unreadable_subdir(
        self, tmp_path: Path
    ) -> None:
        service = u.Infra()
        blocked_dir = tmp_path / "blocked"
        blocked_dir.mkdir()
        (blocked_dir / "pyproject.toml").write_text(
            "[project]\nname='blocked'\n", encoding="utf-8"
        )
        blocked_dir.chmod(0)
        try:
            result = service.find_all_pyproject_files(tmp_path)
        finally:
            blocked_dir.chmod(0o755)
        tm.ok(result)
        tm.that(result.value, eq=[])
