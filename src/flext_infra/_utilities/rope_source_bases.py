"""Qualified runtime-base discovery over captured, unpublished source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import m, t
from flext_infra._utilities._rope_source_bases_aliases import (
    FlextInfraUtilitiesRopeSourceBasesAliases,
)
from flext_infra._utilities._rope_source_bases_inventory import (
    FlextInfraUtilitiesRopeSourceBasesInventory,
)
from flext_infra._utilities._rope_source_bases_runtime import (
    FlextInfraUtilitiesRopeSourceBasesRuntime,
)


class FlextInfraUtilitiesRopeSourceBases:
    """Source-bases composite facade over the inventory, aliases, and runtime parts."""

    @classmethod
    def inventory(
        cls,
        request: m.Infra.SourceBindingInventoryRequest,
        definitions: MutableMapping[str, m.Infra.SourceClassDefinition],
    ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
        """Index lexical bindings without installing a cross-module Rope overlay.

        Returns:
            The module's explicit lexical bindings, including value shadowing.

        """
        return FlextInfraUtilitiesRopeSourceBasesInventory.inventory(
            request,
            definitions,
        )

    @staticmethod
    def _module_table_target(
        target: ast.expr,
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
    ) -> bool:
        """Recognize a subscript store that cannot rebind a live class.

        Returns:
            The resulting ``bool``.
        """
        if not isinstance(target, ast.Subscript):
            return False
        expression = target.value
        attributes: list[str] = []
        while isinstance(expression, ast.Attribute):
            attributes.insert(0, expression.attr)
            expression = expression.value
        if not isinstance(expression, ast.Name):
            return False
        rebind = m.Infra.SubscriptRebind(
            root_name=expression.id,
            attribute=".".join(attributes) if attributes else None,
        )
        return rebind.is_module_table_mutation or bindings.get(rebind.root_name) is None

    @classmethod
    def _collect(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        statements: t.SequenceOf[ast.stmt],
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Index lexical declarations in order, preserving provider conditionality.

        Raises:
            ValueError: If Relative import escapes package in; or if Star import has no
                explicit class binding in; or if Unsupported class binding mutation in;
                or if Conditional exception-backed class bindings in.
        """
        for node in statements:
            if (
                spec.required_line is not None
                and not scope
                and node.lineno > spec.required_line
            ):
                break
            if isinstance(node, ast.ClassDef):
                if (
                    spec.required_line is not None
                    and not scope
                    and not (
                        node.lineno
                        <= spec.required_line
                        <= (node.end_lineno or node.lineno)
                    )
                ):
                    bindings[node.name] = m.Infra.SourceClassReference(
                        target=spec.module,
                        attributes=tuple(f"{scope}{node.name}".split(".")),
                        qualified_base=f"{spec.module}.{scope}{node.name}",
                    )
                    continue
                visible = {**spec.lexical, **bindings}
                bases = tuple(
                    cls._reference(base, visible, spec.module) for base in node.bases
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
                # Nested bases see class locals; nested bodies retain module lexical scope.
                cls._collect(spec, node.body, members, f"{scope}{node.name}.")
                spec.definitions[identity] = m.Infra.SourceClassDefinition(
                    identity=identity,
                    bases=bases,
                    members=members,
                )
                bindings[node.name] = m.Infra.SourceClassReference(
                    target=identity,
                    qualified_base=f"{spec.module}.{node.name}",
                )
            elif isinstance(node, ast.ImportFrom):
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
                            continue
                        message = f"Star import has no explicit class binding in {spec.module}"
                        raise ValueError(message)
                    bindings[alias.asname or alias.name] = m.Infra.SourceClassReference(
                        target=imported,
                        attributes=(alias.name,),
                        qualified_base=f"{imported}.{alias.name}",
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    target = (
                        alias.name if alias.asname else alias.name.partition(".")[0]
                    )
                    bindings[alias.asname or target] = m.Infra.SourceClassReference(
                        target=target,
                        qualified_base=target,
                    )
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                if any(not isinstance(target, ast.Name) for target in targets):
                    if spec.allow_conditional and all(
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id in bindings
                        and (
                            bindings[target.value.id] is None
                            or target.attr
                            in {"__module__", "__name__", "__qualname__", "__doc__"}
                        )
                        for target in targets
                    ):
                        # Class metadata does not rebind a class or its bases;
                        # providers may annotate imported and declared classes.
                        continue
                    if all(
                        cls._module_table_target(target, bindings) for target in targets
                    ):
                        continue
                    value = node.value
                    target = targets[0]
                    visible = {**spec.lexical, **bindings}
                    if (
                        spec.allow_conditional
                        and len(targets) == 1
                        and isinstance(value, ast.Name)
                        and isinstance(target, ast.Attribute)
                        and target.attr
                        not in {
                            "__bases__",
                            "__base__",
                            "__mro__",
                            "__class__",
                            "__dict__",
                        }
                        and isinstance(target.value, ast.Name)
                        and target.value.id in visible
                        and visible[target.value.id] is not None
                    ):
                        owner = cls._reference(target.value, visible, spec.module)
                        if (
                            owner.target in spec.definitions
                            and not owner.attributes
                            and value.id in visible
                        ):
                            definition = spec.definitions[owner.target]
                            spec.definitions[owner.target] = definition.model_copy(
                                update={
                                    "members": {
                                        **definition.members,
                                        target.attr: visible[value.id],
                                    },
                                },
                            )
                            continue
                    message = (
                        f"Unsupported class binding mutation in {spec.module}: "
                        f"{ast.unparse(node)}"
                    )
                    raise ValueError(message)
                value = node.value
                if value is None:
                    continue
                visible = {**spec.lexical, **bindings}
                head = value
                while isinstance(head, ast.Attribute | ast.Subscript):
                    head = head.value
                reference = (
                    m.Infra.SourceClassReference(
                        target="builtins",
                        attributes=(str(value.value),),
                    )
                    if isinstance(value, ast.Constant) and isinstance(value.value, bool)
                    else cls._reference(value, visible, spec.module)
                    if isinstance(head, ast.Name)
                    and isinstance(value, ast.Name | ast.Attribute | ast.Subscript)
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
            elif isinstance(node, ast.AugAssign | ast.Delete):
                if not spec.allow_conditional:
                    message = (
                        f"Unsupported class binding mutation in {spec.module}: "
                        f"{ast.unparse(node)}"
                    )
                    raise ValueError(message)
                if isinstance(node, ast.AugAssign):
                    if isinstance(node.target, ast.Name):
                        bindings[node.target.id] = None
                elif all(isinstance(target, ast.Name) for target in node.targets):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            bindings.pop(target.id, None)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                bindings[node.name] = None
            elif isinstance(node, ast.If):
                match node.test:
                    case ast.Compare(
                        left=ast.Name(id="__name__"),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value="__main__")],
                    ):
                        cls._collect(
                            spec,
                            node.body if spec.module == "__main__" else node.orelse,
                            bindings,
                            scope,
                        )
                        continue
                    case ast.Constant(value=bool(value)):
                        cls._collect(
                            spec,
                            node.body if value else node.orelse,
                            bindings,
                            scope,
                        )
                        continue
                    case _:
                        pass
                head = (
                    node.test.value
                    if isinstance(node.test, ast.Attribute)
                    else node.test
                )
                visible = {**spec.lexical, **bindings}
                if (
                    isinstance(node.test, ast.Name | ast.Attribute)
                    and isinstance(head, ast.Name)
                    and head.id in visible
                    and visible[head.id] is not None
                ):
                    guard = cls._reference(node.test, visible, spec.module)
                    if (
                        guard.target in {"typing", "typing_extensions"}
                        and guard.attributes == ("TYPE_CHECKING",)
                    ) or (
                        guard.target == "builtins"
                        and guard.attributes in {("True",), ("False",)}
                    ):
                        cls._collect(
                            spec,
                            node.body if guard.attributes == ("True",) else node.orelse,
                            bindings,
                            scope,
                        )
                        continue
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
                cls._collect(spec, node.body, left, scope)
                cls._collect(spec, node.orelse, right, scope)
                for name in left.keys() | right.keys():
                    bindings[name] = (
                        left[name]
                        if name in left and name in right and left[name] == right[name]
                        else None
                    )
            elif isinstance(node, ast.Try | ast.TryStar):
                if not spec.allow_conditional:
                    message = (
                        f"Conditional exception-backed class bindings in {spec.module}"
                    )
                    raise ValueError(message)
                conditional_bindings: MutableMapping[
                    str, m.Infra.SourceClassReference | None
                ] = {}
                cls._collect(spec, node.body, conditional_bindings, scope)
                cls._collect(spec, node.orelse, conditional_bindings, scope)
                for handler in node.handlers:
                    cls._collect(spec, handler.body, conditional_bindings, scope)
                for name in conditional_bindings:
                    bindings[name] = None

    @classmethod
    def lazy_module_aliases(
        cls,
        module: str,
        path: Path,
        source: str,
    ) -> dict[str, str]:
        """Read the ``install_lazy_exports`` namespace alias map of one module.

        Returns:
            The module's facade alias names routed to their lazy module paths.

        """
        return FlextInfraUtilitiesRopeSourceBasesAliases.lazy_module_aliases(
            module,
            path,
            source,
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
        definitions: MutableMapping[str, m.Infra.SourceClassDefinition] = {}
        modules = {
            module: cls.inventory(
                m.Infra.SourceBindingInventoryRequest(
                    project=project,
                    module=module,
                    path=path,
                    source=source,
                ),
                definitions,
            )
            for module, (path, source) in sources.items()
        }
        namespaces = {
            ".".join(parts[:index])
            for module in modules
            for parts in (module.split("."),)
            for index in range(1, len(parts) + 1)
        }
        module_aliases: dict[str, str] = {}
        for module, (path, source) in sources.items():
            for alias, absolute in cls.lazy_module_aliases(
                module, path, source
            ).items():
                qualified = f"{module}.{alias}"
                if qualified not in namespaces:
                    module_aliases.setdefault(qualified, absolute)
        for alias, absolute in (extra_module_aliases or {}).items():
            if alias not in namespaces:
                module_aliases.setdefault(alias, absolute)
        owned_definitions = tuple(definitions.values())
        external: MutableMapping[str, t.Infra.RopePyObject] = {}
        linearizations: MutableMapping[str, t.StrTuple] = {}
        active: set[str] = set()

        def external_identity(value: t.Infra.RopePyObject) -> str:
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
                if name in modules:
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
                    return resolve(
                        m.Infra.SourceClassReference(
                            target=name,
                            attributes=tuple(path.split(".")),
                            qualified_base=f"{name}.{path}",
                        )
                    )
                identity = next(
                    (
                        identity
                        for identity in definitions
                        if identity.startswith(f"{name}:")
                        and identity.endswith(f":{line}")
                    ),
                    None,
                )
                if identity is None:
                    cls.inventory(
                        m.Infra.SourceBindingInventoryRequest(
                            project=project,
                            module=name,
                            path=Path(resource.real_path),
                            source=module.source_code,
                            required_line=line,
                            allow_conditional=True,
                        ),
                        definitions,
                        provider=module,
                    )
                    identity = next(
                        (
                            identity
                            for identity in definitions
                            if identity.startswith(f"{name}:")
                            and identity.endswith(f":{line}")
                        ),
                        None,
                    )
                if identity is None:
                    message = f"Missing external class declaration: {name}:{line}"
                    raise ValueError(message)
                return identity
            for identity, known in external.items():
                if known == value or (
                    isinstance(known, p.Infra.RopeBuiltinClass)
                    and isinstance(value, p.Infra.RopeBuiltinClass)
                    and known.builtin is value.builtin
                ):
                    return identity
            identity = f"external:{len(external)}"
            external[identity] = value
            return identity

        def provider_module_name(
            imported: p.Infra.RopeImportedModule,
        ) -> str:
            if imported.module_name is None:
                if imported.resource is None:
                    message = "Import has no declared module location"
                    raise ValueError(message)
                return FlextInfraUtilitiesRopeCore.resolve_pymodule(
                    project,
                    imported.resource,
                ).get_name()
            if not imported.level:
                return imported.module_name
            declaring = imported.importing_module.get_module()
            source = declaring.get_resource() if declaring is not None else None
            if declaring is None or source is None:
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

        def provider_module(
            imported: p.Infra.RopeImportedModule,
        ) -> t.Infra.RopePyModule:
            resource = imported.resource
            if resource is not None:
                return FlextInfraUtilitiesRopeCore.resolve_pymodule(project, resource)
            name = provider_module_name(imported)
            module = project.get_module(name)
            resource = project.find_module(name)
            if resource is not None:
                module = FlextInfraUtilitiesRopeCore.resolve_pymodule(project, resource)
            return module

        def provider_reference(
            module: t.Infra.RopePyModule,
            attributes: t.StrTuple,
            visiting: frozenset[str] = frozenset(),
            depth: int = 0,
        ) -> str:
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
                message = f"Cyclic provider reexport: {target}"
                raise ValueError(message)
            binding = module.get_attribute(name)
            if isinstance(binding, p.Infra.RopeImportedName):
                imported_name = provider_module_name(binding.imported_module)
                if imported_name in namespaces:
                    return resolve(
                        m.Infra.SourceClassReference(
                            target=imported_name,
                            attributes=(binding.imported_name, *remaining),
                            qualified_base=target,
                        ),
                        visiting | {target},
                        depth + 1,
                    )
                imported = provider_module(binding.imported_module)
                return provider_reference(
                    imported,
                    (binding.imported_name, *remaining),
                    visiting | {target},
                    depth + 1,
                )
            if isinstance(binding, p.Infra.RopeImportedModule):
                imported_name = provider_module_name(binding)
                if imported_name in namespaces:
                    return resolve(
                        m.Infra.SourceClassReference(
                            target=imported_name,
                            attributes=tuple(remaining),
                            qualified_base=target,
                        ),
                        visiting | {target},
                        depth + 1,
                    )
                imported = provider_module(binding)
                return provider_reference(
                    imported,
                    tuple(remaining),
                    visiting | {target},
                    depth + 1,
                )
            identity = external_identity(binding.get_object())
            for attribute in remaining:
                identity = member(identity, attribute, depth + 1, visiting)
            return identity

        def external_reference(
            target: str,
            attributes: t.StrTuple,
            visiting: frozenset[str] = frozenset(),
            depth: int = 0,
        ) -> str:
            module = project.get_module(target)
            resource = project.find_module(target)
            if resource is not None:
                module = FlextInfraUtilitiesRopeCore.resolve_pymodule(project, resource)
            return provider_reference(module, attributes, visiting, depth)

        object_id = external_reference("builtins", ("object",))
        # Resolved-reference memo: deep facade attribute chains (the root
        # workspace test models re-export the full fleet facade depth) resolve
        # the same keys thousands of times and recursed past the interpreter
        # stack (RecursionError inside rope's path join). The memo is keyed by
        # the reference key alone; a key being visited cycles through the
        # visiting guard below, never through the memo. flext-qwvb5 2026-10-05.
        resolved_memo: dict[str, str] = {}

        def resolve(
            reference: m.Infra.SourceClassReference,
            visiting: frozenset[str] = frozenset(),
            depth: int = 0,
        ) -> str:
            if depth > c.Infra.ROPE_WALK_DEPTH_BUDGET:
                message = f"Unresolved external base: {reference.target}"
                raise ValueError(message)
            target = reference.target
            attributes = list(reference.attributes)
            if target in module_aliases:
                attributes.insert(0, target.rpartition(".")[2])
                target = module_aliases[target]
            elif attributes:
                qualified_head = f"{target}.{attributes[0]}"
                if qualified_head in module_aliases:
                    target = module_aliases[qualified_head]
            key = ".".join((target, *attributes))
            if key in visiting:
                message = f"Cyclic class alias: {key}"
                raise ValueError(message)
            memo = resolved_memo.get(key)
            if memo is not None:
                return memo
            if target not in definitions and target not in external:
                parts = target.split(".")
                if parts[0] in namespaces:
                    index = next(
                        index
                        for index in range(len(parts), 0, -1)
                        if ".".join(parts[:index]) in namespaces
                    )
                    module = ".".join(parts[:index])
                    attributes = [*parts[index:], *attributes]
                    # Import-from can bind a captured child module rather than
                    # a package export. Explicit package bindings still win.
                    while (
                        attributes
                        and (
                            module not in modules
                            or attributes[0] not in modules[module]
                        )
                        and f"{module}.{attributes[0]}" in namespaces
                    ):
                        module = f"{module}.{attributes.pop(0)}"
                    if not attributes:
                        message = f"Module used as a class base: {module}"
                        raise ValueError(message)
                    name = attributes.pop(0)
                    if module not in modules:
                        message = (
                            f"Planned namespace has no module binding: {module}.{name}"
                        )
                        raise ValueError(message)
                    binding = modules[module].get(name)
                    if binding is None:
                        message = (
                            f"Unresolved planned base: {module}.{name} "
                            f"(reference={reference.qualified_base!r}, "
                            f"target={reference.target!r}, "
                            f"attributes={reference.attributes!r})"
                        )
                        raise ValueError(message)
                    target = resolve(binding, visiting | {key}, depth + 1)
                else:
                    target = external_reference(
                        target,
                        tuple(attributes),
                        visiting,
                        depth + 1,
                    )
                    attributes.clear()
            for attribute in attributes:
                target = member(target, attribute, 0, visiting | {key})
            resolved_memo[key] = target
            return target

        def bases(identity: str) -> t.StrTuple:
            if identity == object_id:
                return ()
            if identity in definitions:
                declared = definitions[identity].bases
                return (
                    tuple(resolve(base) for base in declared)
                    if declared
                    else (object_id,)
                )
            value = external[identity]
            if not isinstance(value, p.Infra.RopeBuiltinClass):
                message = f"External class has no declared source or native identity: {identity}"
                raise ValueError(message)
            # Native ancestry contains actual classes, including private parents
            # that are not exported under their module/qualified-name metadata.
            return tuple(
                external_identity(FlextInfraUtilitiesRopeRuntime.native_class(base))
                for base in value.builtin.__bases__
            )

        def linearize(identity: str) -> t.StrTuple:
            if identity in linearizations:
                return linearizations[identity]
            if identity in active:
                message = f"Cyclic class inheritance: {identity}"
                raise ValueError(message)
            active.add(identity)
            parents = bases(identity)
            if len(set(parents)) != len(parents):
                message = f"Duplicate class base: {identity}"
                raise ValueError(message)
            sequences = [list(linearize(parent)) for parent in parents]
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
            active.remove(identity)
            linearizations[identity] = tuple(result)
            return linearizations[identity]

        def member(
            identity: str,
            name: str,
            depth: int = 0,
            visiting: frozenset[str] = frozenset(),
        ) -> str:
            if name == "__base__" and identity in external:
                value = external[identity]
                if isinstance(value, p.Infra.RopeBuiltinClass):
                    return external_identity(
                        FlextInfraUtilitiesRopeRuntime.native_class_primary_base(
                            value.builtin,
                        ),
                    )
            for ancestor in linearize(identity):
                if ancestor in definitions:
                    members = definitions[ancestor].members
                    if name not in members:
                        continue
                    reference = members[name]
                    if reference is None:
                        message = (
                            f"Non-class member shadows required base: {ancestor}.{name}"
                        )
                        raise ValueError(message)
                    return resolve(reference, visiting, depth + 1)
                value = external[ancestor]
                external_members = value.get_attributes()
                if name in external_members:
                    return external_identity(external_members[name].get_object())
            message = f"Missing inherited class member: {identity}.{name}"
            raise ValueError(message)

        def root_reference(root: str) -> m.Infra.SourceClassReference:
            parts = root.split(".")
            index = next(
                (
                    index
                    for index in range(len(parts) - 1, 0, -1)
                    if ".".join(parts[:index]) in modules
                    or project.find_module(".".join(parts[:index])) is not None
                ),
                1,
            )
            return m.Infra.SourceClassReference(
                target=".".join(parts[:index]),
                attributes=tuple(parts[index:]),
                qualified_base=root,
            )

        root_ids = frozenset(resolve(root_reference(root)) for root in roots)
        derived = set(roots)
        # Required provider parents participate in C3, but only captured project
        # expressions belong to the project's generated Ruff configuration.
        for definition in owned_definitions:
            linearize(definition.identity)
            for reference in definition.bases:
                lineage = linearize(resolve(reference))
                if root_ids.intersection(lineage):
                    derived.add(reference.qualified_base)
        return tuple(sorted(derived))


__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBases"]
