"""Per-project artifact rendering for documentation generation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import config, m, t

from ._docs_generate_plan import (
    DocsRenderedArtifactTuple,
    FlextInfraUtilitiesDocsGeneratePlanMixin,
)
from ._docs_guides import FlextInfraUtilitiesDocsGuidesMixin
from .docs_api import FlextInfraUtilitiesDocsApi
from .docs_contract import FlextInfraUtilitiesDocsContract
from .docs_render import FlextInfraUtilitiesDocsRender

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesDocsGenerateProjectMixin(
    FlextInfraUtilitiesDocsGeneratePlanMixin
):
    """Render the complete desired artifact inventory for one project scope."""

    @staticmethod
    def _module_names(scope: m.Infra.DocScope) -> list[str]:
        """Return config-owned public API module names for one distribution."""
        declared = config.Infra.codegen.make.docs.api_modules.get(scope.name, ())
        return [f"{scope.package_name}.{module}" for module in declared]

    @staticmethod
    def docs_project_api_artifacts(scope: m.Infra.DocScope) -> list[t.Pair[Path, str]]:
        """Render package API pages before their owning tree is pruned."""
        module_names = FlextInfraUtilitiesDocsGenerateProjectMixin._module_names(scope)
        api_root = scope.path / "docs/api-reference/generated"
        rendered = [
            (
                api_root / "public-api.md",
                FlextInfraUtilitiesDocsRender.docs_directive_page(
                    f"{scope.name} Public API", scope.package_name
                ),
            ),
            (
                api_root / "modules/index.md",
                FlextInfraUtilitiesDocsRender.docs_modules_index(scope, module_names),
            ),
        ]
        for module_name in module_names:
            relative = module_name.removeprefix(f"{scope.package_name}.").replace(
                ".", "/"
            )
            rendered.append((
                api_root / "modules" / f"{relative}.md",
                FlextInfraUtilitiesDocsRender.docs_directive_page(
                    module_name, module_name
                ),
            ))
        return rendered

    @staticmethod
    def docs_project_artifacts(
        scope: m.Infra.DocScope,
        *,
        repository_root: Path,
        source_states: t.SequenceOf[m.Cli.AtomicFileState],
    ) -> p.Result[t.VariadicTuple[DocsRenderedArtifactTuple]]:
        """Render the complete target inventory for one FLEXT project."""
        guides = FlextInfraUtilitiesDocsGuidesMixin.docs_project_guides_artifacts(
            scope, repository_root=repository_root, source_states=source_states
        )
        if guides.failure:
            return r[t.VariadicTuple[DocsRenderedArtifactTuple]].from_failure(guides)
        guide_paths = {
            state.path
            for state in source_states
            if state.path.parent == scope.path / "docs/guides"
            and state.path.suffix == ".md"
            and state.path.name != "README.md"
        }
        for _project, path, content in guides.value:
            if content is None:
                guide_paths.discard(path)
            else:
                guide_paths.add(path)
        analyzed_contract = FlextInfraUtilitiesDocsApi.public_contract(
            scope.path, scope.package_name
        )
        contract = FlextInfraUtilitiesDocsContract.docs_current_project_contract(
            scope.path, analyzed_contract
        )
        module_names = FlextInfraUtilitiesDocsGenerateProjectMixin._module_names(scope)
        rendered: list[t.Pair[Path, str]] = [
            (
                scope.path / "README.md",
                FlextInfraUtilitiesDocsRender.docs_project_readme(scope, contract),
            ),
            (
                scope.path / "docs/index.md",
                FlextInfraUtilitiesDocsRender.docs_project_index(scope, contract),
            ),
            (
                scope.path / "docs/guides/README.md",
                FlextInfraUtilitiesDocsRender.docs_guides_index(
                    scope, guide_paths=tuple(sorted(guide_paths))
                ),
            ),
            (
                scope.path / "docs/api-reference/README.md",
                FlextInfraUtilitiesDocsRender.docs_api_readme(scope, contract),
            ),
            (
                scope.path / "mkdocs.yml",
                FlextInfraUtilitiesDocsRender.docs_project_mkdocs(
                    scope, contract, module_names
                ),
            ),
            (
                scope.path / "docs/api-reference/generated/overview.md",
                FlextInfraUtilitiesDocsRender.docs_overview_page(scope, contract),
            ),
            *FlextInfraUtilitiesDocsGenerateProjectMixin.docs_project_api_artifacts(
                scope
            ),
        ]
        pruned = (
            FlextInfraUtilitiesDocsGenerateProjectMixin._prune_generated_tree_artifacts(
                scope.path, scope.path / "docs/api-reference/generated", rendered
            )
        )
        if pruned.failure:
            return r[t.VariadicTuple[DocsRenderedArtifactTuple]].from_failure(pruned)
        return FlextInfraUtilitiesDocsGenerateProjectMixin.docs_normalize_artifacts((
            *((scope.path, path, content) for path, content in rendered),
            *guides.value,
            *pruned.value,
        ))


__all__: list[str] = ["FlextInfraUtilitiesDocsGenerateProjectMixin"]
