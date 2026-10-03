"""LibCST qualified-name metadata utilities.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    import libcst as cst

    from flext_infra import p, t


class FlextInfraUtilitiesQualifiedNames:
    """Resolve lazy LibCST qualified-name metadata through its public visitor API."""

    @staticmethod
    def dotted_name(node: cst.BaseExpression | None) -> str | None:
        """Return a static dotted name, or ``None`` for a dynamic expression.

        Returns:
            A static dotted name, or ``None`` for a dynamic expression.

        """
        import libcst as cst

        if isinstance(node, cst.Name):
            return node.value
        if isinstance(node, cst.Attribute):
            parent = FlextInfraUtilitiesQualifiedNames.dotted_name(node.value)
            return f"{parent}.{node.attr.value}" if parent else None
        return None

    @staticmethod
    def without_exports(
        value: cst.BaseExpression,
        names: t.Infra.Container[str],
    ) -> cst.BaseExpression:
        """Drop ``names`` from a literal ``__all__`` list or tuple expression.

        Returns:
            The resulting ``cst.BaseExpression``.

        """
        import libcst as cst

        if not isinstance(value, cst.List | cst.Tuple):
            return value
        return value.with_changes(
            elements=tuple(
                element
                for element in value.elements
                if not isinstance(element.value, cst.SimpleString)
                or not isinstance(element.value.evaluated_value, str)
                or element.value.evaluated_value not in names
            ),
        )

    @staticmethod
    def filter_exports[N: (cst.Assign, cst.AnnAssign)](
        node: N,
        names: t.Infra.Container[str],
    ) -> N:
        """Drop ``names`` from an ``__all__`` assignment; other assignments pass.

        Returns:
            The resulting ``N``.

        """
        import libcst as cst

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
            value=FlextInfraUtilitiesQualifiedNames.without_exports(node.value, names),
        )

    @staticmethod
    def normalized_import_aliases(
        aliases: t.SequenceOf[cst.ImportAlias],
        *,
        parenthesized: bool,
    ) -> t.VariadicTuple[cst.ImportAlias]:
        """Repair separators after import aliases were dropped or rewritten.

        Returns:
            The resulting ``t.VariadicTuple[cst.ImportAlias]``.

        """
        import libcst as cst

        last_index = len(aliases) - 1
        return tuple(
            alias.with_changes(comma=cst.MaybeSentinel.DEFAULT)
            if index == last_index and not parenthesized
            else alias.with_changes(
                comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" ")),
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

        Returns:
            Whether ``parent`` spells ``node`` as a binding, not a reference.

        """
        import libcst as cst

        if isinstance(parent, cst.ImportAlias):
            return True
        if isinstance(parent, cst.Attribute) and parent.attr is node:
            return True
        return isinstance(parent, cst.Arg) and parent.keyword is node

    @classmethod
    def qualified_name_residue(
        cls,
        source: str,
        candidates: t.Infra.Container[str],
    ) -> frozenset[str]:
        """Return candidate qualified names referenced by Python source.

        Returns:
            Candidate qualified names referenced by Python source.

        """
        import libcst as cst
        from libcst.metadata import MetadataWrapper, QualifiedNameProvider

        class _ResidueCollector(cst.CSTVisitor):
            METADATA_DEPENDENCIES = (QualifiedNameProvider,)

            def __init__(self, candidates: t.Infra.Container[str]) -> None:
                self.candidates = candidates
                self.residue: set[str] = set()

            @override
            def on_visit(self, node: cst.CSTNode) -> bool:
                self.residue.update(
                    qualified_name.name
                    for qualified_name in self.get_metadata(
                        QualifiedNameProvider,
                        node,
                        (),
                    )
                    if qualified_name.name in self.candidates
                )
                return True

        collector = _ResidueCollector(candidates)
        MetadataWrapper(cst.parse_module(source)).visit(collector)
        return frozenset(collector.residue)


__all__: list[str] = ["FlextInfraUtilitiesQualifiedNames"]
