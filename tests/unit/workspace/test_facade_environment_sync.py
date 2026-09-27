"""Public ``infra`` facade contract for workspace environment sync."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config, infra
from tests import c, m, t, u


class TestsFlextInfraFacadeEnvironmentSync:
    """Pin direnv ownership without competing with codegen's Mise owner."""

    @staticmethod
    def _write_pyproject(root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        _ = (root / "pyproject.toml").write_text(
            '[project]\nname = "workspace"\nversion = "0.1.0"\nrequires-python = ">=3.13"\n',
            encoding="utf-8",
        )

    @staticmethod
    def _activated_value(
        workspace: Path, home: Path, name: str, env: t.StrMapping
    ) -> str:
        """Return one variable as the real direnv activation of ``workspace`` sees it.

        ``HOME`` is isolated so the activation creates its scratch root under the
        test tree instead of the operator's home; the inherited Mise storage
        still provides the pinned runtime ``make setup`` installed.
        """
        # A governed checkout is a Git work tree (activation resolves its
        # runtime root from the Git superproject topology) carrying its Mise
        # declaration, launcher, and release pin.
        u.Tests.initialize_git_repo(workspace)
        u.Tests.copy_tracked_mise_seeds(workspace)
        activation_env = {"HOME": str(home), **env}
        isolation = c.Tests.DIRENV_STATE_ENV_KEYS
        tm.ok(
            u.Cli.run_checked(
                ["direnv", "allow", str(workspace)],
                cwd=workspace,
                env=activation_env,
                remove_env_keys=isolation,
            )
        )
        return tm.ok(
            u.Cli.capture(
                ["direnv", "exec", str(workspace), "printenv", name],
                cwd=workspace,
                env=activation_env,
                remove_env_keys=isolation,
            )
        )

    def test_scratch_root_never_mirrors_a_vcs_directory(self, tmp_path: Path) -> None:
        """A checkout nested in a VCS directory activates a VCS-free scratch root."""
        home = tmp_path / "home"
        home.mkdir()
        for segment, alias in c.Infra.SCRATCH_IDENTITY_SEGMENT_ALIASES:
            workspace = tmp_path / "superproject" / segment / "modules" / "member"
            self._write_pyproject(workspace)
            tm.ok(
                infra.sync_environment_files(
                    m.Infra.WorkspaceEnvironmentSyncRequest(
                        repository_root=workspace, allow_direnv=False
                    )
                )
            )
            toolchain = config.Infra.codegen.toolchain
            scratch = Path(self._activated_value(workspace, home, "TMPDIR", {}))
            scratch_home = (
                home / toolchain.scratch_home_relative / toolchain.state_directory_name
            )
            tm.that(scratch.is_relative_to(scratch_home), eq=True)
            tm.that(scratch.name, eq=toolchain.scratch_namespace)
            tm.that(segment in scratch.parts, eq=False)
            tm.that(alias in scratch.parts, eq=True)
            tm.that(scratch.is_dir(), eq=True)

    def test_activation_preserves_caller_beads_routing(self, tmp_path: Path) -> None:
        """A caller-selected Beads ledger survives activation (linked worktrees)."""
        home = tmp_path / "home"
        home.mkdir()
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        tm.ok(
            infra.sync_environment_files(
                m.Infra.WorkspaceEnvironmentSyncRequest(
                    repository_root=workspace, allow_direnv=False
                )
            )
        )
        ledger = tmp_path / "main-checkout" / c.Infra.BEADS_DIRNAME
        routed = self._activated_value(
            workspace, home, "BEADS_DIR", {"BEADS_DIR": str(ledger)}
        )
        tm.that(routed, eq=str(ledger))

    def test_sync_creates_envrc_without_creating_mise(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=workspace)
        )
        tm.ok(result)
        envrc = (workspace / ".envrc").read_text(encoding="utf-8")
        tm.that("strict_env" in envrc, eq=True)
        tm.that('PROJECT_ROOT="$(find_up pyproject.toml)"' in envrc, eq=True)
        tm.that((workspace / ".mise.toml").exists(), eq=False)

    def test_sync_preserves_custom_envrc_without_force(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        custom = workspace / ".envrc"
        _ = custom.write_text("PATH_add bin\n", encoding="utf-8")
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=workspace)
        )
        tm.ok(result)
        tm.that(custom.read_text(encoding="utf-8"), eq="PATH_add bin\n")

    def test_sync_force_converts_custom_envrc_to_generated(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        custom = workspace / ".envrc"
        _ = custom.write_text("PATH_add bin\n", encoding="utf-8")
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(
                repository_root=workspace, force=True
            )
        )
        tm.ok(result)
        content = custom.read_text(encoding="utf-8")
        tm.that("strict_env" in content, eq=True)
        tm.that("PATH_add bin" in content, eq=False)
        tm.that(
            any(
                marker in content for marker in c.Infra.WORKSPACE_ENV_GENERATED_MARKERS
            ),
            eq=True,
        )

    def test_sync_never_mutates_codegen_owned_mise(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        mise = workspace / ".mise.toml"
        custom = '[tools]\nnode = "22"\npython = "3.14"\n'
        _ = mise.write_text(custom, encoding="utf-8")
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(
                repository_root=workspace, force=True
            )
        )
        tm.ok(result)
        tm.that(mise.read_text(encoding="utf-8"), eq=custom)

    def test_sync_removes_generated_envrc_without_pyproject(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        setup = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=workspace)
        )
        tm.ok(setup)
        (workspace / "pyproject.toml").unlink()
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=workspace)
        )
        tm.ok(result)
        tm.that((workspace / ".envrc").exists(), eq=False)
