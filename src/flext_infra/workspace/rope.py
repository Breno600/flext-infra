"""Public Rope workspace DSL and facade mixin.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from keyword import iskeyword
from pathlib import Path
from time import perf_counter
from types import TracebackType
from typing import Annotated, ClassVar, Self, override

from flext_infra import c, m, p, r, t, u
from flext_infra.base import s
from flext_infra.workspace._rope_query import FlextInfraRopeQueryMixin


class FlextInfraRopeWorkspace(
    FlextInfraRopeQueryMixin,
    s[m.Infra.RopeWorkspaceSession],
):
    """Open one shared Rope workspace with cached public DSL methods."""

    _IDENTIFIER_PATTERN: ClassVar[t.RegexPattern] = c.Infra.IDENTIFIER_PATTERN

    rope_repository_root_override: Annotated[
        Path | None,
        m.Field(description="Optional Rope project root; defaults to repository_root"),
    ] = None

    _rope_repository_root: Path = u.PrivateAttr()
    _rope_project: t.Infra.RopeProject | None = u.PrivateAttr(
        default_factory=lambda: None,
    )
    _workspace_index: m.Infra.RopeWorkspaceIndex | None = u.PrivateAttr(
        default_factory=lambda: None,
    )
    _codegen_projects: t.VariadicTuple[p.Infra.ProjectInfo] | None = u.PrivateAttr(
        default_factory=lambda: None,
    )
    _project_layout_cache: MutableMapping[str, m.Infra.RopeProjectLayout | None] = (
        u.PrivateAttr(default_factory=dict)
    )
    _package_context_cache: MutableMapping[str, m.Infra.LazyInitPackageContext] = (
        u.PrivateAttr(default_factory=dict)
    )
    _module_policy_cache: MutableMapping[
        t.Triple[str, str, str],
        m.Infra.NamespaceModulePolicy,
    ] = u.PrivateAttr(default_factory=dict)
    _module_convention_cache: MutableMapping[str, m.Infra.RopeModuleConvention] = (
        u.PrivateAttr(default_factory=dict)
    )
    _module_object_cache: MutableMapping[
        t.Triple[str, bool, bool],
        t.VariadicTuple[m.Infra.Object],
    ] = u.PrivateAttr(default_factory=dict)
    _resource_cache: MutableMapping[str, t.Infra.RopeFile | None] = u.PrivateAttr(
        default_factory=dict,
    )
    _name_index: (
        MutableMapping[str, t.VariadicTuple[t.Triple[Path, str, t.VariadicTuple[int]]]]
        | None
    ) = u.PrivateAttr(default_factory=lambda: None)
    _import_dependents_index: MutableMapping[str, t.VariadicTuple[Path]] | None = (
        u.PrivateAttr(default_factory=lambda: None)
    )

    @override
    def model_post_init(self, __context: t.ScalarMapping | None, /) -> None:
        """Resolve the canonical Rope root once for the full session."""
        super().model_post_init(__context)
        self._rope_repository_root = (
            self.rope_repository_root_override
            or u.Infra.rope_repository_root(self.repository_root)
        )

    @classmethod
    def open_workspace(
        cls,
        repository_root: Path,
        *,
        rope_repository_root: Path | None = None,
    ) -> Self:
        """Create one ready-to-use Rope workspace session.

        Returns:
            The resulting ``Self``.

        """
        # Scan policy is owned only by the
        # validated config singleton, never copied into a session.
        resolved_rope_root = rope_repository_root or u.Infra.rope_repository_root(
            repository_root,
        )
        workspace = cls(
            repository_root=repository_root,
            rope_repository_root_override=resolved_rope_root,
        )
        _ = workspace.rope_project
        return workspace

    @property
    @override
    def rope_repository_root(self) -> Path:
        """Canonical root used for the shared Rope project."""
        return self._rope_repository_root

    @property
    @override
    def rope_project(self) -> t.Infra.RopeProject:
        """Shared Rope project, opening it lazily once."""
        rope_project = self._rope_project
        if rope_project is None:
            started_at = perf_counter()
            u.Cli.info(f"rope: opening workspace at {self._rope_repository_root}")
            # Why: the session indexes every project this repository owns,
            # not just its root folder (flext-infra: 0 modules bug); declared
            # submodules are other repositories and stay installed libraries.
            rope_project = u.Infra.init_rope_workspace(self._rope_repository_root)
            self._rope_project = rope_project
            u.Cli.info(f"rope: workspace ready in {perf_counter() - started_at:.2f}s")
        return rope_project

    @property
    @override
    def workspace_index(self) -> m.Infra.RopeWorkspaceIndex:
        """Cached workspace index for the shared Rope project."""
        workspace_index = self._workspace_index
        if workspace_index is None:
            started_at = perf_counter()
            u.Cli.info(
                f"rope: indexing python workspace at {self._rope_repository_root}",
            )
            workspace_index = u.Infra.index_rope_workspace(
                self.rope_project,
                self._rope_repository_root,
            )
            self._workspace_index = workspace_index
            u.Cli.info(
                "rope: indexed "
                f"{len(workspace_index.package_dirs)} package dirs and "
                f"{len(workspace_index.modules_by_path)} modules in "
                f"{perf_counter() - started_at:.2f}s",
            )
        return workspace_index

    @override
    def execute(self) -> p.Result[m.Infra.RopeWorkspaceSession]:
        """Materialize the public Rope session snapshot.

        Returns:
            The resulting ``p.Result[m.Infra.RopeWorkspaceSession]``.

        """
        snapshot: m.Infra.RopeWorkspaceSession = self.session_snapshot()
        return r[m.Infra.RopeWorkspaceSession].ok(snapshot)

    def session_snapshot(self) -> m.Infra.RopeWorkspaceSession:
        """Return the current public Rope session state.

        Returns:
            The current public Rope session state.

        """
        return m.Infra.RopeWorkspaceSession(
            repository_root=self.repository_root,
            rope_repository_root=self._rope_repository_root,
            workspace_index=self.workspace_index,
        )

    @override
    def refresh(
        self,
        *,
        preserve_indexes: bool = False,
        validate_project: bool = True,
    ) -> m.Infra.RopeWorkspaceSession:
        """Invalidate Rope caches without reopening the Rope project.

        ``preserve_indexes=True`` is reserved for flows that temporarily wrote
        files and already restored the original on-disk content before the
        refresh runs. ``validate_project=False`` is reserved for those reverted
        preview flows so cleanup does not rescan an already-restored project.

        Returns:
            The resulting ``m.Infra.RopeWorkspaceSession``.

        """
        if validate_project and self._rope_project is not None:
            self._rope_project.validate()
        self._package_context_cache.clear()
        self._module_policy_cache.clear()
        self._module_convention_cache.clear()
        self._module_object_cache.clear()
        self._resource_cache.clear()
        if not preserve_indexes:
            self._name_index = None
            self._import_dependents_index = None
        return self.session_snapshot()

    @override
    def reload(self) -> m.Infra.RopeWorkspaceSession:
        """Reopen the shared Rope project and drop all transient caches.

        Returns:
            The resulting ``m.Infra.RopeWorkspaceSession``.

        """
        self.close()
        _ = self.rope_project
        return self.session_snapshot()

    @override
    def projects(self) -> t.SequenceOf[p.Infra.ProjectInfo]:
        """Return the canonical codegen project selection for this workspace.

        Returns:
            The canonical codegen project selection for this workspace.

        """
        if self._codegen_projects is None:
            projects_result = u.Infra.projects(self.repository_root)
            if projects_result.failure:
                self._codegen_projects = ()
            else:
                discovered_projects: t.SequenceOf[p.Infra.ProjectInfo] = (
                    projects_result.unwrap()
                )
                self._codegen_projects = tuple(discovered_projects)
        return self._codegen_projects

    @override
    def layout(self, project_root: Path) -> m.Infra.RopeProjectLayout | None:
        """Return one centralized project layout contract for codegen pipelines.

        Returns:
            One centralized project layout contract for codegen pipelines.

        """
        resolved_root = project_root.resolve()
        cache_key = str(resolved_root)
        if cache_key in self._project_layout_cache:
            return self._project_layout_cache[cache_key]
        project_info = next(
            (
                project
                for project in self.projects()
                if project.path.resolve() == resolved_root
            ),
            None,
        )
        layout = u.Infra.layout(resolved_root, project=project_info)
        self._project_layout_cache[cache_key] = layout
        return layout

    @override
    def package_context(self, package_dir: Path) -> m.Infra.LazyInitPackageContext:
        """Return one centralized lazy-init package context for a package dir.

        Returns:
            One centralized lazy-init package context for a package dir.

        """
        resolved_dir = package_dir.resolve()
        cache_key = str(resolved_dir)
        cached = self._package_context_cache.get(cache_key)
        if cached is not None:
            return cached
        package_entry = self.package(resolved_dir)
        init_path = resolved_dir / c.Infra.INIT_PY
        current_pkg = package_entry.package_name if package_entry is not None else ""
        init_resource = self.resource(init_path) if init_path.is_file() else None
        generated_init = init_resource is not None and init_resource.read().startswith(
            c.Infra.AUTOGEN_HEADERS,
        )
        context = m.Infra.LazyInitPackageContext(
            pkg_dir=resolved_dir,
            init_path=init_path,
            current_pkg=current_pkg,
            surface=current_pkg.split(".", maxsplit=1)[0] if current_pkg else "",
            generated_init=generated_init,
            importable=bool(current_pkg)
            and all(
                part.isidentifier() and not iskeyword(part)
                for part in current_pkg.split(".")
            ),
        )
        self._package_context_cache[cache_key] = context
        return context

    @override
    def policy(
        self,
        file_path: Path,
        *,
        rel_path: Path | None = None,
        current_pkg: str = "",
    ) -> m.Infra.NamespaceModulePolicy:
        """Return the centralized naming policy for one module path.

        Returns:
            The centralized naming policy for one module path.

        """
        resolved_file = file_path.resolve()
        resolved_rel_path = (
            rel_path if rel_path is not None else Path(resolved_file.name)
        )
        cache_key = (str(resolved_file), str(resolved_rel_path), current_pkg)
        cached = self._module_policy_cache.get(cache_key)
        if cached is not None:
            return cached
        policy: m.Infra.NamespaceModulePolicy = u.Infra.policy(
            resolved_file,
            rope_project=self.rope_project,
            rel_path=resolved_rel_path,
            current_pkg=current_pkg,
        )
        self._module_policy_cache[cache_key] = policy
        return policy

    @override
    def convention(
        self,
        file_path: Path,
        *,
        rel_path: Path | None = None,
    ) -> m.Infra.RopeModuleConvention:
        """Return one unified project/package/module convention contract.

        Returns:
            One unified project/package/module convention contract.

        """
        resolved_file = file_path.resolve()
        cache_key = f"{resolved_file}::{rel_path or ''}"
        cached = self._module_convention_cache.get(cache_key)
        if cached is not None:
            return cached
        module_entry = self.module(resolved_file)
        package_dir = (
            module_entry.package_dir.resolve()
            if module_entry is not None
            else resolved_file.parent.resolve()
        )
        resolved_rel_path = (
            rel_path
            if rel_path is not None
            else resolved_file.relative_to(package_dir)
            if resolved_file.is_relative_to(package_dir)
            else Path(resolved_file.name)
        )
        package_context = self.package_context(package_dir)
        policy = self.policy(
            resolved_file,
            rel_path=resolved_rel_path,
            current_pkg=package_context.current_pkg,
        )
        project_root = (
            module_entry.project_root
            if module_entry is not None and module_entry.project_root is not None
            else u.Infra.project_root(resolved_file)
        )
        project_layout = self.layout(project_root) if project_root is not None else None
        convention = m.Infra.RopeModuleConvention(
            file_path=resolved_file,
            relative_path=resolved_rel_path,
            module_name=module_entry.module_name
            if module_entry is not None
            else resolved_file.stem,
            package_name=package_context.current_pkg,
            package_dir=package_dir,
            package_context=package_context,
            module_policy=policy,
            project_layout=project_layout,
        )
        self._module_convention_cache[cache_key] = convention
        return convention

    @override
    def semantic(self, file_path: Path) -> m.Infra.ModuleSemanticState:
        """Return one cached semantic snapshot for a module path.

        Returns:
            One cached semantic snapshot for a module path.

        """
        state: m.Infra.ModuleSemanticState = u.Infra.resolve_module_semantic_state(
            self.rope_project,
            self._resource_for(file_path),
        )
        return state

    @override
    def exports(
        self,
        file_path: Path,
        *,
        export_options: m.Infra.ExportOptions | None = None,
    ) -> t.StrSequence:
        """Return public export names for one module path.

        Returns:
            Public export names for one module path.

        """
        resolved_export_options = export_options or m.Infra.ExportOptions()
        return u.Infra.resolve_module_export_names(
            self.rope_project,
            self._resource_for(file_path),
            export_options=resolved_export_options,
        )

    @override
    def close(self) -> None:
        """Close the shared Rope project and clear transient caches."""
        if self._rope_project is not None:
            self._rope_project.close()
            self._rope_project = None
        self._workspace_index = None
        self._codegen_projects = None
        self._project_layout_cache.clear()
        self._package_context_cache.clear()
        self._module_policy_cache.clear()
        self._module_convention_cache.clear()
        self._module_object_cache.clear()
        self._resource_cache.clear()
        self._name_index = None
        self._import_dependents_index = None

    @override
    def __enter__(self) -> Self:
        """Open the Rope project on context-manager entry.

        Returns:
            The resulting ``Self``.

        """
        _ = self.rope_project
        return self

    @override
    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        """Close the Rope project on context-manager exit."""
        self.close()

    @override
    def _resource_for(self, file_path: Path) -> t.Infra.RopeFile:
        """Require a resource inside the active Rope workspace.

        Returns:
            The resulting ``t.Infra.RopeResource``.

        Raises:
            FileNotFoundError: If
                ``resolved_path.is_relative_to(self._rope_repository_root.resolve()) and
                (not resolved_path.exists())``.
            ValueError: If path is outside the active rope workspace.

        """
        resource = self.resource(file_path)
        if resource is not None:
            return resource
        resolved_path = file_path.resolve()
        if (
            resolved_path.is_relative_to(self._rope_repository_root.resolve())
            and not resolved_path.exists()
        ):
            raise FileNotFoundError(resolved_path)
        msg = f"path is outside the active rope workspace: {file_path}"
        raise ValueError(msg)


__all__: t.StrSequence = ("FlextInfraRopeWorkspace",)
