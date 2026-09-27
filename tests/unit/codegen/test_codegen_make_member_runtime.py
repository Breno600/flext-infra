"""A member checked out inside a workspace uses the workspace runtime (flext-x8gn6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeMemberRuntime:
    """Prove where a generated member Makefile resolves its runtime."""

    RUNTIME_NAMES = (
        "PROJECT_ROOT",
        "REPOSITORY_ROOT",
        "RUNTIME_ROOT",
        "RUNTIME_VENV",
        "UV_PROJECT",
        "UV_PROJECT_ENVIRONMENT",
    )

    @classmethod
    def _runtime_values(cls, project_root: Path) -> dict[str, str]:
        """Print the resolved runtime through the public help verb's post hook."""
        (project_root / "custom.mk").write_text(
            "post-help:\n\t@printf '%s\\n' "
            + " ".join(f"'{name}=$({name})'" for name in cls.RUNTIME_NAMES)
            + "\n",
            encoding="utf-8",
        )
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "help"], cwd=project_root
            )
        )
        tm.that(u.Cli.process_succeeded(process.outcome), eq=True, msg=process.stderr)
        return dict(
            line.split("=", 1)
            for line in process.stdout.splitlines()
            if line.split("=", 1)[0] in cls.RUNTIME_NAMES
        )

    @staticmethod
    def _workspace_with_member(tmp_path: Path, member_source: Path) -> Path:
        """Check the rendered member out as a submodule of a real superproject."""
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=member_source))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "--quiet", "-m", "render member"], cwd=member_source
            )
        )
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        u.Tests.initialize_git_repo(workspace)
        tm.ok(
            u.Cli.run_checked(
                [
                    "git",
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    "--quiet",
                    str(member_source),
                    member_source.name,
                ],
                cwd=workspace,
            )
        )
        return workspace.resolve()

    def test_checkout_without_superproject_owns_its_runtime(
        self, tmp_path: Path
    ) -> None:
        """A standalone clone resolves its own checkout and its own .venv."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )

        values = self._runtime_values(project_root)

        root = str(project_root.resolve())
        tm.that(values["RUNTIME_ROOT"], eq=root)
        tm.that(values["RUNTIME_VENV"], eq=f"{root}/.venv")

    def test_submodule_member_resolves_the_workspace_runtime(
        self, tmp_path: Path
    ) -> None:
        """A member checked out as a submodule shares the superproject runtime."""
        member_source, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        workspace = self._workspace_with_member(tmp_path, member_source)
        member = workspace / member_source.name

        values = self._runtime_values(member)

        tm.that(values["PROJECT_ROOT"], eq=str(member))
        for name in ("REPOSITORY_ROOT", "RUNTIME_ROOT", "UV_PROJECT"):
            tm.that(values[name], eq=str(workspace))
        for name in ("RUNTIME_VENV", "UV_PROJECT_ENVIRONMENT"):
            tm.that(values[name], eq=f"{workspace}/.venv")
