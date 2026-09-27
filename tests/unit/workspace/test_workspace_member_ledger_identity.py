"""Workspace members must resolve one ledger without owning a second identity."""

from __future__ import annotations

import shutil
from pathlib import Path

from flext_tests import tm

from flext_infra import c, m
from flext_infra.workspace import FlextInfraWorkspaceDetector
from tests import t, u


class TestsFlextInfraWorkspaceMemberLedgerIdentity:
    """Prove parent and member identities remain in their own coordinates."""

    @staticmethod
    def _member_ledger_identity(member: Path) -> m.Infra.WorkspaceSpec:
        """Rewrite the member's ledger input and self-load its typed identity."""
        u.Tests.WorktreeFixture.write_beads_project(
            member,
            workspace="member-workspace",
            database="member-database",
            issue_prefix="member-prefix",
        )
        return tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(member))

    @staticmethod
    def _attach_member_to_workspace(tmp_path: Path) -> t.Pair[Path, Path]:
        """Create one governed, committed workspace/member checkout pair."""
        child_source = tmp_path / "child-source"
        u.Tests.WorktreeFixture.initialize_governed_project(
            child_source,
            "fixture-member",
            workspace="member-workspace",
            database="member-database",
            issue_prefix="member-prefix",
            beads_owner=False,
        )
        parent = tmp_path / "workspace"
        u.Tests.WorktreeFixture.initialize_governed_project(
            parent,
            "fixture-workspace",
            workspace="root-workspace",
            database="root-database",
            issue_prefix="root-prefix",
        )
        member = parent / "apps" / "member"
        shutil.copytree(child_source, member)
        u.Tests.WorktreeFixture.link_member_beads(
            member,
            parent,
            workspace_name="root-workspace",
            database="root-database",
            issue_prefix="root-prefix",
        )
        u.Tests.WorktreeFixture.attach_submodule(
            parent, member, distribution="fixture-member", relative_path="apps/member"
        )
        return member, parent

    def test_parent_preserves_member_commands_and_git_coordinates(
        self, tmp_path: Path
    ) -> None:
        """A member's commands survive composition without importing its topology."""
        member, parent = self._attach_member_to_workspace(tmp_path)
        observed = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(member))
        verb = m.Infra.MakeVerbSpec(name="charts", description="Render charts")
        dispatch = m.Infra.ScriptDispatchSpec(
            dispatcher="scripts/dispatch.py", roots=("scripts",)
        )
        declared = observed.repository.model_copy(
            update={
                "extra_verbs": (verb,),
                "script_dispatch": dispatch,
                "editable": False,
            }
        )
        manifest = m.Infra.WorkspaceManifestSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=declared.name,
            repository=declared,
        )
        tm.ok(
            u.Cli.yaml_dump(
                member / "config/workspace.yaml", manifest.model_dump(mode="json")
            )
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(parent))

        reference = workspace.subprojects[0]
        tm.that(reference.path, eq=Path("apps/member"))
        tm.that(reference.branch, eq=u.Tests.integration_branch(parent))
        tm.that(reference.editable, eq=True)
        tm.that(reference.extra_verbs, eq=(verb,))
        tm.that(reference.script_dispatch, eq=dispatch)
        tm.that(workspace.repository.extra_verbs, empty=True)

    def test_parent_rejects_invalid_member_command_manifest(
        self, tmp_path: Path
    ) -> None:
        """Selected command metadata must pass the manifest's typed contract."""
        member, parent = self._attach_member_to_workspace(tmp_path)
        member_manifest = member / "config/workspace.yaml"
        member_manifest.parent.mkdir(parents=True, exist_ok=True)
        member_manifest.write_text(
            "version: parent-must-not-parse-member-manifest\n", encoding="utf-8"
        )

        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(parent)
        tm.that(workspace.failure, eq=True)
        tm.that(str(workspace.error), has="workspace manifest model validation")

    def test_submodule_self_load_accepts_an_independent_ledger(
        self, tmp_path: Path
    ) -> None:
        """A member owning a real ledger directory keeps its own identity."""
        member, _ = self._attach_member_to_workspace(tmp_path)
        member_beads = member / ".beads"
        member_beads.unlink()
        member_beads.mkdir()
        workspace = self._member_ledger_identity(member)
        tm.that(workspace.beads.workspace, eq="member-workspace")
        tm.that(workspace.beads.database, eq="member-database")

    def test_submodule_self_load_accepts_config_only_ledger(
        self, tmp_path: Path
    ) -> None:
        """A member's config remains sufficient when it owns no ledger directory."""
        member, _ = self._attach_member_to_workspace(tmp_path)
        (member / ".beads").unlink()
        workspace = self._member_ledger_identity(member)
        tm.that(workspace.beads.workspace, eq="member-workspace")

    def test_submodule_self_load_rejects_a_divergent_linked_identity(
        self, tmp_path: Path
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


__all__: t.VariadicTuple[str] = ()
