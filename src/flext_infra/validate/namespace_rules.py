"""Public strict namespace rule facade."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._namespace_rules.contracts import FlextInfraNamespaceRulesContracts
from ._namespace_rules.imports import FlextInfraNamespaceRulesImports
from ._namespace_rules.structure import FlextInfraNamespaceRulesStructure

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import m, p, t


class FlextInfraNamespaceRules(
    FlextInfraNamespaceRulesStructure,
    FlextInfraNamespaceRulesImports,
    FlextInfraNamespaceRulesContracts,
):
    """Compose every namespace invariant through one explicit diamond MRO."""

    @classmethod
    def check_module(
        cls,
        tree: p.AttributeProbe,
        filepath: Path,
        *,
        class_stem: str,
        package_name: str,
        source: str,
        is_test_file: bool,
        policy: m.Infra.NamespaceModulePolicy,
    ) -> t.StrSequence:
        """Evaluate the complete strict contract for one Rope AST module."""
        return (
            *cls.check_structure(
                tree,
                filepath,
                class_stem=class_stem,
                is_test_file=is_test_file,
                policy=policy,
                source=source,
            ),
            *cls.check_imports(tree, filepath, package_name=package_name),
            *cls.check_contracts(tree, filepath, source=source),
        )


__all__: list[str] = ["FlextInfraNamespaceRules"]
