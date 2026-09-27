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
        cls,
        module: m.Infra.ParsedPythonModule,
        filepath: Path,
        *,
        class_stem: str,
        package_name: str,
        policy: m.Infra.NamespaceModulePolicy,
    ) -> t.StrSequence:
        """Evaluate the complete strict contract for one parsed Rope module.

        ``filepath`` is project-relative; ``module`` carries the source text
        and the Rope module whose AST every rule family inspects.
        """
        tree = module.tree.get_ast()
        return (
            *cls.check_structure(
                tree,
                filepath,
                class_stem=class_stem,
                policy=policy,
                source=module.source,
            ),
            *cls.check_imports(tree, filepath, package_name=package_name),
            *cls.check_contracts(tree, filepath, source=module.source),
        )


__all__: list[str] = ["FlextInfraNamespaceRules"]
