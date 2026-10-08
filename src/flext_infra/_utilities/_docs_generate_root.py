"""Aggregate workspace artifact rendering for documentation generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections import Counter
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, m, p, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesDocsApi,
    FlextInfraUtilitiesDocsContract,
    FlextInfraUtilitiesDocsGenerateProjectMixin,
    FlextInfraUtilitiesDocsRender,
)


class FlextInfraUtilitiesDocsGenerateRootMixin(
    FlextInfraUtilitiesDocsGenerateProjectMixin,
):
    """Render aggregate docs from the complete discovered project set."""

    @staticmethod
    def _aggregate_root_pages(
        repository_root: Path,
        workspace_contract: t.JsonMapping,
        src_paths: t.SequenceOf[str],
        catalog_entries: t.SequenceOf[m.Infra.DocsCatalogEntry],
        exclude_docs: t.StrSequence,
    ) -> list[t.Pair[Path, str]]:
        """Render the static aggregate mkdocs and catalog root pages.

        Returns:
            The resulting ``list[t.Pair[Path, str]]``.

        """
        return [
            (
                repository_root / "mkdocs.yml",
                FlextInfraUtilitiesDocsRender.docs_root_mkdocs(
                    workspace_contract,
                    src_paths,
                ),
            ),
            (
                repository_root / "docs/projects/generated/catalog.md",
                FlextInfraUtilitiesDocsRender.docs_project_catalog_page(
                    catalog_entries,
                    exclude_docs=exclude_docs,
                ),
            ),
        ]

    @classmethod
    def _root_rendered(
        cls,
        repository_root: Path,
        scopes: t.SequenceOf[m.Infra.DocScope],
        workspace_contract: t.JsonMapping,
        exclude_docs: t.StrSequence,
    ) -> p.Result[
        t.Triple[
            list[t.Pair[Path, str]],
            list[m.Infra.DocScope],
            dict[str, list[str]],
        ]
    ]:
        """Render the aggregate root pages and collect per-project inputs.

        Returns:
            The resulting ``(rendered, project scopes, scope modules)`` triple.

        """
        project_scopes = [scope for scope in scopes if scope.path != repository_root]
        catalog_entries: t.MutableSequenceOf[m.Infra.DocsCatalogEntry] = []
        scope_modules: MutableMapping[str, list[str]] = {}
        src_paths: t.MutableSequenceOf[str] = []
        root_api: list[t.Pair[Path, str]] = []
        for scope in scopes:
            if scope.name == c.Infra.RK_ROOT:
                continue
            src_exists = (
                FlextInfraUtilitiesDocsGenerateRootMixin._source_directory_exists(
                    scope.path / "src",
                )
            )
            if src_exists.failure:
                return r[
                    t.Triple[
                        list[t.Pair[Path, str]],
                        list[m.Infra.DocScope],
                        dict[str, list[str]],
                    ]
                ].from_failure(src_exists)
            if src_exists.value:
                src_paths.append(
                    (scope.path / "src").relative_to(repository_root).as_posix(),
                )
            if scope.path == repository_root:
                if scope.package_name:
                    root_api.extend(
                        FlextInfraUtilitiesDocsGenerateRootMixin.docs_project_api_artifacts(
                            scope,
                        ),
                    )
                continue
            project_contract = (
                FlextInfraUtilitiesDocsContract.docs_current_project_contract(
                    scope.path,
                    FlextInfraUtilitiesDocsApi.public_contract(
                        scope.path,
                        scope.package_name,
                    ),
                )
            )
            scope_modules[scope.name] = (
                FlextInfraUtilitiesDocsGenerateRootMixin._module_names(scope)
            )
            catalog_entries.append(
                m.Infra.DocsCatalogEntry(
                    name=scope.name,
                    project_class=scope.project_class,
                    package_name=scope.package_name,
                    description=str(project_contract.get("description", "")).strip(),
                    api_page=f"../../api-reference/generated/{scope.name}.md",
                ),
            )
        class_counts = Counter(entry.project_class for entry in catalog_entries)
        rendered: list[t.Pair[Path, str]] = [
            *root_api,
            *cls._aggregate_root_pages(
                repository_root,
                workspace_contract,
                src_paths,
                catalog_entries,
                exclude_docs,
            ),
            (
                repository_root / "docs/api-reference/generated/overview.md",
                FlextInfraUtilitiesDocsRender.docs_root_overview_page(
                    workspace_contract,
                    project_count=len(project_scopes),
                    class_counts=tuple(
                        m.Infra.DocsClassCount(project_class=name, count=count)
                        for name, count in sorted(class_counts.items())
                    ),
                ),
            ),
        ]
        return r[
            t.Triple[
                list[t.Pair[Path, str]],
                list[m.Infra.DocScope],
                dict[str, list[str]],
            ]
        ].ok((rendered, project_scopes, dict(scope_modules)))

    @staticmethod
    def _project_rendered(
        repository_root: Path,
        project_scopes: t.SequenceOf[m.Infra.DocScope],
        scope_modules: t.MappingKV[str, list[str]],
        rendered: list[t.Pair[Path, str]],
    ) -> list[t.Pair[Path, str]]:
        """Append every project's generated API pages and the projects index.

        Returns:
            The resulting ``list[t.Pair[Path, str]]``.

        """
        projects_index_entries: t.MutableSequenceOf[m.Infra.DocsProjectIndexEntry] = []
        for scope in project_scopes:
            rendered.append((
                repository_root / "docs/api-reference/generated" / f"{scope.name}.md",
                FlextInfraUtilitiesDocsRender.docs_directive_page(
                    f"{scope.name} Public API",
                    scope.package_name,
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
                    ".",
                    "/",
                )
                rendered.append((
                    modules_root / f"{relative}.md",
                    FlextInfraUtilitiesDocsRender.docs_directive_page(
                        module_name,
                        module_name,
                    ),
                ))
            projects_index_entries.append(
                m.Infra.DocsProjectIndexEntry(
                    name=scope.name,
                    module_count=len(module_names),
                ),
            )
        rendered.append((
            repository_root / "docs/api-reference/generated/projects/index.md",
            FlextInfraUtilitiesDocsRender.docs_root_projects_index(
                projects_index_entries,
            ),
        ))
        return rendered

    @classmethod
    def _prune_generated(
        cls,
        repository_root: Path,
        rendered: t.SequenceOf[t.Pair[Path, str]],
    ) -> p.Result[
        t.Pair[
            t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple],
            t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple],
        ]
    ]:
        """Prune both generated docs trees against the rendered inventory.

        Returns:
            The resulting ``(api, projects)`` pruned artifact pair.

        """
        api_pruned = (
            FlextInfraUtilitiesDocsGenerateRootMixin._prune_generated_tree_artifacts(
                repository_root,
                repository_root / "docs/api-reference/generated",
                rendered,
            )
        )
        if api_pruned.failure:
            return r[
                t.Pair[
                    t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple],
                    t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple],
                ]
            ].from_failure(api_pruned)
        projects_pruned = (
            FlextInfraUtilitiesDocsGenerateRootMixin._prune_generated_tree_artifacts(
                repository_root,
                repository_root / "docs/projects/generated",
                rendered,
            )
        )
        if projects_pruned.failure:
            return r[
                t.Pair[
                    t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple],
                    t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple],
                ]
            ].from_failure(projects_pruned)
        return r[
            t.Pair[
                t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple],
                t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple],
            ]
        ].ok((api_pruned.value, projects_pruned.value))

    @classmethod
    def docs_root_artifacts(
        cls,
        repository_root: Path,
        scopes: t.SequenceOf[m.Infra.DocScope],
    ) -> p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]:
        """Render aggregate root targets from the complete discovered project set.

        Returns:
            The resulting
                ``p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]``.

        """
        workspace_contract = FlextInfraUtilitiesDocsContract.docs_workspace_contract(
            repository_root,
        )
        exclude_docs = FlextInfraUtilitiesDocsRender.as_string_sequence(
            workspace_contract,
            "exclude_docs",
        )
        aggregated = cls._root_rendered(
            repository_root,
            scopes,
            workspace_contract,
            exclude_docs,
        )
        if aggregated.failure:
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].from_failure(
                aggregated,
            )
        rendered, project_scopes, scope_modules = aggregated.value
        rendered = cls._project_rendered(
            repository_root,
            project_scopes,
            scope_modules,
            rendered,
        )
        pruned = cls._prune_generated(repository_root, rendered)
        if pruned.failure:
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].from_failure(
                pruned,
            )
        return FlextInfraUtilitiesDocsGenerateRootMixin.docs_normalize_artifacts((
            *((repository_root, path, content) for path, content in rendered),
            *pruned.value[0],
            *pruned.value[1],
        ))

    @staticmethod
    def docs_scope_artifacts(
        scope: m.Infra.DocScope,
        *,
        repository_root: Path,
        aggregate_scopes: t.SequenceOf[m.Infra.DocScope],
        source_states: t.SequenceOf[m.Cli.AtomicFileState],
    ) -> p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]:
        """Return the rendered artifact inventory for one docs scope.

        The scope label is the only topology input (see ``build_scopes``).

        Returns:
            The rendered artifact inventory for one docs scope.

        """
        if scope.name == c.Infra.RK_ROOT:
            return FlextInfraUtilitiesDocsGenerateRootMixin.docs_root_artifacts(
                repository_root,
                aggregate_scopes,
            )
        return FlextInfraUtilitiesDocsGenerateRootMixin.docs_project_artifacts(
            scope,
            repository_root=repository_root,
            source_states=source_states,
        )


__all__: list[str] = ["FlextInfraUtilitiesDocsGenerateRootMixin"]
