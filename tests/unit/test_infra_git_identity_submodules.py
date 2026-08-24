"""Submodule facts reported by the canonical Git identity probe.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
from pathlib import Path

from flext_infra import m, u
from flext_tests import tm
from tests import u as test_u


class TestInfraGitIdentitySubmodules:
    """Report a superproject from the index, never from ``status --porcelain``.

    Gitlink modes (``160000``) appear only in the index listing. ``git status
    --porcelain`` emits XY status codes and paths and never a file mode, so
    deriving submodule facts from it silently reported every superproject as
    having no submodules.
    """

    @staticmethod
    def _repo(root: Path) -> Path:
        """Initialize one real Git repository carrying a single commit."""
        root.mkdir(parents=True, exist_ok=True)
        test_u.Tests.initialize_git_repo(root)
        return root

    @classmethod
    def _superproject(cls, tmp_path: Path) -> Path:
        """Build a real superproject whose index carries a gitlink entry."""
        child = cls._repo(tmp_path / "child")
        parent = cls._repo(tmp_path / "parent")
        tm.ok(
            u.Cli.run_checked([
                "git",
                "-C",
                str(parent),
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                "--quiet",
                str(child),
                "vendored",
            ])
        )
        tm.ok(
            u.Cli.run_checked([
                "git",
                "-C",
                str(parent),
                "commit",
                "--quiet",
                "-m",
                "add submodule",
            ])
        )
        return parent

    def test_superproject_reports_its_submodules(self, tmp_path: Path) -> None:
        """A repository holding a gitlink is recognized as a superproject."""
        parent = self._superproject(tmp_path)
        identity = tm.ok(u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=parent)))
        tm.that(identity.has_submodules, eq=True)

    def test_plain_repository_reports_no_submodules(self, tmp_path: Path) -> None:
        """A repository without any gitlink reports no submodules."""
        plain = self._repo(tmp_path / "plain")
        identity = tm.ok(u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=plain)))
        tm.that(identity.has_submodules, eq=False)

    def test_submodule_checkout_is_not_a_superproject(self, tmp_path: Path) -> None:
        """The nested checkout is a submodule, and owns none of its own."""
        parent = self._superproject(tmp_path)
        identity = tm.ok(
            u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=parent / "vendored"))
        )
        tm.that(identity.has_submodules, eq=False)
        tm.that(identity.is_submodule, eq=True)

    def test_absorbed_submodule_with_git_dir_is_still_a_submodule(
        self, tmp_path: Path
    ) -> None:
        """Nested checkout with a real .git directory still reports is_submodule.

        Why (flext-infra-c3h): operator trees like cosmos-charts under cosmos-main
        keep a full .git directory (not a gitfile) while the superproject index
        holds a gitlink. Git still reports --show-superproject-working-tree;
        ``git_identity.is_submodule`` must follow that signal.
        """
        child = self._repo(tmp_path / "child")
        parent = self._repo(tmp_path / "parent")
        member = parent / "apps" / "member"
        shutil.copytree(child, member)
        (parent / ".gitmodules").write_text(
            f"[submodule 'member']\n\tpath = apps/member\n\turl = {child.as_uri()}\n",
            encoding="utf-8",
        )
        head = (member / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(" ", 1)[1].strip()
            oid = (member / ".git" / ref).read_text(encoding="utf-8").strip()
        else:
            oid = head
        tm.ok(u.Cli.run_checked(["git", "-C", str(parent), "add", ".gitmodules"]))
        tm.ok(
            u.Cli.run_checked([
                "git",
                "-C",
                str(parent),
                "update-index",
                "--add",
                "--cacheinfo",
                f"160000,{oid},apps/member",
            ])
        )
        tm.ok(
            u.Cli.run_checked([
                "git",
                "-C",
                str(parent),
                "commit",
                "--quiet",
                "-m",
                "absorb member",
            ])
        )
        tm.that((member / ".git").is_dir(), eq=True)
        identity = tm.ok(u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=member)))
        tm.that(identity.superproject_root, eq=parent.resolve())
        tm.that(identity.is_submodule, eq=True)

    def test_git_identity_ascends_from_nested_path(self, tmp_path: Path) -> None:
        """Nested file/dir paths resolve through git_open_repo parent search.

        Why (flext-infra-c3h): ai-hub must not keep a parallel ``.git`` walk;
        ``git_identity`` owns ascent and reports ``repo_root`` at the checkout.
        """
        root = self._repo(tmp_path / "repo")
        nested = root / "src" / "pkg"
        nested.mkdir(parents=True)
        (nested / "module.py").write_text("x = 1\n", encoding="utf-8")
        identity = tm.ok(
            u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=nested / "module.py"))
        )
        tm.that(identity.repo_root, eq=root.resolve())
        tm.that(identity.requested_path, eq=(nested / "module.py").resolve())
