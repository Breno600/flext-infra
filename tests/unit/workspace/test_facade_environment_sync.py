"""Public ``infra`` facade contract for workspace environment sync.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import infra
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
        workspace: Path,
        home: Path,
        name: str,
        env: t.StrMapping,
    ) -> str:
        """Return one variable as the real direnv activation of ``workspace`` sees it.

        ``HOME`` is isolated so activation never reads the operator's home; the
        inherited Mise storage still provides the pinned runtime ``make setup``
        installed.

        Returns:
            One variable as the real direnv activation of ``workspace`` sees it.

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
            ),
        )
        return tm.ok(
            u.Cli.capture(
                ["direnv", "exec", str(workspace), "printenv", name],
                cwd=workspace,
                env=activation_env,
                remove_env_keys=isolation,
            ),
        )

    def test_activation_leaves_the_temp_directory_to_the_caller(
        self,
        tmp_path: Path,
    ) -> None:
        """Activation forces no scratch root: the caller's TMPDIR survives."""
        home = tmp_path / "home"
        home.mkdir()
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        tm.ok(
            infra.sync_environment_files(
                m.Infra.WorkspaceEnvironmentSyncRequest(
                    repository_root=workspace,
                    allow_direnv=False,
                ),
            ),
        )
        caller_tmp = tmp_path / "caller-tmp"
        caller_tmp.mkdir()
        activated = self._activated_value(
            workspace,
            home,
            "TMPDIR",
            {"TMPDIR": str(caller_tmp)},
        )
        tm.that(activated.strip(), eq=str(caller_tmp))

    def test_activation_preserves_caller_beads_routing(self, tmp_path: Path) -> None:
        """A caller-selected Beads ledger survives activation (linked worktrees)."""
        home = tmp_path / "home"
        home.mkdir()
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        tm.ok(
            infra.sync_environment_files(
                m.Infra.WorkspaceEnvironmentSyncRequest(
                    repository_root=workspace,
                    allow_direnv=False,
                ),
            ),
        )
        ledger = tmp_path / "main-checkout" / c.Infra.BEADS_DIRNAME
        routed = self._activated_value(
            workspace,
            home,
            "BEADS_DIR",
            {"BEADS_DIR": str(ledger)},
        )
        tm.that(routed, eq=str(ledger))

    def test_sync_creates_envrc_without_creating_mise(self, tmp_path: Path) -> None:
        """Test sync creates envrc without creating mise."""
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=workspace),
        )
        tm.ok(result)
        envrc = (workspace / ".envrc").read_text(encoding="utf-8")
        tm.that("strict_env" in envrc, eq=True)
        tm.that('PROJECT_ROOT="$(find_up pyproject.toml)"' in envrc, eq=True)
        tm.that((workspace / ".mise.toml").exists(), eq=False)

    def test_sync_preserves_custom_envrc_without_force(self, tmp_path: Path) -> None:
        """Test sync preserves custom envrc without force."""
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        custom = workspace / ".envrc"
        _ = custom.write_text("PATH_add bin\n", encoding="utf-8")
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=workspace),
        )
        tm.ok(result)
        tm.that(custom.read_text(encoding="utf-8"), eq="PATH_add bin\n")

    def test_sync_force_converts_custom_envrc_to_generated(
        self,
        tmp_path: Path,
    ) -> None:
        """Test sync force converts custom envrc to generated."""
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        custom = workspace / ".envrc"
        _ = custom.write_text("PATH_add bin\n", encoding="utf-8")
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(
                repository_root=workspace,
                force=True,
            ),
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
        """Test sync never mutates codegen owned mise."""
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        mise = workspace / ".mise.toml"
        custom = '[tools]\nnode = "22"\npython = "3.14"\n'
        _ = mise.write_text(custom, encoding="utf-8")
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(
                repository_root=workspace,
                force=True,
            ),
        )
        tm.ok(result)
        tm.that(mise.read_text(encoding="utf-8"), eq=custom)

    def test_sync_removes_generated_envrc_without_pyproject(
        self,
        tmp_path: Path,
    ) -> None:
        """Test sync removes generated envrc without pyproject."""
        workspace = tmp_path / "workspace"
        self._write_pyproject(workspace)
        setup = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=workspace),
        )
        tm.ok(setup)
        (workspace / "pyproject.toml").unlink()
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=workspace),
        )
        tm.ok(result)
        tm.that((workspace / ".envrc").exists(), eq=False)
