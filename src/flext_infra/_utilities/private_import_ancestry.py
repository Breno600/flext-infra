"""Static lexical inheritance discovery for public facade cutover."""

from __future__ import annotations

import ast
from importlib.util import resolve_name

from flext_infra import t


class FlextInfraUtilitiesPrivateImportAncestry:
    """Resolve bases using bindings present when each class is declared."""

    @staticmethod
    def class_bases(
        sources: t.MappingKV[str, t.Pair[str, bool]],
    ) -> t.MappingKV[str, t.VariadicTuple[str]]:
        """Index static class ancestry, including private intermediate owners."""
        bases: t.MutableMappingKV[str, t.VariadicTuple[str]] = {}
        for module, (source, is_package) in sources.items():
            tree = ast.parse(source, filename=module)
            package = module if is_package else module.rpartition(".")[0]

            def collect(
                statements: t.SequenceOf[ast.stmt],
                scope: str,
                names: t.MutableStrMapping,
                module_names: t.MutableStrMapping,
                module: str,
                package: str,
            ) -> None:
                def reference(node: ast.expr) -> str:
                    expression = ast.unparse(
                        node.value if isinstance(node, ast.Subscript) else node
                    )
                    root, separator, suffix = expression.partition(".")
                    return names.get(root, f"{module}.{root}") + (
                        f".{suffix}" if separator else ""
                    )

                for node in statements:
                    if isinstance(node, ast.ImportFrom) and node.module:
                        imported = (
                            resolve_name(f"{'.' * node.level}{node.module}", package)
                            if node.level
                            else node.module
                        )
                        for alias in node.names:
                            names[alias.asname or alias.name] = (
                                f"{imported}.{alias.name}"
                            )
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            names[alias.asname or alias.name.split(".")[0]] = (
                                alias.name if alias.asname else alias.name.split(".")[0]
                            )
                    elif isinstance(node, ast.ClassDef):
                        identity = f"{scope}.{node.name}"
                        bases[identity] = tuple(
                            reference(base)
                            for base in node.bases
                            if isinstance(
                                base, ast.Name | ast.Attribute | ast.Subscript
                            )
                        )
                        # Bases see the declaration scope; class bodies do not
                        # close over an enclosing class's local namespace.
                        collect(
                            node.body,
                            identity,
                            dict(module_names),
                            module_names,
                            module,
                            package,
                        )
                        names[node.name] = identity
                    elif isinstance(node, ast.Assign | ast.AnnAssign):
                        value = node.value
                        targets = (
                            node.targets
                            if isinstance(node, ast.Assign)
                            else [node.target]
                        )
                        for target in targets:
                            if isinstance(target, ast.Name):
                                names[target.id] = (
                                    reference(value)
                                    if isinstance(value, ast.Name | ast.Attribute)
                                    else f"{scope}.{target.id}"
                                )

            module_names: t.MutableStrMapping = {}
            collect(tree.body, module, module_names, module_names, module, package)
        return bases


__all__: list[str] = ["FlextInfraUtilitiesPrivateImportAncestry"]
