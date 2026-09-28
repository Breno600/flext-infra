"""Binding-aware reference rewrites for automatic class nesting."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, override

import libcst as cst
from libcst.metadata import MetadataWrapper, ParentNodeProvider, QualifiedNameProvider

from ..qualified_names import FlextInfraUtilitiesQualifiedNames

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesSemanticCutoverNestingReferences:
    """Rewrite imports and usages of classes moved below a module owner."""

    class _NestingTransformer(cst.CSTTransformer):
        METADATA_DEPENDENCIES = (ParentNodeProvider, QualifiedNameProvider)

        def __init__(
            self,
            *,
            module_name: str,
            is_package_init: bool,
            bindings_by_module: t.MappingKV[str, t.StrMapping],
            definitions: t.StrMapping,
        ) -> None:
            self.module_name = module_name
            self.is_package_init = is_package_init
            self.bindings_by_module = bindings_by_module
            self.definitions = definitions
            self.qualified = {
                f"{module}.{name}": f"{owner}.{name}"
                for module, bindings in bindings_by_module.items()
                for name, owner in bindings.items()
            }
            self.qualified.update(
                (name, f"{owner}.{name}") for name, owner in definitions.items()
            )
            self.local_expressions: MutableMapping[str, str] = {
                name: f"{owner}.{name}" for name, owner in definitions.items()
            }

        @staticmethod
        def _alias_name(asname: cst.AsName) -> str:
            """Return the bound alias identifier, rejecting impossible shapes.

            libcst types ``AsName.name`` as ``Name | Tuple | List``, but import
            aliases parsed from valid Python can only carry a ``Name``
            (``import x as (a, b)`` is a SyntaxError); Tuple/List belong to
            ``WithItem``/``ExceptHandler`` clauses only.
            """
            if not isinstance(asname.name, cst.Name):
                msg = f"unsupported import alias target: {type(asname.name).__name__}"
                raise TypeError(msg)
            return asname.name.value

        def _import_module(self, node: cst.ImportFrom) -> str:
            suffix = FlextInfraUtilitiesQualifiedNames.dotted_name(node.module) or ""
            if not node.relative:
                return suffix
            package_parts = self.module_name.split(".")
            if not self.is_package_init:
                package_parts = package_parts[:-1]
            ascend = len(node.relative) - 1
            if ascend > len(package_parts):
                return ""
            prefix = package_parts[: len(package_parts) - ascend]
            return ".".join((*prefix, suffix) if suffix else prefix)

        @override
        def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
            bindings = self.bindings_by_module.get(self._import_module(node), {})
            if not bindings or isinstance(node.names, cst.ImportStar):
                return
            for imported in node.names:
                name = (
                    FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""
                )
                if name not in bindings:
                    continue
                local_name = (
                    self._alias_name(imported.asname) if imported.asname else name
                )
                owner_name = local_name if imported.asname else bindings[name]
                self.local_expressions[local_name] = f"{owner_name}.{name}"

        def _resolves_bare_after_nesting(self, node: cst.CSTNode) -> bool:
            """Report whether a moved class stays reachable by its bare name here.

            References are rewritten before the structural move, so the current
            tree cannot answer this; the plan can. After nesting, the owner's
            class body holds every moved class as a sibling, and a class body
            reaches its siblings by bare name while it is executing. A method
            body does not: the enclosing class scope is invisible from inside a
            function, so there the qualified form is the only one that resolves.
            Walking outward, a function boundary therefore means qualify, and a
            class that is the owner or is itself being moved under the owner
            means the reference will land in that shared class scope.
            """
            current: cst.CSTNode | None = self.get_metadata(
                ParentNodeProvider, node, None
            )
            while current is not None:
                if isinstance(current, cst.FunctionDef):
                    return False
                if isinstance(current, cst.ClassDef):
                    name = current.name.value
                    return name in self.definitions or name in set(
                        self.definitions.values()
                    )
                current = self.get_metadata(ParentNodeProvider, current, None)
            return False

        def _single_binding(
            self, original_node: cst.CSTNode, *, ambiguity: str
        ) -> str | None:
            """Return the one class-nesting replacement bound to ``original_node``.

            ``None`` when the node carries no nesting binding; two competing
            bindings are ambiguous and raise with ``ambiguity`` naming the site.
            """
            replacements = {
                replacement
                for qualified_name in self.get_metadata(
                    QualifiedNameProvider, original_node, ()
                )
                if (replacement := self.qualified.get(qualified_name.name)) is not None
            }
            if not replacements:
                return None
            if len(replacements) != 1:
                msg = f"ambiguous class-nesting {ambiguity}: {sorted(replacements)}"
                raise ValueError(msg)
            return replacements.pop()

        @override
        def leave_Name(
            self, original_node: cst.Name, updated_node: cst.Name
        ) -> cst.BaseExpression:
            bound = self._single_binding(original_node, ambiguity="binding")
            if bound is None:
                return updated_node
            parent = self.get_metadata(ParentNodeProvider, original_node)
            if FlextInfraUtilitiesQualifiedNames.rebinds_name_in_place(
                parent, original_node
            ):
                return updated_node
            if isinstance(parent, cst.ClassDef) and parent.name is original_node:
                return updated_node
            if original_node.value in self.definitions and (
                self._resolves_bare_after_nesting(original_node)
            ):
                return updated_node
            replacement = self.local_expressions.get(original_node.value)
            if replacement is None:
                replacement = bound
            return cst.parse_expression(replacement)

        @override
        def leave_Attribute(
            self, original_node: cst.Attribute, updated_node: cst.Attribute
        ) -> cst.BaseExpression:
            bound = self._single_binding(original_node, ambiguity="attribute")
            if bound is None:
                return updated_node
            owner, name = bound.split(".", maxsplit=1)
            return cst.Attribute(
                value=cst.Attribute(value=updated_node.value, attr=cst.Name(owner)),
                attr=cst.Name(name),
            )

        @override
        def leave_ImportFrom(
            self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
        ) -> cst.BaseSmallStatement | cst.RemovalSentinel:
            bindings = self.bindings_by_module.get(
                self._import_module(original_node), {}
            )
            if not bindings or isinstance(updated_node.names, cst.ImportStar):
                return updated_node
            aliases: list[cst.ImportAlias] = []
            seen: set[t.Pair[str, str]] = set()
            for imported in updated_node.names:
                name = (
                    FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""
                )
                owner = bindings.get(name)
                rewritten = (
                    imported.with_changes(name=cst.Name(owner)) if owner else imported
                )
                identity = (
                    FlextInfraUtilitiesQualifiedNames.dotted_name(rewritten.name) or "",
                    self._alias_name(rewritten.asname) if rewritten.asname else "",
                )
                if identity not in seen:
                    seen.add(identity)
                    aliases.append(rewritten)
            if not aliases:
                return cst.RemoveFromParent()
            return updated_node.with_changes(
                names=FlextInfraUtilitiesQualifiedNames.normalized_import_aliases(
                    aliases, parenthesized=bool(updated_node.lpar)
                )
            )

        @override
        def leave_Assign(
            self, original_node: cst.Assign, updated_node: cst.Assign
        ) -> cst.BaseSmallStatement:
            return FlextInfraUtilitiesQualifiedNames.filter_exports(
                updated_node, self.definitions
            )

        @override
        def leave_AnnAssign(
            self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
        ) -> cst.BaseSmallStatement:
            return FlextInfraUtilitiesQualifiedNames.filter_exports(
                updated_node, self.definitions
            )

    @classmethod
    def _rewrite_class_nesting_references(
        cls,
        source: str,
        *,
        module_name: str,
        is_package_init: bool,
        bindings_by_module: t.MappingKV[str, t.StrMapping],
        definitions: t.StrMapping,
    ) -> str:
        """Return binding-proven import and usage rewrites without effects."""
        return (
            MetadataWrapper(cst.parse_module(source))
            .visit(
                cls._NestingTransformer(
                    module_name=module_name,
                    is_package_init=is_package_init,
                    bindings_by_module=bindings_by_module,
                    definitions=definitions,
                )
            )
            .code
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverNestingReferences"]
