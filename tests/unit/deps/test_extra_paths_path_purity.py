"""Generated search paths never leave the project that owns them.

A search-path entry is written into a project's own ``pyproject.toml``, so it
describes that project forever. ``../<sibling>/src`` describes the *host* the
generator happened to run on: it is wrong in any clone whose siblings sit
elsewhere, it is absent in a worktree that materializes one project alone, and
it makes the same generator emit different content per checkout. Cross-checkout
dependencies resolve through their installed distributions instead (mro-c6di).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm
from tests.unit.deps._extra_paths_support import ExtraPathsTestSupport

if TYPE_CHECKING:
    from pathlib import Path


def _project(root: Path, name: str, package: str) -> Path:
    """Materialize one importable project with a declared distribution name."""
    project = root / name
    (project / "src" / package).mkdir(parents=True)
    (project / "src" / package / "__init__.py").write_text("", encoding="utf-8")
    (project / ".git").mkdir()
    (project / "Makefile").write_text("", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        f"[project]\nname = '{name}'\n", encoding="utf-8"
    )
    return project


class TestsFlextInfraExtraPathsArePure:
    """No emitted entry may address another project on the filesystem."""

    def test_workspace_member_source_roots_are_not_emitted_at_the_root(
        self, tmp_path: Path
    ) -> None:
        """A uv workspace member is a distribution, not a search path."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "pyproject.toml").write_text(
            (
                "[project]\n"
                "name = 'flext'\n"
                "dependencies = ['flext-core']\n"
                "[tool.uv.workspace]\n"
                "members = ['flext-core']\n"
            ),
            encoding="utf-8",
        )
        _ = _project(tmp_path, "flext-core", "flext_core")

        manager = ExtraPathsTestSupport.manager(tmp_path)
        result = manager.pyrefly_search_paths(project_dir=tmp_path, is_root=True)

        tm.that(result, eq=("src", "."))

    def test_sibling_source_roots_are_not_emitted_for_a_member(
        self, tmp_path: Path
    ) -> None:
        """A member never reaches out of its own root to find a dependency."""
        consumer = _project(tmp_path, "flext-ldap", "flext_ldap")
        consumer.joinpath("pyproject.toml").write_text(
            (
                "[project]\n"
                "name = 'flext-ldap'\n"
                "dependencies = ['flext-core']\n"
                "[tool.uv.sources]\n"
                "flext-core = { path = '../flext-core', editable = true }\n"
            ),
            encoding="utf-8",
        )
        _ = _project(tmp_path, "flext-core", "flext_core")

        manager = ExtraPathsTestSupport.manager(tmp_path)
        search_paths = manager.pyrefly_search_paths(project_dir=consumer, is_root=False)
        extra_paths = manager.pyright_extra_paths(project_dir=consumer, is_root=False)

        for entry in (*search_paths, *extra_paths):
            assert not entry.startswith(".."), (
                f"generated search path leaves the project: {entry}"
            )
        tm.that(search_paths, eq=("src", "."))

    def test_search_paths_survive_a_project_only_worktree(self, tmp_path: Path) -> None:
        """The same project alone on disk yields the same entries.

        A `make work` lane materializes one project without its siblings. Entries
        derived from sibling existence differ there, so `make gen` in the lane
        would rewrite what the primary just generated.
        """
        with_siblings = _project(tmp_path / "workspace", "flext-ldap", "flext_ldap")
        _ = _project(tmp_path / "workspace", "flext-core", "flext_core")
        alone = _project(tmp_path / "lane", "flext-ldap", "flext_ldap")

        workspace_manager = ExtraPathsTestSupport.manager(tmp_path / "workspace")
        lane_manager = ExtraPathsTestSupport.manager(tmp_path / "lane")

        tm.that(
            workspace_manager.pyrefly_search_paths(
                project_dir=with_siblings, is_root=False
            ),
            eq=lane_manager.pyrefly_search_paths(project_dir=alone, is_root=False),
        )


__all__: tuple[str, ...] = ()
