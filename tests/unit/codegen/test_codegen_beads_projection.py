"""Projection-only contract for repository-owned Beads configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, infra, m
from tests import u


class TestsFlextInfraCodegenBeadsProjection:
    """Keep codegen on its declarative projection boundary."""

    @staticmethod
    def _project(root: Path, *, database: str, issue_prefix: str) -> Path:
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-project",
            workspace="fixture-workspace",
            database=database,
            issue_prefix=issue_prefix,
        )
        return root

    def test_local_identity_renders_declarative_beads_routing(
        self, tmp_path: Path
    ) -> None:
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )

        plan = u.Tests.governed_project_plan(root)
        rendered_config = u.Tests.planned_text(plan, c.Infra.BEADS_CONFIG_RELPATH)
        rendered_metadata = u.Tests.planned_text(plan, c.Infra.BEADS_METADATA_RELPATH)

        if rendered_config is None:
            pytest.fail("local identity must produce the declarative Beads config")
        # `issue_prefix` is the key bd itself resolves (`bd config get
        # issue_prefix`); the hyphenated spelling reads as unset, so bd appended
        # its own key on first write and left every governed checkout dirty.
        tm.that(rendered_config, has='issue_prefix: "project-prefix"')
        tm.that(rendered_config, lacks="issue-prefix:")
        # A checkout with no workspace manifest declares city participation by
        # fleet default (True): the endpoint keys mirror the inherited city and
        # `types.custom` stays generator-owned.
        tm.that(rendered_config, has="gc.endpoint_origin:")
        tm.that(rendered_config, has="gc.endpoint_status:")
        tm.that(rendered_config, has="types.custom:")
        tm.that(rendered_config, has="dolt.auto-start:")
        if rendered_metadata is None:
            pytest.fail("local identity must produce the declarative Beads marker")
        metadata = u.Tests.json_payload(rendered_metadata)
        tm.that(metadata["backend"], eq="dolt")
        tm.that(metadata["database"], eq="dolt")
        tm.that(metadata["dolt_database"], eq="project_database")
        tm.that(
            metadata["dolt_mode"], eq=config.Infra.codegen.toolchain.beads.dolt_mode
        )
        # A fresh checkout has no checkout-owned identity.toml. Conform owns
        # the portable routing marker but never mints the ledger identity.
        tm.that("project_id" in metadata, eq=False)
        tm.that(set(metadata), eq={"backend", "database", "dolt_mode", "dolt_database"})

    def test_gascity_disabled_renders_standalone_beads_config(
        self, tmp_path: Path
    ) -> None:
        """A disabled city never moves runtime ownership into generated config."""
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        u.Tests.write_standalone_workspace_manifest(
            root, "fixture-project", gascity_enabled=False
        )

        plan = u.Tests.governed_project_plan(root)
        rendered_config = u.Tests.planned_text(plan, c.Infra.BEADS_CONFIG_RELPATH)
        rendered_mise = u.Tests.planned_text(plan, ".mise.toml")

        if rendered_config is None:
            pytest.fail("standalone identity must produce the declarative Beads config")
        tm.that(rendered_config, has='issue_prefix: "project-prefix"')
        tm.that(rendered_config, lacks="issue-prefix:")
        tm.that(rendered_config, lacks="dolt.auto-start:")
        tm.that(rendered_config, lacks="gc.endpoint_origin")
        tm.that(rendered_config, lacks="gc.endpoint_status")
        tm.that(rendered_config, lacks="Gas City contract")
        if rendered_mise is None:
            pytest.fail("standalone identity must produce the managed Mise manifest")
        # bd and gc are host binaries owned by the global mise config; a
        # project manifest never declares either distribution.
        tm.that(rendered_mise, lacks="beads")
        tm.that(rendered_mise, lacks="gascity")

    def test_mise_manifest_provisions_managed_make(self, tmp_path: Path) -> None:
        """The generated ``.mise.toml`` must declare make as a managed tool.

        Root cause (R1): when make is absent from [tools], direnv resolves
        make from the stale host shim (conda-carried) instead of a Mise
        installation, so ``make setup`` exits 1. The projection must own
        make so the setup runtime resolves/executes it without conda.
        """
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )

        plan = u.Tests.governed_project_plan(root)
        rendered_mise = u.Tests.planned_text(plan, ".mise.toml")

        if rendered_mise is None:
            pytest.fail("conform must produce the managed .mise.toml")
        tm.that(
            rendered_mise, has=f'make = "{config.Infra.codegen.toolchain.make_version}"'
        )
        tm.that(rendered_mise, lacks="conda")
        tm.that(rendered_mise, lacks="stale")

    def test_gascity_disabled_renders_local_envrc_tier(self, tmp_path: Path) -> None:
        """A disabled city renders the repository-local bd activation tier."""
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        u.Tests.write_standalone_workspace_manifest(
            root, "fixture-project", gascity_enabled=False
        )

        plan = u.Tests.governed_project_plan(root)
        rendered_envrc = u.Tests.planned_text(plan, ".envrc")

        if rendered_envrc is None:
            pytest.fail("standalone identity must produce the managed .envrc")
        tm.that(rendered_envrc, lacks="AGENTS_GAS_CITY_ROOT")
        tm.that(rendered_envrc, lacks="dolt-state.json")
        tm.that(rendered_envrc, lacks="jq -er")
        tm.that(
            rendered_envrc, has='watch_file "${checkout_root}/.beads/metadata.json"'
        )
        tm.that(
            rendered_envrc, has="unset BEADS_DOLT_SERVER_HOST BEADS_DOLT_SERVER_PORT"
        )
        tm.that(rendered_envrc, has="unset BEADS_DOLT_AUTO_START")
        # Caller-owned Beads routing survives activation so bd resolves the
        # selected ledger inside a linked worktree.
        tm.that(rendered_envrc, lacks="unset BEADS_DIR")

    def test_envrc_local_generated_residue_is_normalized(self, tmp_path: Path) -> None:
        """The merge keeps custom overrides and strips stale generated sections.

        Every member checkout carries a historical generated ``Gas City Beads
        activation`` section in ``.envrc.local`` duplicating the managed
        ``.envrc`` block with drifted jq conditions; conform is the single
        activation owner and removes exactly that residue.
        """
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        _ = (root / ".envrc.local").write_text(
            "# Generated by `flext-infra codegen conform`.\n"
            "# === SECTION: Gas City Beads activation (managed) ===\n"
            "unset GT_ROOT\n"
            'source_env_if_exists "$HOME/.config/environment.d/projects/agent-tools.envrc"\n'
            "# End SECTION: Gas City Beads activation\n"
            "export CUSTOM_OVERRIDE=1\n",
            encoding="utf-8",
        )

        entry = next(
            (
                item
                for item in u.Tests.governed_project_plan(root).files
                if item.path.name == ".envrc.local"
            ),
            None,
        )

        if entry is None or entry.desired_content is None:
            pytest.fail("custom overrides must keep .envrc.local planned")
        desired = entry.desired_content.decode("utf-8")
        tm.that(desired, has="export CUSTOM_OVERRIDE=1")
        tm.that(desired, lacks="SECTION")
        tm.that(desired, lacks="Generated by")
        tm.that(desired, lacks="GT_ROOT")

    def test_envrc_local_without_custom_content_is_removed(
        self, tmp_path: Path
    ) -> None:
        """A .envrc.local carrying only generated residue is deleted."""
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        _ = (root / ".envrc.local").write_text(
            "# Generated by `flext-infra codegen conform`.\n"
            "# === SECTION: Gas City Beads activation (managed) ===\n"
            "unset GT_ROOT\n"
            "# End SECTION: Gas City Beads activation\n",
            encoding="utf-8",
        )

        entry = next(
            (
                item
                for item in u.Tests.governed_project_plan(root).files
                if item.path.name == ".envrc.local"
            ),
            None,
        )

        if entry is None:
            pytest.fail("residue-only .envrc.local must be planned for removal")
        tm.that(entry.desired_content, none=True)

    @pytest.mark.parametrize("source_exists", [False, True])
    def test_gascity_enabled_sources_activate_conditionally(
        self, tmp_path: Path, *, source_exists: bool
    ) -> None:
        """Optional sources precede the fail-loud city authority boundary."""
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        source = tmp_path / "optional-host.envrc"
        marker = "optional-host-source-executed"
        if source_exists:
            source.write_text(f"printf '%s\\n' '{marker}' >&2\n", encoding="utf-8")
        environment = m.Infra.BeadsWorkspaceEnvironmentSpec(
            environment_sources=(str(source),), identity_var="FLEXT_TEST_CITY_ROOT"
        )
        tm.ok(
            infra.sync_environment_files(
                m.Infra.WorkspaceEnvironmentSyncRequest(
                    repository_root=root, beads=environment, allow_direnv=False
                )
            )
        )
        tm.ok(u.Cli.run_checked((c.Infra.CLI_DIRENV, "allow", str(root)), cwd=root))
        try:
            process = tm.ok(
                u.Cli.run_raw(
                    (c.Infra.CLI_DIRENV, "exec", str(root), "true"),
                    cwd=root,
                    env={environment.identity_var: ""},
                )
            )
        finally:
            tm.ok(u.Cli.run_checked((c.Infra.CLI_DIRENV, "deny", str(root)), cwd=root))
        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(
            process.stderr,
            has=(
                f"{environment.identity_var} must name the canonical Gas City checkout"
            ),
        )
        tm.that(marker in process.stderr, eq=source_exists)

    @pytest.mark.slow
    @pytest.mark.parametrize("gascity_enabled", [True, False])
    def test_envrc_renders_in_both_city_tiers(
        self, tmp_path: Path, *, gascity_enabled: bool
    ) -> None:
        """The managed .envrc renders its city tier in both city modes.

        A duplicated model family let the renderer and its validator bind two
        different classes of the same name, so the ``gascity.backend`` field of
        one was absent from the other and standalone renders failed.
        """
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        u.Tests.write_standalone_workspace_manifest(
            root, "fixture-project", gascity_enabled=gascity_enabled
        )

        rendered_envrc = u.Tests.planned_text(
            u.Tests.governed_project_plan(root), ".envrc"
        )

        if rendered_envrc is None:
            pytest.fail("a governed identity must produce the managed .envrc")
        tm.that("AGENTS_GAS_CITY_ROOT" in rendered_envrc, eq=gascity_enabled)

    def test_metadata_projection_preserves_a_minted_ledger_identity(
        self, tmp_path: Path
    ) -> None:
        """Regenerating must not strip the checkout's own ledger identity.

        Rendering the marker without `project_id` stripped the key on every
        `make gen`, and Beads then minted a fresh identity on next access —
        rig `gmn` lost 2b1a0582-… that way (commit 3e7ba1e).
        """
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        minted = "e9a551fc-a6f8-4e0e-a961-2505f49bc8a3"
        identity = root / ".beads" / "identity.toml"
        identity.parent.mkdir(parents=True, exist_ok=True)
        identity.write_text(f'[project]\nid = "{minted}"\n')
        (root / c.Infra.BEADS_METADATA_RELPATH).write_text(
            '{"backend":"dolt"}\n', encoding="utf-8"
        )

        rendered = u.Tests.planned_text(
            u.Tests.governed_project_plan(root), c.Infra.BEADS_METADATA_RELPATH
        )
        if rendered is None:
            pytest.fail("local identity must produce the Beads marker")
        metadata = u.Tests.json_payload(rendered)
        tm.that(metadata["project_id"], eq=minted)
        tm.that(
            set(metadata),
            eq={"database", "backend", "dolt_mode", "dolt_database", "project_id"},
        )

    def test_projection_preserves_the_manual_identity_input(
        self, tmp_path: Path
    ) -> None:
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        identity = root / "config" / "beads.yaml"
        before = identity.read_bytes()

        _ = u.Tests.governed_project_plan(root)

        tm.that(identity.read_bytes(), eq=before)
