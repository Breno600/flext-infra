"""Captured-source inventory feeding base resolution.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from importlib.util import resolve_name

from flext_infra import m, t


class FlextInfraFlextUtilitiesRopeSourceBasesInventory:
    """Canonical namespace owner."""

    # The dedicated owner of the source-binding collector: the rope facade
    # (rope_source_bases) and the runtime module both import it from here, so
    # exactly one definition exists (q0oyc consolidation contract).
    class _SourceBindingCollector:
        """Index the lexical class bindings of one captured module body.

        The collector walks the module AST exactly once, dispatching every
        statement kind to one private handler. Class locals are visible to a
        nested class's base expressions but are not a closure for that nested
        class's own body.
        """

        def __init__(
            self,
            module: str,
            package: str,
            definitions: MutableMapping[str, m.Infra.SourceClassDefinition],
            *,
            required_line: int | None,
            allow_conditional: bool,
        ) -> None:
            """Bind the captured module context used by every handler.

            Parameters:
                module: The qualified module name under inventory.
                package: The module's enclosing package name.
                definitions: The cross-module definition inventory to extend.
                required_line: When set, index only bindings visible at the line.
                allow_conditional: Whether conditional bindings may degrade.

            """
            self._module = module
            self._package = package
            self._definitions = definitions
            self._required_line = required_line
            self._allow_conditional = allow_conditional

        def collect(
            self,
            statements: t.SequenceOf[ast.stmt],
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
            scope: str,
        ) -> None:
            """Index each statement into ``bindings`` in declaration order.

            Parameters:
                statements: The module or class body to index.
                bindings: The mutable binding map the statements extend.
                lexical: The enclosing read-only bindings visible to bases.
                scope: The dotted nesting prefix of the statements.

            """
            for node in statements:
                if (
                    self._required_line is not None
                    and not scope
                    and node.lineno > self._required_line
                ):
                    break
                self._dispatch(node, bindings, lexical, scope)

        def _dispatch(
            self,
            node: ast.stmt,
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
            scope: str,
        ) -> None:
            """Route one statement to its handler; unlisted kinds are ignored."""
            if isinstance(node, ast.ClassDef):
                self._class_def(node, bindings, lexical, scope)
            elif isinstance(node, ast.ImportFrom):
                self._import_from(node, bindings)
            elif isinstance(node, ast.Import):
                self._import(node, bindings)
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                self._assign(node, bindings, lexical)
            elif isinstance(node, ast.AugAssign):
                self._aug_assign(node, bindings)
            elif isinstance(node, ast.Delete):
                self._delete(node, bindings)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                bindings[node.name] = None
            elif isinstance(node, ast.If):
                self._if(node, bindings, lexical, scope)
            elif isinstance(node, ast.Try | ast.TryStar):
                self._try(node, bindings, lexical, scope)

        def _class_def(
            self,
            node: ast.ClassDef,
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
            scope: str,
        ) -> None:
            """Index one class declaration and its nested declaration identities."""
            if (
                self._required_line is not None
                and not scope
                and not (
                    node.lineno
                    <= self._required_line
                    <= (node.end_lineno or node.lineno)
                )
            ):
                bindings[node.name] = m.Infra.SourceClassReference(
                    target=self._module,
                    attributes=tuple(f"{scope}{node.name}".split(".")),
                    qualified_base=f"{self._module}.{scope}{node.name}",
                )
                return
            visible = {**lexical, **bindings}
            bases = tuple(
                self._reference(base, visible, self._module) for base in node.bases
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
            identity = f"{self._module}:{scope}{node.name}:{node.lineno}"
            members: MutableMapping[str, m.Infra.SourceClassReference | None] = {}
            self.collect(node.body, members, lexical, f"{scope}{node.name}.")
            self._definitions[identity] = m.Infra.SourceClassDefinition(
                identity=identity,
                bases=bases,
                members=members,
            )
            bindings[node.name] = m.Infra.SourceClassReference(
                target=identity,
                qualified_base=f"{self._module}.{node.name}",
            )

        def _import_from(
            self,
            node: ast.ImportFrom,
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        ) -> None:
            """Index the explicit class bindings of one ``from`` import.

            Raises:
                ValueError: If a relative import escapes the package or a star
                    import has no explicit class binding.

            """
            parts = self._package.split(".") if self._package else []
            if node.level:
                if node.level > len(parts):
                    message = f"Relative import escapes package in {self._module}"
                    raise ValueError(message)
                prefix = ".".join(parts[: len(parts) - node.level + 1])
                imported = ".".join(part for part in (prefix, node.module) if part)
            else:
                imported = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    if self._allow_conditional:
                        # External/installed modules re-export through star
                        # imports; the re-exported names resolve in the module's
                        # own runtime, not statically.
                        continue
                    message = (
                        f"Star import has no explicit class binding in {self._module}"
                    )
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

        def _assign(
            self,
            node: ast.Assign | ast.AnnAssign,
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
        ) -> None:
            """Index one assignment by its target shape."""
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(not isinstance(target, ast.Name) for target in targets):
                self._non_name_assignment(node, targets, bindings, lexical)
                return
            self._name_assignment(node, targets, bindings, lexical)

        def _non_name_assignment(
            self,
            node: ast.Assign | ast.AnnAssign,
            targets: t.SequenceOf[ast.expr],
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
        ) -> None:
            """Classify one non-name assignment target mutation.

            Raises:
                ValueError: If the mutation is not a recognized provider
                    metadata, module table, or class namespace rebinding.

            """
            if self._provider_metadata_rebind(targets, bindings):
                return
            if self._module_table_mutation(targets, bindings):
                return
            if self._complete_class_namespace(node, targets, bindings, lexical):
                return
            message = f"Unsupported class binding mutation in {self._module}: {ast.unparse(node)}"
            raise ValueError(message)

        def _provider_metadata_rebind(
            self,
            targets: t.SequenceOf[ast.expr],
            bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
        ) -> bool:
            """Return whether every target only annotates provider metadata."""
            return self._allow_conditional and all(
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id in bindings
                and bindings[target.value.id] is None
                for target in targets
            )

        @staticmethod
        def _module_table_mutation(
            targets: t.SequenceOf[ast.expr],
            bindings: t.MappingKV[str, m.Infra.SourceClassReference | None]
            | None = None,
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
            of the enclosing conditionality.

            """
            return all(
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and (
                    m.Infra.SubscriptRebind(
                        root_name=target.value.id,
                    ).is_module_table_mutation
                    or bindings is None
                    or bindings.get(target.value.id) is None
                )
                for target in targets
            )

        @staticmethod
        def _is_class_namespace_completion(
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

        def _complete_class_namespace(
            self,
            node: ast.Assign | ast.AnnAssign,
            targets: t.SequenceOf[ast.expr],
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
        ) -> bool:
            """Publish the RHS class under the attribute name; return handling.

            Returns:
                True when the assignment completed a class namespace.

            """
            if not self._is_class_namespace_completion(node, targets, bindings):
                return False
            attribute_target = targets[0]
            if not isinstance(attribute_target, ast.Attribute):
                return False
            visible = {**lexical, **bindings}
            value = node.value
            if not isinstance(value, ast.Name):
                return False
            if value.id in visible and visible[value.id] is not None:
                reference = self._reference(node.value, visible, self._module)
                if reference is not None:
                    bindings[attribute_target.attr] = reference.model_copy(
                        update={
                            "qualified_base": f"{self._module}.{attribute_target.attr}",
                        },
                    )
            return True

        def _name_assignment(
            self,
            node: ast.Assign | ast.AnnAssign,
            targets: t.SequenceOf[ast.expr],
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
        ) -> None:
            """Bind one name-target assignment's value as a class reference."""
            value = node.value
            if value is None:
                return
            visible = {**lexical, **bindings}
            head = value
            while isinstance(head, (ast.Attribute, ast.Subscript)):
                head = head.value
            reference = (
                self._reference(value, visible, self._module)
                if isinstance(head, ast.Name)
                and isinstance(value, (ast.Name, ast.Attribute, ast.Subscript))
                and not (head.id in visible and visible[head.id] is None)
                else None
            )
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = (
                        reference.model_copy(
                            update={"qualified_base": f"{self._module}.{target.id}"},
                        )
                        if reference is not None
                        else None
                    )

        def _aug_assign(
            self,
            node: ast.AugAssign,
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        ) -> None:
            """Degrade one augmented assignment's name binding.

            An augmented assignment mutates an existing object and never
            declares a class binding; a Name target reads as an unknown binding
            going forward.

            """
            if self._allow_conditional and isinstance(node.target, ast.Name):
                bindings[node.target.id] = None
                return
            if isinstance(node.target, ast.Name):
                bindings.setdefault(node.target.id, None)

        def _delete(
            self,
            node: ast.Delete,
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        ) -> None:
            """Drop one deletion's name bindings when conditionals are allowed."""
            if self._allow_conditional and all(
                isinstance(target, ast.Name) for target in node.targets
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        bindings.pop(target.id, None)

        def _if(
            self,
            node: ast.If,
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
            scope: str,
        ) -> None:
            """Index one conditional statement's statically knowable branch."""
            match node.test:
                case ast.Compare(
                    left=ast.Name(id="__name__"),
                    ops=[ast.Eq()],
                    comparators=[ast.Constant(value="__main__")],
                ):
                    self.collect(
                        node.body if self._module == "__main__" else node.orelse,
                        bindings,
                        lexical,
                        scope,
                    )
                    return
            if isinstance(node.test, ast.Constant) and isinstance(
                node.test.value,
                bool,
            ):
                self.collect(
                    node.body if node.test.value else node.orelse,
                    bindings,
                    lexical,
                    scope,
                )
                return
            if self._is_type_checking_test(node.test):
                # A TYPE_CHECKING gate never executes at runtime; its imports and
                # assignments are the module's declared static binding surface,
                # so they index directly.
                self.collect(node.body, bindings, lexical, scope)
                return
            # Non-constant conditions with class declarations (pydantic's own
            # version-dependent models, read from the runtime environment) have
            # no statically knowable class-ness: the conditional names bind as
            # None so the base derivation degrades them exactly like any other
            # non-class binding.
            self._bind_conditional_branches(node, bindings, lexical, scope)

        def _bind_conditional_branches(
            self,
            node: ast.If,
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
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
            self.collect(node.body, left, lexical, scope)
            self.collect(node.orelse, right, lexical, scope)
            for name in left.keys() | right.keys():
                bindings[name] = (
                    left[name]
                    if name in left and name in right and left[name] == right[name]
                    else None
                )

        def _try(
            self,
            node: ast.Try | ast.TryStar,
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
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
            if not self._allow_conditional:
                message = (
                    f"Conditional exception-backed class bindings in {self._module}"
                )
                raise ValueError(message)
            conditional: MutableMapping[str, m.Infra.SourceClassReference | None] = {}
            self.collect(node.body, conditional, lexical, scope)
            self.collect(node.orelse, conditional, lexical, scope)
            for handler in node.handlers:
                self.collect(handler.body, conditional, lexical, scope)
            for name in conditional:
                bindings[name] = None

        @staticmethod
        def _is_type_checking_test(test: ast.expr) -> bool:
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
                message = f"Unsupported class reference in {module}: {ast.unparse(expression)}"
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

    class FlextInfraUtilitiesRopeSourceBasesInventory:
        """Captured-source inventory part of the source-bases composite."""

        @classmethod
        def inventory(
            cls,
            request: m.Infra.SourceBindingInventoryRequest,
            definitions: MutableMapping[str, m.Infra.SourceClassDefinition],
        ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
            """Index lexical bindings without installing a cross-module Rope overlay.

            A provider class is indexed at its native declaration line. Unreferenced
            module-level provider classes remain qualified declarations, not fabricated
            lineages. A captured class owns its nested declaration identities.

            Returns:
                The module's explicit lexical bindings, including value shadowing.

            Raises:
                TypeError: If Rope does not return a module AST.
                ValueError: If a required binding has unsupported source semantics.

            """
            from flext_infra._utilities import FlextInfraUtilitiesRopeAnalysisSourceScan, FlextInfraUtilitiesRopeCore, FlextInfraUtilitiesRopeRuntime, FlextInfraUtilitiesRopeSourceBindingCollector
            resource = (
                FlextInfraUtilitiesRopeCore.resolve_resource_from_path(
                    request.project,
                    request.path,
                )
                if request.path.is_file()
                else None
            )
            parsed = FlextInfraUtilitiesRopeRuntime.build_string_module(
                request.project,
                request.source,
                resource=resource,
            ).get_ast()
            if not isinstance(parsed, ast.Module):
                message = f"Rope returned a non-module AST for {request.path}"
                raise TypeError(message)
            package = (
                request.module
                if request.path.name == "__init__.py"
                else request.module.rpartition(".")[0]
            )
            globals_: MutableMapping[str, m.Infra.SourceClassReference | None] = {}
            spec = m.Infra.SourceBindingCollectorSpec(
                module=request.module,
                package=package,
                required_line=request.required_line,
                allow_conditional=request.allow_conditional,
                definitions=definitions,
                lexical=globals_,
            )
            FlextInfraUtilitiesRopeSourceBindingCollector.collect(
                spec,
                parsed.body,
                globals_,
                "",
            )
            targets, references = (
                FlextInfraUtilitiesRopeAnalysisSourceScan.lazy_import_mapping_source(
                    request.source,
                )
            )
            if references and not request.module.startswith(("tests.", "tests.")):
                # Test and benchmark modules build installer maps at runtime from
                # the constants they exercise; the declared-mapping invariant
                # gates the production lazy-init modules only.
                message = (
                    f"Unresolved declared lazy import mapping in {request.module}: "
                    f"{references}"
                )
                raise ValueError(message)
            for target, exports in targets:
                destination = (
                    resolve_name(target, package) if target.startswith(".") else target
                )
                for name in exports:
                    globals_[name] = m.Infra.SourceClassReference(
                        target=destination,
                        attributes=(name,),
                        qualified_base=f"{request.module}.{name}",
                    )
            return globals_


__all__: list[str] = ["FlextInfraFlextUtilitiesRopeSourceBasesInventory"]
