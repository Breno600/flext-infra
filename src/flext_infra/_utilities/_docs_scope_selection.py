"""Docs scope selection helpers."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m

from .docs_scope import FlextInfraUtilitiesDocsScope

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesDocsScopeSelectionMixin:
    """Resolve selected docs project names into DocScope models."""

    @staticmethod
    def _selected_project_scopes(
        repository_root: Path,
        discovered: t.SequenceOf[m.Infra.ProjectInfo],
        selected_names: t.StrSequence,
        output_dir: Path | str,
    ) -> t.SequenceOf[m.Infra.DocScope]:
        """Build docs scopes for selected project names."""
        project_by_name = FlextInfraUtilitiesDocsScopeSelectionMixin._project_by_name(
            discovered
        )
        scopes: list[m.Infra.DocScope] = []
        for name in selected_names:
            scope = FlextInfraUtilitiesDocsScopeSelectionMixin._selected_scope(
                repository_root, name, project_by_name, output_dir
            )
            if scope is not None:
                scopes.append(scope)
        return tuple(scopes)

    @staticmethod
    def _selected_scope(
        repository_root: Path,
        name: str,
        project_by_name: MutableMapping[str, m.Infra.ProjectInfo],
        output_dir: Path | str,
    ) -> m.Infra.DocScope | None:
        """Build one selected scope from discovery or a local path."""
        selected = project_by_name.get(name)
        if selected is not None:
            return FlextInfraUtilitiesDocsScopeSelectionMixin._doc_scope(
                project=selected, output_dir=output_dir, repository_root=repository_root
            )
        return FlextInfraUtilitiesDocsScopeSelectionMixin._optional_path_scope(
            repository_root, name, output_dir
        )

    @staticmethod
    def _project_by_name(
        discovered: t.SequenceOf[m.Infra.ProjectInfo],
    ) -> MutableMapping[str, m.Infra.ProjectInfo]:
        """Index discovered projects by canonical and directory names."""
        project_by_name: MutableMapping[str, m.Infra.ProjectInfo] = {}
        for project in discovered:
            project_by_name.setdefault(project.name, project)
            project_by_name.setdefault(project.path.name, project)
        return project_by_name

    @staticmethod
    def _optional_path_scope(
        repository_root: Path, name: str, output_dir: Path | str
    ) -> m.Infra.DocScope | None:
        """Build a selected path scope when it is a local pyproject project."""
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            msg = f"docs project selector escapes repository: {name}"
            raise ValueError(msg)
        project_root = repository_root / relative
        roots = FlextInfraUtilitiesDocsScope.docs_repository_roots(
            repository_root, (project_root,)
        )
        if roots.failure:
            raise ValueError(
                roots.error or f"docs project path is unsafe: {project_root}"
            )
        if project_root not in roots.value:
            return None
        if not FlextInfraUtilitiesDocsScope.project_state(project_root).payload:
            return None
        return FlextInfraUtilitiesDocsScopeSelectionMixin._governed_scope(
            project_root, output_dir, repository_root=repository_root
        )

    @staticmethod
    def _report_directory(project_root: Path, output_dir: Path | str) -> Path:
        """Return one lexical report path owned by its project root."""
        relative = Path(output_dir)
        if relative.is_absolute() or ".." in relative.parts:
            # Each scope anchors its own reports under its own root, so the
            # argument is a project-relative directory. An absolute path is
            # rejected even when it happens to sit inside one of the roots:
            # it would force every member scope into a single owner.
            msg = (
                "docs output directory must be relative to each project root, "
                f"got {relative} for {project_root}"
            )
            raise ValueError(msg)
        return project_root / relative

    @staticmethod
    def _doc_scope(
        *, project: m.Infra.ProjectInfo, output_dir: Path | str, repository_root: Path
    ) -> m.Infra.DocScope:
        """Build one canonical docs scope model."""
        resolved = project.path
        return m.Infra.DocScope(
            name=project.name,
            path=resolved,
            report_dir=FlextInfraUtilitiesDocsScopeSelectionMixin._report_directory(
                resolved, output_dir
            ),
            project_class=project.project_class,
            package_name=project.package_name,
            repository_root_override=repository_root,
        )

    @staticmethod
    def _governed_scope(
        project_root: Path, output_dir: Path | str, *, repository_root: Path
    ) -> m.Infra.DocScope:
        """Build docs scope for a governed project root."""
        payload = FlextInfraUtilitiesDocsScope.project_payload(project_root)
        docs_meta = FlextInfraUtilitiesDocsScope.docs_meta_from_payload(payload)
        project_name = FlextInfraUtilitiesDocsScope.project_name_from_payload(
            project_root, payload
        )
        return m.Infra.DocScope(
            name=project_name,
            path=project_root,
            report_dir=FlextInfraUtilitiesDocsScopeSelectionMixin._report_directory(
                project_root, output_dir
            ),
            project_class=FlextInfraUtilitiesDocsScope.classify_project_from_meta(
                project_name, docs_meta
            ),
            package_name=FlextInfraUtilitiesDocsScope.package_name_from_payload(
                project_root, payload, docs_meta
            ),
            repository_root_override=repository_root,
        )


__all__: list[str] = ["FlextInfraUtilitiesDocsScopeSelectionMixin"]
