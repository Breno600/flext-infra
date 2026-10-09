"""Lexical class-binding collector over one captured module body.

The collector is stateless: every pass is a pure function of its
``SourceBindingCollectorSpec`` and the per-call binding maps. The spec
carries the injected shared inventories by reference, so no run ever owns
mutable state.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping

from flext_infra import m, t


class FlextInfraUtilitiesRopeSourceBindingCollector:
    """Index the lexical class bindings of one captured module body.

    Class locals are visible to a nested class's base expressions but are
    not a closure for that nested class's own body.
    """

    @classmethod
    def collect(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        statements: t.SequenceOf[ast.stmt],
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Index each statement into ``bindings`` in declaration order.

        Parameters:
            spec: The module's indexing context with injected inventories.
            statements: The module or class body to index.
            bindings: The mutable binding map the statements extend.
            scope: The dotted nesting prefix of the statements.

        """
        for node in statements:
            if (
                spec.required_line is not None
                and not scope
                and node.lineno > spec.required_line
            ):
                break
            cls._index_node(spec, node, bindings, scope)

    @classmethod
    def _index_node(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.stmt,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Dispatch declarations, mutations and control flow in source order."""
        if isinstance(node, ast.ClassDef):
            cls._class_def(spec, node, bindings, scope)
        elif isinstance(node, ast.ImportFrom):
            cls._import_from(spec, node, bindings)
        elif isinstance(node, ast.Import):
            cls._import(node, bindings)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            cls._assign(spec, node, bindings)
        elif isinstance(node, ast.AugAssign):
            cls._aug_assign(spec, node, bindings)
        elif isinstance(node, ast.Delete):
            cls._delete(spec, node, bindings)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            bindings[node.name] = None
        elif isinstance(node, ast.If):
            cls._if(spec, node, bindings, scope)
        elif isinstance(node, ast.Try | ast.TryStar):
            cls._try(spec, node, bindings, scope)

    @classmethod
    def _class_def(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.ClassDef,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Index one class declaration and its nested declaration identities."""
        if (
            spec.required_line is not None
            and not scope
            and not (
                node.lineno <= spec.required_line <= (node.end_lineno or node.lineno)
            )
        ):
            bindings[node.name] = m.Infra.SourceClassReference(
                target=spec.module,
                attributes=tuple(f"{scope}{node.name}".split(".")),
                qualified_base=f"{spec.module}.{scope}{node.name}",
            )
            return
        visible = {**spec.lexical, **bindings}
        bases = tuple(cls._reference(base, visible, spec.module) for base in node.bases)
        if node.type_params:
            bases = (
                *bases,
                m.Infra.SourceClassReference(
                    target="typing",
                    attributes=("Generic",),
                    qualified_base="typing.Generic",
                ),
            )
        identity = f"{spec.module}:{scope}{node.name}:{node.lineno}"
        members: MutableMapping[str, m.Infra.SourceClassReference | None] = {}
        # Nested bases see class locals; bodies keep module lexical scope.
        cls.collect(spec, node.body, members, f"{scope}{node.name}.")
        spec.definitions[identity] = m.Infra.SourceClassDefinition(
            identity=identity,
            bases=bases,
            members=members,
        )
        bindings[node.name] = m.Infra.SourceClassReference(
            target=identity,
            qualified_base=f"{spec.module}.{node.name}",
        )

    @staticmethod
    def _import_from(
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.ImportFrom,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> None:
        """Index the explicit class bindings of one ``from`` import.

        Raises:
            ValueError: If a relative import escapes the package or a star
                import has no explicit class binding.

        """
        parts = spec.package.split(".") if spec.package else []
        if node.level:
            if node.level > len(parts):
                message = f"Relative import escapes package in {spec.module}"
                raise ValueError(message)
            prefix = ".".join(parts[: len(parts) - node.level + 1])
            imported = ".".join(part for part in (prefix, node.module) if part)
        else:
            imported = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                if spec.allow_conditional:
                    # External/installed modules re-export through star
                    # imports; the re-exported names resolve in the module's
                    # own runtime, not statically.
                    continue
                message = f"Star import has no explicit class binding in {spec.module}"
                raise ValueError(message)
            target = f"{imported}.{alias.name}"
            bindings[alias.asname or alias.name] = m.Infra.SourceClassReference(
                target=imported,
                attributes=(alias.name,),
                qualified_base=target,
            )

    @staticmethod
    def _import(
        node: ast.Import,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> None:
        """Index one ``import`` statement's module bindings."""
        for alias in node.names:
            target = alias.name if alias.asname else alias.name.partition(".")[0]
            bindings[alias.asname or target] = m.Infra.SourceClassReference(
                target=target,
                qualified_base=target,
            )

    @classmethod
    def _assign(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Assign | ast.AnnAssign,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> None:
        """Classify targets before publishing one captured value reference."""
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(not isinstance(target, ast.Name) for target in targets):
            cls._non_name_assignment(spec, node, targets, bindings)
            return
        if node.value is None:
            return
        reference = cls._name_assignment(spec, node, bindings)
        for target in targets:
            if isinstance(target, ast.Name):
                bindings[target.id] = (
                    reference.model_copy(
                        update={"qualified_base": f"{spec.module}.{target.id}"},
                    )
                    if reference is not None
                    else None
                )

    @classmethod
    def _non_name_assignment(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Assign | ast.AnnAssign,
        targets: t.SequenceOf[ast.expr],
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> None:
        """Classify one non-name assignment target mutation.

        Raises:
            ValueError: If the mutation is not a recognized provider
                metadata, module table, or class namespace rebinding.

        """
        if FlextInfraUtilitiesRopeSourceBindingCollector._provider_metadata_rebind(
            spec,
            node,
            targets,
            bindings,
        ):
            return
        if cls._module_table_mutation(targets, bindings):
            return
        if cls._complete_class_namespace(spec, node, targets, bindings):
            return
        message = cls._mutation_message(spec, node)
        raise ValueError(message)

    @staticmethod
    def _mutation_message(
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.stmt,
    ) -> str:
        """Describe one binding mutation the captured module cannot declare.

        Returns:
            The message naming the module and the mutating statement.

        """
        return (
            f"Unsupported class binding mutation in {spec.module}: {ast.unparse(node)}"
        )

    @staticmethod
    def _provider_metadata_rebind(
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Assign | ast.AnnAssign,
        targets: t.SequenceOf[ast.expr],
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
    ) -> bool:
        """Return whether every target only annotates provider metadata.

        A literal written to a dunder of a bound class (the stdlib
        ``ABCMeta.__module__ = 'abc'``) relabels metadata: it binds no class
        and changes no base. A dunder name the module never binds is an
        interpreter-provided module attribute (``Contract.__module__ =
        __name__``): module metadata, never a class.
        """
        value = node.value
        metadata_value = isinstance(value, ast.Constant) or (
            isinstance(value, ast.Name)
            and value.id.startswith("__")
            and value.id.endswith("__")
            and value.id not in spec.lexical
            and value.id not in bindings
        )
        return spec.allow_conditional and all(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id in bindings
            and (
                bindings[target.value.id] is None
                or (
                    metadata_value
                    and target.attr.startswith("__")
                    and target.attr.endswith("__")
                )
            )
            for target in targets
        )

    @staticmethod
    def subscript_rebind_target(
        target: ast.Subscript,
    ) -> m.Infra.SubscriptRebind | None:
        """Return the typed rebind rule for one subscript target, or None.

        The subscript's value expression is either a plain name
        (``_control_char_table[...]``) or a rooted attribute chain
        (``_sys.modules[...]``); any other shape is not a recognized
        rebind target.

        Returns:
            The typed rule, or None when the shape is unsupported.

        """
        expression: ast.expr = target.value
        attributes: list[str] = []
        while isinstance(expression, ast.Attribute):
            attributes.insert(0, expression.attr)
            expression = expression.value
        if not isinstance(expression, ast.Name):
            return None
        return m.Infra.SubscriptRebind(
            root_name=expression.id,
            attribute=".".join(attributes) if attributes else None,
        )

    @classmethod
    def _module_table_mutation(
        cls,
        targets: t.SequenceOf[ast.expr],
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None] | None = None,
    ) -> bool:
        """Recognize runtime table stores without rebinding a live class.

        Returns:
            True when every target writes a module table or non-class root.
        """
        return all(
            isinstance(target, ast.Subscript)
            and cls._is_module_table_target(target, bindings)
            for target in targets
        )

    @classmethod
    def _is_module_table_target(
        cls,
        target: ast.Subscript,
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None] | None,
    ) -> bool:
        """Return whether one subscript target only writes a runtime table.

        Returns:
            True when the typed rule classifies the rebind as a module-table
            write or the store runs through a non-class table binding.

        """
        rebind = cls.subscript_rebind_target(target)
        if rebind is None:
            return False
        return (
            rebind.is_module_table_mutation
            or bindings is None
            or bindings.get(rebind.root_name) is None
        )

    @staticmethod
    def _completes_class_namespace(
        node: ast.Assign | ast.AnnAssign,
        targets: t.SequenceOf[ast.expr],
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
    ) -> bool:
        """Recognize a name-valued, non-structural store on a bound receiver.

        Returns:
            True when the target shape permits an exact class-member update.
        """
        value = node.value
        if len(targets) != 1 or not isinstance(value, ast.Name):
            return False
        target = targets[0]
        return (
            isinstance(target, ast.Attribute)
            and target.attr
            not in {"__bases__", "__base__", "__mro__", "__class__", "__dict__"}
            and isinstance(target.value, ast.Name)
            and target.value.id in bindings
            and bindings[target.value.id] is not None
        )

    @classmethod
    def _complete_class_namespace(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Assign | ast.AnnAssign,
        targets: t.SequenceOf[ast.expr],
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> bool:
        """Update only the exact inventoried class receiver's member map.

        Returns:
            True when the store updated a known definition, otherwise False.
        """
        if not spec.allow_conditional:
            return False
        visible = {**spec.lexical, **bindings}
        if not cls._completes_class_namespace(node, targets, visible):
            return False
        target = targets[0]
        value = node.value
        if not isinstance(target, ast.Attribute) or not isinstance(value, ast.Name):
            return False
        owner = cls._reference(target.value, visible, spec.module)
        if owner.target not in spec.definitions or owner.attributes:
            return False
        if value.id not in visible:
            return False
        definition = spec.definitions[owner.target]
        spec.definitions[owner.target] = definition.model_copy(
            update={
                "members": {
                    **definition.members,
                    target.attr: visible[value.id],
                },
            },
        )
        return True

    @classmethod
    def _name_assignment(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Assign | ast.AnnAssign,
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
    ) -> m.Infra.SourceClassReference | None:
        """Capture a name assignment's class or real Boolean reference.

        Returns:
            The captured reference, or None for a non-class value.
        """
        value = node.value
        if value is None:
            return None
        if isinstance(value, ast.Constant) and isinstance(value.value, bool):
            return m.Infra.SourceClassReference(
                target="builtins",
                attributes=(str(value.value),),
            )
        visible = {**spec.lexical, **bindings}
        head = value
        while isinstance(head, ast.Attribute | ast.Subscript):
            head = head.value
        if not isinstance(head, ast.Name) or not isinstance(
            value, ast.Name | ast.Attribute | ast.Subscript
        ):
            return None
        if head.id in visible and visible[head.id] is None:
            return None
        return cls._reference(value, visible, spec.module)

    @classmethod
    def _aug_assign(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.AugAssign,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> None:
        """Degrade one augmented assignment's name binding.

        An external provider module's augmented assignment mutates an
        existing object and never declares a class binding; a Name target
        reads as an unknown binding going forward. Captured project sources
        never mutate a binding in place: the previous class would silently
        survive the mutation, so the statement fails.

        Raises:
            ValueError: If a captured project source mutates a binding.

        """
        if not spec.allow_conditional:
            message = cls._mutation_message(spec, node)
            raise ValueError(message)
        if isinstance(node.target, ast.Name):
            bindings[node.target.id] = None

    @classmethod
    def _delete(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Delete,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> None:
        """Drop one deletion's name bindings when conditionals are allowed.

        Captured project sources never delete a binding: keeping the previous
        class would silently survive the deletion, so the statement fails.

        Raises:
            ValueError: If a captured project source deletes a binding.

        """
        if not spec.allow_conditional:
            message = cls._mutation_message(spec, node)
            raise ValueError(message)
        if all(isinstance(target, ast.Name) for target in node.targets):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings.pop(target.id, None)

    @classmethod
    def _if(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.If,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Select a proven branch or conservatively merge unknown alternatives."""
        selected = cls._runtime_guard(spec, node.test, bindings)
        if selected is None:
            cls._bind_conditional_branches(spec, node, bindings, scope)
            return
        cls.collect(
            spec,
            node.body if selected else node.orelse,
            bindings,
            scope,
        )

    @classmethod
    def _bind_conditional_branches(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.If,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Merge both conditional branches; disagreement degrades to None."""
        conditional = {
            child.name
            for statement in (*node.body, *node.orelse)
            for child in ast.walk(statement)
            if isinstance(child, ast.ClassDef)
        }
        left = dict(bindings)
        right = dict(bindings)
        for name in conditional:
            left[name] = None
            right[name] = None
        cls.collect(spec, node.body, left, scope)
        cls.collect(spec, node.orelse, right, scope)
        for name in left.keys() | right.keys():
            bindings[name] = (
                left[name]
                if name in left and name in right and left[name] == right[name]
                else None
            )

    @classmethod
    def _try(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Try | ast.TryStar,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Degrade exception-backed conditional bindings while indexing nested.

        External/installed modules may carry conditional imports: their
        bindings resolve at that module's own runtime, not statically, so
        the names read as unknown here while any nested declarations still
        join the definition inventory.

        Raises:
            ValueError: If conditional exception-backed class bindings are
                not allowed for this module.

        """
        if not spec.allow_conditional:
            message = f"Conditional exception-backed class bindings in {spec.module}"
            raise ValueError(message)
        conditional: MutableMapping[str, m.Infra.SourceClassReference | None] = {}
        cls.collect(spec, node.body, conditional, scope)
        cls.collect(spec, node.orelse, conditional, scope)
        for handler in node.handlers:
            cls.collect(spec, handler.body, conditional, scope)
        for name in conditional:
            bindings[name] = None

    @classmethod
    def _runtime_guard(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        test: ast.expr,
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
    ) -> bool | None:
        """Resolve only literal guards and captured constant provenance.

        Returns:
            The proven runtime truth value, or None for an unknown guard.
        """
        match test:
            case ast.Compare(
                left=ast.Name(id="__name__"),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value="__main__")],
            ):
                return spec.module == "__main__"
            case ast.Constant(value=bool(literal_guard)):
                return literal_guard
            case _:
                pass
        if not isinstance(test, ast.Name | ast.Attribute):
            return None
        head = test.value if isinstance(test, ast.Attribute) else test
        if not isinstance(head, ast.Name):
            return None
        visible = {**spec.lexical, **bindings}
        if head.id not in visible or visible[head.id] is None:
            return None
        guard = cls._reference(test, visible, spec.module)
        selected: bool | None = None
        match (guard.target, guard.attributes):
            case ("typing" | "typing_extensions", ("TYPE_CHECKING",)):
                selected = False
            case ("builtins", ("True",)):
                selected = True
            case ("builtins", ("False",)):
                selected = False
            case _:
                pass
        return selected

    @staticmethod
    def type_checking_test(test: ast.expr) -> bool:
        """Return whether one condition gate is the TYPE_CHECKING constant.

        Returns:
            True for the bare name and for the ``typing`` /
            ``typing_extensions`` attribute forms.

        """
        if isinstance(test, ast.Name):
            return test.id == "TYPE_CHECKING"
        return (
            isinstance(test, ast.Attribute)
            and test.attr == "TYPE_CHECKING"
            and isinstance(test.value, ast.Name)
            and test.value.id in {"typing", "typing_extensions"}
        )

    @staticmethod
    def _subscript_root_name(target: ast.Subscript) -> str:
        """Return the root name of a subscript target's value expression."""
        value = target.value
        if isinstance(value, ast.Attribute):
            value = value.value
        return value.id if isinstance(value, ast.Name) else ""

    @staticmethod
    def _reference(
        expression: ast.expr,
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
        module: str,
    ) -> m.Infra.SourceClassReference:
        """Capture the binding visible when a base expression is evaluated.

        Returns:
            The bound identity, attributes, and Ruff-qualified spelling.

        Raises:
            TypeError: If the expression is not a supported class reference.
            ValueError: If its lexical binding is not a class.

        """
        # Unwrap interleaved attributes and subscriptions before resolving the root.
        attributes: list[str] = []
        while isinstance(expression, ast.Subscript | ast.Attribute):
            if isinstance(expression, ast.Attribute):
                attributes.insert(0, expression.attr)
            expression = expression.value
        if not isinstance(expression, ast.Name):
            message = (
                f"Unsupported class reference in {module}: {ast.unparse(expression)}"
            )
            raise TypeError(message)
        name = expression.id
        if name in bindings:
            binding = bindings[name]
            if binding is None:
                message = f"Non-class binding used as a base in {module}: {name}"
                raise ValueError(message)
        else:
            binding = m.Infra.SourceClassReference(
                target="builtins",
                attributes=(name,),
                qualified_base=f"{module}.{name}",
            )
        return m.Infra.SourceClassReference(
            target=binding.target,
            attributes=(*binding.attributes, *attributes),
            qualified_base=".".join((binding.qualified_base, *attributes)),
        )
