"""Concrete-syntax ownership moves for automatic class nesting.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast

import libcst as cst
from libcst.codemod import CodemodContext
from libcst.codemod.visitors import AddImportsVisitor

from flext_infra import t
from flext_infra._utilities._semantic_cutover.nesting_references import (
    FlextInfraUtilitiesSemanticCutoverNestingReferences,
)


class FlextInfraUtilitiesSemanticCutoverNestingCst(
    FlextInfraUtilitiesSemanticCutoverNestingReferences,
):
    """Move proven top-level class nodes under one existing owner class."""

    @classmethod
    def _rewrite_class_nesting_source(
        cls,
        source: str,
        *,
        module_name: str,
        is_package_init: bool,
        bindings_by_module: t.MappingKV[str, t.StrMapping],
        definitions: t.StrMapping,
    ) -> str:
        """Return a binding-proven structural rewrite without filesystem effects.

        Returns:
            A binding-proven structural rewrite without filesystem effects.

        """
        rewritten = cls._rewrite_class_nesting_references(
            source,
            module_name=module_name,
            is_package_init=is_package_init,
            bindings_by_module=bindings_by_module,
            definitions=definitions,
        )
        return cls._nest_definitions(rewritten, definitions)

    @staticmethod
    def _annotation_tail(annotation: cst.BaseExpression) -> str:
        """Return an annotation's qualifier name (``ClassVar[int]``: ``ClassVar``).

        Returns:
            The trailing identifier of the annotation's qualifier, or ``""``.

        """
        qualifier = (
            annotation.value if isinstance(annotation, cst.Subscript) else annotation
        )
        if isinstance(qualifier, cst.Attribute):
            return qualifier.attr.value
        if isinstance(qualifier, cst.Name):
            return qualifier.value
        return ""

    @classmethod
    def _class_variable_type(
        cls,
        statement: cst.BaseSmallStatement,
    ) -> cst.BaseExpression | None:
        """Return the type a moved binding declares as its ``ClassVar``.

        An annotated binding keeps its annotation (unless it already is a
        ``ClassVar`` or ``Final``); a plain binding of a number or string
        literal declares the literal's builtin type. Anything else stays a
        plain class attribute.

        Returns:
            The type expression to wrap in ``ClassVar``, or ``None``.

        """
        if isinstance(statement, cst.AnnAssign):
            annotation = statement.annotation.annotation
            if cls._annotation_tail(annotation) in {"ClassVar", "Final"}:
                return None
            return annotation
        if isinstance(statement, cst.Assign) and isinstance(
            statement.value,
            cst.Integer | cst.Float | cst.SimpleString,
        ):
            return cst.Name(type(ast.literal_eval(statement.value.value)).__name__)
        return None

    @classmethod
    def _class_member(
        cls,
        node: cst.BaseStatement,
    ) -> t.Pair[cst.BaseStatement, bool]:
        """Return a module member in its owner-body form.

        A function becomes a static method; a constant binding becomes a
        ``ClassVar`` (its own annotation, or the literal's builtin type) so the
        owner never mistakes it for an instance field. The flag reports whether
        the member now names ``ClassVar``.

        Returns:
            The member statement for the owner body and its ``ClassVar`` flag.

        Raises:
            TypeError: If class-nesting cannot move.
        """
        if not isinstance(
            node,
            cst.ClassDef | cst.FunctionDef | cst.SimpleStatementLine,
        ):
            msg = f"class-nesting cannot move {type(node).__name__} members"
            raise TypeError(msg)
        # Comments that documented the member move with it; the blank
        # separator carries no indentation (W293).
        leading: tuple[cst.EmptyLine, ...] = (
            cst.EmptyLine(indent=False),
            *(line for line in node.leading_lines if line.comment is not None),
        )
        if isinstance(node, cst.FunctionDef):
            static = cst.Decorator(decorator=cst.Name("staticmethod"))
            return (
                node.with_changes(
                    leading_lines=leading,
                    decorators=(static, *node.decorators),
                ),
                False,
            )
        statement = node.body[0] if isinstance(node, cst.SimpleStatementLine) else None
        declared = (
            cls._class_variable_type(statement) if statement is not None else None
        )
        if not isinstance(statement, cst.AnnAssign | cst.Assign) or declared is None:
            return node.with_changes(leading_lines=leading), False
        classvar = cst.AnnAssign(
            target=cls._assignment_targets(statement)[0],
            annotation=cst.Annotation(
                annotation=cst.Subscript(
                    value=cst.Name("ClassVar"),
                    slice=(cst.SubscriptElement(slice=cst.Index(value=declared)),),
                ),
            ),
            value=statement.value,
        )
        return node.with_changes(leading_lines=leading, body=(classvar,)), True

    @staticmethod
    def _module_with_owner(
        module: cst.Module,
        owner_name: str,
        moved: t.VariadicTuple[cst.BaseStatement],
    ) -> t.Pair[cst.Module, t.VariadicTuple[cst.ClassDef]]:
        """Return the module holding its owner class, creating it before the moves.

        Returns:
            The module and every top-level class named as the owner.

        Raises:
            TypeError: If the owner declaration cannot be built.

        """
        owner_nodes = tuple(
            node
            for node in module.body
            if isinstance(node, cst.ClassDef) and node.name.value == owner_name
        )
        if owner_nodes:
            return module, owner_nodes
        owner = cst.parse_statement(
            f'class {owner_name}:\n    """Canonical namespace owner."""\n',
        )
        if not isinstance(owner, cst.ClassDef):
            msg = f"class-nesting could not create owner {owner_name}"
            raise TypeError(msg)
        index = next(index for index, node in enumerate(module.body) if node in moved)
        body = (*module.body[:index], owner, *module.body[index:])
        return module.with_changes(body=body), (owner,)

    @classmethod
    def _owner_holding(
        cls,
        owner: cst.ClassDef,
        nested: t.VariadicTuple[cst.BaseStatement],
    ) -> cst.ClassDef:
        """Return the owner class whose body leads with the moved members.

        A moved class was defined before the owner at module level, so a class
        body member may already use it as a definition-time base. Appending
        would place the definition after that use and break import; the
        docstring keeps position and the moves lead the rest.

        Returns:
            The owner class with the moved members in its body.

        Raises:
            TypeError: If the owner body shape is unsupported.

        """
        if isinstance(owner.body, cst.IndentedBlock):
            existing = owner.body.body
            if (
                len(existing) == 1
                and isinstance(existing[0], cst.SimpleStatementLine)
                and len(existing[0].body) == 1
                and isinstance(existing[0].body[0], cst.Pass)
            ):
                existing = ()
            docstring, remainder = cls._split_docstring(existing)
            return owner.with_changes(
                body=owner.body.with_changes(body=(*docstring, *nested, *remainder)),
            )
        if isinstance(owner.body, cst.SimpleStatementSuite):
            # A simple suite can only hold small statements; narrow before
            # promoting the remaining ones into an IndentedBlock line.
            statements = tuple(
                statement
                for statement in owner.body.body
                if not isinstance(statement, cst.Pass)
            )
            existing_lines = (
                (cst.SimpleStatementLine(body=statements),) if statements else ()
            )
            docstring, remainder = cls._split_docstring(existing_lines)
            return owner.with_changes(
                body=cst.IndentedBlock(body=(*docstring, *nested, *remainder)),
            )
        msg = (
            f"unsupported class body for {owner.name.value}: "
            f"{type(owner.body).__name__}"
        )
        raise TypeError(msg)

    @classmethod
    def _module_statement(
        cls,
        node: cst.BaseStatement,
        owner: cst.ClassDef,
        nested_owner: cst.ClassDef,
    ) -> cst.BaseStatement:
        """Return one kept module statement after the owner absorbed its members.

        Returns:
            The rewritten export list, the nested owner, or the node itself.

        """
        if cls._declares_exports(node):
            return cls._rewritten_exports(node, owner.name.value)
        return nested_owner if node is owner else node

    @classmethod
    def _nest_definitions(cls, source: str, definitions: t.StrMapping) -> str:
        if not definitions:
            return source
        owners = frozenset(definitions.values())
        if len(owners) != 1:
            msg = f"class-nesting file has multiple owners: {sorted(owners)}"
            raise ValueError(msg)
        owner_name = next(iter(owners))
        module = cst.parse_module(source)
        moved = tuple(
            node for node in module.body if cls._member_name(node) in definitions
        )
        moved_names = {cls._member_name(node) for node in moved}
        module, owner_nodes = cls._module_with_owner(module, owner_name, moved)
        if len(owner_nodes) != 1 or moved_names != set(definitions):
            msg = (
                f"class-nesting structure mismatch for {owner_name}: "
                f"owner_count={len(owner_nodes)} moved={sorted(map(str, moved_names))}"
            )
            raise ValueError(msg)
        owner = owner_nodes[0]
        # CST indentation moves code without changing the values of data
        # literals or docstrings carried by the original declaration; members
        # keep their module order, so a binding still follows what it reads.
        members = tuple(cls._class_member(node) for node in moved)
        nested_owner = cls._owner_holding(owner, tuple(member for member, _ in members))
        exports = (
            ()
            if any(cls._declares_exports(node) for node in module.body)
            else (cst.parse_statement(f'__all__: list[str] = ["{owner_name}"]\n'),)
        )
        module = module.with_changes(
            body=(
                *(
                    cls._module_statement(node, owner, nested_owner)
                    for node in module.body
                    if node not in moved
                ),
                *exports,
            ),
        )
        if any(flag for _, flag in members):
            context = CodemodContext()
            AddImportsVisitor.add_needed_import(context, "typing", "ClassVar")
            module = AddImportsVisitor(context).transform_module(module)
        return module.code

    @classmethod
    def _binds_exports(cls, statement: cst.BaseSmallStatement) -> bool:
        """Whether one small statement assigns the module ``__all__``.

        Returns:
            The resulting ``bool``.

        """
        return any(
            isinstance(target, cst.Name) and target.value == "__all__"
            for target in cls._assignment_targets(statement)
        )

    @classmethod
    def _declares_exports(cls, node: cst.BaseStatement) -> bool:
        """Whether one module-level statement declares ``__all__``.

        Returns:
            The resulting ``bool``.

        """
        return isinstance(node, cst.SimpleStatementLine) and any(
            cls._binds_exports(statement) for statement in node.body
        )

    @classmethod
    def _rewritten_exports(
        cls,
        node: cst.BaseStatement,
        owner_name: str,
    ) -> cst.BaseStatement:
        """Declare the owner first in the export list, keeping the node's shape.

        Parsing a fresh statement discarded two things the original carried:
        its ``leading_lines``, so the rebuilt declaration lost the blank lines
        separating it from the preceding block (E305 on every moved module),
        and its declared annotation, so a module using a tuple annotation was
        silently rewritten to a list. Only the value changes here. Names that
        stay at module level (the facade alias, a typing declaration) stay
        declared after the owner; moved names were already dropped.

        Returns:
            The resulting ``cst.BaseStatement``.

        """
        if not isinstance(node, cst.SimpleStatementLine):
            return node
        body: list[cst.BaseSmallStatement] = []
        for statement in node.body:
            if not (
                isinstance(statement, cst.AnnAssign | cst.Assign)
                and statement.value is not None
                and cls._binds_exports(statement)
            ):
                body.append(statement)
                continue
            declared = ast.literal_eval(
                cst.Module(body=()).code_for_node(statement.value),
            )
            names = list(dict.fromkeys((owner_name, *declared)))
            rendered = ", ".join(f'"{name}"' for name in names)
            value = cst.parse_expression(
                f"({rendered},)" if isinstance(declared, tuple) else f"[{rendered}]",
            )
            body.append(statement.with_changes(value=value))
        return node.with_changes(body=tuple(body))

    @staticmethod
    def _split_docstring(
        body: t.SequenceOf[cst.BaseStatement],
    ) -> t.Pair[t.VariadicTuple[cst.BaseStatement], t.VariadicTuple[cst.BaseStatement]]:
        """Split one class body into its leading docstring and the remainder.

        Returns:
            The resulting ``t.Pair[t.VariadicTuple[cst.BaseStatement],
                t.VariadicTuple[cst.BaseStatement]]``.

        """
        if not body:
            return ((), ())
        head = body[0]
        if (
            isinstance(head, cst.SimpleStatementLine)
            and len(head.body) == 1
            and isinstance(head.body[0], cst.Expr)
            and isinstance(
                head.body[0].value,
                cst.SimpleString | cst.ConcatenatedString,
            )
        ):
            return ((head,), tuple(body[1:]))
        return ((), tuple(body))


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverNestingCst"]
