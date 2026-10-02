"""Repository-local topology and Beads identity contracts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m, t
from flext_infra.codegen import FlextInfraCodegenConform
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from tests import u


class TestsFlextInfraRepositoryLocalTopology:
    """Prove each repository owns its topology and typed Beads identity."""

    @staticmethod
    def _beads_fixture_root(tmp_path: Path, directory: str) -> Path:
        """Initialize one governed checkout carrying the canonical Beads identity.

        Returns:
            The resulting ``Path``.

        """
        return u.Tests.WorktreeFixture.governed_workspace(
            tmp_path,
            directory,
            distribution=f"fixture-{directory}",
            workspace="fixture-workspace",
            database="fixture-database",
            issue_prefix="fixture-prefix",
        )

    @staticmethod
    def _beads_fixture_payload() -> t.MutableMappingKV[str, t.JsonValue]:
        """Return the canonical Beads identity payload a fixture checkout declares.

        Returns:
            The canonical Beads identity payload a fixture checkout declares.

        """
        return {
            "version": 1,
            "workspace": "fixture-workspace",
            "database": "fixture-database",
            "issue_prefix": "fixture-prefix",
        }

    @staticmethod
    def _self_named_governed_root(tmp_path: Path, directory: str) -> Path:
        """Initialize one governed checkout whose identity derives from its directory.

        Returns:
            The resulting ``Path``.

        """
        name = f"fixture-{directory}"
        return u.Tests.WorktreeFixture.governed_workspace(
            tmp_path,
            directory,
            distribution=name,
            workspace=name,
            database=name.replace("-", "_"),
            issue_prefix=name,
        )

    def test_selected_workspace_manifest_owns_repository_policy(
        self,
        tmp_path: Path,
    ) -> None:
        """Preserve typed local policy after reconciling it with observed Git."""
        root = self._self_named_governed_root(tmp_path, "manifest-policy")
        observed = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        manifest: t.MutableMappingKV[str, t.JsonValue] = {
            "version": c.Infra.WORKSPACE_MANIFEST_VERSION,
            "name": observed.name,
            "repository": {
                **observed.repository.model_dump(mode="json"),
                "kind": c.Infra.ProjectKind.THIRD_PARTY_FORK.value,
                "uv_link_mode": "clone",
            },
        }
        tm.ok(
            u.Cli.yaml_dump(
                root / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME,
                manifest,
            ),
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(workspace.repository.kind, eq=c.Infra.ProjectKind.THIRD_PARTY_FORK)
        tm.that(workspace.repository.uv_link_mode, eq="clone")

    def test_declared_beads_free_repository_loads_without_ledger(
        self,
        tmp_path: Path,
    ) -> None:
        """An explicit standalone policy needs no Beads or Gas City identity."""
        root = self._self_named_governed_root(tmp_path, "without-beads")
        observed = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        manifest: t.MutableMappingKV[str, t.JsonValue] = {
            "version": c.Infra.WORKSPACE_MANIFEST_VERSION,
            "name": observed.name,
            "repository": observed.repository.model_dump(mode="json"),
            "repository_policy_overlays": [
                {
                    "project": observed.repository.distribution,
                    "beads_enabled": False,
                    "gascity_enabled": False,
                },
            ],
        }
        tm.ok(
            u.Cli.yaml_dump(
                root / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME,
                manifest,
            ),
        )
        (root / "config" / c.Infra.BEADS_CONFIG_FILENAME).unlink()
        ledger = root / c.Infra.BEADS_DIRNAME
        if ledger.is_dir():
            shutil.rmtree(ledger)
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        tm.that(workspace.name, eq=observed.name)
        tm.that(workspace.beads, none=True)
        tm.that(workspace.gascity_enabled, eq=False)

    def test_overlay_omitting_beads_policy_keeps_beads_enabled(
        self,
        tmp_path: Path,
    ) -> None:
        """An overlay that omits beads_enabled resolves like no overlay at all."""
        root = self._self_named_governed_root(tmp_path, "overlay-default-beads")
        observed = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        manifest: t.MutableMappingKV[str, t.JsonValue] = {
            "version": c.Infra.WORKSPACE_MANIFEST_VERSION,
            "name": observed.name,
            "repository": observed.repository.model_dump(mode="json"),
            "repository_policy_overlays": [
                {"project": observed.repository.distribution, "ci_enabled": False},
            ],
        }
        tm.ok(
            u.Cli.yaml_dump(
                root / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME,
                manifest,
            ),
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(workspace.beads, eq=observed.beads)
        tm.that(workspace.gascity_enabled, eq=observed.gascity_enabled)

    def test_selected_workspace_manifest_rejects_git_contradiction(
        self,
        tmp_path: Path,
    ) -> None:
        """Fail closed when selected declarative identity disagrees with Git."""
        root = self._self_named_governed_root(tmp_path, "manifest-contradiction")
        _ = u.Tests.WorktreeFixture.override_repository_manifest(
            root,
            {"distribution": "different-distribution"},
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="workspace manifest contradicts Git")
        tm.that(result.error or "", has="distribution")

    @pytest.mark.parametrize(
        ("overrides", "missing_field", "expected_error"),
        [
            pytest.param({"version": 4}, None, "version", id="unknown-version"),
            pytest.param(
                {"unknown_contract": True},
                None,
                "unknown_contract",
                id="unknown-field",
            ),
            pytest.param({}, "name", "name", id="missing-name"),
        ],
    )
    def test_selected_workspace_manifest_validates_the_complete_document(
        self,
        tmp_path: Path,
        overrides: t.MappingKV[str, t.JsonValue],
        missing_field: str | None,
        expected_error: str,
    ) -> None:
        """Reject incompatible or partial manifest envelopes before policy use."""
        root = self._self_named_governed_root(tmp_path, expected_error)
        observed = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        payload: t.MutableMappingKV[str, t.JsonValue] = {
            "version": c.Infra.WORKSPACE_MANIFEST_VERSION,
            "name": f"fixture-{expected_error}",
            "repository": observed.repository.model_dump(mode="json"),
        }
        payload.update(overrides)
        if missing_field is not None:
            del payload[missing_field]
        tm.ok(
            u.Cli.yaml_dump(
                root / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME,
                payload,
            ),
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="workspace manifest model validation")
        tm.fail(result, has=expected_error)

    @staticmethod
    def test_loads_typed_beads_identity_from_the_repository_itself(
        tmp_path: Path,
    ) -> None:
        """Parse required identity and project extensions into one typed model."""
        root = tmp_path / "project"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-project",
            workspace="fixture-workspace",
            database="fixture-database",
            issue_prefix="fixture-prefix",
            custom_issue_types=("incident",),
        )

        beads = tm.ok(FlextInfraWorkspaceDetector.load_beads_spec(root))
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(type(beads), eq=m.Infra.BeadsProjectSpec)
        tm.that(
            beads.model_dump(mode="json"),
            eq={
                "version": 1,
                "workspace": "fixture-workspace",
                "database": "fixture-database",
                "issue_prefix": "fixture-prefix",
                "custom_issue_types": ["incident"],
            },
        )
        tm.that(workspace.beads, eq=beads)

    @pytest.mark.parametrize(
        "missing_field",
        ["version", "workspace", "database", "issue_prefix"],
    )
    def test_beads_identity_requires_every_declared_field(
        self,
        tmp_path: Path,
        missing_field: str,
    ) -> None:
        """Reject partial identity instead of inferring a value elsewhere."""
        root = self._beads_fixture_root(tmp_path, missing_field)
        payload = self._beads_fixture_payload()
        del payload[missing_field]
        tm.ok(u.Cli.yaml_dump(root / "config" / "beads.yaml", payload))

        result = FlextInfraWorkspaceDetector.load_beads_spec(root)

        tm.fail(result, has=missing_field)

    @pytest.mark.parametrize(
        ("field", "invalid_value"),
        [
            pytest.param("version", 2, id="unknown-version"),
            pytest.param("workspace", "", id="empty-workspace"),
            pytest.param("database", ["not", "a", "scalar"], id="database-list"),
            pytest.param("issue_prefix", None, id="null-prefix"),
            pytest.param(
                "custom_issue_types",
                ["incident", "incident"],
                id="duplicate-custom-type",
            ),
        ],
    )
    def test_beads_identity_rejects_malformed_values(
        self,
        tmp_path: Path,
        field: str,
        invalid_value: t.JsonValue,
    ) -> None:
        """Fail closed on values outside the typed local contract."""
        root = self._beads_fixture_root(tmp_path, field)
        payload = self._beads_fixture_payload()
        payload["custom_issue_types"] = list[t.JsonValue]()
        payload[field] = invalid_value
        tm.ok(u.Cli.yaml_dump(root / "config" / "beads.yaml", payload))

        result = FlextInfraWorkspaceDetector.load_beads_spec(root)

        tm.fail(result, has=field)

    @staticmethod
    def test_gitmodules_without_governed_members_remains_standalone(
        tmp_path: Path,
    ) -> None:
        """Vendored or empty Git topology does not create a FLEXT workspace."""
        root = tmp_path / "workspace"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-workspace",
            workspace="fixture-workspace",
            database="fixture-database",
            issue_prefix="fixture-prefix",
        )
        u.Tests.WorktreeFixture.write_gitmodules(root, ())

        mode = tm.ok(FlextInfraWorkspaceDetector().detect(root))
        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(root))

        tm.that(mode, eq=c.Infra.MakeProfile.STANDALONE)
        tm.that(target.make_profile, eq=c.Infra.MakeProfile.STANDALONE)

    @staticmethod
    def test_parent_gitmodules_never_classifies_or_governs_a_child(
        tmp_path: Path,
    ) -> None:
        """Ignore every parent input when deriving one child repository."""
        parent = tmp_path / "parent"
        u.Tests.WorktreeFixture.initialize_governed_project(
            parent,
            "parent",
            workspace="parent-workspace",
            database="parent-database",
            issue_prefix="parent-prefix",
        )
        u.Tests.WorktreeFixture.write_gitmodules(parent, ("child",))
        child = parent / "child"
        u.Tests.WorktreeFixture.initialize_governed_project(
            child,
            "child",
            workspace="child-workspace",
            database="child-database",
            issue_prefix="child-prefix",
        )

        mode = tm.ok(FlextInfraWorkspaceDetector().detect(child))
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(child))
        resolved = tm.ok(
            u.Infra.git_show_toplevel(m.Infra.GitRepoRequest(repo_root=child)),
        ).repository_root

        tm.that(mode, eq=c.Infra.MakeProfile.STANDALONE)
        tm.that(workspace.repository.name, eq="child")
        tm.that(workspace.name, eq="child-workspace")
        tm.that(u.Tests.required_beads(workspace).workspace, eq="child-workspace")
        tm.that(workspace.subprojects, empty=True)
        tm.that(resolved, eq=child.resolve())

    @staticmethod
    def _attached_member(tmp_path: Path) -> Path:
        """Attach a governed member to a parent workspace and return its path.

        Returns:
            The resulting ``Path``.

        """
        child_source = tmp_path / "child-source"
        u.Tests.WorktreeFixture.initialize_governed_project(
            child_source,
            "fixture-member",
            workspace="member-workspace",
            database="member-database",
            issue_prefix="member-prefix",
            beads_owner=False,
        )
        parent = tmp_path / "parent"
        u.Tests.WorktreeFixture.initialize_governed_project(
            parent,
            "fixture-parent",
            workspace="parent-workspace",
            database="parent-database",
            issue_prefix="parent-prefix",
        )
        member = parent / "apps" / "member"
        shutil.copytree(child_source, member)
        # A composed project follows the workspace ledger through its own
        # declared identity. The ``.beads -> ../.beads`` link that used to
        # carry it is prohibited, and both conform and the detector reject it.
        u.Tests.WorktreeFixture.write_beads_project(
            member,
            workspace="parent-workspace",
            database="parent-database",
            issue_prefix="parent-prefix",
        )
        u.Tests.WorktreeFixture.attach_submodule(
            parent,
            member,
            distribution="fixture-member",
            relative_path="apps/member",
        )
        return member

    @staticmethod
    def _declare_members(
        root: Path,
        members: t.VariadicTuple[m.Infra.RepositoryRef],
    ) -> None:
        """Record ``members`` as the root manifest's declared member contracts."""
        (manifest,) = tm.ok(u.Infra.load_workspace_manifest(root))
        tm.ok(
            u.Cli.yaml_dump(
                u.Infra.workspace_manifest_path(root),
                manifest.model_copy(update={"members": members}).model_dump(
                    mode="json",
                ),
            ),
        )

    def test_root_generation_preserves_declared_members_without_checkouts(
        self,
        tmp_path: Path,
    ) -> None:
        """Root-only CI planning keeps declared topology without member checkouts."""
        member = self._attached_member(tmp_path)
        root = member.parents[1]
        before = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        self._declare_members(root, before.subprojects)
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        first = tm.ok(
            FlextInfraCodegenConform(repository_root=root, request=request).plan(
                request,
            ),
        )
        relative = member.relative_to(root).as_posix()
        # CI checks out the root alone: the member keeps its indexed gitlink
        # and an empty working directory, with no Git directory of its own.
        tm.ok(
            u.Cli.run_checked(
                (c.Infra.GIT, "submodule", "absorbgitdirs", "--", relative),
                cwd=root,
            ),
        )
        tm.ok(
            u.Cli.run_checked(
                (c.Infra.GIT, "submodule", "deinit", "-f", "--", relative),
                cwd=root,
            ),
        )

        after = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        second = tm.ok(
            FlextInfraCodegenConform(repository_root=root, request=request).plan(
                request,
            ),
        )

        tm.that(after.subprojects, eq=before.subprojects)
        tm.that(after.external_dependency_paths, empty=True)
        tm.that(second.repositories, eq=first.repositories)
        tm.that(second.files, eq=first.files)
        tm.that((member / c.PYPROJECT_FILENAME).exists(), eq=False)
        tm.that((member / c.Infra.GIT_DIR).exists(), eq=False)

    def test_declared_content_member_remains_governed_without_checkout(
        self,
        tmp_path: Path,
    ) -> None:
        """A content-only member's declared identity survives deinitialization."""
        member = self._attached_member(tmp_path)
        root = member.parents[1]
        before = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        declared = tuple(
            item.model_copy(update={"package": False}) for item in before.subprojects
        )
        self._declare_members(root, declared)
        relative = member.relative_to(root).as_posix()
        tm.ok(
            u.Cli.run_checked(
                (c.Infra.GIT, "submodule", "absorbgitdirs", "--", relative),
                cwd=root,
            ),
        )
        tm.ok(
            u.Cli.run_checked(
                (c.Infra.GIT, "submodule", "deinit", "-f", "--", relative),
                cwd=root,
            ),
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(workspace.subprojects, eq=declared)
        tm.that(workspace.external_dependency_paths, empty=True)
        tm.that((member / c.Infra.GIT_DIR).exists(), eq=False)

    def test_explicitly_unmanaged_content_member_remains_external(
        self,
        tmp_path: Path,
    ) -> None:
        """The .gitmodules opt-out takes precedence over a cataloged member."""
        member = self._attached_member(tmp_path)
        root = member.parents[1]
        before = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        self._declare_members(
            root,
            tuple(
                item.model_copy(update={"package": False})
                for item in before.subprojects
            ),
        )
        relative = member.relative_to(root).as_posix()
        tm.ok(
            u.Cli.run_checked(
                (
                    c.Infra.GIT,
                    "config",
                    "-f",
                    c.Infra.GITMODULES,
                    # The fixture names the section after the distribution.
                    "submodule.fixture-member.flext-managed",
                    "false",
                ),
                cwd=root,
            ),
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(workspace.subprojects, empty=True)
        tm.that(workspace.external_dependency_paths, has=Path(relative))

    def test_declared_member_url_must_match_its_gitmodules_url(
        self,
        tmp_path: Path,
    ) -> None:
        """Reject a manifest member whose URL identity differs from .gitmodules."""
        member = self._attached_member(tmp_path)
        root = member.parents[1]
        before = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        foreign_url = u.Tests.WorktreeFixture.governed_repository_url("foreign-member")
        self._declare_members(
            root,
            tuple(
                item.model_copy(update={"url": foreign_url})
                for item in before.subprojects
            ),
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="declared workspace member URL differs")

    def test_declared_member_checkout_without_pyproject_fails_closed(
        self,
        tmp_path: Path,
    ) -> None:
        """A present Git checkout of a declared package must carry its pyproject."""
        member = self._attached_member(tmp_path)
        root = member.parents[1]
        before = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        self._declare_members(root, before.subprojects)
        (member / c.PYPROJECT_FILENAME).unlink()

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="declared Python member checkout has no")

    def test_makefile_bootstrap_accepts_unprovisioned_declared_member(
        self,
        tmp_path: Path,
    ) -> None:
        """The setup Makefile can be rendered before a partial member is ready."""
        member = self._attached_member(tmp_path)
        root = member.parents[1]
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        self._declare_members(root, workspace.subprojects)
        (member / c.PYPROJECT_FILENAME).unlink()

        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
        )
        plan = tm.ok(
            FlextInfraCodegenConform(repository_root=root, request=request).plan(
                request,
            ),
        )

        planned = tuple(item.path for item in plan.files)
        for destination in c.Infra.MAKEFILE_BOOTSTRAP_DESTINATIONS:
            tm.that(planned, has=root / destination)
        tm.fail(
            FlextInfraWorkspaceDetector.load_workspace_spec(root),
            has="no pyproject",
        )

    def test_composed_self_load_records_its_workspace_checkout(
        self,
        tmp_path: Path,
    ) -> None:
        """A composed project keeps its own coordinates and the root ledger."""
        member = self._attached_member(tmp_path)

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(member))

        # Topology is the declared role alone; being checked out inside a
        # workspace right now is the Git fact carried by ``editable``.
        tm.that(workspace.repository.path, eq=Path())
        tm.that(workspace.repository.role, eq=c.Infra.MakeProfile.STANDALONE)
        tm.that(workspace.repository.editable, eq=True)
        tm.that(tm.not_none(workspace.beads).workspace, eq="parent-workspace")

    def test_composed_self_load_accepts_a_self_coordinate_manifest(
        self,
        tmp_path: Path,
    ) -> None:
        """One manifest loads standalone and inside a workspace unchanged."""
        member = self._attached_member(tmp_path)
        _ = u.Tests.WorktreeFixture.override_repository_manifest(
            member,
            {"uv_link_mode": "clone"},
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(member))

        tm.that(workspace.repository.path, eq=Path())
        tm.that(workspace.repository.role, eq=c.Infra.MakeProfile.STANDALONE)
        tm.that(workspace.repository.uv_link_mode, eq="clone")

    def test_standalone_rejects_a_manifest_that_claims_the_workspace_role(
        self,
        tmp_path: Path,
    ) -> None:
        """A checkout without .gitmodules cannot declare the workspace role."""
        root = self._self_named_governed_root(tmp_path, "manifest-role-claim")
        _ = u.Tests.WorktreeFixture.override_repository_manifest(
            root,
            {"role": c.Infra.MakeProfile.WORKSPACE},
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="role 'workspace' contradicts the observed topology")

    @staticmethod
    def test_workspace_members_inherit_a_single_ledger_identity(
        tmp_path: Path,
    ) -> None:
        """Reject member-local identities and retain exactly the root ledger."""
        root = tmp_path / "workspace"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-workspace",
            workspace="root-workspace",
            database="root-database",
            issue_prefix="root-prefix",
        )
        identities = {
            "fixture-alpha": ("alpha-workspace", "alpha-database", "alpha-prefix"),
            "fixture-beta": ("beta-workspace", "beta-database", "beta-prefix"),
        }
        for project_name, identity in identities.items():
            u.Tests.WorktreeFixture.initialize_governed_project(
                root / project_name,
                project_name,
                workspace=identity[0],
                database=identity[1],
                issue_prefix=identity[2],
                beads_owner=False,
            )
            u.Tests.WorktreeFixture.link_member_beads(
                root / project_name,
                root,
                workspace_name="root-workspace",
                database="root-database",
                issue_prefix="root-prefix",
            )
        u.Tests.WorktreeFixture.write_gitmodules(root, tuple(identities))

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(
            tuple(project.path.as_posix() for project in workspace.subprojects),
            eq=tuple(identities),
        )
        tm.that(u.Tests.required_beads(workspace).workspace, eq="root-workspace")
        for project_name in identities:
            beads = tm.ok(
                FlextInfraWorkspaceDetector.load_beads_spec(root / project_name),
            )
            tm.that(beads.workspace, eq="root-workspace")
            tm.that(beads.database, eq="root-database")
            tm.that(beads.issue_prefix, eq="root-prefix")
            tm.that((root / project_name / ".beads").is_symlink(), eq=True)

    @staticmethod
    def test_workspace_excludes_governed_non_python_gitlinks_from_codegen(
        tmp_path: Path,
    ) -> None:
        """Keep provider-owned services outside Python conformance ownership."""
        root = tmp_path / "workspace"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-workspace",
            workspace="root-workspace",
            database="root-database",
            issue_prefix="root-prefix",
        )
        python_project = "fixture-python"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root / python_project,
            python_project,
            workspace="python-workspace",
            database="python-database",
            issue_prefix="python-prefix",
            beads_owner=False,
        )
        u.Tests.WorktreeFixture.link_member_beads(
            root / python_project,
            root,
            workspace_name="root-workspace",
            database="root-database",
            issue_prefix="root-prefix",
        )
        service_project = "fixture-service"
        service_root = root / service_project
        service_root.mkdir()
        (service_root / "go.mod").write_text(
            "module github.com/flext-sh/fixture-service\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(
            service_root,
            origin_url=u.Tests.WorktreeFixture.governed_repository_url(service_project),
        )
        u.Tests.WorktreeFixture.write_gitmodules(
            root,
            (python_project, service_project),
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(
            tuple(project.path.as_posix() for project in workspace.subprojects),
            eq=(python_project,),
        )
        tm.that(workspace.external_dependency_paths, eq=(Path(service_project),))
        tm.that(
            FlextInfraWorkspaceDetector.workspace_analysis_exclusion_paths(workspace),
            eq=(Path(service_project),),
        )

    @staticmethod
    def test_invalid_repository_path_fails_closed(tmp_path: Path) -> None:
        """Return a typed failure for a path that is not a repository directory."""
        result = FlextInfraWorkspaceDetector().detect(tmp_path / "absent")

        tm.fail(result, has="not a directory")

    @staticmethod
    def test_repository_without_origin_fails_closed(tmp_path: Path) -> None:
        """Require an explicit origin before classifying provider ownership."""
        root = tmp_path / "without-origin"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "without-origin",
            workspace="without-origin",
            database="without_origin",
            issue_prefix="without-origin",
        )
        tm.ok(u.Cli.run_checked(["git", "remote", "remove", "origin"], cwd=root))

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="No item found with id origin")

    @pytest.mark.parametrize(
        ("missing_key", "expected_error"),
        [
            ("url", "Git submodule URL is missing"),
            ("branch", "Git submodule branch is missing"),
        ],
    )
    def test_gitmodule_requires_complete_contract(
        self,
        tmp_path: Path,
        missing_key: str,
        expected_error: str,
    ) -> None:
        """Reject a declared_repository entry without its exact URL or branch."""
        root = tmp_path / missing_key
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-workspace",
            workspace="fixture-workspace",
            database="fixture_workspace",
            issue_prefix="fixture-workspace",
        )
        provider = u.Tests.provider()
        fields = {
            "url": f"\turl = {provider.base_url}/fixture-child.git\n",
            "branch": f"\tbranch = {u.Tests.provider_branch()}\n",
        }
        fields.pop(missing_key)
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "fixture-child"]\n'
            "\tpath = fixture-child\n"
            f"{''.join(fields.values())}",
            encoding="utf-8",
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has=expected_error)

    @staticmethod
    def test_gitmodule_rejects_duplicate_paths(tmp_path: Path) -> None:
        """Reject two declarations that claim the same checkout path."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "duplicate")
        provider = u.Tests.provider()
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "first"]\n'
            "\tpath = fixture-child\n"
            f"\turl = {provider.base_url}/fixture-child.git\n"
            f"\tbranch = {u.Tests.provider_branch()}\n"
            '[submodule "second"]\n'
            "\tpath = fixture-child\n"
            f"\turl = {provider.base_url}/fixture-child.git\n"
            f"\tbranch = {u.Tests.provider_branch()}\n",
            encoding="utf-8",
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="duplicate Git submodule path")

    @staticmethod
    def test_gitmodule_rejects_malformed_configuration(tmp_path: Path) -> None:
        """Reject syntax that cannot define an exact submodule contract."""
        root = u.Tests.WorktreeFixture.governed_workspace(
            tmp_path,
            "malformed-gitmodules",
        )
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "unterminated"\npath = fixture-child\n',
            encoding="utf-8",
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="failed to read Git submodule declarations")

    @pytest.mark.parametrize("declared_path", ["../escape", "/absolute/escape"])
    def test_gitmodule_rejects_escaping_path(
        self,
        tmp_path: Path,
        declared_path: str,
    ) -> None:
        """Reject relative traversal and absolute checkout destinations."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "escaping-path")
        provider = u.Tests.provider()
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "fixture-child"]\n'
            f"\tpath = {declared_path}\n"
            f"\turl = {provider.base_url}/fixture-child.git\n"
            f"\tbranch = {u.Tests.provider_branch()}\n",
            encoding="utf-8",
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="invalid Git submodule path")

    @staticmethod
    def test_gitmodule_rejects_missing_checkout(tmp_path: Path) -> None:
        """Reject a governed declaration whose checkout is absent."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "missing-checkout")
        u.Tests.WorktreeFixture.write_gitmodules(root, ("fixture-child",))

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="governed subproject checkout is missing")

    @staticmethod
    def test_uninitialized_gitlink_does_not_borrow_parent_origin(
        tmp_path: Path,
    ) -> None:
        """Classify an indexed but uninitialized checkout as an external dependency."""
        root = u.Tests.WorktreeFixture.governed_workspace(
            tmp_path,
            "uninitialized-gitlink",
        )
        child_path = Path("fixture-child")
        u.Tests.WorktreeFixture.write_gitmodules(root, (child_path.as_posix(),))
        recorded = tm.ok(
            u.Cli.capture([c.Infra.GIT, "rev-parse", c.Infra.GIT_HEAD], cwd=root),
        ).strip()
        tm.ok(
            u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"160000,{recorded},{child_path.as_posix()}",
                ],
                cwd=root,
            ),
        )
        (root / child_path).mkdir()

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(workspace.subprojects, empty=True)
        tm.that(workspace.external_dependency_paths, eq=(child_path,))

    @staticmethod
    def test_gitmodule_rejects_provider_branch_divergence(tmp_path: Path) -> None:
        """Reject a governed checkout declared on another integration line."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "branch-divergence")
        u.Tests.WorktreeFixture.write_gitmodules(root, ("fixture-child",))
        gitmodules = root / c.Infra.GITMODULES
        gitmodules.write_text(
            gitmodules.read_text(encoding="utf-8").replace(
                u.Tests.provider_branch(),
                "unexpected-integration",
            ),
            encoding="utf-8",
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="branch differs from the workspace integration line")

    @staticmethod
    def test_declared_unmanaged_gitlink_classifies_as_external_dependency(
        tmp_path: Path,
    ) -> None:
        """Honor the .gitmodules overlay: flext-managed=false is never governed."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "overlay-external")
        (root / "external-fork").mkdir()
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "external-fork"]\n'
            "\tpath = external-fork\n"
            "\turl = https://github.com/foreign-owner/external-fork.git\n"
            "\tbranch = master\n"
            "\tflext-classification = external-fork\n"
            "\tflext-managed = false\n",
            encoding="utf-8",
        )
        # A root declaring submodules is a workspace; its manifest must agree.
        _ = u.Tests.write_workspace_manifest(
            root,
            "fixture-workspace",
            role=c.Infra.MakeProfile.WORKSPACE,
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(workspace.subprojects, empty=True)
        tm.that(workspace.external_dependency_paths, eq=(Path("external-fork"),))

    @staticmethod
    def test_gitmodule_accepts_the_published_integration_branch(
        tmp_path: Path,
    ) -> None:
        """Accept a governed checkout declared on the published integration line."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "integration-line")
        baseline = tm.ok(u.Cli.capture([c.Infra.GIT, "rev-parse", "HEAD"], cwd=root))
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "update-ref", "refs/remotes/origin/develop", baseline],
                cwd=root,
            ),
        )
        tm.ok(
            u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "update-ref",
                    "-d",
                    f"refs/remotes/origin/{u.Tests.provider_branch()}",
                ],
                cwd=root,
            ),
        )
        _ = u.Tests.WorktreeFixture.attach_member_child(root)
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "fixture-child"]\n'
            "\tpath = fixture-child\n"
            f"\turl = {u.Tests.WorktreeFixture.governed_repository_url('fixture-child')}\n"
            "\tbranch = develop\n",
            encoding="utf-8",
        )
        # A root declaring submodules is a workspace; its manifest must agree.
        _ = u.Tests.write_workspace_manifest(
            root,
            "fixture-workspace",
            role=c.Infra.MakeProfile.WORKSPACE,
        )

        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(
            [item.path.as_posix() for item in workspace.subprojects],
            eq=["fixture-child"],
        )

    @staticmethod
    def test_gitmodule_rejects_origin_url_divergence(tmp_path: Path) -> None:
        """Reject a checkout whose origin identity differs from its declaration."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "url-divergence")
        _ = u.Tests.WorktreeFixture.attach_member_child(root)
        provider = u.Tests.provider()
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "fixture-child"]\n'
            "\tpath = fixture-child\n"
            f"\turl = {provider.base_url}/different-child.git\n"
            f"\tbranch = {u.Tests.provider_branch()}\n",
            encoding="utf-8",
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="subproject origin differs from its .gitmodules URL")

    @staticmethod
    def test_gitmodule_rejects_unknown_provider_without_raw_url(
        tmp_path: Path,
    ) -> None:
        """Reject an unknown declared owner without leaking its raw URL."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "unknown-provider")
        # The detector requires the governed checkout before comparing origins.
        _ = u.Tests.WorktreeFixture.attach_member_child(root)
        raw_host_marker = "private-submodule-host"
        (root / c.Infra.GITMODULES).write_text(
            '[submodule "fixture-child"]\n'
            "\tpath = fixture-child\n"
            f"\turl = git@{raw_host_marker}:unknown-owner/fixture-child.git\n"
            f"\tbranch = {u.Tests.provider_branch()}\n",
            encoding="utf-8",
        )

        result = FlextInfraWorkspaceDetector.load_workspace_spec(root)

        tm.fail(result, has="subproject origin differs from its .gitmodules URL")
        tm.that(result.error or "", lacks=raw_host_marker)

    @staticmethod
    def test_detected_provider_identity_normalizes_the_git_suffix() -> None:
        """Accept equivalent provider URLs with or without the clone suffix."""
        suffixed = u.Tests.repository_ref("fixture-project")
        bare = suffixed.model_copy(update={"url": suffixed.url.removesuffix(".git")})

        first = tm.ok(u.Infra.repository_provider(suffixed))
        second = tm.ok(u.Infra.repository_provider(bare))

        tm.that(first, eq=second)
        tm.that(first.name, eq=u.Tests.provider().name)
        tm.that(first.organization, eq=u.Tests.provider().organization)
