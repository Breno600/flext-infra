"""Deps modernize honors the ``.gitmodules`` governance opt-out."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDepsModernizerUnmanagedSubmodules:
    """Modernize governed members only; an opted-out submodule is no project."""

    @staticmethod
    def _workspace(modernizer_workspace: Path, *, managed_has_pyproject: bool) -> Path:
        """Declare one governed member and one ``flext-managed = false`` checkout."""
        member = modernizer_workspace / "member"
        member.mkdir()
        if managed_has_pyproject:
            (member / c.PYPROJECT_FILENAME).write_text(
                '[project]\nname = "member"\nversion = "0.1.0"\n', encoding="utf-8",
            )
            u.Tests.write_beads_project(
                member, workspace="workspace", database="member", issue_prefix="member",
            )
        vendored = modernizer_workspace / "vendored"
        vendored.mkdir()
        (vendored / "README.md").write_text(
            "# Not a Python project\n", encoding="utf-8",
        )
        (modernizer_workspace / c.Infra.GITMODULES).write_text(
            '[submodule "member"]\n\tpath = member\n'
            "\turl = https://github.com/flext-sh/member.git\n"
            '[submodule "vendored"]\n\tpath = vendored\n'
            "\turl = https://github.com/example/vendored.git\n"
            f"\t{c.Infra.GITMODULE_MANAGED_KEY} = false\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(modernizer_workspace)
        return modernizer_workspace

    @staticmethod
    def _modernize(workspace: Path) -> int:
        return main([
            "deps",
            "modernize",
            "--repository-root",
            str(workspace),
            "--apply",
            "--skip-check",
            "--projects",
            "member",
        ])

    def test_modernize_skips_opted_out_submodule(
        self, modernizer_workspace: Path,
    ) -> None:
        """Modernize the governed member and leave the opted-out checkout alone."""
        workspace = self._workspace(modernizer_workspace, managed_has_pyproject=True)

        tm.that(self._modernize(workspace), eq=0)
        tm.that(
            (workspace / "member" / c.PYPROJECT_FILENAME).read_text(encoding="utf-8"),
            has='build-backend = "hatchling.build"',
        )
        tm.that((workspace / "vendored" / c.PYPROJECT_FILENAME).exists(), eq=False)

    def test_modernize_fails_for_governed_member_without_pyproject(
        self, modernizer_workspace: Path,
    ) -> None:
        """A governed member whose pyproject is missing still fails loud.

        The public CLI maps every failed modernization service to exit 1.
        """
        workspace = self._workspace(modernizer_workspace, managed_has_pyproject=False)

        tm.that(self._modernize(workspace), eq=1)
