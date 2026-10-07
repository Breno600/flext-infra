"""Qualified runtime-base discovery over captured, unpublished source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, m, p, t


class FlextInfraUtilitiesRopeSourceBases:
    """Canonical namespace owner."""

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

        if self._provider_metadata_rebind(targets, bindings):
            return
        if self._module_table_mutation(targets, bindings):
            return
        if self._complete_class_namespace(node, targets, bindings, lexical):
            return
        message = (
            f"Unsupported class binding mutation in {self._module}: {ast.unparse(node)}"
        )
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

    def _module_table_mutation(
        self,
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

        return None

    class _RuntimeBaseResolver:
        """Resolve owned classes in C3 order and external classes through Rope.

        Only configured roots mark model evaluation boundaries. No first-party
        module is imported or resolved from disk when its planned source exists.
        Provider reexports follow Rope's declared import provenance. Their source
        declarations, not Rope's possibly incomplete superclass inference, supply
        the ordered bases. Missing references and invalid inheritance fail
        loudly.
        """

        def __init__(
            self,
            project: t.Infra.RopeProject,
            sources: t.MappingKV[str, t.Pair[Path, str]],
            roots: t.StrSequence,
            extra_module_aliases: t.MappingKV[str, str] | None,
        ) -> None:
            """Bind the resolution inputs and initialize the derived state.

            Parameters:
                project: The open Rope project scoped to the analysis roots.
                sources: The qualified module name to captured path and source.
                roots: The configured root qualified names.
                extra_module_aliases: Facade alias maps read outside the sources.

            """
            from flext_infra._utilities import FlextInfraUtilitiesRopeRuntime

            self._project = project
            self._sources = sources
            self._roots = roots
            self._extra_module_aliases = extra_module_aliases
            self._definitions: dict[str, m.Infra.SourceClassDefinition] = {}
            self._modules: dict[
                str,
                t.MappingKV[str, m.Infra.SourceClassReference | None],
            ] = {}
            self._namespaces: set[str] = set()
            self._module_aliases: dict[str, str] = {}
            self._definition_keys: dict[str, str] = {}
            self._external: dict[str, t.Infra.RopePyObject] = {}
            self._linearizations: dict[str, t.StrTuple] = {}
            self._active: set[str] = set()
            self._resolved_memo: dict[str, str] = {}
            self._native_module_type = FlextInfraUtilitiesRopeRuntime.runtime_type(
                "rope.base.builtins",
                "BuiltinModule",
            )
            self._object_id = ""

        def run(self) -> t.StrTuple:
            """Index every captured module and derive the ordered base set.

            Returns:
                Sorted configured roots and derived Ruff-qualified base
                expressions.

            """
            self._index_modules()
            self._build_module_alias_map()
            self._object_id = self._external_reference("builtins", ("object",))
            return self._derived_roots()

        def _index_modules(self) -> None:
            """Index every captured module and its declared namespaces."""
            sys.setrecursionlimit(max(sys.getrecursionlimit(), 4096))
            self._modules = {
                module: self._inventory(module, captured)
                for module, captured in self._sources.items()
            }
            self._namespaces = {
                ".".join(parts[:index])
                for module in self._modules
                for parts in (module.split("."),)
                for index in range(1, len(parts) + 1)
            }
            for definition_identity in self._definitions:
                module_name, qualified, _ = definition_identity.split(":", 2)
                self._definition_keys[f"{module_name}.{qualified}"] = (
                    definition_identity
                )

        def _build_module_alias_map(self) -> None:
            """Merge the captured and extra lazy-export alias maps.

            A lazy re-export alias is a module-local binding, never a global
            rename. When its name collides with a real analyzed module (or
            namespace), the real module wins: an absolute import elsewhere in
            the tree refers to the real module — a facade re-exporting a
            subpackage named like the project package must not shadow it
            (cosmos-docgen tests/unit re-exports a `dcdoc` subpackage; class
            bases declared as `from dcdoc import DcdocServiceBase` mean the
            project one).
            """
            for alias_module, captured in self._sources.items():
                alias_path, alias_source = captured
                for alias, absolute in (
                    FlextInfraUtilitiesRopeSourceBases.FlextInfraUtilitiesRopeSourceBases.lazy_module_aliases(
                        alias_module,
                        alias_path,
                        alias_source,
                    )
                ).items():
                    if alias in self._modules or alias in self._namespaces:
                        continue
                    self._module_aliases.setdefault(alias, absolute)
            for alias, absolute in (self._extra_module_aliases or {}).items():
                if alias in self._modules or alias in self._namespaces:
                    continue
                self._module_aliases.setdefault(alias, absolute)

        def _derived_roots(self) -> t.StrTuple:
            """Linearize every owned definition and collect the derived bases.

            Required provider parents participate in C3, but only captured
            project expressions belong to the project's generated Ruff
            configuration.

            Returns:
                The sorted union of configured roots and derived bases.

            """
            root_ids = frozenset(
                self._resolve(self._root_reference(root)) for root in self._roots
            )
            derived = set(self._roots)
            for definition in tuple(self._definitions.values()):
                self._linearize(definition.identity)
                for reference in definition.bases:
                    lineage = self._linearize(self._resolve(reference))
                    if root_ids.intersection(lineage):
                        derived.add(reference.qualified_base)
            return tuple(sorted(derived))

        def _inventory(
            self,
            module: str,
            captured: t.Pair[Path, str],
            *,
            required_line: int | None = None,
            allow_conditional: bool = False,
        ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
            """Index lexical bindings without installing a cross-module overlay.

            A provider class is indexed at its native declaration line.
            Unreferenced module-level provider classes remain qualified
            declarations, not fabricated lineages. A captured class owns its
            nested declaration identities.

            Parameters:
                module: The qualified module name under inventory.
                captured: The module's path and captured source text.
                required_line: When set, index only bindings visible at the line.
                allow_conditional: Whether conditional bindings may degrade.

            Returns:
                The module's explicit lexical bindings, including value
                shadowing.

            Raises:
                TypeError: If Rope does not return a module AST.
                ValueError: If a required binding has unsupported source
                    semantics.

            """
            from flext_infra._utilities import (
                FlextInfraUtilitiesRopeAnalysisSourceScan,
                FlextInfraUtilitiesRopeCore,
                FlextInfraUtilitiesRopeRuntime,
            )

            path, source = captured
            resource = (
                FlextInfraUtilitiesRopeCore.resolve_resource_from_path(
                    self._project,
                    path,
                )
                if path.is_file()
                else None
            )
            parsed = FlextInfraUtilitiesRopeRuntime.build_string_module(
                self._project,
                source,
                resource=resource,
            ).get_ast()
            if not isinstance(parsed, ast.Module):
                message = f"Rope returned a non-module AST for {path}"
                raise TypeError(message)
            package = (
                module if path.name == "__init__.py" else module.rpartition(".")[0]
            )
            globals_: MutableMapping[str, m.Infra.SourceClassReference | None] = {}
            collector = FlextInfraUtilitiesRopeSourceBases._SourceBindingCollector(
                module=module,
                package=package,
                definitions=self._definitions,
                required_line=required_line,
                allow_conditional=allow_conditional,
            )
            collector.collect(parsed.body, globals_, globals_, "")
            targets, references = (
                FlextInfraUtilitiesRopeAnalysisSourceScan.lazy_import_mapping_source(
                    source,
                )
            )
            if references and not module.startswith(("tests.", "tests.")):
                # Test and benchmark modules build installer maps at runtime from
                # the constants they exercise; the declared-mapping invariant
                # gates the production lazy-init modules only.
                message = (
                    f"Unresolved declared lazy import mapping in {module}: {references}"
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
                        qualified_base=f"{module}.{name}",
                    )
            return globals_

        def _external_identity(self, value: t.Infra.RopePyObject) -> str:
            """Return the declaration identity of one external Rope object.

            Raises:
                TypeError: If Rope resolves a required base to a non-class.

            """
            from flext_infra._utilities import FlextInfraUtilitiesRopeRuntime

            function_identity = self._function_object_identity(value)
            if function_identity is not None:
                return function_identity
            if not FlextInfraUtilitiesRopeRuntime.abstract_class(value):
                message = "Rope did not resolve a required base to a class"
                raise TypeError(message)
            if isinstance(
                value,
                FlextInfraUtilitiesRopeRuntime.runtime_type(
                    "rope.base.pyobjectsdef",
                    "PyClass",
                ),
            ):
                return self._pyclass_identity(value)
            return self._deduplicated_external_identity(value)

        @staticmethod
        def _function_object_identity(
            value: t.Infra.RopePyObject,
        ) -> str | None:
            """Return the constructed class identity of a TypedDict/NamedTuple.

            TypedDict and NamedTuple build their classes through function calls,
            so Rope resolves the declared base to a PyFunction; the base identity
            is still the class that call constructs at runtime.

            Returns:
                The constructed class identity, or None for other objects.

            """
            from flext_infra._utilities import FlextInfraUtilitiesRopeRuntime

            if not isinstance(
                value,
                FlextInfraUtilitiesRopeRuntime.runtime_type(
                    "rope.base.pyobjectsdef",
                    "PyFunction",
                ),
            ):
                return None
            if value.get_name() not in {"TypedDict", "NamedTuple"}:
                return None
            module = value.get_module()
            module_name = module.get_name() if module is not None else ""
            name = value.get_name()
            return f"{module_name}.{name}" if module_name else name

        def _pyclass_identity(self, value: t.Infra.RopePyObject) -> str:
            """Return the declaration identity of one external Rope class.

            Returns:
                The resolved declaration identity.

            Raises:
                ValueError: If the class has no source declaration.

            """
            module = value.get_module()
            scope = value.get_scope()
            resource = module.get_resource() if module is not None else None
            if module is None or scope is None or resource is None:
                message = (
                    f"External class has no source declaration: {value.get_name()}"
                )
                raise ValueError(message)
            name = module.get_name()
            line = scope.get_start()
            if name in self._modules:
                return self._declared_pyclass_identity(value, module, name, line)
            return self._inventory_pyclass_identity(name, module, line)

        def _declared_pyclass_identity(
            self,
            value: t.Infra.RopePyObject,
            module: t.Infra.RopePyModule,
            name: str,
            line: int,
        ) -> str:
            """Resolve one external class declared in a captured module.

            Returns:
                The resolved declaration identity.

            Raises:
                TypeError: If the captured module has no module AST.
                ValueError: If no class declaration encloses the line.

            """
            tree = module.get_ast()
            if not isinstance(tree, ast.Module):
                message = f"External class has no module AST: {name}"
                raise TypeError(message)
            path = ".".join(
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
                and node.lineno <= line <= (node.end_lineno or node.lineno)
            )
            if not path or path.rsplit(".", 1)[-1] != value.get_name():
                message = f"Missing external class declaration: {name}:{line}"
                raise ValueError(message)
            return self._resolve(
                m.Infra.SourceClassReference(
                    target=name,
                    attributes=tuple(path.split(".")),
                    qualified_base=f"{name}.{path}",
                ),
            )

        def _inventory_pyclass_identity(
            self,
            name: str,
            module: t.Infra.RopePyModule,
            line: int,
        ) -> str:
            """Index the declaring module at the line and return the identity.

            Returns:
                The resolved declaration identity.

            Raises:
                ValueError: If no class declaration encloses the line.

            """
            identity = self._declared_identity_at_line(name, line)
            if identity is None:
                resource = module.get_resource()
                self._inventory(
                    name,
                    (Path(resource.real_path), module.source_code),
                    required_line=line,
                    allow_conditional=True,
                )
                self._register_module_definitions(name)
                identity = self._declared_identity_at_line(name, line)
            if identity is None:
                message = f"Missing external class declaration: {name}:{line}"
                raise ValueError(message)
            return identity

        def _declared_identity_at_line(self, name: str, line: int) -> str | None:
            """Return the definition identity declared at one line, or None.

            Returns:
                The definition identity declared at the line, or None.

            """
            prefix = f"{name}:"
            suffix = f":{line}"
            return next(
                (
                    identity
                    for identity in self._definitions
                    if identity.startswith(prefix) and identity.endswith(suffix)
                ),
                None,
            )

        def _register_module_definitions(self, name: str) -> None:
            """Register every definition of one module in the key map."""
            for definition_identity in self._definitions:
                module_name, qualified, _ = definition_identity.split(":", 2)
                if module_name == name:
                    self._definition_keys[f"{module_name}.{qualified}"] = (
                        definition_identity
                    )

        def _deduplicated_external_identity(self, value: t.Infra.RopePyObject) -> str:
            """Return a stable shared identity for one external runtime object."""
            for identity, known in self._external.items():
                if known == value or (
                    isinstance(known, p.Infra.RopeBuiltinClass)
                    and isinstance(value, p.Infra.RopeBuiltinClass)
                    and known.builtin is value.builtin
                ):
                    return identity
            identity = f"external:{len(self._external)}"
            self._external[identity] = value
            return identity

        def _provider_module_name(self, imported: p.Infra.RopeImportedModule) -> str:
            """Return the absolute module name one Rope import points at.

            Raises:
                ValueError: If the import has no declared module location or a
                    relative import escapes the package.

            """
            from flext_infra._utilities import FlextInfraUtilitiesRopeCore

            if imported.module_name is None:
                if imported.resource is None:
                    message = "Import has no declared module location"
                    raise ValueError(message)
                return FlextInfraUtilitiesRopeCore.resolve_pymodule(
                    self._project,
                    imported.resource,
                ).get_name()
            if not imported.level:
                return imported.module_name
            declaring = imported.importing_module.get_module()
            source = declaring.get_resource() if declaring is not None else None
            if imported.module_name is None or declaring is None or source is None:
                message = "Import has no declared module location"
                raise ValueError(message)
            name = imported.module_name
            if imported.level:
                package = declaring.get_name()
                if Path(source.real_path).name != "__init__.py":
                    package = package.rpartition(".")[0]
                parts = package.split(".") if package else []
                if imported.level > len(parts):
                    message = f"Relative import escapes package: {package}.{name}"
                    raise ValueError(message)
                name = ".".join(
                    filter(
                        None,
                        (
                            ".".join(parts[: len(parts) - imported.level + 1]),
                            name,
                        ),
                    ),
                )
            return name

        def _provider_module(
            self,
            imported: p.Infra.RopeImportedModule,
        ) -> t.Infra.RopePyModule:
            """Return the Rope module object one import points at.

            Returns:
                The resolved Rope module object.

            """
            from flext_infra._utilities import FlextInfraUtilitiesRopeCore

            name = self._provider_module_name(imported)
            module = self._project.get_module(name)
            resource = imported.resource or self._project.find_module(name)
            if resource is not None and not isinstance(
                module,
                self._native_module_type,
            ):
                module = FlextInfraUtilitiesRopeCore.resolve_pymodule(
                    self._project,
                    resource,
                )
            return module

        def _provider_reference(
            self,
            module: t.Infra.RopePyModule,
            attributes: t.StrTuple,
            visiting: frozenset[str] = frozenset(),
            depth: int = 0,
        ) -> str:
            """Follow one provider module's reexport chain to a class identity.

            Returns:
                The resolved declaration identity.

            Raises:
                ValueError: If the walk exceeds the depth budget, uses a module
                    as a class base, or cycles through provider reexports.

            """
            from flext_infra._utilities import FlextInfraUtilitiesRopeRuntime

            if depth > c.Infra.ROPE_WALK_DEPTH_BUDGET:
                message = (
                    f"Unresolved external base: {module.get_name()} at depth {depth}"
                )
                raise ValueError(message)
            if not attributes:
                message = f"Module used as a class base: {module.get_name()}"
                raise ValueError(message)
            name, *remaining = attributes
            target = f"{module.get_name()}.{name}"
            if target in visiting:
                chain = " <- ".join(sorted(visiting))
                message = f"Cyclic provider reexport: {target} (visiting: {chain})"
                raise ValueError(message)
            try:
                binding = module.get_attribute(name)
            except (
                FlextInfraUtilitiesRopeRuntime.rope_attribute_not_found_error_types()
            ):
                # The provider cannot resolve the attribute statically (a star
                # re-export, a runtime-injected name): the base degrades to its
                # qualified name as a synthetic terminal identity instead of
                # failing the whole walk.
                return target
            if isinstance(binding, p.Infra.RopeImportedName):
                return self._provider_imported_name_reference(
                    binding,
                    remaining,
                    target,
                    visiting,
                    depth,
                )
            if isinstance(binding, p.Infra.RopeImportedModule):
                return self._provider_imported_module_reference(
                    binding,
                    remaining,
                    target,
                    visiting,
                    depth,
                )
            identity = self._external_identity(binding.get_object())
            for attribute in remaining:
                identity = self._member(identity, attribute, depth + 1, visiting)
            return identity

        def _provider_imported_name_reference(
            self,
            binding: p.Infra.RopeImportedName,
            remaining: t.StrSequence,
            target: str,
            visiting: frozenset[str],
            depth: int,
        ) -> str:
            """Resolve one provider imported-name binding to an identity.

            Returns:
                The resolved declaration identity.

            """
            imported_name = self._provider_module_name(binding.imported_module)
            if imported_name in self._namespaces:
                return self._resolve(
                    m.Infra.SourceClassReference(
                        target=imported_name,
                        attributes=(binding.imported_name, *remaining),
                        qualified_base=target,
                    ),
                    visiting | {target},
                    depth + 1,
                )
            imported = self._provider_module(binding.imported_module)
            return self._provider_reference(
                imported,
                (binding.imported_name, *remaining),
                visiting | {target},
                depth + 1,
            )

        def _provider_imported_module_reference(
            self,
            binding: p.Infra.RopeImportedModule,
            remaining: t.StrSequence,
            target: str,
            visiting: frozenset[str],
            depth: int,
        ) -> str:
            """Resolve one provider imported-module binding to an identity.

            Returns:
                The resolved declaration identity.

            """
            imported_name = self._provider_module_name(binding)
            if imported_name in self._namespaces:
                return self._resolve(
                    m.Infra.SourceClassReference(
                        target=imported_name,
                        attributes=tuple(remaining),
                        qualified_base=target,
                    ),
                    visiting | {target},
                    depth + 1,
                )
            imported = self._provider_module(binding)
            return self._provider_reference(
                imported,
                tuple(remaining),
                visiting | {target},
                depth + 1,
            )

        def _external_reference(
            self,
            target: str,
            attributes: t.StrTuple,
            visiting: frozenset[str] = frozenset(),
            depth: int = 0,
        ) -> str:
            """Resolve one external qualified target through Rope.

            Rope raises its own ModuleNotFoundError (not the builtin). Virtual
            stdlib submodules (collections.abc since 3.13, and aliases like
            os.path) exist only through runtime module aliasing, so static file
            lookup cannot see them. Their declarations live in the backing real
            module, which rope resolves normally.

            Returns:
                The resolved declaration identity.

            Raises:
                ModuleNotFoundError: If the target has no virtual stdlib backing.

            """
            from flext_infra._utilities import (
                FlextInfraUtilitiesRopeCore,
                FlextInfraUtilitiesRopeRuntime,
            )

            try:
                module = self._project.get_module(target)
            except (
                *FlextInfraUtilitiesRopeRuntime.rope_runtime_errors(),
                ModuleNotFoundError,
            ):
                real = self._stdlib_backing_module(target)
                if real is None:
                    raise
                module = self._project.get_module(real)
            resource = self._project.find_module(target)
            if resource is not None and not isinstance(
                module,
                self._native_module_type,
            ):
                module = FlextInfraUtilitiesRopeCore.resolve_pymodule(
                    self._project,
                    resource,
                )
            return self._provider_reference(module, attributes, visiting, depth)

        def _resolve(
            self,
            reference: m.Infra.SourceClassReference,
            visiting: frozenset[str] = frozenset(),
            depth: int = 0,
        ) -> str:
            """Resolve one source class reference to a declaration identity.

            Returns:
                The resolved declaration identity.

            Raises:
                ValueError: If the walk exceeds the depth budget, cycles
                    through class aliases, or resolves a module as a base.

            """
            if depth > c.Infra.ROPE_WALK_DEPTH_BUDGET:
                message = (
                    f"Unresolved external base: {reference.target} at depth {depth}"
                )
                raise ValueError(message)
            target, attributes = self._alias_rewritten_target(reference)
            key = ".".join((target, *attributes))
            if key in visiting:
                message = f"Cyclic class alias: {key}"
                raise ValueError(message)
            memo = self._resolved_memo.get(key)
            if memo is not None:
                return memo
            direct = self._definition_keys.get(key)
            if direct is not None:
                self._resolved_memo[key] = direct
                return direct
            target, attributes = self._unresolved_target(
                target,
                list(attributes),
                key,
                visiting,
                depth,
            )
            for attribute in attributes:
                target = self._member(target, attribute, 0, visiting)
            self._resolved_memo[key] = target
            return target

        def _alias_rewritten_target(
            self,
            reference: m.Infra.SourceClassReference,
        ) -> t.Pair[str, t.StrTuple]:
            """Rewrite facade-qualified targets through the lazy alias map.

            Returns:
                The rewritten target and its remaining attribute path.

            """
            rewrite_target = reference.target
            rewrite_attributes = reference.attributes
            if rewrite_attributes:
                qualified_head = f"{rewrite_target}.{rewrite_attributes[0]}"
                if qualified_head in self._module_aliases:
                    rewrite_target = self._module_aliases[qualified_head]
                    rewrite_attributes = rewrite_attributes[1:]
            return (
                self._module_aliases.get(rewrite_target, rewrite_target),
                rewrite_attributes,
            )

        def _unresolved_target(
            self,
            target: str,
            attributes: list[str],
            key: str,
            visiting: frozenset[str],
            depth: int,
        ) -> t.Pair[str, list[str]]:
            """Resolve a target that is not a direct definition key.

            Returns:
                The resolved target and its remaining attribute path.

            """
            if target in self._definitions or target in self._external:
                return target, attributes
            parts = target.split(".")
            if parts[0] in self._namespaces:
                return self._resolve_namespace_prefix(
                    parts,
                    attributes,
                    key,
                    visiting,
                    depth,
                )
            resolved = self._external_reference(
                target,
                tuple(attributes),
                visiting,
                depth + 1,
            )
            return resolved, []

        def _resolve_namespace_prefix(
            self,
            parts: t.StrSequence,
            attributes: list[str],
            key: str,
            visiting: frozenset[str],
            depth: int,
        ) -> t.Pair[str, list[str]]:
            """Resolve a namespace-qualified target through its planned module.

            Returns:
                The resolved target and its remaining attribute path.

            Raises:
                ValueError: If the namespace has no module binding or the name
                    is unresolved.

            """
            index = next(
                index
                for index in range(len(parts), 0, -1)
                if ".".join(parts[:index]) in self._namespaces
            )
            module = ".".join(parts[:index])
            remaining = [*parts[index:], *attributes]
            if not remaining:
                message = f"Module used as a class base: {module}"
                raise ValueError(message)
            name = remaining.pop(0)
            if module not in self._modules:
                message = f"Planned namespace has no module binding: {module}.{name}"
                raise ValueError(message)
            binding = self._modules[module].get(name)
            if binding is None:
                message = f"Unresolved planned base: {module}.{name}"
                raise ValueError(message)
            return self._resolve(binding, visiting | {key}, depth + 1), remaining

        def _bases(self, identity: str) -> t.StrTuple:
            """Return one identity's declared or native base identities.

            Returns:
                The base declaration identities in declaration order.

            """
            if identity == self._object_id:
                return ()
            if identity not in self._definitions and identity not in self._external:
                # Synthetic terminal identities (runtime-constructed bases such
                # as TypedDict) carry no ancestry of their own; they linearize
                # as direct object children.
                return (self._object_id,)
            if identity in self._definitions:
                declared = self._definitions[identity].bases
                return (
                    tuple(self._resolve(base) for base in declared)
                    if declared
                    else (self._object_id,)
                )
            return self._external_bases(identity)

        def _external_bases(self, identity: str) -> t.StrTuple:
            """Return the native base identities of one external builtin class.

            Returns:
                The external base declaration identities.

            Raises:
                TypeError: If the external value is not a Rope builtin class.

            """
            from flext_infra._utilities import FlextInfraUtilitiesRopeRuntime

            value = self._external[identity]
            if not isinstance(value, p.Infra.RopeBuiltinClass):
                message = f"External class has no declared source or native identity: {identity}"
                raise TypeError(message)
            builtin_class = FlextInfraUtilitiesRopeRuntime.runtime_type(
                "rope.base.builtins",
                "BuiltinClass",
            )
            return tuple(
                self._external_identity(builtin_class(base, {}))
                for base in value.builtin.__bases__
            )

        def _linearize(self, identity: str) -> t.StrTuple:
            """Return the C3 linearization of one identity's ancestry.

            Returns:
                The ordered linearization of the identity.

            Raises:
                ValueError: If the inheritance graph cycles, duplicates a base,
                    or is inconsistent.

            """
            if identity in self._linearizations:
                return self._linearizations[identity]
            if identity in self._active:
                message = f"Cyclic class inheritance: {identity}"
                raise ValueError(message)
            self._active.add(identity)
            parents = self._bases(identity)
            if len(set(parents)) != len(parents):
                message = f"Duplicate class base: {identity}"
                raise ValueError(message)
            linearization = self._c3_merge(identity, parents)
            self._active.remove(identity)
            self._linearizations[identity] = linearization
            return self._linearizations[identity]

        def _c3_merge(self, identity: str, parents: t.StrTuple) -> t.StrTuple:
            """Merge the parent linearizations into one C3 ordering.

            Returns:
                The merged linearization headed by the identity.

            Raises:
                ValueError: If no consistent C3 ordering exists.

            """
            sequences = [list(self._linearize(parent)) for parent in parents]
            sequences.append(list(parents))
            result = [identity]
            while any(sequences):
                candidate = next(
                    (
                        sequence[0]
                        for sequence in sequences
                        if sequence
                        and all(sequence[0] not in other[1:] for other in sequences)
                    ),
                    None,
                )
                if candidate is None:
                    message = f"Inconsistent class MRO: {identity}"
                    raise ValueError(message)
                result.append(candidate)
                for sequence in sequences:
                    if sequence and sequence[0] == candidate:
                        sequence.pop(0)
            return tuple(result)

        def _member(
            self,
            identity: str,
            name: str,
            depth: int = 0,
            visiting: frozenset[str] = frozenset(),
        ) -> str:
            """Resolve one inherited class member through the ancestry.

            Returns:
                The member's resolved declaration identity.

            Raises:
                ValueError: If no ancestor declares the member as a class.

            """
            for ancestor in self._linearize(identity):
                if ancestor in self._definitions:
                    members = self._definitions[ancestor].members
                    if name not in members:
                        continue
                    reference = members[name]
                    if reference is None:
                        message = (
                            f"Non-class member shadows required base: {ancestor}.{name}"
                        )
                        raise ValueError(message)
                    return self._resolve(reference, visiting, depth + 1)
                value = self._external[ancestor]
                external_members = value.get_attributes()
                if name in external_members:
                    return self._external_identity(external_members[name].get_object())
            message = f"Missing inherited class member: {identity}.{name}"
            raise ValueError(message)

        def _root_reference(self, root: str) -> m.Infra.SourceClassReference:
            """Split one configured root into its reference parts.

            Returns:
                The root's source class reference.

            """
            parts = root.split(".")
            index = next(
                (
                    index
                    for index in range(len(parts) - 1, 0, -1)
                    if ".".join(parts[:index]) in self._modules
                    or self._project.find_module(".".join(parts[:index])) is not None
                ),
                1,
            )
            return m.Infra.SourceClassReference(
                target=".".join(parts[:index]),
                attributes=tuple(parts[index:]),
                qualified_base=root,
            )

        def _stdlib_backing_module(self, target: str) -> str | None:
            """Return the importable real module backing one virtual stdlib module.

            Returns:
                The backing module name when the target imports at runtime and
                its declaration file is importable under its own stem; otherwise
                None.

            """
            if self._stdlib_backing_cache is None:
                self._stdlib_backing_cache = {}
            cached = self._stdlib_backing_cache.get(target, "")
            if cached:
                return cached or None
            backing: str | None = None
            try:
                runtime = importlib.import_module(target)
            except ImportError:
                runtime = None
            file = getattr(runtime, "__file__", None)
            if file:
                stem = Path(file).stem
                if stem != target.rpartition(".")[-1] and importlib.util.find_spec(
                    stem,
                ):
                    backing = stem
            self._stdlib_backing_cache[target] = backing or ""
            return backing

        _stdlib_backing_cache: ClassVar[dict[str, str] | None] = None


class FlextInfraUtilitiesRopeSourceBases:
    """Source-bases composite facade over the inventory and runtime parts."""

    @classmethod
    def inventory(
        cls,
        request: m.Infra.SourceBindingInventoryRequest,
        definitions: MutableMapping[str, m.Infra.SourceClassDefinition],
    ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
        """Index lexical bindings without installing a cross-module Rope overlay.

        Returns:
            The module's explicit lexical bindings, including value shadowing.

        Raises:
            TypeError: If Rope does not return a module AST.
            ValueError: If a required binding has unsupported source semantics.

        """
        return FlextInfraUtilitiesRopeSourceBasesInventory.inventory(
            request,
            definitions,
        )

    @classmethod
    def runtime_bases(
        cls,
        project: t.Infra.RopeProject,
        sources: t.MappingKV[str, t.Pair[Path, str]],
        roots: t.StrSequence,
        extra_module_aliases: t.MappingKV[str, str] | None = None,
    ) -> t.StrTuple:
        """Resolve owned classes in C3 order and external classes through Rope.

        Only configured roots mark model evaluation boundaries. No first-party
        module is imported or resolved from disk when its planned source exists.
        Provider reexports follow Rope's declared import provenance. Their source
        declarations, not Rope's possibly incomplete superclass inference, supply
        the ordered bases. Missing references and invalid inheritance fail
        loudly.

        Returns:
            Sorted configured roots and derived Ruff-qualified base expressions.

        """
        return FlextInfraUtilitiesRopeSourceBases._RuntimeBaseResolver(
            project,
            sources,
            roots,
            extra_module_aliases,
        ).run()


# The flat module-level re-export: the package lazy map and the
# internal from-import contract resolve this name at module scope
# (the S6 nesting moved the class inside the family facade).

__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBases"]
