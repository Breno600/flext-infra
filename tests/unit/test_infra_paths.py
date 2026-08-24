"""Tests for public workspace path resolution utilities."""

from __future__ import annotations

from pathlib import Path

from flext_infra import u
from flext_tests import tm


class TestsFlextInfraInfraPaths:
    """Verify workspace path resolution through the public utility."""

    def test_resolve_workspace_root_with_current_directory(self) -> None:
        result = u.Infra.resolve_workspace_root_or_cwd(None)
        tm.that(result.is_absolute(), eq=True)

    def test_resolve_workspace_root_with_absolute_path(self, tmp_path: Path) -> None:
        result = u.Infra.resolve_workspace_root_or_cwd(tmp_path)
        tm.that(result.is_absolute(), eq=True)

    def test_resolve_workspace_root_returns_resolved_path(self, tmp_path: Path) -> None:
        result = u.Infra.resolve_workspace_root_or_cwd(tmp_path)
        tm.that(result, eq=tmp_path.resolve())

    def test_resolve_workspace_root_with_none_uses_cwd(self) -> None:
        result = u.Infra.resolve_workspace_root_or_cwd(None)
        tm.that(result, eq=Path.cwd().resolve())

    def test_resolve_workspace_root_with_file_returns_parent(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "some_file.txt"
        file_path.write_text("", encoding="utf-8")
        result = u.Infra.resolve_workspace_root_or_cwd(file_path)
        tm.that(result, eq=tmp_path.resolve())

    def test_member_checkout_never_escalates_to_its_superproject(
        self, tmp_path: Path
    ) -> None:
        """Invoking inside a member scopes the run to that member only.

        Scope follows the invocation point: run it in the workspace and it
        works on the whole active workspace; run it in a project and it works
        on that project alone. Escalating a member checkout to its enclosing
        superproject inverts that rule -- a verb invoked in one project would
        silently operate relative to a root shared by every sibling worktree.

        The existing cases above only pass because ``tmp_path`` is never a
        submodule, so the escalation branch stays dormant. This builds a real
        superproject/member pair so the branch is actually exercised.
        """
        superproject = tmp_path / "workspace"
        member = superproject / "member"
        member.mkdir(parents=True)
        u.Cli.run_raw(["git", "init", "-q"], cwd=member).unwrap()
        u.Cli.run_raw(
            ["git", "config", "user.email", "tests@flext.sh"], cwd=member
        ).unwrap()
        u.Cli.run_raw(
            ["git", "config", "user.name", "FLEXT Tests"], cwd=member
        ).unwrap()
        (member / "tracked.txt").write_text("fixture\n", encoding="utf-8")
        u.Cli.run_raw(["git", "add", "tracked.txt"], cwd=member).unwrap()
        u.Cli.run_raw(["git", "commit", "-q", "-m", "fixture"], cwd=member).unwrap()
        u.Cli.run_raw(["git", "init", "-q"], cwd=superproject).unwrap()
        u.Cli.run_raw(
            ["git", "config", "user.email", "tests@flext.sh"], cwd=superproject
        ).unwrap()
        u.Cli.run_raw(
            ["git", "config", "user.name", "FLEXT Tests"], cwd=superproject
        ).unwrap()
        u.Cli.run_raw(
            [
                "git",
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                "-q",
                "./member",
                "member",
            ],
            cwd=superproject,
        ).unwrap()

        result = u.Infra.resolve_workspace_root_or_cwd(member)

        tm.that(result, eq=member.resolve())
