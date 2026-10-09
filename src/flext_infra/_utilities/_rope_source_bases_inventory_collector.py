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

    @staticmethod
    def collect(
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
            FlextInfraUtilitiesRopeSourceBindingCollector._index_node(
                spec,
                node,
                bindings,
                scope,
            )

    @staticmethod
    def _index_node(
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.stmt,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Dispatch one statement to its shape-specific indexing handler."""
        if isinstance(node, ast.ClassDef):
            FlextInfraUtilitiesRopeSourceBindingCollector._class_def(
                spec,
                node,
                bindings,
                scope,
            )
        elif isinstance(node, ast.ImportFrom):
            FlextInfraUtilitiesRopeSourceBindingCollector._import_from(
                spec,
                node,
                bindings,
            )
        elif isinstance(node, ast.Import):
            FlextInfraUtilitiesRopeSourceBindingCollector._import(node, bindings)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            FlextInfraUtilitiesRopeSourceBindingCollector._assign(
                spec,
                node,
                bindings,
            )
        elif isinstance(node, ast.AugAssign):
            FlextInfraUtilitiesRopeSourceBindingCollector._aug_assign(
                spec,
                node,
                bindings,
            )
        elif isinstance(node, ast.Delete):
            FlextInfraUtilitiesRopeSourceBindingCollector._delete(
                spec,
                node,
                bindings,
            )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            bindings[node.name] = None
        elif isinstance(node, ast.If):
            FlextInfraUtilitiesRopeSourceBindingCollector._if(
                spec,
                node,
                bindings,
                scope,
            )
        elif isinstance(node, ast.Try | ast.TryStar):
            FlextInfraUtilitiesRopeSourceBindingCollector._try(
                spec,
                node,
                bindings,
                scope,
            )

    @staticmethod
    def _class_def(
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
        bases = tuple(
            FlextInfraUtilitiesRopeSourceBindingCollector._reference(
                base,
                visible,
                spec.module,
            )
            for base in node.bases
        )
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
        # Class locals are visible to a nested class's base expressions,
        # but are not a closure for that nested class's own body.
        FlextInfraUtilitiesRopeSourceBindingCollector.collect(
            spec,
            node.body,
            members,
            f"{scope}{node.name}.",
        )
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

    @staticmethod
    def _assign(
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Assign | ast.AnnAssign,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> None:
        """Index one assignment by its target shape."""
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(not isinstance(target, ast.Name) for target in targets):
            FlextInfraUtilitiesRopeSourceBindingCollector._non_name_assignment(
                spec,
                node,
                targets,
                bindings,
            )
            return
        FlextInfraUtilitiesRopeSourceBindingCollector._name_assignment(
            spec,
            node,
            targets,
            bindings,
        )

    @staticmethod
    def _non_name_assignment(
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
            targets,
            bindings,
        ):
            return
        if FlextInfraUtilitiesRopeSourceBindingCollector._module_table_mutation(
            targets,
            bindings,
        ):
            return
        if FlextInfraUtilitiesRopeSourceBindingCollector._complete_class_namespace(
            spec,
            node,
            targets,
            bindings,
        ):
            return
        message = FlextInfraUtilitiesRopeSourceBindingCollector._mutation_message(
            spec,
            node,
        )
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
        targets: t.SequenceOf[ast.expr],
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
    ) -> bool:
        """Return whether every target only annotates provider metadata.

        A write to a class's naming metadata (the stdlib
        ``ABCMeta.__module__ = 'abc'``, a provider's
        ``Contract.__module__ = __name__``) relabels the class: it binds no
        class and changes no base. Identity slots such as ``__bases__`` are
        never metadata.
        """
        return spec.allow_conditional and all(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id in bindings
            and (
                bindings[target.value.id] is None
                or target.attr in {"__module__", "__name__", "__qualname__", "__doc__"}
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

    @staticmethod
    def _module_table_mutation(
        targets: t.SequenceOf[ast.expr],
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None] | None = None,
    ) -> bool:
        """Return whether every target is an external runtime table mutation.

        Standard-library alias re-registration (CPython's ``collections``
        publishes ``sys.modules['collections.abc'] = _collections_abc``) is
        an external runtime table mutation, never a class rebinding — the
        touched names stay unknown. The same holds for subscript stores
        through any plain module-level table whose name is not a live class
        binding (CPython's http.server ``_control_char_table[ord(...)] =
        ...``): a subscript store cannot redefine a class through a
        non-class root, so the mutation is a runtime table write regardless
        of the enclosing conditionality (flext-2klp8).

        """
        return all(
            isinstance(target, ast.Subscript)
            and FlextInfraUtilitiesRopeSourceBindingCollector._is_module_table_target(
                target,
                bindings,
            )
            for target in targets
        )

    @staticmethod
    def _is_module_table_target(
        target: ast.Subscript,
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None] | None,
    ) -> bool:
        """Return whether one subscript target only writes a runtime table.

        Returns:
            True when the typed rule classifies the rebind as a module-table
            write or the store runs through a non-class table binding.

        """
        rebind = FlextInfraUtilitiesRopeSourceBindingCollector.subscript_rebind_target(
            target,
        )
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
        """Return whether the assignment completes a declared class namespace.

        A class-namespace completion rebind (``base.t = final``): a module
        completes a deferred base namespace and publishes the RHS class
        under the attribute name in its own exported namespace.

        """
        value = node.value
        if len(targets) != 1 or not isinstance(value, ast.Name):
            return False
        target = targets[0]
        return (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id in bindings
            and bindings[target.value.id] is not None
        )

    @staticmethod
    def _complete_class_namespace(
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Assign | ast.AnnAssign,
        targets: t.SequenceOf[ast.expr],
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> bool:
        """Record a member written onto a declared class; return handling.

        Only an external provider module (``allow_conditional``) completes a
        declared class namespace (``Owner.member = value``): the value joins
        that class definition's members, so inherited member lookup sees it.
        A write onto anything that is not a declared class (an imported
        module such as ``typing``, a nested attribute) or onto class identity
        slots stays an unsupported mutation, and so does every rebind in
        captured project sources.

        Returns:
            True when the assignment completed a declared class namespace.

        """
        if not spec.allow_conditional:
            return False
        if not FlextInfraUtilitiesRopeSourceBindingCollector._completes_class_namespace(
            node,
            targets,
            bindings,
        ):
            return False
        attribute_target = targets[0]
        value = node.value
        if (
            not isinstance(attribute_target, ast.Attribute)
            or not isinstance(attribute_target.value, ast.Name)
            or not isinstance(value, ast.Name)
            or attribute_target.attr
            in {"__bases__", "__base__", "__mro__", "__class__", "__dict__"}
        ):
            return False
        visible = {**spec.lexical, **bindings}
        owner = FlextInfraUtilitiesRopeSourceBindingCollector._reference(
            attribute_target.value,
            visible,
            spec.module,
        )
        if (
            owner.target not in spec.definitions
            or owner.attributes
            or value.id not in visible
        ):
            return False
        definition = spec.definitions[owner.target]
        spec.definitions[owner.target] = definition.model_copy(
            update={
                "members": {
                    **definition.members,
                    attribute_target.attr: visible[value.id],
                },
            },
        )
        return True

    @staticmethod
    def _name_assignment(
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.Assign | ast.AnnAssign,
        targets: t.SequenceOf[ast.expr],
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
    ) -> None:
        """Bind one name-target assignment's value as a class reference."""
        value = node.value
        if value is None:
            return
        visible = {**spec.lexical, **bindings}
        head = value
        while isinstance(head, (ast.Attribute, ast.Subscript)):
            head = head.value
        reference = (
            # A boolean constant binds as its builtin so guards can prove it.
            m.Infra.SourceClassReference(
                target="builtins",
                attributes=(str(value.value),),
            )
            if isinstance(value, ast.Constant) and isinstance(value.value, bool)
            else FlextInfraUtilitiesRopeSourceBindingCollector._reference(
                value,
                visible,
                spec.module,
            )
            if isinstance(head, ast.Name)
            and isinstance(value, (ast.Name, ast.Attribute, ast.Subscript))
            and not (head.id in visible and visible[head.id] is None)
            else None
        )
        for target in targets:
            if isinstance(target, ast.Name):
                bindings[target.id] = (
                    reference.model_copy(
                        update={"qualified_base": f"{spec.module}.{target.id}"},
                    )
                    if reference is not None
                    else None
                )

    @staticmethod
    def _aug_assign(
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
            message = FlextInfraUtilitiesRopeSourceBindingCollector._mutation_message(
                spec,
                node,
            )
            raise ValueError(message)
        if isinstance(node.target, ast.Name):
            bindings[node.target.id] = None

    @staticmethod
    def _delete(
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
            message = FlextInfraUtilitiesRopeSourceBindingCollector._mutation_message(
                spec,
                node,
            )
            raise ValueError(message)
        if all(isinstance(target, ast.Name) for target in node.targets):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bindings.pop(target.id, None)

    @staticmethod
    def _if(
        spec: m.Infra.SourceBindingCollectorSpec,
        node: ast.If,
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Index one conditional statement's statically knowable branch."""
        test = node.test
        if FlextInfraUtilitiesRopeSourceBindingCollector._is_main_guard(test):
            FlextInfraUtilitiesRopeSourceBindingCollector.collect(
                spec,
                node.body if spec.module == "__main__" else node.orelse,
                bindings,
                scope,
            )
            return
        if isinstance(node.test, ast.Constant) and isinstance(
            node.test.value,
            bool,
        ):
            FlextInfraUtilitiesRopeSourceBindingCollector.collect(
                spec,
                node.body if node.test.value else node.orelse,
                bindings,
                scope,
            )
            return
        selected = FlextInfraUtilitiesRopeSourceBindingCollector._runtime_guard(
            spec,
            test,
            bindings,
        )
        if selected is not None:
            # A guard whose runtime value is proven by import identity or a
            # boolean binding selects the branch that actually executes;
            # TYPE_CHECKING is False at runtime.
            FlextInfraUtilitiesRopeSourceBindingCollector.collect(
                spec,
                node.body if selected else node.orelse,
                bindings,
                scope,
            )
            return
        # Non-constant conditions with class declarations (pydantic's own
        # version-dependent models, read from the runtime environment) have
        # no statically knowable class-ness: the conditional names bind as
        # None so the base derivation degrades them exactly like any other
        # non-class binding.
        FlextInfraUtilitiesRopeSourceBindingCollector._bind_conditional_branches(
            spec,
            node,
            bindings,
            scope,
        )

    @staticmethod
    def _runtime_guard(
        spec: m.Infra.SourceBindingCollectorSpec,
        test: ast.expr,
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
    ) -> bool | None:
        """Return the proven runtime value of one guard, or None when unknown.

        The guard's identity comes from the visible bindings, never from its
        spelling: an aliased or rebound ``TYPE_CHECKING`` is still False at
        runtime, and a name bound to a boolean constant keeps that value. A
        head without a class-capable binding stays undecidable.

        Returns:
            True or False when the guard is proven, otherwise None.

        """
        if not isinstance(test, ast.Name | ast.Attribute):
            return None
        head = test.value if isinstance(test, ast.Attribute) else test
        visible = {**spec.lexical, **bindings}
        if not (
            isinstance(head, ast.Name)
            and head.id in visible
            and visible[head.id] is not None
        ):
            return None
        guard = FlextInfraUtilitiesRopeSourceBindingCollector._reference(
            test,
            visible,
            spec.module,
        )
        if guard.target in {"typing", "typing_extensions"} and guard.attributes == (
            "TYPE_CHECKING",
        ):
            return False
        if guard.target == "builtins" and guard.attributes in {("True",), ("False",)}:
            return guard.attributes == ("True",)
        return None

    @staticmethod
    def _bind_conditional_branches(
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
        FlextInfraUtilitiesRopeSourceBindingCollector.collect(
            spec,
            node.body,
            left,
            scope,
        )
        FlextInfraUtilitiesRopeSourceBindingCollector.collect(
            spec,
            node.orelse,
            right,
            scope,
        )
        for name in left.keys() | right.keys():
            bindings[name] = (
                left[name]
                if name in left and name in right and left[name] == right[name]
                else None
            )

    @staticmethod
    def _try(
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
        FlextInfraUtilitiesRopeSourceBindingCollector.collect(
            spec,
            node.body,
            conditional,
            scope,
        )
        FlextInfraUtilitiesRopeSourceBindingCollector.collect(
            spec,
            node.orelse,
            conditional,
            scope,
        )
        for handler in node.handlers:
            FlextInfraUtilitiesRopeSourceBindingCollector.collect(
                spec,
                handler.body,
                conditional,
                scope,
            )
        for name in conditional:
            bindings[name] = None

    @staticmethod
    def _is_main_guard(test: ast.expr) -> bool:
        """Return whether one condition is the ``__name__ == "__main__"`` guard."""
        match test:
            case ast.Compare(
                left=ast.Name(id="__name__"),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value="__main__")],
            ):
                return True
            case _:
                return False

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
        # Unwrap Subscript and Attribute in ONE loop: a chained form like
        # `_CLUSTERS[0].environment` is Attribute(Subscript(Name)) — consuming
        # attributes first left the inner Subscript unprocessed and raised
        # "Unsupported class reference" on every consumer whose SSOT-derived
        # constants subscript a module-level binding (cosmos-main
        # tests/constants.py, bead cosmos-gamnt).
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
