"""Docs project discovery and canonical descriptor construction."""

from __future__ import annotations

import operator
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core.result import FlextResult as r
from flext_infra import c, m, t

from ._docs_scope_policy import FlextInfraUtilitiesDocsScopePolicyMixin
from .git import FlextInfraUtilitiesGit
from .project_discovery import FlextInfraUtilitiesProjectDiscovery

if TYPE_CHECKING:
    from flext_infra import FlextInfraProtocols as p


class FlextInfraUtilitiesDocsScopeProjectsMixin(
    FlextInfraUtilitiesDocsScopePolicyMixin
):
    """Discover governed projects from the authenticated workspace topology."""

    @staticmethod
    def resolve_projects(
        repository_root: Path, names: t.StrSequence
    ) -> p.Result[t.SequenceOf[m.Infra.ProjectInfo]]:
        """Resolve project names through repository-local topology only."""
        owner = FlextInfraUtilitiesDocsScopeProjectsMixin
        discovered = owner.discover_projects(repository_root)
        if discovered.failure:
            return r[t.SequenceOf[m.Infra.ProjectInfo]].from_failure(discovered)
        projects = list(discovered.value)
        root = owner.absolute_lexical(repository_root)
        if all(project.path != root for project in projects):
            root_project = owner.project_info_for_entry(
                root,
                workspace_declared_repositories=owner.workspace_declared_repository_path_set(
                    root
                ),
            )
            if root_project is not None:
                projects.append(root_project)
        if not names:
            return r[t.SequenceOf[m.Infra.ProjectInfo]].ok(
                sorted(projects, key=operator.attrgetter("name"))
            )
        by_name: MutableMapping[str, m.Infra.ProjectInfo] = {}
        for project in projects:
            by_name.setdefault(project.name, project)
            by_name.setdefault(project.path.name, project)
            if project.path == root:
                by_name.setdefault(".", project)
            elif project.path.is_relative_to(root):
                by_name.setdefault(project.path.relative_to(root).as_posix(), project)
        missing = [name for name in names if name not in by_name]
        if missing:
            return r[t.SequenceOf[m.Infra.ProjectInfo]].fail(
                f"unknown projects: {', '.join(sorted(missing))}"
            )
        return r[t.SequenceOf[m.Infra.ProjectInfo]].ok(
            sorted((by_name[name] for name in names), key=operator.attrgetter("name"))
        )

    @staticmethod
    def workspace_declared_repository_path_set(
        repository_root: Path,
    ) -> frozenset[Path]:
        """Return lexical subprojects freshly read from this root's manifest."""
        root = FlextInfraUtilitiesDocsScopeProjectsMixin.absolute_lexical(
            repository_root
        )
        declared = FlextInfraUtilitiesGit.git_declared_submodule_paths(root)
        if declared.failure:
            raise ValueError(declared.error or f"invalid workspace: {root}")
        return frozenset(root / path for path in declared.value)

    @staticmethod
    def project_info_for_entry(
        entry: Path, *, workspace_declared_repositories: frozenset[Path]
    ) -> m.Infra.ProjectInfo | None:
        """Build one canonical project descriptor for one discovered project root."""
        entry = FlextInfraUtilitiesDocsScopeProjectsMixin.absolute_lexical(entry)
        project_state = FlextInfraUtilitiesDocsScopeProjectsMixin.project_state(entry)
        project_section = project_state.payload.get("project")
        project_name = (
            project_section.get("name") if isinstance(project_section, dict) else None
        )
        if (
            not isinstance(project_section, dict)
            or not isinstance(project_name, str)
            or not project_name.strip()
        ):
            return None
        is_workspace_declared_repository = entry in workspace_declared_repositories
        if not FlextInfraUtilitiesDocsScopeProjectsMixin.docs_scope_enabled(
            project_state.docs_meta
        ):
            return None
        has_src = FlextInfraUtilitiesDocsScopeProjectsMixin.physical_directory_exists(
            entry / c.Infra.DEFAULT_SRC_DIR
        )
        has_tests = FlextInfraUtilitiesDocsScopeProjectsMixin.physical_directory_exists(
            entry / c.Infra.DIR_TESTS
        )
        has_deps = bool(project_section.get("dependencies"))
        if (
            not is_workspace_declared_repository
            and not has_src
            and not has_tests
            and not has_deps
        ):
            return None
        make_profile = (
            c.Infra.MakeProfile.WORKSPACE
            if FlextInfraUtilitiesDocsScopeProjectsMixin._physical_file_exists(
                entry / c.Infra.GITMODULES
            )
            else c.Infra.MakeProfile.STANDALONE
        )
        return m.Infra.ProjectInfo(
            path=entry,
            name=project_state.project_name,
            stack="python/flext",
            has_tests=has_tests,
            has_src=has_src,
            project_class=(
                FlextInfraUtilitiesDocsScopeProjectsMixin.classify_project_from_meta(
                    project_state.project_name, project_state.docs_meta
                )
            ),
            package_name=project_state.package_name,
            make_profile=make_profile,
            declared_subproject=is_workspace_declared_repository,
        )

    @staticmethod
    def discover_projects(
        repository_root: Path,
    ) -> p.Result[t.SequenceOf[m.Infra.ProjectInfo]]:
        """Discover the root or projects declared by its own ``.gitmodules``."""
        owner = FlextInfraUtilitiesDocsScopeProjectsMixin
        roots = owner.docs_repository_roots(repository_root)
        if roots.failure:
            return r[t.SequenceOf[m.Infra.ProjectInfo]].from_failure(roots)
        repository_root = roots.value[0]
        excluded = owner.excluded_roots(repository_root)
        workspace_declared_repositories = owner.workspace_declared_repository_path_set(
            repository_root
        )
        project_roots = FlextInfraUtilitiesProjectDiscovery.discover_project_candidates(
            repository_root
        )
        root_project: m.Infra.ProjectInfo | None = None
        projects: list[m.Infra.ProjectInfo] = []
        for project_root in project_roots:
            if project_root.name == "cmd" or project_root.name in excluded:
                continue
            if project_root == repository_root and not owner.physical_directory_exists(
                project_root / c.Infra.DEFAULT_SRC_DIR
            ):
                continue
            project_info = owner.project_info_for_entry(
                project_root,
                workspace_declared_repositories=workspace_declared_repositories,
            )
            if project_info is None:
                continue
            if project_root == repository_root:
                root_project = project_info
                continue
            projects.append(project_info)
        if not projects and root_project is not None:
            return r[t.SequenceOf[m.Infra.ProjectInfo]].ok([root_project])
        return r[t.SequenceOf[m.Infra.ProjectInfo]].ok(projects)


__all__: list[str] = ["FlextInfraUtilitiesDocsScopeProjectsMixin"]
