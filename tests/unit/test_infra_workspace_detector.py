"""Tests for public, manifest-backed workspace mode detection."""

from __future__ import annotations

from pathlib import Path

from flext_infra import config
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_tests import tm
from tests import c, m, u


class TestsFlextInfraInfraWorkspaceDetector:
    """Exercise detection through real manifests and Git repositories."""

    # NOTE (multi-agent, mro-wkii.17.10 / agent: implement_topology_detector):
    # scenarios build real Git topology and assert only the detector's public result.

    @staticmethod
    def _repository(
        *, name: str, path: str, role: c.Infra.RepositoryRole, url: str | None = None
    ) -> m.Infra.RepositoryRef:
        """Build one typed manifest repository contract."""
        provider = config.Infra.codegen.providers[0]
        return m.Infra.RepositoryRef(
            name=name,
            distribution=name,
            provider=provider.name,
            url=url or f"{provider.base_url}/{name}.git",
            path=Path(path),
            role=role,
            state=c.Infra.RepositoryState.ACTIVE,
            checkout=(
                c.Infra.CheckoutKind.ROOT
                if role is c.Infra.RepositoryRole.WORKSPACE_ROOT
                else (
                    c.Infra.CheckoutKind.INDEPENDENT
                    if role is c.Infra.RepositoryRole.STANDALONE
                    else c.Infra.CheckoutKind.SUBMODULE
                )
            ),
            codegen=c.Infra.CodegenKind.CONFORM,
            package=role is not c.Infra.RepositoryRole.WORKSPACE_ROOT,
            editable=role is c.Infra.RepositoryRole.WORKSPACE_MEMBER,
            read_only=False,
        )

    @staticmethod
    def _write_manifest(
        repository_root: Path,
        repository: m.Infra.RepositoryRef,
        *,
        members: tuple[m.Infra.RepositoryRef, ...] = (),
        overlays: tuple[m.Infra.RepositoryPolicyOverlaySpec, ...] = (),
    ) -> None:
        """Write one schema-shaped manifest through the public YAML facade."""
        spec = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=repository.name,
            repository=repository,
            members=members,
            exclusions=(),
            repository_policy_overlays=overlays,
        )
        tm.ok(
            u.Cli.yaml_dump(
                repository_root / "config" / "workspace.yaml",
                spec.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude={"external_dependency_paths"},
                ),
            )
        )

    @staticmethod
    def _initialize_repository(repository_root: Path) -> None:
        """Create a real provider-baseline Git repository with one commit."""
        repository_root.mkdir(parents=True)
        baseline = config.Infra.codegen.providers[0].branch
        tm.ok(
            u.Cli.run_checked(
                ["git", "init", "-q", "-b", baseline], cwd=repository_root
            )
        )
        u.Tests.configure_git_identity(repository_root)
        (repository_root / "README.md").write_text("# Repository\n", encoding="utf-8")
        tm.ok(u.Cli.run_checked(["git", "add", "README.md"], cwd=repository_root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Initial commit"], cwd=repository_root
            )
        )

    @classmethod
    def _attached_member(cls, tmp_path: Path, *, declare_member: bool = True) -> Path:
        """Create a real Git superproject and checked-out submodule."""
        workspace_root = tmp_path / "workspace"
        source_root = tmp_path / "member-source"
        cls._initialize_repository(workspace_root)
        cls._initialize_repository(source_root)
        (source_root / "pyproject.toml").write_text(
            '[project]\nname = "flext-member"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        tm.ok(u.Cli.run_checked(["git", "add", "pyproject.toml"], cwd=source_root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Declare member metadata"],
                cwd=source_root,
            )
        )
        member_path = "members/flext-member"
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
                    config.Infra.codegen.providers[0].branch,
                    str(source_root),
                    member_path,
                ],
                cwd=workspace_root,
            )
        )
        member_root = workspace_root / member_path
        u.Tests.configure_git_identity(member_root)
        provider = config.Infra.codegen.providers[0]
        canonical_url = f"{provider.base_url}/flext-member.git"
        section = "submodule.members/flext-member"
        tm.ok(
            u.Cli.run_checked(
                ["git", "remote", "set-url", "origin", canonical_url], cwd=member_root
            )
        )
        tm.ok(
            u.Cli.run_checked(
                [
                    "git",
                    "config",
                    "--file",
                    ".gitmodules",
                    f"{section}.url",
                    canonical_url,
                ],
                cwd=workspace_root,
            )
        )
        root_repository = cls._repository(
            name="workspace-root", path=".", role=c.Infra.RepositoryRole.WORKSPACE_ROOT
        )
        declared_repository = cls._repository(
            name="flext-member",
            path=member_path,
            role=c.Infra.RepositoryRole.WORKSPACE_MEMBER,
            url=canonical_url,
        )
        local_repository = cls._repository(
            name="flext-member",
            path=".",
            role=c.Infra.RepositoryRole.WORKSPACE_MEMBER,
            url=canonical_url,
        )
        cls._write_manifest(
            workspace_root,
            root_repository,
            members=(declared_repository,) if declare_member else (),
        )
        cls._write_manifest(member_root, local_repository)
        return member_root

    def test_root_without_governed_gitlinks_is_standalone(self, tmp_path: Path) -> None:
        """Infer effective profile from live topology, not declared role metadata."""
        root_repository = self._repository(
            name="workspace-root", path=".", role=c.Infra.RepositoryRole.WORKSPACE_ROOT
        )
        self._write_manifest(tmp_path, root_repository)

        tm.ok(
            FlextInfraWorkspaceDetector().detect(tmp_path),
            eq=c.Infra.WorkspaceMode.STANDALONE,
        )

    def test_ancestor_gitmodules_does_not_attach_project(self, tmp_path: Path) -> None:
        """Ignore an ancestor .gitmodules file without real Git attachment."""
        project_root = tmp_path / "nested" / "project"
        project_root.mkdir(parents=True)
        (tmp_path / ".gitmodules").write_text("", encoding="utf-8")

        tm.ok(
            FlextInfraWorkspaceDetector().detect(project_root),
            eq=c.Infra.WorkspaceMode.STANDALONE,
        )

    def test_independent_member_clone_is_standalone(self, tmp_path: Path) -> None:
        """Classify an independently cloned member as standalone."""
        project_root = tmp_path / "flext-member"
        self._initialize_repository(project_root)
        member_repository = self._repository(
            name="flext-member", path=".", role=c.Infra.RepositoryRole.WORKSPACE_MEMBER
        )
        self._write_manifest(project_root, member_repository)

        tm.ok(
            FlextInfraWorkspaceDetector().detect(project_root),
            eq=c.Infra.WorkspaceMode.STANDALONE,
        )

    def test_declared_real_submodule_is_workspace_member(self, tmp_path: Path) -> None:
        """Classify a fully validated attached member as a workspace member."""
        member_root = self._attached_member(tmp_path)

        tm.ok(
            FlextInfraWorkspaceDetector().detect(member_root),
            eq=c.Infra.WorkspaceMode.WORKSPACE_MEMBER,
        )

    def test_feature_branch_at_gitlink_is_workspace_member(
        self, tmp_path: Path
    ) -> None:
        member_root = self._attached_member(tmp_path)
        tm.ok(
            u.Cli.run_checked(
                ["git", "switch", "-q", "-c", "feature/gitlink-validation"],
                cwd=member_root,
            )
        )

        tm.ok(
            FlextInfraWorkspaceDetector().detect(member_root),
            eq=c.Infra.WorkspaceMode.WORKSPACE_MEMBER,
        )

    def test_detached_head_at_gitlink_is_workspace_member(self, tmp_path: Path) -> None:
        member_root = self._attached_member(tmp_path)
        tm.ok(
            u.Cli.run_checked(
                ["git", "switch", "-q", "--detach", "HEAD"], cwd=member_root
            )
        )

        tm.ok(
            FlextInfraWorkspaceDetector().detect(member_root),
            eq=c.Infra.WorkspaceMode.WORKSPACE_MEMBER,
        )

    def test_member_head_different_from_gitlink_fails_closed(
        self, tmp_path: Path
    ) -> None:
        member_root = self._attached_member(tmp_path)
        (member_root / "member-change.txt").write_text("changed\n", encoding="utf-8")
        tm.ok(u.Cli.run_checked(["git", "add", "member-change.txt"], cwd=member_root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Member change"], cwd=member_root
            )
        )

    def test_unknown_submodule_path_fails_closed(self, tmp_path: Path) -> None:
        """An attached submodule absent from the parent manifest is standalone."""
        member_root = self._attached_member(tmp_path, declare_member=False)

        tm.ok(
            FlextInfraWorkspaceDetector().detect(member_root),
            eq=c.Infra.WorkspaceMode.STANDALONE,
        )

    def test_gitmodule_url_mismatch_fails_closed(self, tmp_path: Path) -> None:
        """Reject a Git submodule whose configured URL differs from the manifest."""
        member_root = self._attached_member(tmp_path)
        workspace_root = member_root.parents[1]
        tm.ok(
            u.Cli.run_checked(
                [
                    "git",
                    "config",
                    "--file",
                    ".gitmodules",
                    "submodule.members/flext-member.url",
                    "https://github.com/other-org/flext-member.git",
                ],
                cwd=workspace_root,
            )
        )

        tm.fail(
            FlextInfraWorkspaceDetector().detect(member_root),
            has="governed workspace member contract differs",
        )

    def test_gitmodule_branch_mismatch_fails_closed(self, tmp_path: Path) -> None:
        """Reject a Git submodule whose configured branch differs from the manifest."""
        member_root = self._attached_member(tmp_path)
        workspace_root = member_root.parents[1]
        tm.ok(
            u.Cli.run_checked(
                [
                    "git",
                    "config",
                    "--file",
                    ".gitmodules",
                    "submodule.members/flext-member.branch",
                    "release",
                ],
                cwd=workspace_root,
            )
        )

        tm.fail(
            FlextInfraWorkspaceDetector().detect(member_root),
            has="governed workspace member contract differs",
        )

    def test_malformed_parent_manifest_fails(self, tmp_path: Path) -> None:
        """Reject an attached member when the parent manifest is malformed."""
        member_root = self._attached_member(tmp_path)
        parent_manifest = member_root.parents[1] / "config" / "workspace.yaml"
        parent_manifest.write_text("version: malformed\n", encoding="utf-8")

        tm.fail(FlextInfraWorkspaceDetector().detect(member_root), has="workspace")

    def test_malformed_local_manifest_fails(self, tmp_path: Path) -> None:
        """Reject a malformed repository-local manifest."""
        manifest = tmp_path / "config" / "workspace.yaml"
        manifest.parent.mkdir()
        manifest.write_text("version: malformed\n", encoding="utf-8")

        tm.fail(FlextInfraWorkspaceDetector().detect(tmp_path), has="workspace")

    def test_execute_uses_workspace_root(self, tmp_path: Path) -> None:
        """Execute detection against the detector's configured workspace root."""
        tm.ok(
            FlextInfraWorkspaceDetector(workspace_root=tmp_path).execute(),
            eq=c.Infra.WorkspaceMode.STANDALONE,
        )

    def test_invalid_path_returns_failure(self) -> None:
        """Return a typed failure for an invalid filesystem path."""
        tm.fail(
            FlextInfraWorkspaceDetector().detect(Path("\0")),
            has="Workspace detection failed",
        )

    def test_manifestless_repo_derives_spec_from_catalog(self, tmp_path: Path) -> None:
        """Derive a generic minimal spec from the catalog when no manifest exists."""
        # mro-4gbp: the engine catalog declares only repositories it owns, so the
        # fixture is derived from whatever this engine publishes - never a
        # hardcoded name and never a downstream consumer.
        declared = u.Tests.repository_ref(config.Infra.name)
        (tmp_path / "pyproject.toml").write_text(
            f'[project]\nname = "{declared.name}"\nversion = "0.0.0"\n',
            encoding="utf-8",
        )
        spec = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(tmp_path))
        tm.that(spec.name, eq=declared.name)
        tm.that(spec.repository.role, eq=declared.role)
        tm.that(spec.version, eq=c.Infra.WORKSPACE_MANIFEST_VERSION)

    def test_manifestless_repo_derives_its_own_identity(self, tmp_path: Path) -> None:
        """Derive a manifest-less project from itself, with no catalog lookup."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "not-a-declared-flext-project"\nversion = "0.0.0"\n',
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(tmp_path)

        spec = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(tmp_path))

        tm.that(spec.name, eq="not-a-declared-flext-project")

    def test_manifested_repo_absent_from_catalog_loads_spec(
        self, tmp_path: Path
    ) -> None:
        """Load a valid manifest even when the project is absent from the catalog."""
        repository = self._repository(
            name="consumer-project",
            path=".",
            role=c.Infra.RepositoryRole.WORKSPACE_ROOT,
        )
        self._write_manifest(tmp_path, repository)

        spec = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(tmp_path))
        tm.that(spec.name, eq="consumer-project")
        tm.that(spec.repository.name, eq="consumer-project")

    def test_workspace_manifest_declares_task_lane_kind_policy(
        self, tmp_path: Path
    ) -> None:
        repository = self._repository(
            name="consumer-project",
            path=".",
            role=c.Infra.RepositoryRole.WORKSPACE_ROOT,
        )
        self._write_manifest(tmp_path, repository)

        spec = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(tmp_path))

        tm.that(spec.work.task_kind, eq=c.Infra.WorkKind.FEATURE)
        tm.that(spec.work.chore_kind, eq=c.Infra.WorkKind.FEATURE)

    def test_workspace_root_with_governed_member_is_workspace(
        self, tmp_path: Path
    ) -> None:
        """Classify a root owning a real governed member as the workspace."""
        member_root = self._attached_member(tmp_path)
        workspace_root = member_root.parents[1]

        tm.ok(
            FlextInfraWorkspaceDetector().detect(workspace_root),
            eq=c.Infra.WorkspaceMode.WORKSPACE,
        )

    def test_attached_standalone_marker_is_workspace_member(
        self, tmp_path: Path
    ) -> None:
        """Classify a repo declaring ``[tool.flext.workspace] attached`` as member."""
        project_root = tmp_path / "attached-standalone"
        self._initialize_repository(project_root)
        (project_root / "pyproject.toml").write_text(
            '[project]\nname = "attached-standalone"\nversion = "0.1.0"\n'
            "\n[tool.flext.workspace]\nattached = true\n",
            encoding="utf-8",
        )

        tm.ok(
            FlextInfraWorkspaceDetector().detect(project_root),
            eq=c.Infra.WorkspaceMode.WORKSPACE_MEMBER,
        )

    def test_pyproject_without_attached_marker_stays_standalone(
        self, tmp_path: Path
    ) -> None:
        """Keep a repo without the attached opt-in marker standalone."""
        project_root = tmp_path / "independent"
        self._initialize_repository(project_root)
        (project_root / "pyproject.toml").write_text(
            '[project]\nname = "independent"\nversion = "0.1.0"\n', encoding="utf-8"
        )

        tm.ok(
            FlextInfraWorkspaceDetector().detect(project_root),
            eq=c.Infra.WorkspaceMode.STANDALONE,
        )

    def test_aggregator_gitmodules_without_toolchain_is_standalone(
        self, tmp_path: Path
    ) -> None:
        """Never promote an aggregator with .gitmodules but no FLEXT toolchain."""
        project_root = tmp_path / "aggregator"
        self._initialize_repository(project_root)
        (project_root / ".gitmodules").write_text(
            '[submodule "vendored"]\n'
            "\tpath = vendored\n"
            "\turl = https://github.com/other-org/vendored.git\n",
            encoding="utf-8",
        )
        (project_root / "pyproject.toml").write_text(
            '[project]\nname = "foreign-aggregator"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )

        tm.ok(
            FlextInfraWorkspaceDetector().detect(project_root),
            eq=c.Infra.WorkspaceMode.STANDALONE,
        )

    def test_toolchain_owner_with_branchless_gitlink_fails_closed(
        self, tmp_path: Path
    ) -> None:
        """Fail closed when a declared gitlink names no branch to derive from."""
        project_root = tmp_path / "toolchain-owner"
        self._initialize_repository(project_root)
        (project_root / ".gitmodules").write_text(
            '[submodule "vendored"]\n'
            "\tpath = vendored\n"
            "\turl = https://github.com/other-org/vendored.git\n",
            encoding="utf-8",
        )
        (project_root / "pyproject.toml").write_text(
            '[project]\nname = "foreign-aggregator"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        infra_repository = u.Tests.repository_ref(config.Infra.name)
        toolchain_marker = project_root / infra_repository.path / c.Infra.BASE_MK
        toolchain_marker.parent.mkdir(parents=True, exist_ok=True)
        toolchain_marker.write_text("# toolchain marker\n", encoding="utf-8")

        tm.fail(
            FlextInfraWorkspaceDetector().detect(project_root),
            has="Git submodule branch is missing: vendored",
        )

    def test_conform_target_member_overlay_never_promotes_beads(
        self, tmp_path: Path
    ) -> None:
        """Keep an attached member beadless even with an enabling overlay."""
        member_root = self._attached_member(tmp_path)
        workspace_root = member_root.parents[1]
        provider = config.Infra.codegen.providers[0]
        canonical_url = f"{provider.base_url}/flext-member.git"
        self._write_manifest(
            workspace_root,
            self._repository(
                name="workspace-root",
                path=".",
                role=c.Infra.RepositoryRole.WORKSPACE_ROOT,
            ),
            members=(
                self._repository(
                    name="flext-member",
                    path="members/flext-member",
                    role=c.Infra.RepositoryRole.WORKSPACE_MEMBER,
                    url=canonical_url,
                ),
            ),
            overlays=(
                m.Infra.RepositoryPolicyOverlaySpec(
                    project="flext-member", beads_enabled=True
                ),
            ),
        )

        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(member_root))
        tm.that(target.make_profile, eq=c.Infra.MakeProfile.WORKSPACE_MEMBER)
        tm.that(target.beads_enabled, eq=False)

    def test_conform_target_standalone_overlay_enables_beads(
        self, tmp_path: Path
    ) -> None:
        """Keep the overlay opt-in for an independent standalone repository."""
        project_root = tmp_path / "flext-alone"
        self._initialize_repository(project_root)
        (project_root / "pyproject.toml").write_text(
            '[project]\nname = "flext-alone"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        self._write_manifest(
            project_root,
            self._repository(
                name="flext-alone", path=".", role=c.Infra.RepositoryRole.STANDALONE
            ),
            overlays=(
                m.Infra.RepositoryPolicyOverlaySpec(
                    project="flext-alone", beads_enabled=True
                ),
            ),
        )

        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(project_root))
        tm.that(target.make_profile, eq=c.Infra.MakeProfile.STANDALONE)
        tm.that(target.beads_enabled, eq=True)

    def test_conform_target_member_is_not_attached_standalone(
        self, tmp_path: Path
    ) -> None:
        """Keep a manifest-declared member distinct from a marker-attached one.

        A manifest member resolves to its governing root, so it is never an
        attached standalone; a marker-attached repository owns its own
        workspace.yaml and resolves to itself. The two classes stay separate
        even though both now project routing-only Beads client config.
        """
        member_root = self._attached_member(tmp_path)

        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(member_root))
        tm.that(target.make_profile, eq=c.Infra.MakeProfile.WORKSPACE_MEMBER)
        tm.that(target.attached_standalone, eq=False)
        tm.that(target.beads_enabled, eq=False)

    def test_conform_target_member_is_not_routing_only(self, tmp_path: Path) -> None:
        member_root = self._attached_member(tmp_path)

        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(member_root))
        tm.that(target.make_profile, eq=c.Infra.MakeProfile.WORKSPACE_MEMBER)
        tm.that(target.routing_only, eq=False)
        tm.that(target.beads_enabled, eq=False)

    def test_external_member_worktree_inherits_governing_topology(
        self, tmp_path: Path
    ) -> None:
        member_root = self._attached_member(tmp_path)
        workspace_root = member_root.parents[1]
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=workspace_root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Declare workspace topology"],
                cwd=workspace_root,
            )
        )
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=member_root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Declare member topology"],
                cwd=member_root,
            )
        )
        lane = tmp_path / "external-member-lane"
        tm.ok(
            u.Cli.run_checked(
                ["git", "worktree", "add", "-q", "--detach", str(lane)], cwd=member_root
            )
        )

        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(lane))

        tm.that(
            tm.ok(FlextInfraWorkspaceDetector.resolve_workspace_root(lane)),
            eq=workspace_root.resolve(),
        )
        tm.that(target.root, eq=lane.resolve())
        tm.that(target.make_profile, eq=c.Infra.MakeProfile.WORKSPACE_MEMBER)
        tm.that(target.routing_only, eq=False)
        tm.that(target.beads_enabled, eq=False)

    def test_external_member_worktree_reads_lane_metadata(self, tmp_path: Path) -> None:
        """Keep dirty primary metadata outside the lane target boundary."""
        member_root = self._attached_member(tmp_path)
        workspace_root = member_root.parents[1]
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=workspace_root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Declare workspace topology"],
                cwd=workspace_root,
            )
        )
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=member_root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Declare member topology"],
                cwd=member_root,
            )
        )
        lane = tmp_path / "external-member-metadata-lane"
        tm.ok(
            u.Cli.run_checked(
                ["git", "worktree", "add", "-q", "--detach", str(lane)], cwd=member_root
            )
        )
        (member_root / "pyproject.toml").write_text(
            "invalid [[[ primary WIP", encoding="utf-8"
        )

        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(lane))

        tm.that(target.root, eq=lane.resolve())
        tm.that(target.canonical_project_name, eq="flext-member")

    def test_external_standalone_worktree_stays_standalone(
        self, tmp_path: Path
    ) -> None:
        primary = tmp_path / "standalone"
        self._initialize_repository(primary)
        (primary / "pyproject.toml").write_text(
            '[project]\nname = "flext-alone"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        self._write_manifest(
            primary,
            self._repository(
                name="flext-alone", path=".", role=c.Infra.RepositoryRole.STANDALONE
            ),
        )
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=primary))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Declare standalone topology"],
                cwd=primary,
            )
        )
        lane = tmp_path / "standalone-lane"
        tm.ok(
            u.Cli.run_checked(
                ["git", "worktree", "add", "-q", "--detach", str(lane)], cwd=primary
            )
        )

        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(lane))

        tm.that(target.make_profile, eq=c.Infra.MakeProfile.STANDALONE)
        tm.that(target.routing_only, eq=True)
        tm.that(target.beads_enabled, eq=True)

    def test_linked_worktree_without_resolvable_primary_fails_closed(
        self, tmp_path: Path
    ) -> None:
        primary = tmp_path / "primary"
        self._initialize_repository(primary)
        lane = tmp_path / "lane"
        tm.ok(
            u.Cli.run_checked(
                ["git", "worktree", "add", "-q", "--detach", str(lane)], cwd=primary
            )
        )
        primary.rename(tmp_path / "unavailable-primary")

        tm.fail(
            FlextInfraWorkspaceDetector.resolve_workspace_root(lane), has="resolve Git"
        )

    def test_conform_target_marker_repo_is_attached_standalone(
        self, tmp_path: Path
    ) -> None:
        """Classify a marker-attached standalone into the routing-config class."""
        project_root = tmp_path / "attached-standalone"
        self._initialize_repository(project_root)
        (project_root / "pyproject.toml").write_text(
            '[project]\nname = "attached-standalone"\nversion = "0.1.0"\n'
            "\n[tool.flext.workspace]\nattached = true\n",
            encoding="utf-8",
        )
        self._write_manifest(
            project_root,
            self._repository(
                name="attached-standalone",
                path=".",
                role=c.Infra.RepositoryRole.STANDALONE,
            ),
        )

        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(project_root))
        tm.that(target.make_profile, eq=c.Infra.MakeProfile.WORKSPACE_MEMBER)
        tm.that(target.attached_standalone, eq=True)
        tm.that(target.beads_enabled, eq=False)

    def test_persistent_state_artifacts_follow_make_profile(self) -> None:
        """Own persistent-state directories only at the workspace-root profile."""
        detector = FlextInfraWorkspaceDetector()
        ssot_owned = tuple(
            artifact
            for artifact in config.Infra.codegen.artifacts
            if artifact.name in c.Infra.PERSISTENT_STATE_ARTIFACT_NAMES
        )
        tm.that(bool(ssot_owned), eq=True)
        tm.that(
            detector.persistent_state_artifacts(c.Infra.MakeProfile.WORKSPACE_ROOT),
            eq=ssot_owned,
        )
        for profile in (
            c.Infra.MakeProfile.WORKSPACE_MEMBER,
            c.Infra.MakeProfile.STANDALONE,
        ):
            tm.that(detector.persistent_state_artifacts(profile), eq=())
        ssot_names = {artifact.name for artifact in config.Infra.codegen.artifacts}
        tm.that(c.Infra.PERSISTENT_STATE_ARTIFACT_NAMES.issubset(ssot_names), eq=True)

    def test_repository_is_governed_accepts_remote_url_without_git_suffix(self) -> None:
        """CI remotes may omit ``.git``; governance must still match provider org."""
        provider = config.Infra.codegen.providers[0]
        with_suffix = self._repository(
            name="flext-infra",
            path=".",
            role=c.Infra.RepositoryRole.STANDALONE,
            url=f"{provider.base_url}/flext-infra.git",
        )
        without_suffix = self._repository(
            name="flext-infra",
            path=".",
            role=c.Infra.RepositoryRole.STANDALONE,
            url=f"{provider.base_url}/flext-infra",
        )
        tm.that(
            FlextInfraWorkspaceDetector.repository_is_governed(with_suffix, provider),
            eq=True,
        )
        tm.that(
            FlextInfraWorkspaceDetector.repository_is_governed(
                without_suffix, provider
            ),
            eq=True,
        )
