"""Public strict namespace rule facade."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._namespace_rules.contracts import FlextInfraNamespaceRulesContracts
from ._namespace_rules.imports import FlextInfraNamespaceRulesImports
from ._namespace_rules.structure import FlextInfraNamespaceRulesStructure

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import m, t


class FlextInfraNamespaceRules(
    FlextInfraNamespaceRulesStructure,
    FlextInfraNamespaceRulesImports,
    FlextInfraNamespaceRulesContracts,
):
    """Compose every namespace invariant through one explicit diamond MRO."""

    @classmethod
    def check_module(
        cls, visit: m.Infra.RopeModuleVisit, filepath: Path
    ) -> t.StrSequence:
        """Evaluate one shared Rope visit against its declared convention."""
        layout = visit.convention.project_layout
        return (
            *cls.check_structure(
                visit.tree,
                filepath,
                class_stem=layout.class_stem if layout is not None else "",
                policy=visit.convention.module_policy,
                source=visit.source,
            ),
            *cls.check_imports(
                visit.tree, filepath, package_name=visit.convention.package_name
            ),
            *cls.check_contracts(visit, filepath),
        )


__all__: list[str] = ["FlextInfraNamespaceRules"]
