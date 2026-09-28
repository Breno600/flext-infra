"""Synchronize pyright, mypy, and pyrefly paths from workspace dependencies.

Handlers are called by the canonical CLI via FlextInfraCliDeps.register_deps.

Every emitted entry is relative to the project that owns the file it is written
into. A dependency that lives in another checkout resolves through its installed
distribution in the environment the project runs against, never through a
filesystem hop out of the project root: a generated surface that encodes
``../<sibling>/src`` describes one host layout, so it is wrong in any checkout
whose siblings sit elsewhere and it makes one generator emit different content
per clone (flext-c6di).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, override

from flext_core import r
from flext_infra import c, config, m, p, t, u
from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase

from ._extra_paths_sync import FlextInfraExtraPathsSyncMixin


class FlextInfraExtraPathsManager(
    FlextInfraExtraPathsSyncMixin, FlextInfraProjectSelectionServiceBase[bool]
):
    """Manager for synchronizing type-checker search paths from dependencies."""

    # Why (fixed point): codegen materializes managed roots (tests/) while it
    # applies. Discovery that only sees the pre-apply tree would omit them and
    # the post-apply verification plan would want the pyproject changed again.
    generated_python_roots: Annotated[
        t.StrSequence,
        m.Field(
            default=(),
            description="Analyzer roots the active codegen plan materializes",
        ),
    ] = ()
    analysis_exclusions: Annotated[
        t.StrSequence,
        m.Field(
            default=(),
            description="Workspace-relative paths excluded from analyzer discovery",
        ),
    ] = ()

    _workspace_project_names: t.Infra.StrSet = u.PrivateAttr(default_factory=set)

    @override
    def model_post_init(self, __context: t.MappingKV[str, p.AttributeProbe], /) -> None:
        """Initialize workspace metadata after validation."""
        self._workspace_project_names = set(
            u.Infra.workspace_project_paths(self.repository_root)
        )

    @property
    def workspace_project_names(self) -> t.StrSequence:
        """Managed workspace project names backing dependency resolution."""
        return tuple(sorted(self._workspace_project_names))

    @property
    def analysis_excluded_top_dirs(self) -> frozenset[str]:
        """First path segments from the caller's validated topology."""
        return frozenset(
            Path(path).parts[0] for path in self.analysis_exclusions if Path(path).parts
        )

    @override
    def execute(self) -> p.Result[bool]:
        """Synchronize extra paths for the configured project slice."""
        result = self.sync_extra_paths(
            dry_run=self.effective_dry_run, project_dirs=self.project_dirs
        )
        if result.failure:
            return r[bool].from_failure(result)
        return r[bool].ok(True)

    @staticmethod
    def _existing_typings_paths(
        rules: p.Infra.TypeCheckerPathRules, *, project_dir: Path, is_root: bool
    ) -> t.StrSequence:
        """Return the configured typings roots that exist under ``project_dir``."""
        configured_typings = (
            rules.root_typings_paths if is_root else rules.project_typings_paths
        )
        return tuple(
            relative_path
            for relative_path in configured_typings
            if (project_dir / relative_path).is_dir()
        )

    def _search_path_set(
        self,
        rules: p.Infra.TypeCheckerPathRules,
        *,
        project_dir: Path,
        is_root: bool,
        shared_search_paths: t.StrSequence,
        include_generated_roots: bool,
    ) -> t.Infra.StrSet:
        """Return the unordered search roots a checker shares, minus ordered ones.

        ``include_generated_roots`` carries the only difference between the two
        callers: pyrefly also accepts a shared root the active codegen plan is
        about to materialize, mypy accepts only roots already on disk.
        """
        shared_paths = [
            relative_path
            for relative_path in shared_search_paths
            if (project_dir / relative_path).is_dir()
            or (
                include_generated_roots and relative_path in self.generated_python_roots
            )
        ]
        paths: t.Infra.StrSet = {
            *self._existing_typings_paths(
                rules, project_dir=project_dir, is_root=is_root
            ),
            *shared_paths,
        }
        paths.discard(rules.source_dir)
        paths.discard(rules.project_root)
        return paths

    @override
    def pyright_extra_paths(self, *, project_dir: Path, is_root: bool) -> t.StrSequence:
        """Compute pyright extra paths for a project."""
        rules = config.Infra.tooling.tools.pyright.path_rules
        source_root = rules.source_dir
        typings_paths = self._existing_typings_paths(
            rules, project_dir=project_dir, is_root=is_root
        )
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
        workspace projects are importable through their installed distributions,
        so they need no search-path entry and must never be described by a path
        that leaves the project (flext-c6di).
        """
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        source_root = rules.source_dir
        # Why (cosmos-45hiv, 2026-08-31): the project root closes the chain for
        # cross-tree imports. `scripts/` is a checked env dir and owns
        # `scripts/__init__.py`, so `tests/` and `scripts/` import its modules
        # as `scripts.*`; resolving them needs the repo root on the search
        # path. It must come LAST: pyrefly resolves the FIRST matching entry,
        # so `source_dir` ahead of "." keeps `src.x` from also resolving as
        # `x` (the ai-hub-qwoc duplicate-class failure below). mypy cannot
        # share this value — it enumerates every search-path root and reports
        # the same file under two module names as source-file-found-twice —
        # which is why the two tools now derive separately.
        root_path = rules.project_root
        has_project_root = (project_dir / root_path).is_dir()
        paths = self._search_path_set(
            rules,
            project_dir=project_dir,
            is_root=is_root,
            shared_search_paths=rules.project_shared_search_paths,
            include_generated_roots=True,
        )
        has_source_root = (
            project_dir / source_root
        ).is_dir() or source_root in self.generated_python_roots
        ordered = sorted(paths)
        if has_project_root:
            ordered.append(root_path)
        if has_source_root:
            return (source_root, *ordered)
        return tuple(ordered)

    @override
    def mypy_search_paths(self, *, project_dir: Path, is_root: bool) -> t.StrSequence:
        """Compute mypy search paths: like pyrefly but without the project root.

        mypy treats each search-path entry as a package root and enumerates the
        files under it. When a root re-spells a module that another root already
        provides -- the repo root resolving ``scripts/legado/lib/argocd.py`` as
        ``scripts.legado.lib.argocd`` while ``scripts/`` on the same path offers
        it as ``legado.lib.argocd`` -- mypy reports "Source file found twice
        under different module names" and aborts before checking anything.
        pyrefly does not have that failure mode: it resolves imports
        first-match-wins, so the project root is a safe resolution aid there
        and stays one (see :meth:`pyrefly_search_paths`).
        """
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        source_root = rules.source_dir
        paths = self._search_path_set(
            rules,
            project_dir=project_dir,
            is_root=is_root,
            shared_search_paths=rules.project_shared_search_paths,
            include_generated_roots=False,
        )
        if (project_dir / source_root).is_dir():
            return (source_root, *sorted(paths))
        return tuple(sorted(paths))

    def pyrefly_project_includes(
        self, *, project_dir: Path, is_root: bool
    ) -> t.StrSequence:
        """Build Pyrefly includes from configured productive directories."""
        rules = config.Infra.tooling.tools.pyrefly.path_rules
        # flext-j47u (codex): never reread an on-disk Pyright table while its
        # in-memory payload is being conformed; include only real production roots.
        discovered_python_roots = set(
            u.Infra.discover_python_dirs(
                project_dir, workspace_excluded_top_dirs=self.analysis_excluded_top_dirs
            )
        )
        includes: t.Infra.StrSet = set(
            self.pyrefly_include_globs(
                tuple(
                    directory
                    for directory in rules.env_dirs
                    if directory in discovered_python_roots
                    or directory in self.generated_python_roots
                )
            )
        )
        if not is_root or (not rules.workspace_include_children):
            return sorted(includes)
        for child in sorted(project_dir.iterdir()):
            if not child.is_dir() or not (child / c.PYPROJECT_FILENAME).exists():
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


__all__: list[str] = ["FlextInfraExtraPathsManager"]
