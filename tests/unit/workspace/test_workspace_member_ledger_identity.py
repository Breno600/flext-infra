"""Workspace members must resolve one ledger without owning a second identity.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra.workspace import FlextInfraWorkspaceDetector
from tests import c, m, t, u


class TestsFlextInfraWorkspaceMemberLedgerIdentity:
    """Prove parent and member identities remain in their own coordinates."""

    @staticmethod
    @pytest.mark.parametrize("root_produces_activation", [False, True])
    @pytest.mark.parametrize("member_produces_activation", [False, True])
    def test_manifest_load_preserves_each_activation_producer(
        tmp_path: Path,
        *,
        root_produces_activation: bool,
        member_produces_activation: bool,
    ) -> None:
        """Load both declared command boundaries without losing typed fields."""
        root_verb = m.Infra.MakeVerbSpec(
            name="fixture-runtime",
            description="Produce the root activation inputs",
            produces_activation=root_produces_activation,
        )
        member_verb = m.Infra.MakeVerbSpec(
            name="fixture-runtime",
            description="Produce the member activation inputs",
            produces_activation=member_produces_activation,
        )
        repository = u.Tests.repository_ref(
            "fixture-workspace",
            role=c.Infra.MakeProfile.WORKSPACE,
        ).model_copy(update={"extra_verbs": (root_verb,)})
        member = u.Tests.repository_ref(
            "fixture-member",
            path=Path("members/fixture-member"),
        ).model_copy(update={"extra_verbs": (member_verb,)})
        project = u.Tests.project_spec(repository.distribution)
        declaration = m.Infra.WorkspaceManifestSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=repository.name,
            repository=repository,
            project=project,
            members=(member,),
        )
        manifest = u.Infra.workspace_manifest_path(tmp_path)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        tm.ok(
            u.Cli.yaml_dump(
                manifest,
                declaration.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude_computed_fields=True,
                ),
            ),
        )

        loaded = tm.ok(u.Infra.load_workspace_manifest(tmp_path))

        tm.that(loaded, len=1)
        tm.that(loaded[0].repository.extra_verbs, eq=(root_verb,))
        tm.that(loaded[0].members, len=1)
        tm.that(loaded[0].members[0].extra_verbs, eq=(member_verb,))

    @staticmethod
    def _member_ledger_identity(member: Path) -> m.Infra.WorkspaceSpec:
        """Rewrite the member's ledger input and self-load its typed identity.

        Returns:
            The resulting ``m.Infra.WorkspaceSpec``.

        """
        u.Tests.WorktreeFixture.write_beads_project(
            member,
            workspace="member-workspace",
            database="member-database",
            issue_prefix="member-prefix",
        )
        return tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(member))

    @staticmethod
    def _attach_member_to_workspace(tmp_path: Path) -> t.Pair[Path, Path]:
        """Create one governed, committed workspace/member checkout pair.

        Returns:
            The resulting ``t.Pair[Path, Path]``.

        """
        parent = tmp_path / "workspace"
        member = u.Tests.WorktreeFixture.copied_member(
            parent,
            "fixture-workspace",
            workspace="root-workspace",
            database="root-database",
            issue_prefix="root-prefix",
        )
        u.Tests.WorktreeFixture.link_member_beads(
            member,
            parent,
            workspace_name="root-workspace",
            database="root-database",
            issue_prefix="root-prefix",
        )
        u.Tests.WorktreeFixture.attach_submodule(
            parent,
            member,
            distribution="fixture-member",
            relative_path="apps/member",
        )
        return member, parent

    def test_parent_preserves_member_commands_and_git_coordinates(
        self,
        tmp_path: Path,
    ) -> None:
        """A member's commands survive composition without importing its topology."""
        member, parent = self._attach_member_to_workspace(tmp_path)
        observed = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(member))
        verb = m.Infra.MakeVerbSpec(name="charts", description="Render charts")
        dispatch = m.Infra.ScriptDispatchSpec(
            dispatcher="scripts/dispatch.py",
            roots=("scripts",),
        )
        declared = observed.repository.model_copy(
            update={
                "extra_verbs": (verb,),
                "script_dispatch": dispatch,
                "editable": False,
            },
        )
        manifest = m.Infra.WorkspaceManifestSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=declared.name,
            repository=declared,
        )
        tm.ok(
            u.Cli.yaml_dump(
                member / "config/workspace.yaml",
                manifest.model_dump(mode="json"),
            ),
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(parent))

        reference = workspace.subprojects[0]
        tm.that(reference.path, eq=Path("apps/member"))
        tm.that(reference.editable, eq=True)
        tm.that(reference.extra_verbs, eq=(verb,))
        tm.that(reference.script_dispatch, eq=dispatch)
        tm.that(workspace.repository.extra_verbs, empty=True)

    def test_parent_rejects_invalid_member_command_manifest(
        self,
        tmp_path: Path,
    ) -> None:
        """Selected command metadata must pass the manifest's typed contract."""
        member, parent = self._attach_member_to_workspace(tmp_path)
        member_manifest = member / "config/workspace.yaml"
        member_manifest.parent.mkdir(parents=True, exist_ok=True)
        member_manifest.write_text(
            "version: parent-must-not-parse-member-manifest\n",
            encoding="utf-8",
        )

        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(parent)
        tm.that(workspace.failure, eq=True)
        tm.that(str(workspace.error), has="workspace manifest model validation")

    def test_submodule_self_load_accepts_an_independent_ledger(
        self,
        tmp_path: Path,
    ) -> None:
        """A member owning a real ledger directory keeps its own identity."""
        member, _ = self._attach_member_to_workspace(tmp_path)
        member_beads = member / ".beads"
        member_beads.unlink()
        member_beads.mkdir()
        workspace = self._member_ledger_identity(member)
        beads = tm.not_none(workspace.beads)
        tm.that(beads.workspace, eq="member-workspace")
        tm.that(beads.database, eq="member-database")

    def test_submodule_self_load_accepts_config_only_ledger(
        self,
        tmp_path: Path,
    ) -> None:
        """A member's config remains sufficient when it owns no ledger directory."""
        member, _ = self._attach_member_to_workspace(tmp_path)
        (member / ".beads").unlink()
        workspace = self._member_ledger_identity(member)
        tm.that(tm.not_none(workspace.beads).workspace, eq="member-workspace")

    def test_submodule_self_load_rejects_a_divergent_linked_identity(
        self,
        tmp_path: Path,
    ) -> None:
        """A linked member cannot self-authorize a second ledger."""
        member, _ = self._attach_member_to_workspace(tmp_path)
        u.Tests.WorktreeFixture.write_beads_project(
            member,
            workspace="rogue-workspace",
            database="rogue-database",
            issue_prefix="rogue-prefix",
        )

        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(member)

        tm.that(workspace.failure, eq=True)
        tm.that(str(workspace.error), has="member Beads routing identity differs")
        tm.that(str(workspace.error), has="rogue-workspace")
