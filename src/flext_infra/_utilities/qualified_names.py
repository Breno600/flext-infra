"""LibCST qualified-name metadata utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

import libcst as cst
from libcst.metadata import (
    CodePosition,
    CodeRange,
    MetadataWrapper,
    PositionProvider,
    QualifiedNameProvider,
    QualifiedNameSource,
)

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraUtilitiesQualifiedNames:
    """Resolve lazy LibCST qualified-name metadata through its public visitor API."""

    class _ResidueCollector(cst.CSTVisitor):
        METADATA_DEPENDENCIES = (QualifiedNameProvider,)

        def __init__(self, candidates: t.Infra.Container[str]) -> None:
            self.candidates = candidates
            self.residue: set[str] = set()

        @override
        def on_visit(self, node: cst.CSTNode) -> bool:
            self.residue.update(
                qualified_name.name
                for qualified_name in self.get_metadata(QualifiedNameProvider, node, ())
                if qualified_name.name in self.candidates
            )
            return True

    class _CallableCollector(cst.CSTVisitor):
        METADATA_DEPENDENCIES = (PositionProvider, QualifiedNameProvider)

        def __init__(self, source: str) -> None:
            self.lines = source.splitlines()
            self.names: t.MutableMappingKV[t.Pair[int, int], frozenset[str]] = {}

        def _collect(self, node: cst.BaseExpression) -> None:
            if not isinstance(node, (cst.Name, cst.Attribute)):
                return
            location = self.get_metadata(
                PositionProvider,
                node,
                CodeRange(CodePosition(0, 0), CodePosition(0, 0)),
            )
            position = location.start
            # Python AST columns count UTF-8 bytes; LibCST columns count characters.
            column = len(self.lines[position.line - 1][: position.column].encode())
            self.names[position.line, column] = frozenset(
                name.name
                for name in self.get_metadata(QualifiedNameProvider, node, ())
                if name.source is QualifiedNameSource.IMPORT
            )

        @override
        def visit_Call(self, node: cst.Call) -> None:
            self._collect(node.func)

        @override
        def visit_Decorator(self, node: cst.Decorator) -> None:
            if not isinstance(node.decorator, cst.Call):
                self._collect(node.decorator)

    @staticmethod
    def dotted_name(node: cst.BaseExpression | None) -> str | None:
        """Return a static dotted name, or ``None`` for a dynamic expression."""
        if isinstance(node, cst.Name):
            return node.value
        if isinstance(node, cst.Attribute):
            parent = FlextInfraUtilitiesQualifiedNames.dotted_name(node.value)
            return f"{parent}.{node.attr.value}" if parent else None
        return None

    @staticmethod
    def module_expression(module: str) -> cst.Attribute | cst.Name:
        """Build a typed LibCST expression for a dotted module name."""
        parts = module.split(".")
        expression: cst.Attribute | cst.Name = cst.Name(parts[0])
        for part in parts[1:]:
            expression = cst.Attribute(value=expression, attr=cst.Name(part))
        return expression

    @staticmethod
    def without_exports(
        value: cst.BaseExpression, names: t.Infra.Container[str]
    ) -> cst.BaseExpression:
        """Drop ``names`` from a literal ``__all__`` list or tuple expression."""
        if not isinstance(value, cst.List | cst.Tuple):
            return value
        return value.with_changes(
            elements=tuple(
                element
                for element in value.elements
                if not isinstance(element.value, cst.SimpleString)
                or not isinstance(element.value.evaluated_value, str)
                or element.value.evaluated_value not in names
            )
        )

    @staticmethod
    def filter_exports[N: (cst.Assign, cst.AnnAssign)](
        node: N, names: t.Infra.Container[str]
    ) -> N:
        """Drop ``names`` from an ``__all__`` assignment; other assignments pass."""
        targets = (
            tuple(target.target for target in node.targets)
            if isinstance(node, cst.Assign)
            else (node.target,)
        )
        if (
            len(targets) != 1
            or not isinstance(targets[0], cst.Name)
            or targets[0].value != "__all__"
            or node.value is None
        ):
            return node
        return node.with_changes(
            value=FlextInfraUtilitiesQualifiedNames.without_exports(node.value, names)
        )

    @staticmethod
    def normalized_import_aliases(
        aliases: t.SequenceOf[cst.ImportAlias], *, parenthesized: bool
    ) -> t.VariadicTuple[cst.ImportAlias]:
        """Repair separators after import aliases were dropped or rewritten."""
        last_index = len(aliases) - 1
        return tuple(
            alias.with_changes(comma=cst.MaybeSentinel.DEFAULT)
            if index == last_index and not parenthesized
            else alias.with_changes(
                comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
            )
            if index < last_index and not isinstance(alias.comma, cst.Comma)
            else alias
            for index, alias in enumerate(aliases)
        )

    @staticmethod
    def rebinds_name_in_place(parent: p.AttributeProbe, node: cst.CSTNode) -> bool:
        """Return whether ``parent`` spells ``node`` as a binding, not a reference.

        An import alias, an attribute's own ``attr``, and a keyword argument's
        name are written by the surrounding syntax, so a rename must leave them
        exactly as they are.
        """
        if isinstance(parent, cst.ImportAlias):
            return True
        if isinstance(parent, cst.Attribute) and parent.attr is node:
            return True
        return isinstance(parent, cst.Arg) and parent.keyword is node

    @classmethod
    def qualified_name_residue(
        cls, source: str, candidates: t.Infra.Container[str]
    ) -> frozenset[str]:
        """Return candidate qualified names referenced by Python source."""
        collector = cls._ResidueCollector(candidates)
        MetadataWrapper(cst.parse_module(source)).visit(collector)
        return frozenset(collector.residue)

    @classmethod
    def imported_callable_names(
        cls, source: str
    ) -> t.MappingKV[t.Pair[int, int], frozenset[str]]:
        """Resolve call/decorator import provenance at Python AST source positions."""
        collector = cls._CallableCollector(source)
        MetadataWrapper(cst.parse_module(source)).visit(collector)
        return collector.names


__all__: list[str] = ["FlextInfraUtilitiesQualifiedNames"]
