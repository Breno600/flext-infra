"""Aggregate workspace artifact rendering for documentation generation."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t

from ._docs_generate_plan import DocsRenderedArtifactTuple
from ._docs_generate_project import FlextInfraUtilitiesDocsGenerateProjectMixin
from .docs_api import FlextInfraUtilitiesDocsApi
from .docs_contract import FlextInfraUtilitiesDocsContract
from .docs_render import FlextInfraUtilitiesDocsRender

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesDocsGenerateRootMixin(
    FlextInfraUtilitiesDocsGenerateProjectMixin
):
    """Render aggregate docs from the complete discovered project set."""

    @staticmethod
    def docs_root_artifacts(
        repository_root: Path, scopes: t.SequenceOf[m.Infra.DocScope]
    ) -> p.Result[t.VariadicTuple[DocsRenderedArtifactTuple]]:
        """Render aggregate root targets from the complete discovered project set."""
        workspace_contract = FlextInfraUtilitiesDocsContract.docs_workspace_contract(
            repository_root
        )
        exclude_docs = FlextInfraUtilitiesDocsRender.as_string_sequence(
            workspace_contract, "exclude_docs"
        )
        project_scopes = [scope for scope in scopes if scope.path != repository_root]
        catalog_entries: t.MutableSequenceOf[MutableMapping[str, str]] = []
        class_counts: MutableMapping[str, int] = {}
        scope_modules: MutableMapping[str, list[str]] = {}
        src_paths: t.MutableSequenceOf[str] = []
        root_api: list[t.Pair[Path, str]] = []
        for scope in scopes:
            if scope.name == c.Infra.RK_ROOT:
                continue
            src_dir = scope.path / "src"
            src_exists = (
                FlextInfraUtilitiesDocsGenerateRootMixin._source_directory_exists(
                    src_dir
                )
            )
            if src_exists.failure:
                return r[t.VariadicTuple[DocsRenderedArtifactTuple]].from_failure(
                    src_exists
                )
            if src_exists.value:
                src_paths.append(src_dir.relative_to(repository_root).as_posix())
            if scope.path == repository_root:
                if scope.package_name:
                    root_api.extend(
                        FlextInfraUtilitiesDocsGenerateRootMixin.docs_project_api_artifacts(
                            scope
                        )
                    )
                continue
            class_counts[scope.project_class] = (
                class_counts.get(scope.project_class, 0) + 1
            )
            analyzed_contract = FlextInfraUtilitiesDocsApi.public_contract(
                scope.path, scope.package_name
            )
            project_contract = (
                FlextInfraUtilitiesDocsContract.docs_current_project_contract(
                    scope.path, analyzed_contract
                )
            )
            scope_modules[scope.name] = (
                FlextInfraUtilitiesDocsGenerateRootMixin._module_names(scope)
            )
            catalog_entries.append({
                "name": scope.name,
                "project_class": scope.project_class,
                "package_name": scope.package_name,
                "description": str(project_contract.get("description", "")).strip(),
                "api_page": f"../../api-reference/generated/{scope.name}.md",
            })
        rendered: list[t.Pair[Path, str]] = [
            *root_api,
            (
                repository_root / "mkdocs.yml",
                FlextInfraUtilitiesDocsRender.docs_root_mkdocs(
                    workspace_contract, src_paths
                ),
            ),
            (
                repository_root / "docs/api-reference/generated/overview.md",
                FlextInfraUtilitiesDocsRender.docs_root_overview_page(
                    workspace_contract,
                    project_count=len(project_scopes),
                    class_counts=class_counts,
                ),
            ),
            (
                repository_root / "docs/projects/generated/catalog.md",
                FlextInfraUtilitiesDocsRender.docs_project_catalog_page(
                    catalog_entries, exclude_docs=exclude_docs
                ),
            ),
        ]
        projects_index_entries: t.MutableSequenceOf[MutableMapping[str, str]] = []
        for scope in project_scopes:
            rendered.append((
                repository_root / "docs/api-reference/generated" / f"{scope.name}.md",
                FlextInfraUtilitiesDocsRender.docs_directive_page(
                    f"{scope.name} Public API", scope.package_name
                ),
            ))
            module_names = scope_modules.get(scope.name, [])
            modules_root = (
                repository_root
                / "docs/api-reference/generated/projects"
                / scope.name
                / "modules"
            )
            rendered.append((
                modules_root / "index.md",
                FlextInfraUtilitiesDocsRender.docs_modules_index(scope, module_names),
            ))
            for module_name in module_names:
                relative = module_name.removeprefix(f"{scope.package_name}.").replace(
                    ".", "/"
                )
                rendered.append((
                    modules_root / f"{relative}.md",
                    FlextInfraUtilitiesDocsRender.docs_directive_page(
                        module_name, module_name
                    ),
                ))
            projects_index_entries.append({
                "name": scope.name,
                "module_count": str(len(module_names)),
            })
        rendered.append((
            repository_root / "docs/api-reference/generated/projects/index.md",
            FlextInfraUtilitiesDocsRender.docs_root_projects_index(
                projects_index_entries
            ),
        ))
        api_pruned = (
            FlextInfraUtilitiesDocsGenerateRootMixin._prune_generated_tree_artifacts(
                repository_root,
                repository_root / "docs/api-reference/generated",
                rendered,
            )
        )
        if api_pruned.failure:
            return r[t.VariadicTuple[DocsRenderedArtifactTuple]].from_failure(
                api_pruned
            )
        projects_pruned = (
            FlextInfraUtilitiesDocsGenerateRootMixin._prune_generated_tree_artifacts(
                repository_root, repository_root / "docs/projects/generated", rendered
            )
        )
        if projects_pruned.failure:
            return r[t.VariadicTuple[DocsRenderedArtifactTuple]].from_failure(
                projects_pruned
            )
        return FlextInfraUtilitiesDocsGenerateRootMixin.docs_normalize_artifacts((
            *((repository_root, path, content) for path, content in rendered),
            *api_pruned.value,
            *projects_pruned.value,
        ))

    @staticmethod
    def _is_workspace_root_scope(scope: m.Infra.DocScope) -> bool:
        """Whether one scope is the root of a manifest-carrying repository.

        Mirrors the validate-side contract (docs_validate.docs_missing_required_paths):
        a root that carries its own workspace manifest is the workspace scope
        regardless of the scope label, so the generate side must route it to the
        root publisher exactly the way validate demands the root contract.
        """
        return (scope.path / "config" / "workspace.yaml").is_file()

    @staticmethod
    def docs_scope_artifacts(
        scope: m.Infra.DocScope,
        *,
        repository_root: Path,
        aggregate_scopes: t.SequenceOf[m.Infra.DocScope],
        source_states: t.SequenceOf[m.Cli.AtomicFileState],
    ) -> p.Result[t.VariadicTuple[DocsRenderedArtifactTuple]]:
        """Return the rendered artifact inventory for one docs scope."""
        if (
            scope.name == c.Infra.RK_ROOT
            or FlextInfraUtilitiesDocsGenerateRootMixin._is_workspace_root_scope(scope)
        ):
            return FlextInfraUtilitiesDocsGenerateRootMixin.docs_root_artifacts(
                repository_root, aggregate_scopes
            )
        return FlextInfraUtilitiesDocsGenerateRootMixin.docs_project_artifacts(
            scope, repository_root=repository_root, source_states=source_states
        )


__all__: list[str] = ["FlextInfraUtilitiesDocsGenerateRootMixin"]
