"""Topological publish ordering behavior for the release orchestrator.

Publishing to an index is immutable, so a dependent uploaded before its
dependency leaves the index in a state no rollback can repair. The order is
derived from each project's declared dependencies -- never from a hand-written
list that silently diverges from the manifests it claims to describe.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraReleaseDependencyOrder:
    """Behavior contract for wave computation over declared dependencies."""

    def _write_project(
        self, root: Path, name: str, dependencies: t.VariadicTuple[str]
    ) -> None:
        """Materialize one project whose pyproject declares the given dependencies."""
        project = root / name
        project.mkdir(parents=True, exist_ok=True)
        rendered = ", ".join(f'"{dependency}"' for dependency in dependencies)
        (project / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\ndependencies = [{rendered}]\n',
            encoding="utf-8",
        )

    def test_dependency_precedes_dependent(self, tmp_path: Path) -> None:
        """Place a dependency in an earlier wave than everything requiring it."""
        self._write_project(tmp_path, "flext-core", ())
        self._write_project(tmp_path, "flext-cli", ("flext-core>=0.1.0",))
        self._write_project(tmp_path, "flext-ldap", ("flext-cli>=0.1.0",))

        waves = tm.ok(
            u.Infra.release_publish_waves((
                ("flext-core", tmp_path / "flext-core"),
                ("flext-cli", tmp_path / "flext-cli"),
                ("flext-ldap", tmp_path / "flext-ldap"),
            ))
        )

        flattened = [name for wave in waves for name in wave]
        tm.that(flattened.index("flext-core") < flattened.index("flext-cli"), eq=True)
        tm.that(flattened.index("flext-cli") < flattened.index("flext-ldap"), eq=True)

    def test_project_without_internal_dependency_lands_in_first_wave(
        self, tmp_path: Path
    ) -> None:
        """Schedule a project with no internal dependency in the first wave."""
        self._write_project(tmp_path, "flext-core", ())
        self._write_project(tmp_path, "flext-meltano", ("singer-sdk>=0.40.0",))
        self._write_project(tmp_path, "flext-cli", ("flext-core>=0.1.0",))

        waves = tm.ok(
            u.Infra.release_publish_waves((
                ("flext-core", tmp_path / "flext-core"),
                ("flext-meltano", tmp_path / "flext-meltano"),
                ("flext-cli", tmp_path / "flext-cli"),
            ))
        )

        tm.that("flext-meltano" in waves[0], eq=True)
        tm.that("flext-core" in waves[0], eq=True)

    def test_every_selected_project_appears_exactly_once(self, tmp_path: Path) -> None:
        """Emit each selected project once so no upload is skipped or repeated."""
        self._write_project(tmp_path, "flext-core", ())
        self._write_project(tmp_path, "flext-cli", ("flext-core>=0.1.0",))
        self._write_project(tmp_path, "flext-web", ("flext-core>=0.1.0",))

        waves = tm.ok(
            u.Infra.release_publish_waves((
                ("flext-core", tmp_path / "flext-core"),
                ("flext-cli", tmp_path / "flext-cli"),
                ("flext-web", tmp_path / "flext-web"),
            ))
        )

        flattened = [name for wave in waves for name in wave]
        tm.that(len(flattened), eq=3)
        tm.that(len(set(flattened)), eq=3)

    def test_cycle_fails_naming_its_members(self, tmp_path: Path) -> None:
        """Reject a cyclic graph and name the projects that cannot be ordered."""
        self._write_project(tmp_path, "flext-alpha", ("flext-beta>=0.1.0",))
        self._write_project(tmp_path, "flext-beta", ("flext-alpha>=0.1.0",))

        result = u.Infra.release_publish_waves((
            ("flext-alpha", tmp_path / "flext-alpha"),
            ("flext-beta", tmp_path / "flext-beta"),
        ))

        tm.that(result.failure, eq=True)
        tm.that(result.error or "", has="flext-alpha")
        tm.that(result.error or "", has="flext-beta")

    def test_dependency_outside_the_selection_is_not_an_edge(
        self, tmp_path: Path
    ) -> None:
        """Ignore an internal dependency that the release does not publish.

        A project depending on an unselected package is orderable: the
        missing package is already on the index or out of scope, so
        treating it as an edge would deadlock the whole graph.
        """
        self._write_project(tmp_path, "flext-web", ("flext-absent>=0.1.0",))

        waves = tm.ok(
            u.Infra.release_publish_waves((("flext-web", tmp_path / "flext-web"),))
        )

        tm.that(waves[0], eq=("flext-web",))
