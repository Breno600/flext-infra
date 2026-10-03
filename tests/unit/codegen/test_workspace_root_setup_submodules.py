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

from flext_infra import c, config, m, p, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import t, u as test_u

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
                env=env,
            ),
        )

    @staticmethod
    def _render_repository_root_makefile(tmp_path: Path) -> str:
        root_repository = test_u.Tests.repository_ref("flext")
        member = test_u.Tests.repository_ref(
            "flext-core",
            path=Path("flext-core"),
            role=c.Infra.MakeProfile.STANDALONE,
        )
        workspace = test_u.Tests.workspace_spec(
            root_repository,
            project=test_u.Tests.project_spec("flext"),
            subprojects=(member,),
        )

        root = tmp_path / "render-root"
        request = m.Infra.CodegenConformRequest(
            root=root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(
            repository_root=root,
            request=request,
            initial_workspace=workspace,
        ).plan(request)
        plan = tm.ok(planned)
        makefile: m.Infra.CodegenFilePlan = next(
            file for file in plan.files if file.path.name == c.Infra.MAKEFILE_FILENAME
        )
        return tm.not_none(makefile.desired_content).decode("utf-8")

    @staticmethod
    def _create_member_origin(tmp_path: Path) -> Path:
        member = tmp_path / "member-source"
        member.mkdir()
        (member / "pyproject.toml").write_text(
            "[project]\nname = 'flext-core'\nversion = '0.1.0'\n"
            f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\ndependencies = []\n',
            encoding="utf-8",
        )
        pkg = member / "src" / "flext_core"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text(
            "from __future__ import annotations\n\n__all__: list[str] = []\n",
            encoding="utf-8",
        )
        test_u.Tests.initialize_git_repo(member)
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "checkout", "-b", "0.12.0-dev"],
                cwd=member,
            ),
        )
        tm.ok(u.Cli.run_checked([c.Infra.GIT, "checkout", "main"], cwd=member))
        remote_root = tmp_path / "member-remote"
        remote_root.mkdir()
        origin = test_u.Tests.configure_local_origin(member, remote_root)
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
        test_u.Tests.initialize_git_repo(source)
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
                    str(member_origin),
                    "flext-core",
                ],
                cwd=source,
            ),
        )
        test_u.Tests.commit_git_changes(source, "Declare workspace project")
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "checkout", "-b", "0.12.0-dev"],
                cwd=source,
            ),
        )
        tm.ok(u.Cli.run_checked([c.Infra.GIT, "checkout", "main"], cwd=source))
        remote_root = tmp_path / "workspace-remote"
        remote_root.mkdir()
        workspace_origin = test_u.Tests.configure_local_origin(source, remote_root)
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
        tm.that(rendered, has="submodule update --init --")
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
        tm.that(process.stdout + process.stderr, has="Submodule path 'flext-core'")
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
        """Setup provisions governed gitlinks before the environment recipe.

        The workspace projections derive from the member checkouts, so a
        member-less CI checkout renders a different workspace and breaks the
        gen fixed point (flext-gdm8w).
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
                env=env,
            ),
        )

        output = process.stdout + process.stderr
        tm.that(output, has="Submodule path 'flext-core'")
        tm.that((workspace / "flext-core" / "pyproject.toml").is_file(), eq=True)
        gitlink = self._git_stdout(workspace, "rev-parse", "HEAD:flext-core")
        tm.that(self._git_state(workspace / "flext-core"), eq=("", gitlink))
        tm.that(process.stderr, has="missing Mise-resolved Python executable")

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
        test_u.Tests.write_executable(
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
