"""Workspace composition read only from the committed ``.gitmodules``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import c, t, u


class TestsFlextInfraGitSubmoduleComposition:
    """One ``.gitmodules`` owner, its recorded gitlinks and its back edges."""

    @staticmethod
    def _member(
        root: Path,
        name: str,
        runtime: t.StrSequence,
        groups: t.StrSequence,
    ) -> Path:
        """Create one committed member repository declaring its own deps.

        Returns:
            The member repository root.

        """
        member = root / name
        member.mkdir(parents=True)
        u.Tests.initialize_git_repo(member)
        quoted_runtime = ", ".join(f'"{item}"' for item in runtime)
        quoted_groups = ", ".join(f'"{item}"' for item in groups)
        (member / c.PYPROJECT_FILENAME).write_text(
            f'[project]\nname = "{name}"\ndependencies = [{quoted_runtime}]\n\n'
            f"[dependency-groups]\ndev = [{quoted_groups}]\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        u.Tests.commit_git_changes(member, f"declare {name}")
        return member

    @classmethod
    def _workspace(
        cls,
        tmp_path: Path,
        graph: t.MappingKV[str, t.Pair[t.StrSequence, t.StrSequence]],
    ) -> Path:
        """Compose a real superproject whose submodules declare ``graph``.

        Returns:
            The superproject root with every gitlink committed.

        """
        parent = tmp_path / "workspace"
        parent.mkdir()
        u.Tests.initialize_git_repo(parent)
        for name, (runtime, groups) in graph.items():
            member = cls._member(tmp_path / "origins", name, runtime, groups)
            u.Tests.git_run(
                parent,
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                "--quiet",
                "-b",
                c.Infra.GIT_MAIN,
                str(member),
                name,
            )
            u.Tests.git_run(
                parent,
                "config",
                "--file",
                c.Infra.GITMODULES,
                f"submodule.{name}.url",
                f"https://example.test/fleet/{name}.git",
            )
        u.Tests.commit_git_changes(parent, "compose members")
        return parent

    def test_declarations_carry_path_url_branch_and_managed_flag(
        self,
        tmp_path: Path,
    ) -> None:
        """Every section is parsed once, with the opt-out flag kept typed."""
        parent = self._workspace(tmp_path, {"alpha": ((), ()), "beta": ((), ())})
        u.Tests.git_run(
            parent,
            "config",
            "--file",
            c.Infra.GITMODULES,
            f"submodule.beta.{c.Infra.GITMODULE_MANAGED_KEY}",
            "false",
        )
        declared = tm.ok(u.Infra.git_submodule_declarations(parent))
        tm.that([item.path for item in declared], eq=[Path("alpha"), Path("beta")])
        tm.that(
            [item.url for item in declared],
            eq=[
                "https://example.test/fleet/alpha.git",
                "https://example.test/fleet/beta.git",
            ],
        )
        tm.that({item.branch for item in declared}, eq={c.Infra.GIT_MAIN})
        tm.that([item.managed for item in declared], eq=[None, False])

    def test_repository_without_gitmodules_declares_no_members(
        self,
        tmp_path: Path,
    ) -> None:
        """A standalone repository composes nothing."""
        standalone = tmp_path / "standalone"
        standalone.mkdir()
        u.Tests.initialize_git_repo(standalone)
        tm.that(tm.ok(u.Infra.git_submodule_declarations(standalone)), eq=())

    def test_malformed_gitmodules_fails_closed(self, tmp_path: Path) -> None:
        """Git's own parser rejects the file and the owner propagates it."""
        root = tmp_path / "broken"
        root.mkdir()
        u.Tests.initialize_git_repo(root)
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "alpha"\n\tpath = alpha\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.fail(
            u.Infra.git_submodule_declarations(root),
            has="failed to read Git submodule declarations",
        )

    def test_duplicated_path_fails_closed(self, tmp_path: Path) -> None:
        """Two sections claiming one path are a declaration defect."""
        root = tmp_path / "duplicated"
        root.mkdir()
        u.Tests.initialize_git_repo(root)
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "alpha"]\n\tpath = shared\n'
            '[submodule "beta"]\n\tpath = shared\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.fail(
            u.Infra.git_submodule_declarations(root),
            has="duplicate Git submodule path",
        )

    def test_recorded_sources_follow_the_committed_gitlink_only(
        self,
        tmp_path: Path,
    ) -> None:
        """A staged but uncommitted gitlink move is not a recorded position."""
        parent = self._workspace(tmp_path, {"alpha": ((), ())})
        committed = u.Tests.git_capture(parent, "rev-parse", "HEAD:alpha")
        member = parent / "alpha"
        (member / "CHANGELOG.md").write_text(
            "moved\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        u.Tests.commit_git_changes(member, "advance member")
        u.Tests.git_run(parent, "add", "alpha")
        staged = u.Tests.git_capture(parent, "rev-parse", ":alpha")
        tm.that(staged != committed, eq=True)
        sources = tm.ok(u.Infra.recorded_member_sources(parent))
        tm.that(
            [(source.distribution, source.url, source.commit) for source in sources],
            eq=[("alpha", "https://example.test/fleet/alpha.git", committed)],
        )

    def test_back_edges_are_derived_from_member_pyprojects(
        self,
        tmp_path: Path,
    ) -> None:
        """Group edges into a dependent's runtime closure are the back edges."""
        parent = self._workspace(
            tmp_path,
            {
                "alpha": ((), ("gamma",)),
                "beta": (("alpha",), ("gamma",)),
                "gamma": (("beta",), ("alpha",)),
            },
        )
        edges = tm.ok(u.Infra.flext_back_edges(parent))
        tm.that(
            [(edge.dependent, edge.dependency) for edge in edges],
            eq=[("alpha", "gamma"), ("beta", "gamma")],
        )

    def test_runtime_cycle_without_back_edge_fails_loudly(
        self,
        tmp_path: Path,
    ) -> None:
        """A cycle no group edge closes cannot be ordered and is RED."""
        parent = self._workspace(
            tmp_path,
            {"alpha": (("beta",), ()), "beta": (("alpha",), ())},
        )
        tm.fail(
            u.Infra.flext_back_edges(parent),
            has="workspace dependency cycle is not broken by a back edge: alpha, beta",
        )
