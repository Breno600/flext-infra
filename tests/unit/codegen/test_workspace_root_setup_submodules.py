"""Workspace submodule setup behavior through generated Make surfaces.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, m, p, t, u

pytestmark = pytest.mark.slow


class TestsFlextInfraWorkspaceRootSetupSubmodules:
    """Prove root submodule setup initializes once and never repairs."""

    @staticmethod
    def _git_stdout(repository: Path, *args: str) -> str:
        process = tm.ok(u.Cli.run_raw([c.Infra.GIT, *args], cwd=repository))
        tm.that(u.Cli.process_succeeded(process.outcome), eq=True)
        return process.stdout.strip()

    def _git_state(self, repository: Path) -> t.Pair[str, str]:
        return (
            self._git_stdout(repository, "branch", "--show-current"),
            self._git_stdout(repository, "rev-parse", "HEAD"),
        )

    @staticmethod
    def _run_setup(workspace: Path, env: dict[str, str]) -> p.Cli.CommandOutput:
        return tm.ok(
            u.Cli.run_raw(
                ["make", "_builtin_setup_submodules"],
                cwd=workspace,
                options=m.Cli.ProcessOptions(env=env),
            ),
        )

    @staticmethod
    def _render_repository_root_makefile(tmp_path: Path) -> str:
        root_repository = u.Tests.repository_ref("flext")
        member = u.Tests.repository_ref(
            "flext-core",
            path=Path("flext-core"),
            role=c.Infra.MakeProfile.STANDALONE,
        )
        workspace = u.Tests.workspace_spec(
            root_repository,
            project=u.Tests.project_spec("flext"),
            subprojects=(member,),
        )
        rendered: str = u.Tests.conform_makefile_text(
            tmp_path / "render-root",
            workspace,
        )
        return rendered

    @staticmethod
    def _create_member_origin(tmp_path: Path) -> Path:
        member = tmp_path / "member-source"
        member.mkdir()
        (member / "pyproject.toml").write_text(
            "[project]\nname = 'flext-core'\nversion = '0.1.0'\n"
            'requires-python = "'
            f"{config.Infra.codegen.toolchain.python_required_version}"
            '"\ndependencies = []\n',
            encoding="utf-8",
        )
        pkg = member / "src" / "flext_core"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(
            "from __future__ import annotations\n\n__all__: list[str] = []\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(member)
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "checkout", "-b", "0.12.0-dev"],
                cwd=member,
            ),
        )
        tm.ok(u.Cli.run_checked([c.Infra.GIT, "checkout", "main"], cwd=member))
        remote_root = tmp_path / "member-remote"
        remote_root.mkdir()
        origin = u.Tests.configure_local_origin(member, remote_root)
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "push", "-u", c.Infra.GIT_ORIGIN, "0.12.0-dev"],
                cwd=member,
            ),
        )
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "symbolic-ref", "HEAD", "refs/heads/0.12.0-dev"],
                cwd=origin,
            ),
        )
        return origin

    def _create_uninitialized_workspace(self, tmp_path: Path, makefile: str) -> Path:
        member_origin = self._create_member_origin(tmp_path)
        source = tmp_path / "workspace-source"
        source.mkdir()
        (source / "Makefile").write_text(makefile, encoding="utf-8")
        (source / "pyproject.toml").write_text(
            "[project]\nname = 'flext'\nversion = '0.1.0'\n"
            "[tool.uv.workspace]\nmembers = ['flext-core']\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(source)
        tm.ok(
            u.Cli.run_checked(
                [
                    "git",
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    "-q",
                    "-b",
                    "0.12.0-dev",
                    member_origin.as_uri(),
                    "flext-core",
                ],
                cwd=source,
            ),
        )
        u.Tests.commit_git_changes(source, "Declare workspace project")
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "checkout", "-b", "0.12.0-dev"],
                cwd=source,
            ),
        )
        tm.ok(u.Cli.run_checked([c.Infra.GIT, "checkout", "main"], cwd=source))
        remote_root = tmp_path / "workspace-remote"
        remote_root.mkdir()
        workspace_origin = u.Tests.configure_local_origin(source, remote_root)
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "push", "-u", c.Infra.GIT_ORIGIN, "0.12.0-dev"],
                cwd=source,
            ),
        )
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "symbolic-ref", "HEAD", "refs/heads/0.12.0-dev"],
                cwd=workspace_origin,
            ),
        )
        checkout = tmp_path / "workspace-checkout"
        tm.ok(
            u.Cli.run_checked([
                "git",
                "clone",
                "-q",
                str(workspace_origin),
                str(checkout),
            ]),
        )
        return checkout

    def test_generated_setup_orders_submodules_before_first_uv(
        self,
        tmp_path: Path,
    ) -> None:
        """Test generated setup orders submodules before first uv."""
        rendered = self._render_repository_root_makefile(tmp_path)

        tm.that(rendered, has="_builtin_setup_environment: _builtin_setup_submodules")
        # uv syncs the runtime root's project (UV_PROJECT := RUNTIME_ROOT).
        tm.that(rendered, has='$(UV) sync --project "$(UV_PROJECT)"')
        tm.that(rendered, lacks="submodule update --init --recursive")

    def test_make_setup_initializes_once_then_only_validates_present_checkout(
        self,
        tmp_path: Path,
    ) -> None:
        """Initialize the exact gitlink once; never repair a present checkout."""
        rendered = self._render_repository_root_makefile(tmp_path)
        workspace = self._create_uninitialized_workspace(tmp_path, rendered)
        env = os.environ.copy()
        env["GIT_ALLOW_PROTOCOL"] = "file"

        process = self._run_setup(workspace, env)

        # The fixture bootstraps through submodules; the invariant we care about
        # is that the submodule is initialized before environment provisioning.
        if process.outcome.raw_return_code != 0:
            start = rendered.index("_builtin_setup_environment:")
            excerpt = rendered[
                start : rendered.index("# End SECTION: setup environment", start)
            ]
            pytest.fail(f"{process.stdout}{process.stderr}\n{excerpt}")
        tm.that(u.Cli.process_succeeded(process.outcome), eq=True)
        tm.that((workspace / "flext-core" / "pyproject.toml").is_file(), eq=True)
        child = workspace / "flext-core"
        state = self._git_state(child)
        gitlink = self._git_stdout(workspace, "rev-parse", "HEAD:flext-core")
        tm.that(state, eq=("", gitlink))

        second = self._run_setup(workspace, env)
        tm.that(u.Cli.process_succeeded(second.outcome), eq=True)
        tm.that(self._git_state(child), eq=state)
        tm.ok(u.Cli.run_checked([c.Infra.GIT, "switch", "-c", "conflict"], cwd=child))
        process = self._run_setup(workspace, env)

        # A present checkout on its own named change lane is validated, never
        # repaired: containment of the recorded gitlink is the boundary, so the
        # branch name is preserved untouched by a green setup.
        tm.that(u.Cli.process_succeeded(process.outcome), eq=True)
        tm.that(self._git_state(child), eq=("conflict", state[1]))

    def _prepare_clone_state(
        self,
        checkout: Path,
        state: str,
        tmp_path: Path,
        *,
        with_content: bool,
    ) -> None:
        git_dir = Path(self._git_stdout(checkout, "rev-parse", "--absolute-git-dir"))
        head = self._git_stdout(checkout, "rev-parse", "HEAD")
        if state.startswith("strategy-"):
            self._git_stdout(
                checkout.parent,
                "config",
                f"submodule.{checkout.name}.update",
                state.removeprefix("strategy-"),
            )
        if state.startswith("staged-deletions"):
            self._git_stdout(checkout, "read-tree", "--empty")
        elif with_content:
            if state.endswith("ignored"):
                (git_dir / "info" / "exclude").write_text(
                    "preserve.txt\n",
                    encoding="utf-8",
                )
            (checkout / "preserve.txt").write_text("local work\n", encoding="utf-8")
        elif state.startswith("foreign-tree"):
            if state == "foreign-tree-index":
                self._git_stdout(checkout, "read-tree", "--empty")
            foreign = tmp_path / "foreign-worktree"
            foreign.mkdir()
            self._git_stdout(checkout, "config", "core.worktree", str(foreign))
        elif state == "symlink-index":
            (git_dir / "index").symlink_to(tmp_path / "foreign-index")
        elif state == "extra-ref":
            self._git_stdout(checkout, "branch", "preserved", head)
        elif state == "stash-ref":
            self._git_stdout(checkout, "update-ref", "refs/stash", head)

    @pytest.mark.parametrize(
        "state",
        [
            "virgin",
            "strategy-merge",
            "strategy-rebase",
            "strategy-none",
            "staged-deletions",
            "staged-deletions-at-pin",
            "untracked",
            "ignored",
            "head-at-pin",
            "head-at-pin-untracked",
            "head-at-pin-ignored",
            "foreign-tree",
            "foreign-tree-index",
            "relocated-index",
            "symlink-index",
            "extra-ref",
            "stash-ref",
        ],
    )
    def test_setup_resumes_only_unfinished_initial_clone(
        self,
        tmp_path: Path,
        state: str,
    ) -> None:
        """Resume a real unborn clone without overwriting established work."""
        workspace = self._create_uninitialized_workspace(
            tmp_path,
            self._render_repository_root_makefile(tmp_path),
        )
        member = "flext-core"
        pin = self._git_stdout(workspace, "rev-parse", f":{member}")
        origin = Path.from_uri(
            self._git_stdout(
                workspace,
                "config",
                "-f",
                ".gitmodules",
                f"submodule.{member}.url",
            ),
        )
        if not state.startswith("head-at-pin") and state != "staged-deletions-at-pin":
            source = tmp_path / "member-source"
            self._git_stdout(
                source,
                "switch",
                self._git_stdout(origin, "symbolic-ref", "--short", "HEAD"),
            )
            (source / "marker.txt").write_text("newer\n", encoding="utf-8")
            self._git_stdout(source, "add", "marker.txt")
            self._git_stdout(
                source,
                "commit",
                "-m",
                "Advance the origin beyond the pin",
            )
            self._git_stdout(source, "push", c.Infra.GIT_ORIGIN, "HEAD")
        self._git_stdout(workspace, "submodule", "init")
        checkout = workspace / member
        git_dir = workspace / ".git" / "modules" / member
        git_dir.parent.mkdir(parents=True)
        self._git_stdout(
            workspace,
            "clone",
            "--depth",
            "1",
            "--no-checkout",
            "--separate-git-dir",
            str(git_dir),
            origin.as_uri(),
            str(checkout),
        )
        index = Path(
            self._git_stdout(
                checkout,
                "rev-parse",
                "--path-format=absolute",
                "--git-path",
                "index",
            ),
        )
        tm.that(index.exists(), eq=False)
        head = self._git_stdout(checkout, "rev-parse", "HEAD")
        local_content = state in {
            "untracked",
            "ignored",
            "head-at-pin-untracked",
            "head-at-pin-ignored",
        }
        self._prepare_clone_state(
            checkout,
            state,
            tmp_path,
            with_content=local_content,
        )
        prior_index = index.read_bytes() if index.exists() else None
        env = {**os.environ, "GIT_ALLOW_PROTOCOL": "file"}
        if state == "relocated-index":
            env["GIT_INDEX_FILE"] = str(tmp_path / "relocated-index")

        process = self._run_setup(workspace, env)

        if state in {"virgin", "head-at-pin"} or state.startswith("strategy-"):
            tm.that(
                u.Cli.process_succeeded(process.outcome),
                eq=True,
                msg=process.stdout + process.stderr,
            )
            tm.that(self._git_stdout(checkout, "rev-parse", "HEAD"), eq=pin)
            tm.that((checkout / "pyproject.toml").is_file(), eq=True)
            tm.that(index.is_file(), eq=True)
            second = self._run_setup(workspace, env)
            tm.that(
                u.Cli.process_succeeded(second.outcome),
                eq=True,
                msg=second.stdout + second.stderr,
            )
            tm.that(self._git_stdout(checkout, "rev-parse", "HEAD"), eq=pin)
            tm.that(
                second.stdout + second.stderr,
                lacks="resuming unfinished initial clone",
            )
        else:
            tm.that(
                u.Cli.process_succeeded(process.outcome),
                eq=state == "staged-deletions-at-pin",
                msg=process.stdout + process.stderr,
            )
            tm.that(self._git_stdout(checkout, "rev-parse", "HEAD"), eq=head)
            tm.that(index.read_bytes() if index.exists() else None, eq=prior_index)
            if state == "symlink-index":
                tm.that(index.is_symlink(), eq=True)
                tm.that(index.readlink(), eq=tmp_path / "foreign-index")
            elif state == "extra-ref":
                tm.that(
                    self._git_stdout(checkout, "rev-parse", "refs/heads/preserved"),
                    eq=head,
                )
            elif state == "stash-ref":
                tm.that(
                    self._git_stdout(checkout, "rev-parse", "refs/stash"),
                    eq=head,
                )
            if local_content:
                tm.that(
                    (checkout / "preserve.txt").read_text(encoding="utf-8"),
                    eq="local work\n",
                )

    def test_missing_submodule_origin_fails_without_materializing_checkout(
        self,
        tmp_path: Path,
    ) -> None:
        """A failed real Git clone stays red and leaves its gitlink uninitialized."""
        rendered = self._render_repository_root_makefile(tmp_path)
        workspace = self._create_uninitialized_workspace(tmp_path, rendered)
        missing_origin = tmp_path / "missing-member-origin"
        tm.ok(
            u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "config",
                    "-f",
                    ".gitmodules",
                    "submodule.flext-core.url",
                    str(missing_origin),
                ],
                cwd=workspace,
            ),
        )
        credential = "test-submodule-credential-never-log"
        env = {**os.environ, "GIT_ALLOW_PROTOCOL": "file", "GITHUB_TOKEN": credential}

        process = self._run_setup(workspace, env)

        tm.that(process.outcome.raw_return_code, eq=2)
        tm.that(process.stderr, has=str(missing_origin))
        tm.that(process.stdout + process.stderr, lacks=credential)
        tm.that((workspace / "flext-core" / ".git").exists(), eq=False)

    def test_setup_environment_provisions_members_before_the_environment(
        self,
        tmp_path: Path,
    ) -> None:
        """Setup provisions governed gitlinks, then never creates a missing lock.

        The workspace projections derive from the member checkouts, so a
        member-less CI checkout renders a different workspace and breaks the
        gen fixed point (flext-gdm8w). The fixture commits no uv.lock: the
        lock law (operator 2026-10-03, only `make upg` writes uv.lock) makes
        the environment recipe stop there, name the right path, and leave the
        workspace without a lock instead of deriving one.
        """
        rendered = self._render_repository_root_makefile(tmp_path)
        tm.that(rendered, has="MAKE_PROFILE := workspace")
        workspace = self._create_uninitialized_workspace(tmp_path, rendered)
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"SETUP_PYTHON", "CI"}
        }
        env["GIT_ALLOW_PROTOCOL"] = "file"

        process = tm.ok(
            u.Cli.run_raw(
                ["make", "--no-print-directory", "_builtin_setup_environment"],
                cwd=workspace,
                options=m.Cli.ProcessOptions(env=env),
            ),
        )

        tm.that((workspace / "flext-core" / "pyproject.toml").is_file(), eq=True)
        gitlink = self._git_stdout(workspace, "rev-parse", "HEAD:flext-core")
        tm.that(self._git_state(workspace / "flext-core"), eq=("", gitlink))
        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(process.stderr, has=["ERROR[setup] uv.lock is missing", "make upg"])
        tm.that((workspace / "uv.lock").exists(), eq=False)

    def test_unexpected_git_probe_failure_preserves_cause(self, tmp_path: Path) -> None:
        """A Git probe error is never reclassified as a missing remote ref."""
        workspace = self._create_uninitialized_workspace(
            tmp_path,
            self._render_repository_root_makefile(tmp_path),
        )
        real_git = tm.not_none(shutil.which("git"))
        fake_bin = tmp_path / "failing-git-bin"
        fake_bin.mkdir()
        command_fragment = "branch --show-current"
        u.Tests.write_executable(
            fake_bin / "git",
            "#!/bin/sh\n"
            "set -eu\n"
            f'case "$*" in *{shlex.quote(command_fragment)}*)\n'
            "  printf 'injected git failure\\n' >&2\n"
            "  exit 42\n"
            "  ;;\n"
            "esac\n"
            f'exec {shlex.quote(real_git)} "$@"\n',
        )
        env = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "GIT_ALLOW_PROTOCOL": "file",
        }

        process = self._run_setup(workspace, env)

        tm.that(process.outcome.raw_return_code, eq=2)
        tm.that(process.stderr, has="injected git failure")
        tm.that(process.stderr, has="Error 42")
