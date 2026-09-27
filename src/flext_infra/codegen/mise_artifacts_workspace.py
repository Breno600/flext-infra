"""Stable topology and coherent state snapshots for Mise publication."""

from __future__ import annotations

import stat
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r

from .. import c, m, u
from ..workspace import FlextInfraWorkspaceDetector
from ._mise_artifacts_files import FlextInfraMiseArtifactsFiles as files

if TYPE_CHECKING:
    from .. import p, t


class FlextInfraMiseWorkspacePlanner:
    """Resolve layout once, then snapshot mutable inputs only under the lock."""

    def __init__(self, owner: p.Infra.MiseArtifactsOwner) -> None:
        """Initialize workspace planning for the configured artifact owner."""
        self._owner = owner

    def scope_identity(self) -> p.Result[m.Infra.GitIdentityReport]:
        """Resolve the physical Git identity that owns generation coordination."""
        requested = self._owner.repository_root.expanduser().absolute()
        physical = self._physical_directory(requested)
        if physical.failure:
            return r[m.Infra.GitIdentityReport].from_failure(physical)
        identity = self._exact_git_identity(requested)
        if identity.failure:
            return identity
        if not identity.value.is_attached_submodule:
            return identity
        superproject_root = identity.value.superproject_root
        if superproject_root is None:
            return r[m.Infra.GitIdentityReport].fail(
                f"Git submodule has no Mise coordination root: {requested}"
            )
        scope_root = superproject_root.expanduser().absolute()
        # A linked worktree nested under the superproject directory is not the
        # superproject's gitlink checkout: it coordinates through its own
        # per-worktree Git directory, never the superproject's shared journal.
        gitlinks = u.Infra.git_index_gitlink_paths(scope_root)
        if gitlinks.failure:
            return r[m.Infra.GitIdentityReport].from_failure(gitlinks)
        member = identity.value.repo_root.relative_to(superproject_root)
        if member.as_posix() not in gitlinks.value:
            return identity
        physical_scope = self._physical_directory(scope_root)
        if physical_scope.failure:
            return r[m.Infra.GitIdentityReport].from_failure(physical_scope)
        return self._exact_git_identity(scope_root)

    def scope_root(self) -> p.Result[Path]:
        """Return the authenticated generation coordination root."""
        identity = self.scope_identity()
        if identity.failure:
            return r[Path].from_failure(identity)
        return r[Path].ok(identity.value.repo_root)

    @staticmethod
    def _exact_git_identity(requested: Path) -> p.Result[m.Infra.GitIdentityReport]:
        """Reject Git parent discovery when the requested path is not its root.

        # Why: delegates to the promoted `u.Infra.exact_worktree_root` owner
        # (codegen `init` reuses the same exact-root contract) instead of
        # duplicating the check locally.
        """
        return u.Infra.exact_worktree_root(requested)

    def layout(
        self, scope_root: Path | None = None, *, transaction_id: str | None = None
    ) -> p.Result[m.Infra.MiseToolchainWorkspaceLayout]:
        """Resolve governed topology after the stable workspace lock is held."""
        requested = self._owner.repository_root.expanduser().absolute()
        resolved_scope = (
            self.scope_root() if scope_root is None else r[Path].ok(scope_root)
        )
        if resolved_scope.failure:
            return r[m.Infra.MiseToolchainWorkspaceLayout].from_failure(resolved_scope)
        scope_root = resolved_scope.value
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(scope_root)
        if workspace.failure:
            return r[m.Infra.MiseToolchainWorkspaceLayout].from_failure(workspace)
        if requested != scope_root and not any(
            (scope_root / project.path).absolute() == requested
            for project in workspace.value.subprojects
        ):
            return r[m.Infra.MiseToolchainWorkspaceLayout].fail(
                f"Git submodule is absent from governed workspace: {requested}"
            )
        selectors = (
            ".",
            *(project.path.as_posix() for project in workspace.value.subprojects),
        )
        return self.layout_from_selectors(
            scope_root, selectors, transaction_id=transaction_id
        )

    def layout_from_selectors(
        self,
        scope_root: Path,
        selectors: t.VariadicTuple[str],
        *,
        transaction_id: str | None = None,
    ) -> p.Result[m.Infra.MiseToolchainWorkspaceLayout]:
        """Rebuild exact topology from already authenticated journal selectors."""
        identity = self._exact_git_identity(scope_root)
        if identity.failure:
            return r[m.Infra.MiseToolchainWorkspaceLayout].from_failure(identity)
        return self._layout_from_identity(
            identity.value, selectors, transaction_id=transaction_id
        )

    def journal_layout(
        self, identity: m.Infra.GitIdentityReport
    ) -> p.Result[m.Infra.MiseToolchainWorkspaceLayout]:
        """Build the no-effect journal layout from the descriptor-locked identity."""
        return self._layout_from_identity(identity, (".",), transaction_id=None)

    def file_layout(
        self, scope_root: Path, roots: t.MappingKV[str, Path], *, transaction_id: str
    ) -> p.Result[m.Infra.MiseToolchainWorkspaceLayout]:
        """Bind explicit file capabilities without reading any Mise declaration."""
        result_type = r[m.Infra.MiseToolchainWorkspaceLayout]
        identity = self._exact_git_identity(scope_root)
        if identity.failure:
            return result_type.from_failure(identity)
        participants: list[m.Infra.CodegenFileParticipant] = []
        for selector, root in sorted(roots.items()):
            if not root.is_absolute() or ".." in root.parts or root.resolve() != root:
                return result_type.fail(f"file capability root is not physical: {root}")
            physical = files.physical_directory_identity(root)
            if physical.failure:
                return result_type.from_failure(physical)
            staging = self._state_root(root)
            if staging.failure:
                return result_type.from_failure(staging)
            participants.append(
                m.Infra.CodegenFileParticipant(
                    selector=selector,
                    root=root,
                    device=physical.value[0],
                    inode=physical.value[1],
                    transaction_root=staging.value
                    / f"{c.Infra.TRANSACTION_DIR_PREFIX}{transaction_id}",
                )
            )
        state_root = self._state_root(scope_root)
        if state_root.failure:
            return result_type.from_failure(state_root)
        return result_type.ok(
            m.Infra.MiseToolchainWorkspaceLayout(
                scope_root=scope_root,
                state_root=state_root.value,
                journal_path=self.journal_path(identity.value),
                transaction_id=transaction_id,
                projects=(),
                file_participants=tuple(participants),
            )
        )

    @staticmethod
    def journal_path(identity: m.Infra.GitIdentityReport) -> Path:
        """Return the shared journal anchor without materializing layout state."""
        return identity.git_dir / c.Infra.JOURNAL_NAME

    def _layout_from_identity(
        self,
        identity: m.Infra.GitIdentityReport,
        selectors: t.VariadicTuple[str],
        *,
        transaction_id: str | None,
    ) -> p.Result[m.Infra.MiseToolchainWorkspaceLayout]:
        """Build one typed layout from an already exact scope identity."""
        if not selectors or len(set(selectors)) != len(selectors):
            return r[m.Infra.MiseToolchainWorkspaceLayout].fail(
                "Mise project selectors must be nonempty and unique"
            )
        scope_root = identity.repo_root
        projects: list[m.Infra.MiseToolchainProjectLayout] = []
        for selector in selectors:
            project = self._project_layout(
                scope_root, selector, transaction_id=transaction_id
            )
            if project.failure:
                return r[m.Infra.MiseToolchainWorkspaceLayout].from_failure(project)
            projects.append(project.value)
        state_root = self._state_root(scope_root)
        if state_root.failure:
            return r[m.Infra.MiseToolchainWorkspaceLayout].from_failure(state_root)
        return r[m.Infra.MiseToolchainWorkspaceLayout].ok(
            m.Infra.MiseToolchainWorkspaceLayout(
                scope_root=scope_root,
                state_root=state_root.value,
                journal_path=self.journal_path(identity),
                transaction_id=transaction_id,
                projects=tuple(projects),
            )
        )

    def select_layout(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan] = (),
    ) -> p.Result[m.Infra.MiseToolchainWorkspaceLayout]:
        """Select only projects owned by this conform request or direct caller."""
        if config_plans:
            planned_paths = tuple(item.path for item in config_plans)
            if len(set(planned_paths)) != len(planned_paths):
                return r[m.Infra.MiseToolchainWorkspaceLayout].fail(
                    "duplicate Mise configuration plans"
                )
            known = {project.artifacts.config for project in layout.projects}
            unknown = tuple(path for path in planned_paths if path not in known)
            if unknown:
                return r[m.Infra.MiseToolchainWorkspaceLayout].fail(
                    f"Mise configuration plan is outside workspace: {unknown[0]}"
                )
            selected = tuple(
                project
                for project in layout.projects
                if project.artifacts.config in planned_paths
            )
        else:
            requested = self._owner.repository_root.expanduser().absolute()
            selected = (
                layout.projects
                if requested == layout.scope_root
                else tuple(
                    project for project in layout.projects if project.root == requested
                )
            )
        if not selected:
            return r[m.Infra.MiseToolchainWorkspaceLayout].fail(
                "Mise transaction selected no governed project"
            )
        return r[m.Infra.MiseToolchainWorkspaceLayout].ok(
            m.Infra.MiseToolchainWorkspaceLayout(
                scope_root=layout.scope_root,
                state_root=layout.state_root,
                journal_path=layout.journal_path,
                transaction_id=layout.transaction_id,
                projects=selected,
            )
        )

    def layout_for_config_plans(
        self,
        scope_root: Path,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan],
        *,
        transaction_id: str | None = None,
    ) -> p.Result[m.Infra.MiseToolchainWorkspaceLayout]:
        """Derive exact selected project topology from the locked conform plan."""
        if not config_plans:
            return r[m.Infra.MiseToolchainWorkspaceLayout].fail(
                "Mise transaction requires configuration plans"
            )
        selectors: list[str] = []
        expected_paths: list[Path] = []
        for plan in config_plans:
            if plan.path.name != c.Infra.CONFIG_SPEC[0] or ".." in plan.path.parts:
                return r[m.Infra.MiseToolchainWorkspaceLayout].fail(
                    f"invalid Mise configuration plan path: {plan.path}"
                )
            try:
                selector = (
                    plan.path.parent
                    .absolute()
                    .relative_to(scope_root.absolute())
                    .as_posix()
                )
            except ValueError:
                return r[m.Infra.MiseToolchainWorkspaceLayout].fail(
                    f"Mise configuration plan escapes scope: {plan.path}"
                )
            selectors.append(selector)
            expected_paths.append(plan.path)
        layout = self.layout_from_selectors(
            scope_root, tuple(selectors), transaction_id=transaction_id
        )
        if layout.failure:
            return layout
        if tuple(
            project.artifacts.config for project in layout.value.projects
        ) != tuple(expected_paths):
            return r[m.Infra.MiseToolchainWorkspaceLayout].fail(
                "Mise configuration plan paths differ from derived topology"
            )
        return layout

    def snapshot(
        self,
        layout: m.Infra.MiseToolchainWorkspaceLayout,
        config_plans: t.VariadicTuple[m.Infra.CodegenFilePlan] = (),
    ) -> p.Result[m.Infra.MiseToolchainWorkspacePlan]:
        """Capture one complete byte-and-mode snapshot for a stable layout."""
        planned_configs = {item.path: item for item in config_plans}
        expected_paths = {project.artifacts.config for project in layout.projects}
        if config_plans and (
            len(planned_configs) != len(config_plans)
            or set(planned_configs) != expected_paths
        ):
            return r[m.Infra.MiseToolchainWorkspacePlan].fail(
                "Mise configuration plans differ from workspace topology"
            )
        projects: list[m.Infra.MiseToolchainProjectState] = []
        for project_layout in layout.projects:
            project = self._project_state(
                project_layout, planned_configs.get(project_layout.artifacts.config)
            )
            if project.failure:
                return r[m.Infra.MiseToolchainWorkspacePlan].from_failure(project)
            projects.append(project.value)
        return r[m.Infra.MiseToolchainWorkspacePlan].ok(
            m.Infra.MiseToolchainWorkspacePlan(layout=layout, projects=tuple(projects))
        )

    @staticmethod
    def _project_state(
        layout: m.Infra.MiseToolchainProjectLayout,
        config_plan: m.Infra.CodegenFilePlan | None,
    ) -> p.Result[m.Infra.MiseToolchainProjectState]:
        config_state = files.read_state(
            layout.artifacts.config, required=config_plan is None
        )
        if config_state.failure:
            return r[m.Infra.MiseToolchainProjectState].from_failure(config_state)
        if config_plan is None:
            if config_state.value.content is None:
                return r[m.Infra.MiseToolchainProjectState].fail(
                    f"committed Mise configuration is absent: {layout.artifacts.config}"
                )
            replacement_content = config_state.value.content
        else:
            if config_plan.desired_content is None:
                return r[m.Infra.MiseToolchainProjectState].fail(
                    f"invalid Mise configuration plan: {config_plan.path}"
                )
            replacement_content = config_plan.desired_content
        if (
            config_plan is not None
            and isinstance(config_plan.before, m.Cli.AtomicFileState)
            and config_plan.before.content is not None
        ):
            config_sources = config_plan.source_states
        else:
            # A first publication (scaffold or newly governed project) has no
            # pre-publication provenance: the transaction itself publishes the
            # config sources, so the authoritative barrier baseline is the
            # on-disk reality at transaction begin.
            current_sources = u.Infra.snapshot_config_sources(layout.root)
            if current_sources.failure:
                return r[m.Infra.MiseToolchainProjectState].from_failure(
                    current_sources
                )
            config_sources = current_sources.value
        artifacts: list[m.Cli.AtomicFileState] = []
        for path in (layout.artifacts.unix_launcher, layout.artifacts.windows_launcher):
            state = files.read_state(path, required=False)
            if state.failure:
                return r[m.Infra.MiseToolchainProjectState].from_failure(state)
            artifacts.append(state.value)
        artifact_set = m.Infra.MiseToolchainArtifactSet(
            unix_launcher=artifacts[0], windows_launcher=artifacts[1]
        )
        return r[m.Infra.MiseToolchainProjectState].ok(
            m.Infra.MiseToolchainProjectState(
                layout=layout,
                config=m.Infra.MiseToolchainConfigState(
                    before=config_state.value,
                    replacement_content=replacement_content,
                    replacement_mode=c.Infra.CONFIG_SPEC[1],
                    sources=config_sources,
                ),
                artifacts=artifact_set,
            )
        )

    def _project_layout(
        self, scope_root: Path, selector: str, *, transaction_id: str | None = None
    ) -> p.Result[m.Infra.MiseToolchainProjectLayout]:
        root = self._project_root(scope_root, selector)
        if root.failure:
            return r[m.Infra.MiseToolchainProjectLayout].from_failure(root)
        state_root = self._state_root(root.value)
        if state_root.failure:
            return r[m.Infra.MiseToolchainProjectLayout].from_failure(state_root)
        return r[m.Infra.MiseToolchainProjectLayout].ok(
            m.Infra.MiseToolchainProjectLayout(
                selector=selector,
                root=root.value,
                transaction_root=(
                    state_root.value
                    / f"{c.Infra.TRANSACTION_DIR_PREFIX}{transaction_id}"
                    if transaction_id is not None
                    else None
                ),
                artifacts=m.Infra.MiseToolchainArtifactPaths(
                    config=root.value / c.Infra.CONFIG_SPEC[0],
                    unix_launcher=root.value / c.Infra.ARTIFACT_NAMES[0],
                    windows_launcher=root.value / c.Infra.ARTIFACT_NAMES[1],
                ),
            )
        )

    def _project_root(self, scope_root: Path, selector: str) -> p.Result[Path]:
        relative = Path(selector)
        if selector != "." and (
            relative.is_absolute()
            or relative.as_posix() != selector
            or ".." in relative.parts
        ):
            return r[Path].fail(f"unsafe Mise project selector: {selector}")
        cursor = scope_root.absolute()
        for part in relative.parts:
            cursor /= part
            physical = self._physical_directory(cursor)
            if physical.failure:
                return r[Path].from_failure(physical)
        if not cursor.is_relative_to(scope_root.absolute()):
            return r[Path].fail(f"Mise project escapes workspace: {selector}")
        return r[Path].ok(cursor)

    def _state_root(self, root: Path) -> p.Result[Path]:
        cursor = root.absolute()
        for part in c.Infra.MISE_ARTIFACTS_STATE_DIRECTORY.parts:
            cursor /= part
            if not cursor.exists() and not cursor.is_symlink():
                continue
            physical = self._physical_directory(cursor)
            if physical.failure:
                return r[Path].from_failure(physical)
        return r[Path].ok(cursor)

    @staticmethod
    def _physical_directory(path: Path) -> p.Result[bool]:
        try:
            state = path.lstat()
        except OSError as exc:
            return r[bool].fail_op(f"inspect Mise directory {path}", exc)
        reparse = getattr(state, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0
        )
        if not stat.S_ISDIR(state.st_mode) or reparse:
            return r[bool].fail(f"Mise directory is not physical: {path}")
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraMiseWorkspacePlanner"]
