"""Projection-only contract for repository-owned Beads configuration.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config
from flext_infra.codegen import FlextInfraCodegenConformBeadsRoutes
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
        self,
        tmp_path: Path,
    ) -> None:
        """Test local identity renders declarative beads routing."""
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
        # issue_prefix`); a hyphen-only prefix reads as unset, so bd appended its
        # own key on first write. A Gas City rig also carries gc's canonical
        # mirror keys: gc rewrites a managed rig's config into exactly that key
        # set on every adopt and start, so a projection in any other form left
        # every governed checkout dirty after each gc pass.
        beads = config.Infra.codegen.toolchain.beads
        parsed = u.Tests.toml_mapping(tm.ok(u.Cli.yaml_parse(rendered_config)))
        tm.that(parsed["issue_prefix"], eq="project-prefix")
        tm.that(parsed["issue-prefix"], eq="project-prefix")
        tm.that(parsed["dolt.mode"], eq=beads.dolt_mode)
        tm.that(
            parsed["dolt"],
            eq={"disable-event-flush": beads.dolt_disable_event_flush},
        )
        tm.that("dolt.disable-event-flush" in parsed, eq=False)
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
            metadata["dolt_mode"],
            eq=config.Infra.codegen.toolchain.beads.dolt_mode,
        )
        # A fresh checkout has no checkout-owned identity.toml. Conform owns
        # the portable routing marker but never mints the ledger identity.
        tm.that("project_id" in metadata, eq=False)
        tm.that(set(metadata), eq={"backend", "database", "dolt_mode", "dolt_database"})
        # gc writes this marker as a sorted-key JSON object; the projection uses
        # the same order so gc's first write after adoption is byte-identical.
        tm.that(list(metadata), eq=sorted(metadata))

    def test_gascity_disabled_renders_standalone_beads_config(
        self,
        tmp_path: Path,
    ) -> None:
        """A disabled city never moves runtime ownership into generated config."""
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        u.Tests.write_standalone_workspace_manifest(
            root,
            "fixture-project",
            gascity_enabled=False,
        )

        plan = u.Tests.governed_project_plan(root)
        rendered_config = u.Tests.planned_text(plan, c.Infra.BEADS_CONFIG_RELPATH)
        rendered_mise = u.Tests.planned_text(plan, ".mise.toml")

        if rendered_config is None:
            pytest.fail("standalone identity must produce the declarative Beads config")
        tm.that(rendered_config, has='issue_prefix: "project-prefix"')
        tm.that(rendered_config, lacks="issue-prefix:")
        tm.that(rendered_config, lacks="dolt.auto-start:")
        # The mode mirror and the event-flush switch are read only by gc; a
        # standalone ledger carries neither (bd takes the flush switch from its
        # environment and the mode from metadata.json).
        tm.that(rendered_config, lacks="dolt.mode:")
        tm.that(rendered_config, lacks="disable-event-flush")
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
            rendered_mise,
            has=f'make = "{config.Infra.codegen.toolchain.make_version}"',
        )
        tm.that(rendered_mise, lacks="conda")
        tm.that(rendered_mise, lacks="stale")

    def test_generated_envrc_excludes_storage_routing(self, tmp_path: Path) -> None:
        """The project activation leaves Beads routing to native discovery."""
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        u.Tests.write_standalone_workspace_manifest(
            root,
            "fixture-project",
            gascity_enabled=False,
        )

        plan = u.Tests.governed_project_plan(root)
        rendered_envrc = u.Tests.planned_text(plan, ".envrc")

        if rendered_envrc is None:
            pytest.fail("standalone identity must produce the managed .envrc")
        tm.that(rendered_envrc, lacks="AGENTS_GAS_CITY_ROOT")
        tm.that(rendered_envrc, lacks="dolt-state.json")
        tm.that(rendered_envrc, lacks="jq -er")
        tm.that(rendered_envrc, lacks="BEADS_DOLT_")
        tm.that(rendered_envrc, lacks="BEADS_DIR")

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
            'source_env_if_exists "${HOME}/.config/environment.d/projects/agent-tools.envrc"\n'
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
        self,
        tmp_path: Path,
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

    @pytest.mark.slow
    @pytest.mark.parametrize("gascity_enabled", [True, False])
    def test_envrc_is_storage_neutral_in_both_workspace_modes(
        self,
        tmp_path: Path,
        *,
        gascity_enabled: bool,
    ) -> None:
        """Workspace association never changes the storage-neutral activation."""
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        u.Tests.write_standalone_workspace_manifest(
            root,
            "fixture-project",
            gascity_enabled=gascity_enabled,
        )

        rendered_envrc = u.Tests.planned_text(
            u.Tests.governed_project_plan(root),
            ".envrc",
        )

        if rendered_envrc is None:
            pytest.fail("a governed identity must produce the managed .envrc")
        tm.that(rendered_envrc, lacks="AGENTS_GAS_CITY_ROOT")
        tm.that(rendered_envrc, lacks="BEADS_DOLT_")

    def test_metadata_projection_preserves_a_minted_ledger_identity(
        self,
        tmp_path: Path,
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
            '{"backend":"dolt"}\n',
            encoding="utf-8",
        )

        rendered = u.Tests.planned_text(
            u.Tests.governed_project_plan(root),
            c.Infra.BEADS_METADATA_RELPATH,
        )
        if rendered is None:
            pytest.fail("local identity must produce the Beads marker")
        metadata = u.Tests.json_payload(rendered)
        tm.that(metadata["project_id"], eq=minted)
        tm.that(
            set(metadata),
            eq={"database", "backend", "dolt_mode", "dolt_database", "project_id"},
        )
        tm.that(list(metadata), eq=sorted(metadata))

    def test_projection_preserves_the_manual_identity_input(
        self,
        tmp_path: Path,
    ) -> None:
        """Test projection preserves the manual identity input."""
        root = self._project(
            tmp_path / "project",
            database="project_database",
            issue_prefix="project-prefix",
        )
        identity = root / "config" / "beads.yaml"
        before = identity.read_bytes()

        _ = u.Tests.governed_project_plan(root)

        tm.that(identity.read_bytes(), eq=before)

    @staticmethod
    def test_beads_gate_lock_is_tolerated_runtime_state(tmp_path: Path) -> None:
        """The bd gate serialization marker never fails composed verification.

        The bd client writes ``dolt.gate.lock`` beside the ledger on every gate
        transaction — the same projection class as ``.exclusive-lock`` and
        ``.sync.lock``. A composed project whose member holds one (live or left
        by a dead holder) must still verify; an actual stranger file must not.
        """
        route = tmp_path / c.Infra.BEADS_DIRNAME
        route.mkdir(mode=0o700)
        (route / Path(c.Infra.BEADS_CONFIG_RELPATH).name).write_text(
            "{}\n",
            encoding="utf-8",
        )
        (route / "dolt.gate.lock").write_text("", encoding="utf-8")

        state = FlextInfraCodegenConformBeadsRoutes.beads_route_state(tmp_path)

        tm.that(state.failure, eq=False)
        tm.that(state.value, eq=True)

        (route / "stranger.txt").write_text("unexpected\n", encoding="utf-8")

        broken = FlextInfraCodegenConformBeadsRoutes.beads_route_state(tmp_path)

        tm.that(broken.failure, eq=True)
        tm.that(broken.error is not None and "stranger.txt" in broken.error, eq=True)
