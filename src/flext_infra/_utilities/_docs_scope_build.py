"""Docs scope construction helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t

from ._docs_scope_selection import FlextInfraUtilitiesDocsScopeSelectionMixin
from .base import FlextInfraUtilitiesBase
from .docs_scope import FlextInfraUtilitiesDocsScope
from .pyproject import FlextInfraUtilitiesPyproject
from .workspace_manifest import FlextInfraUtilitiesWorkspaceManifest

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesDocsScopeBuildMixin(
    FlextInfraUtilitiesDocsScopeSelectionMixin
):
    """Build canonical DocScope models for docs commands."""

    @staticmethod
    def _selected_project_names(
        repository_root: Path, projects: t.StrSequence | None
    ) -> list[str]:
        """Return normalized project filters for docs-scoped operations."""
        _ = repository_root
        return list(FlextInfraUtilitiesBase.normalize_sequence_values(projects) or ())

    @staticmethod
    def build_scopes(
        repository_root: Path,
        projects: t.StrSequence | None,
        output_dir: Path | str,
        *,
        include_root: bool = True,
    ) -> p.Result[t.SequenceOf[m.Infra.DocScope]]:
        """Build DocScope objects for repository root and selected projects.

        ``include_root`` governs only whether the workspace root itself is
        rendered as a docs OUTPUT scope; root guides/pyproject remain readable
        SOURCES for member projects regardless (see ``docs_source_paths``,
        which always discovers them from the physical repository root).
        """
        try:
            scopes = FlextInfraUtilitiesDocsScopeBuildMixin._build_scopes_unchecked(
                repository_root, projects, output_dir, include_root=include_root
            )
        except c.EXC_OS_TYPE_VALUE as exc:
            return r[t.SequenceOf[m.Infra.DocScope]].fail_op("scope resolution", exc)
        return r[t.SequenceOf[m.Infra.DocScope]].ok(scopes)

    @staticmethod
    def _build_scopes_unchecked(
        repository_root: Path,
        projects: t.StrSequence | None,
        output_dir: Path | str,
        *,
        include_root: bool,
    ) -> t.SequenceOf[m.Infra.DocScope]:
        """Build docs scopes without exception wrapping."""
        resolved_root = repository_root.resolve()
        project_state = FlextInfraUtilitiesDocsScope.project_state(resolved_root)
        is_enabled = FlextInfraUtilitiesDocsScope.docs_scope_enabled(
            project_state.docs_meta
        )
        discovered = FlextInfraUtilitiesDocsScopeBuildMixin._discover_projects(
            resolved_root
        )
        has_declared_members = bool(
            FlextInfraUtilitiesPyproject.workspace_project_paths(resolved_root)
        )
        has_child_projects = any(
            project.path.resolve() != resolved_root for project in discovered
        )
        # Why (README-drop fix): "config/beads.yaml" is a per-project beads
        # override every project may carry, standalone or not — it is not a
        # fleet-topology signal. The handwritten workspace manifest
        # ("config/workspace.yaml", see docs_scope_policy's
        # manifest_excluded_roots and workspace/detector.py) is the actual SSOT
        # for "this repository is itself a fleet umbrella". Using the beads
        # override here misrouted every scaffolded standalone project into
        # `_workspace_scopes`, collapsing its own docs scope onto an identical
        # root scope and silently dropping README.md/docs/index.md/guides.
        has_workspace_topology = FlextInfraUtilitiesWorkspaceManifest.is_fleet_umbrella(
            resolved_root
        )
        if (
            (resolved_root / c.PYPROJECT_FILENAME).is_file()
            and not has_declared_members
            and not has_child_projects
            and not has_workspace_topology
            and is_enabled
        ):
            return (
                FlextInfraUtilitiesDocsScopeBuildMixin._governed_scope(
                    resolved_root, output_dir, repository_root=resolved_root
                ),
            )
        return FlextInfraUtilitiesDocsScopeBuildMixin._workspace_scopes(
            resolved_root, projects, output_dir, discovered, include_root=include_root
        )

    @staticmethod
    def _workspace_scopes(
        repository_root: Path,
        projects: t.StrSequence | None,
        output_dir: Path | str,
        discovered: t.SequenceOf[m.Infra.ProjectInfo],
        *,
        include_root: bool,
    ) -> t.SequenceOf[m.Infra.DocScope]:
        """Build docs scopes for a repository root plus child projects.

        The root scope is an OUTPUT participant only when ``include_root`` is
        true; excluding it never affects source discovery (root guides,
        pyproject, config) which is derived independently from the physical
        repository root.
        """
        scopes: list[m.Infra.DocScope] = (
            [
                m.Infra.DocScope(
                    name=c.Infra.RK_ROOT,
                    path=repository_root,
                    report_dir=(repository_root / output_dir).resolve(),
                    project_class="root",
                    package_name="",
                )
            ]
            if include_root
            else []
        )
        selected_names = FlextInfraUtilitiesDocsScopeBuildMixin._selected_project_names(
            repository_root, projects
        )
        if selected_names:
            scopes.extend(
                FlextInfraUtilitiesDocsScopeBuildMixin._selected_project_scopes(
                    repository_root, discovered, selected_names, output_dir
                )
            )
            return tuple(scopes)
        scopes.extend(
            FlextInfraUtilitiesDocsScopeBuildMixin._doc_scope(
                project=project, output_dir=output_dir, repository_root=repository_root
            )
            for project in discovered
        )
        return tuple(scopes)

    @staticmethod
    def _discover_projects(repository_root: Path) -> t.SequenceOf[m.Infra.ProjectInfo]:
        """Discover workspace projects or raise a typed value error."""
        discovered_result = FlextInfraUtilitiesDocsScope.resolve_projects(
            repository_root, ()
        )
        if discovered_result.failure:
            msg = discovered_result.error or "project discovery failed"
            raise ValueError(msg)
        return discovered_result.value


__all__: list[str] = ["FlextInfraUtilitiesDocsScopeBuildMixin"]
