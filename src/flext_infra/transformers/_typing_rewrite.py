"""Binding-aware rewrites restricted to concrete-syntax type positions."""

from __future__ import annotations

from typing import ClassVar

import libcst as cst
from libcst.metadata import QualifiedNameSource, Scope

from flext_infra import t


class FlextInfraRefactorTypingUnifierRewriteMixin:
    """Share type-position traversal with import migration, preserving payloads."""

    class TypeExpression:
        """Resolve each type name in the original lexical scope before rewriting."""

        _MAPPING_ALIAS: ClassVar[str] = "t.MappingKV"
        _CONTAINERS: ClassVar[t.StrMapping] = {
            "builtins.dict": _MAPPING_ALIAS,
            "typing.Dict": _MAPPING_ALIAS,
            "typing.MutableMapping": _MAPPING_ALIAS,
            "collections.abc.MutableMapping": _MAPPING_ALIAS,
            "builtins.list": "t.SequenceOf",
            "typing.List": "t.SequenceOf",
        }
        _TUPLES: ClassVar[t.MappingKV[int, str]] = {
            2: "t.Pair",
            3: "t.Triple",
            4: "t.Quad",
        }
        _VARIADIC_TUPLE_PARTS: ClassVar[int] = 2

        def __init__(
            self,
            scope: Scope,
            *,
            canonical_map: t.MappingKV[frozenset[str], str],
            replacements: t.StrMapping,
            containers: bool,
            widen: bool,
        ) -> None:
            self.scope = scope
            self.canonical_map = canonical_map
            self.replacements = replacements
            self.containers = containers
            self.widen = widen
            self.changes: list[str] = []
            self.requires_t = False
            self.replaced_symbols: list[t.Pair[cst.BaseExpression, str]] = []
            self.module = cst.Module(body=())

        def qualified_name(self, node: cst.BaseExpression) -> str | None:
            """Resolve one imported or builtin identity; reject competing bindings.

            Competing bindings resolve deterministically before failing loud:
            an IMPORT-source candidate outranks a module-level rebinding, and a
            fully-qualified name outranks a bare one — the binding actually
            imported in the file is the identity the rewrite must honor
            (flext-oolmd: facade aliases shadowed by their own constants
            module, e.g. ``c = FlextDbOracleConstants`` beside
            ``from flext_db_oracle import c``).
            """
            names = list(self.scope.get_qualified_names_for(node))
            if len(names) > 1:
                imported = [
                    name for name in names if name.source == QualifiedNameSource.IMPORT
                ]
                candidates = imported or names
                dotted = [name for name in candidates if "." in name.name]
                names = dotted or candidates
            if len(names) > 1:
                msg = f"ambiguous type binding: {sorted(name.name for name in names)}"
                raise ValueError(msg)
            return next(
                (
                    name.name
                    for name in names
                    if name.source
                    in {QualifiedNameSource.IMPORT, QualifiedNameSource.BUILTIN}
                ),
                None,
            )

        def rewrite(
            self,
            node: cst.BaseExpression,
            *,
            allow_widen: bool | None = None,
        ) -> cst.BaseExpression:
            """Rewrite types while leaving calls and non-type payloads untouched."""
            widen = self.widen if allow_widen is None else allow_widen
            if isinstance(node, cst.SimpleString | cst.ConcatenatedString):
                value = node.evaluated_value
                if not isinstance(value, str):
                    return node
                expression = cst.parse_expression(value)
                rewritten = self.rewrite(expression, allow_widen=widen)
                if rewritten.deep_equals(expression):
                    return node
                return cst.SimpleString(repr(self.module.code_for_node(rewritten)))
            if isinstance(node, cst.Subscript):
                return self._subscript(node, widen=widen)
            if isinstance(node, cst.BinaryOperation) and isinstance(
                node.operator,
                cst.BitOr,
            ):
                canonical = self._union(node)
                if canonical is not None:
                    return canonical
                return node.with_changes(
                    left=self.rewrite(node.left, allow_widen=widen),
                    right=self.rewrite(node.right, allow_widen=widen),
                )
            if isinstance(node, cst.Tuple | cst.List):
                return node.with_changes(
                    elements=tuple(
                        element.with_changes(
                            value=self.rewrite(element.value, allow_widen=False),
                        )
                        for element in node.elements
                    ),
                )
            if isinstance(node, cst.Name | cst.Attribute):
                replacement = self.replacements.get(self.qualified_name(node) or "")
                if replacement is not None:
                    self.replaced_symbols.append((node, replacement))
                    return self._changed(
                        node,
                        cst.parse_expression(replacement),
                        "symbol",
                    )
            return node

        def _subscript(self, node: cst.Subscript, *, widen: bool) -> cst.BaseExpression:
            name = self.qualified_name(node.value)
            if name in {"typing.Literal", "typing_extensions.Literal"}:
                return node
            annotated = name in {"typing.Annotated", "typing_extensions.Annotated"}
            slices = tuple(
                element.with_changes(
                    slice=element.slice.with_changes(
                        value=self.rewrite(
                            element.slice.value,
                            allow_widen=widen if annotated else False,
                        ),
                    ),
                )
                if isinstance(element.slice, cst.Index)
                and (not annotated or index == 0)
                else element
                for index, element in enumerate(node.slice)
            )
            value = self.rewrite(node.value, allow_widen=False)
            if self.containers and name in {"builtins.tuple", "typing.Tuple"}:
                alias = self._tuple_alias(node)
                if alias is not None:
                    self.requires_t = True
                    value = cst.parse_expression(alias)
                    if alias == "t.VariadicTuple":
                        slices = (
                            slices[0].with_changes(comma=cst.MaybeSentinel.DEFAULT),
                        )
            elif (
                self.containers
                and widen
                and (replacement := self._CONTAINERS.get(name or "")) is not None
            ):
                self.requires_t = True
                value = cst.parse_expression(replacement)
            updated = node.with_changes(value=value, slice=slices)
            return self._changed(node, updated, "built-in annotation")

        def _tuple_alias(self, node: cst.Subscript) -> str | None:
            if (
                len(node.slice) == self._VARIADIC_TUPLE_PARTS
                and isinstance(node.slice[1].slice, cst.Index)
                and isinstance(node.slice[1].slice.value, cst.Ellipsis)
            ):
                return "t.VariadicTuple"
            return self._TUPLES.get(len(node.slice))

        def _union(self, node: cst.BinaryOperation) -> cst.BaseExpression | None:
            pending: list[cst.BaseExpression] = [node]
            names: set[str] = set()
            while pending:
                member = pending.pop()
                if isinstance(member, cst.BinaryOperation) and isinstance(
                    member.operator,
                    cst.BitOr,
                ):
                    pending.extend((member.left, member.right))
                    continue
                name = self.qualified_name(member)
                if name is None or not name.startswith(("builtins.", "datetime.")):
                    return None
                names.add(name.rsplit(".", maxsplit=1)[-1])
            replacement = self.canonical_map.get(frozenset(names))
            if replacement is None:
                return None
            self.requires_t = self.requires_t or replacement.startswith("t.")
            return self._changed(
                node,
                cst.parse_expression(replacement),
                "inline union",
            )

        def _changed(
            self,
            original: cst.BaseExpression,
            updated: cst.BaseExpression,
            kind: str,
        ) -> cst.BaseExpression:
            if not original.deep_equals(updated):
                self.changes.append(
                    f"Canonicalized {kind} {self.module.code_for_node(original)} -> "
                    f"{self.module.code_for_node(updated)}",
                )
            return updated


__all__: list[str] = ["FlextInfraRefactorTypingUnifierRewriteMixin"]
