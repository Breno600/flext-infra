"""Public beads-workspace environment sync behavior through the facade."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, infra, m
from tests import TestsFlextInfraUtilities as u


class TestsFlextInfraBeadsEnvironmentSync:
    """Behavior contract for the generated beads-workspace activation."""

    @staticmethod
    def make_request(
        root: Path,
        *,
        apply: bool = True,
        force: bool = False,
        allow_direnv: bool = True,
    ) -> m.Infra.WorkspaceEnvironmentSyncRequest:
        """Build one canonical beads-workspace sync request."""
        return m.Infra.WorkspaceEnvironmentSyncRequest(
            repository_root=root,
            apply=apply,
            force=force,
            beads=m.Infra.BeadsWorkspaceEnvironmentSpec(),
            allow_direnv=allow_direnv,
        )

    def test_sync_writes_generated_envrc_and_allows(self, tmp_path: Path) -> None:
        """An applied sync projects the canonical activation file."""
        result = infra.sync_environment_files(
            self.make_request(tmp_path, allow_direnv=False)
        )
        tm.ok(result)
        envrc = tmp_path / c.Infra.ENVRC_FILENAME
        content = envrc.read_text(encoding="utf-8")
        marker = c.Infra.WORKSPACE_ENV_GENERATED_MARKERS[1]
        tm.that(marker in content, eq=True)
        tm.that('checkout_root="$(pwd -P)"' in content, eq=True)
        tm.that("$DIRENV_DIR" in content, eq=False)
        tm.that(
            ': "${AGENTS_GAS_CITY_ROOT:?AGENTS_GAS_CITY_ROOT must name' in content,
            eq=True,
        )
        tm.that("BEADS_DOLT_SERVER_PORT" in content, eq=True)
        tm.that(
            'gas_city_root="$(cd "${AGENTS_GAS_CITY_ROOT}" && pwd -P)"' in content,
            eq=True,
        )
        tm.that("dolt-state.json" in content, eq=True)
        tm.that(content, lacks="unset BEADS_DIR")

    def test_sync_without_allow_consumes_no_runner(self, tmp_path: Path) -> None:
        """allow_direnv=False never invokes a runner."""
        result = infra.sync_environment_files(
            self.make_request(tmp_path, allow_direnv=False)
        )
        tm.ok(result)
        tm.that((tmp_path / c.Infra.ENVRC_FILENAME).is_file(), eq=True)

    def test_python_activation_composes_external_beads_server(
        self, tmp_path: Path
    ) -> None:
        """Selecting Beads retains Python activation and explicit server mode."""
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "beads-python"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        tm.ok(
            infra.sync_environment_files(
                self.make_request(tmp_path, allow_direnv=False)
            )
        )
        content = (tmp_path / c.Infra.ENVRC_FILENAME).read_text(encoding="utf-8")
        tm.that(content, has='PROJECT_ROOT="$(find_up pyproject.toml)"')
        tm.that(content, has='export VIRTUAL_ENV="${VENV_DIR}"')
        tm.that(content, has="export BEADS_DOLT_SERVER_MODE=1")
        tm.that(content, has='BEADS_DOLT_SERVER_PORT="$(')
        tm.that(content, lacks='export BEADS_DOLT_SERVER_PORT="$(')
        tm.that(content, lacks="unset BEADS_DIR")
        tm.that(content, has="source_env_if_exists .envrc.local")

    def test_report_mode_writes_nothing(self, tmp_path: Path) -> None:
        """apply=False is read-only and consumes no runner."""
        result = infra.sync_environment_files(self.make_request(tmp_path, apply=False))
        tm.ok(result)
        tm.that((tmp_path / c.Infra.ENVRC_FILENAME).exists(), eq=False)

    def test_local_backend_for_standalone_beads_identity(self, tmp_path: Path) -> None:
        """A governed identity without city participation renders the local base."""
        u.Tests.WorktreeFixture.initialize_governed_project(
            tmp_path,
            "local-project",
            workspace="local-workspace",
            database="local_database",
            issue_prefix="local-prefix",
        )
        u.Tests.write_standalone_workspace_manifest(
            tmp_path, "local-project", gascity_enabled=False
        )
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(
                repository_root=tmp_path, allow_direnv=False
            )
        )
        tm.ok(result)
        content = (tmp_path / c.Infra.ENVRC_FILENAME).read_text(encoding="utf-8")
        tm.that(content, lacks="AGENTS_GAS_CITY_ROOT")
        tm.that(content, lacks="dolt-state.json")
        tm.that(content, lacks="jq -er")
        tm.that(content, has='watch_file "${checkout_root}/.beads/metadata.json"')
        tm.that(content, has="unset BEADS_DOLT_SERVER_HOST BEADS_DOLT_SERVER_PORT")
        tm.that(content, has="unset BEADS_DOLT_AUTO_START")
        tm.that(content, lacks="unset BEADS_DIR")
        tm.that(content, has="source_env_if_exists .envrc.local")

    def test_none_backend_without_beads_identity(self, tmp_path: Path) -> None:
        """A repository with no Beads identity renders only the unset chain."""
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "bare"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        result = infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(
                repository_root=tmp_path, allow_direnv=False
            )
        )
        tm.ok(result)
        content = (tmp_path / c.Infra.ENVRC_FILENAME).read_text(encoding="utf-8")
        tm.that(content, lacks="AGENTS_GAS_CITY_ROOT")
        tm.that(content, lacks=".beads/metadata.json")
        tm.that(content, lacks="dolt-state.json")
        tm.that(content, has="unset BEADS_DOLT_SERVER_HOST BEADS_DOLT_SERVER_PORT")
        tm.that(content, has="unset GT_ROOT")
        tm.that(content, has="unset BEADS_DOLT_AUTO_START")
        tm.that(content, lacks="unset BEADS_DIR")

    def test_custom_envrc_preserved_without_force(self, tmp_path: Path) -> None:
        """Custom content is never clobbered without force."""
        custom = tmp_path / c.Infra.ENVRC_FILENAME
        _ = custom.write_text("PATH_add bin\n", encoding="utf-8")
        result = infra.sync_environment_files(
            self.make_request(tmp_path, allow_direnv=False)
        )
        tm.ok(result)
        tm.that(custom.read_text(encoding="utf-8"), eq="PATH_add bin\n")

    def test_force_converts_custom_envrc_to_generated(self, tmp_path: Path) -> None:
        """force=True replaces custom content with the canonical projection."""
        custom = tmp_path / c.Infra.ENVRC_FILENAME
        _ = custom.write_text('checkout_root="${DIRENV_DIR#-}"\n', encoding="utf-8")
        result = infra.sync_environment_files(
            self.make_request(tmp_path, force=True, allow_direnv=False)
        )
        tm.ok(result)
        content = custom.read_text(encoding="utf-8")
        tm.that("$DIRENV_DIR" in content, eq=False)
        tm.that("pwd -P" in content, eq=True)
