"""Synchronize pyright, mypy, and pyrefly paths from workspace dependencies.

Handlers are called by the canonical CLI via FlextInfraCliDeps.register_deps.

Every emitted entry is relative to the project that owns the file it is written
into. A dependency that lives in another checkout resolves through its installed
distribution in the environment the project runs against, never through a
filesystem hop out of the project root: a generated surface that encodes
``../<sibling>/src`` describes one host layout, so it is wrong in any checkout
whose siblings sit elsewhere and it makes one generator emit different content
per clone (mro-c6di).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra import c, config, p, r, t, u
from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase
from flext_infra.deps._extra_paths_sync import FlextInfraExtraPathsSyncMixin

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraExtraPathsManager(
    FlextInfraExtraPathsSyncMixin, FlextInfraProjectSelectionServiceBase[bool]
):
    """Manager for synchronizing type-checker search paths from dependencies."""

    _workspace_project_names: t.Infra.StrSet = u.PrivateAttr(default_factory=set)

    @override
    def model_post_init(self, __context: t.MappingKV[str, p.AttributeProbe], /) -> None:
        """Initialize workspace metadata after validation."""
        self._workspace_project_names = set(
            u.Infra.workspace_member_names(self.workspace_root)
        )

    @property
    def workspace_project_names(self) -> t.StrSequence:
        """Managed workspace member names backing dependency resolution."""
        return tuple(sorted(self._workspace_project_names))

    @override
    def execute(self) -> p.Result[bool]:
        """Synchronize extra paths for the configured project slice."""
        result = self.sync_extra_paths(
            dry_run=self.effective_dry_run, project_dirs=self.project_dirs
        )
        if result.failure:
            return r[bool].fail(result.error or "extra-path synchronization failed")
        return r[bool].ok(True)

    @override
    def pyright_extra_paths(self, *, project_dir: Path, is_root: bool) -> t.StrSequence:
        """Compute pyright extra paths for a project."""
        rules = config.Infra.tooling.tools.pyright.path_rules
        source_root = rules.source_dir
        configured_typings = (
            rules.root_typings_paths if is_root else rules.project_typings_paths
        )
        typings_paths = [
            relative_path
            for relative_path in configured_typings
            if (project_dir / relative_path).is_dir()
        ]
        # Why: naive sorted({".", "src"}) puts "." first and diverges from the
        # declared scaffold roots and pyrefly search-path ordering, so conform
        # apply never reached a fixed point on pyproject.toml. Keep the source
        # import root first; sort everything else for stable comparisons.
        paths: t.Infra.StrSet = {rules.project_root, source_root, *typings_paths}
        paths.discard(source_root)
        return (source_root, *sorted(paths))

    @override
    def pyrefly_search_paths(
        self, *, project_dir: Path, is_root: bool
    ) -> t.StrSequence:
        """Compute pyrefly search paths for a project.

        Only roots inside ``project_dir`` are emitted. Path dependencies and uv
        workspace members are importable through their installed distributions,
        so they need no search-path entry and must never be described by a path
        that leaves the project (mro-c6di).
        """
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        source_root = rules.source_dir
        configured_typings = (
            rules.root_typings_paths if is_root else rules.project_typings_paths
        )
        typings_paths = [
            relative_path
            for relative_path in configured_typings
            if (project_dir / relative_path).is_dir()
        ]
        shared_paths = [
            relative_path
            for relative_path in rules.project_shared_search_paths
            if (project_dir / relative_path).is_dir()
        ]
        # Why (ai-hub-qwoc, fleet-wide fix): pyrefly resolves the FIRST
        # matching search-path entry. "src" must precede "." or every module
        # resolves twice (ai_hub.X via src AND src.ai_hub.X via "."),
        # producing distinct classes for the same symbol and phantom
        # bad-argument-type errors. A naive sorted({...}) puts "." before
        # "src" (ASCII '.' < 's'), silently breaking every consumer with a
        # "." shared search path (e.g. tests.* resolution). Sort everything
        # else, then place the declared source root first so it always wins.
        paths: t.Infra.StrSet = {*typings_paths, *shared_paths}
        has_source_root = (project_dir / source_root).is_dir()
        paths.discard(source_root)
        ordered = sorted(paths)
        if has_source_root:
            return (source_root, *ordered)
        return tuple(ordered)

    def pyrefly_project_includes(
        self, *, project_dir: Path, is_root: bool
    ) -> t.StrSequence:
        """Build Pyrefly includes from configured productive directories."""
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        # Only real productive roots belong in project-includes, and
        # u.Infra.analyzer_python_roots is the single owner shared with conform
        # and the modernizer, so a root one surface writes is never erased by
        # the next. Existing trees declare only roots that discovery proves
        # productive; pre-write scaffold roots are supplied explicitly by the
        # modernizer and do not pass through this disk-based synchronization.
        discovered = frozenset(u.Infra.discover_python_dirs(project_dir))
        includes: t.Infra.StrSet = set(
            self.pyrefly_include_globs(
                u.Infra.analyzer_python_roots(
                    project_dir,
                    tuple(
                        directory
                        for directory in rules.env_dirs
                        if directory in discovered
                    ),
                )
            )
        )
        includes.update(self._pyright_include_globs(project_dir))
        if not is_root or (not rules.workspace_include_children):
            return sorted(includes)
        for child in sorted(project_dir.iterdir()):
            if not child.is_dir() or not (child / c.Infra.PYPROJECT_FILENAME).exists():
                continue
            child_dirs = u.Infra.discover_python_dirs(child)
            includes.update(
                f"{child.name}/{directory}/**/*.py*" for directory in child_dirs
            )
        return sorted(includes)

    @staticmethod
    def pyrefly_include_globs(env_dirs: t.StrSequence) -> t.StrSequence:
        """Render Pyrefly include globs for already validated Python roots."""
        return tuple(f"{directory}/**/*.py*" for directory in env_dirs)

    @staticmethod
    def _pyright_include_globs(project_dir: Path) -> t.StrSequence:
        """Return Pyrefly-compatible globs from declared Pyright includes."""
        payload = u.Infra.pyproject_payload(project_dir / c.Infra.PYPROJECT_FILENAME)
        tool = u.Cli.json_as_mapping(payload.get(c.Infra.TOOL))
        pyright = u.Cli.json_as_mapping(tool.get(c.Infra.PYRIGHT))
        includes: t.Infra.StrSet = set()
        for raw_item in u.Cli.json_as_sequence(pyright.get(c.Infra.INCLUDE)):
            if not isinstance(raw_item, str):
                continue
            normalized = raw_item.strip().rstrip("/")
            if not normalized:
                continue
            includes.add(
                normalized
                if "*" in normalized or normalized.endswith((".py", ".pyi"))
                else f"{normalized}/**/*.py*"
            )
        return tuple(sorted(includes))


__all__: list[str] = ["FlextInfraExtraPathsManager"]
