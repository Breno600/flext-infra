"""Qualified runtime-base discovery over captured, unpublished source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import m, p, t
from flext_infra._utilities.rope_core import FlextInfraUtilitiesRopeCore
from flext_infra._utilities.rope_runtime import FlextInfraUtilitiesRopeRuntime


class FlextInfraUtilitiesRopeSourceBases:
    """Keep source declaration identities separate from Ruff's qualified bases."""

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
            ValueError: If the expression or its lexical binding is not a class.

        """
        while isinstance(expression, ast.Subscript):
            expression = expression.value
        attributes: list[str] = []
        while isinstance(expression, ast.Attribute):
            attributes.insert(0, expression.attr)
            expression = expression.value
        if not isinstance(expression, ast.Name):
            message = (
                f"Unsupported class reference in {module}: {ast.unparse(expression)}"
            )
            raise ValueError(message)
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

    @classmethod
    def _inventory(
        cls,
        project: t.Infra.RopeProject,
        module: str,
        path: Path,
        source: str,
        definitions: MutableMapping[str, m.Infra.SourceClassDefinition],
        *,
        required_line: int | None = None,
    ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
        """Index lexical bindings without installing a cross-module Rope overlay.

        A provider class is indexed at its native declaration line. Unreferenced
        provider classes remain qualified declarations, not fabricated lineages.

        Returns:
            The module's explicit lexical bindings, including value shadowing.

        Raises:
            TypeError: If Rope does not return a module AST.
            ValueError: If a required binding has unsupported source semantics.

        """
        resource = (
            FlextInfraUtilitiesRopeCore.resolve_resource_from_path(project, path)
            if path.is_file()
            else None
        )
        parsed = FlextInfraUtilitiesRopeRuntime.build_string_module(
            project,
            source,
            resource=resource,
        ).get_ast()
        if not isinstance(parsed, ast.Module):
            message = f"Rope returned a non-module AST for {path}"
            raise TypeError(message)
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        globals_: MutableMapping[str, m.Infra.SourceClassReference | None] = {}

        def collect(
            statements: t.SequenceOf[ast.stmt],
            bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
            lexical: t.MappingKV[str, m.Infra.SourceClassReference | None],
            scope: str,
        ) -> None:
            for node in statements:
                if isinstance(node, ast.ClassDef):
                    if required_line is not None and not (
                        node.lineno <= required_line <= (node.end_lineno or node.lineno)
                    ):
                        bindings[node.name] = m.Infra.SourceClassReference(
                            target=module,
                            attributes=tuple(f"{scope}{node.name}".split(".")),
                            qualified_base=f"{module}.{scope}{node.name}",
                        )
                        continue
                    visible = {**lexical, **bindings}
                    bases = tuple(
                        cls._reference(base, visible, module) for base in node.bases
                    )
                    if node.type_params:
                        bases = (*bases, m.Infra.SourceClassReference(
                            target="typing", attributes=("Generic",),
                            qualified_base="typing.Generic",
                        ))
                    identity = f"{module}:{scope}{node.name}:{node.lineno}"
                    members: MutableMapping[
                        str,
                        m.Infra.SourceClassReference | None,
                    ] = {}
                    # Class locals are visible to a nested class's base expressions,
                    # but are not a closure for that nested class's own body.
                    collect(node.body, members, lexical, f"{scope}{node.name}.")
                    definitions[identity] = m.Infra.SourceClassDefinition(
                        identity=identity,
                        bases=bases,
                        members=members,
                    )
                    bindings[node.name] = m.Infra.SourceClassReference(
                        target=identity,
                        qualified_base=f"{module}.{node.name}",
                    )
                elif isinstance(node, ast.ImportFrom):
                    parts = package.split(".") if package else []
                    if node.level:
                        if node.level > len(parts):
                            message = f"Relative import escapes package in {module}"
                            raise ValueError(message)
                        prefix = ".".join(parts[: len(parts) - node.level + 1])
                        imported = ".".join(
                            part for part in (prefix, node.module) if part
                        )
                    else:
                        imported = node.module or ""
                    for alias in node.names:
                        if alias.name == "*":
                            message = (
                                f"Star import has no explicit class binding in {module}"
                            )
                            raise ValueError(message)
                        target = f"{imported}.{alias.name}"
                        binding = m.Infra.SourceClassReference(
                            target=imported,
                            attributes=(alias.name,),
                            qualified_base=target,
                        )
                        bindings[alias.asname or alias.name] = binding
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        target = (
                            alias.name if alias.asname else alias.name.partition(".")[0]
                        )
                        bindings[alias.asname or target] = m.Infra.SourceClassReference(
                            target=target,
                            qualified_base=target,
                        )
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = (
                        node.targets if isinstance(node, ast.Assign) else [node.target]
                    )
                    value = node.value
                    if value is None:
                        continue
                    visible = {**lexical, **bindings}
                    head = value
                    while isinstance(head, (ast.Attribute, ast.Subscript)):
                        head = head.value
                    reference = (
                        cls._reference(value, visible, module)
                        if isinstance(head, ast.Name)
                        and isinstance(value, (ast.Name, ast.Attribute, ast.Subscript))
                        and not (head.id in visible and visible[head.id] is None)
                        else None
                    )
                    for target in targets:
                        if isinstance(target, ast.Name):
                            bindings[target.id] = (
                                reference.model_copy(
                                    update={"qualified_base": f"{module}.{target.id}"},
                                )
                                if reference is not None
                                else None
                            )
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    bindings[node.name] = None
                elif isinstance(node, ast.If):
                    if isinstance(node.test, ast.Constant) and isinstance(
                        node.test.value, bool,
                    ):
                        collect(
                            node.body if node.test.value else node.orelse,
                            bindings, lexical, scope,
                        )
                        continue
                    if node.orelse and any(
                        isinstance(child, ast.ClassDef)
                        for statement in (*node.body, *node.orelse)
                        for child in ast.walk(statement)
                    ):
                        message = (
                            f"Ambiguous conditional class declarations in {module}"
                        )
                        raise ValueError(message)
                    left = dict(bindings)
                    right = dict(bindings)
                    collect(node.body, left, lexical, scope)
                    collect(node.orelse, right, lexical, scope)
                    for name in left.keys() | right.keys():
                        bindings[name] = (
                            left[name]
                            if name in left
                            and name in right
                            and left[name] == right[name]
                            else None
                        )
                elif isinstance(node, (ast.Try, ast.TryStar)):
                    message = f"Conditional exception-backed class bindings in {module}"
                    raise ValueError(message)

        collect(parsed.body, globals_, globals_, "")
        return globals_

    @classmethod
    def runtime_bases(
        cls,
        project: t.Infra.RopeProject,
        sources: t.MappingKV[str, t.Pair[Path, str]],
        roots: t.StrSequence,
    ) -> t.StrTuple:
        """Resolve owned classes in C3 order and external classes through Rope.

        Only configured roots mark model evaluation boundaries. No first-party
        module is imported or resolved from disk when its planned source exists.
        Provider reexports follow Rope's declared import provenance. Their source
        declarations, not Rope's possibly incomplete superclass inference, supply
        the ordered bases. Missing references and invalid inheritance fail loudly.

        Returns:
            Sorted configured roots and derived Ruff-qualified base expressions.

        Raises:
            TypeError: If Rope resolves a required base to a non-class.
            ValueError: If a source binding or inheritance order is invalid.

        """
        definitions: MutableMapping[str, m.Infra.SourceClassDefinition] = {}
        modules = {
            module: cls._inventory(project, module, path, source, definitions)
            for module, (path, source) in sources.items()
        }
        namespaces = {
            ".".join(parts[:index])
            for module in modules
            for parts in (module.split("."),)
            for index in range(1, len(parts) + 1)
        }
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
                    "rope.base.pyobjectsdef", "PyClass",
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
                    return resolve(m.Infra.SourceClassReference(
                        target=name, attributes=tuple(path.split(".")),
                        qualified_base=f"{name}.{path}",
                    ))
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
                    cls._inventory(
                        project,
                        name,
                        Path(resource.real_path),
                        module.source_code,
                        definitions,
                        required_line=line,
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
                if known == value:
                    return identity
            identity = f"external:{len(external)}"
            external[identity] = value
            return identity

        def provider_module(
            imported: p.Infra.RopeImportedModule,
        ) -> t.Infra.RopePyModule:
            resource = imported.resource
            if resource is not None:
                return FlextInfraUtilitiesRopeCore.resolve_pymodule(project, resource)
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
                name = ".".join(filter(None, (
                    ".".join(parts[: len(parts) - imported.level + 1]), name,
                )))
            module = project.get_module(name)
            resource = project.find_module(name)
            if resource is not None:
                module = FlextInfraUtilitiesRopeCore.resolve_pymodule(project, resource)
            return module

        def provider_reference(
            module: t.Infra.RopePyModule,
            attributes: t.StrTuple,
            visiting: frozenset[str] = frozenset(),
        ) -> str:
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
                imported = provider_module(binding.imported_module)
                if imported.get_name() not in namespaces:
                    return provider_reference(
                        imported, (binding.imported_name, *remaining), visiting | {target},
                    )
                destination = (
                    f"{imported.get_name()}.{binding.imported_name}"
                )
                if destination in visiting:
                    # The reexport destination is already being resolved on
                    # this walk: statically it cannot terminate, so the base
                    # is unresolved for this derivation (bases() skips it).
                    raise ValueError(f"Unresolved external base: {target}")
                return resolve(
                    m.Infra.SourceClassReference(
                        target=destination,
                        attributes=tuple(remaining),
                        qualified_base=target,
                    ),
                    visiting | {target, destination},
                )
            if isinstance(binding, p.Infra.RopeImportedModule):
                imported = provider_module(binding)
                if imported.get_name() not in namespaces:
                    return provider_reference(
                        imported, tuple(remaining), visiting | {target},
                    )
                return resolve(
                    m.Infra.SourceClassReference(
                        target=imported.get_name(),
                        attributes=tuple(remaining),
                        qualified_base=target,
                    ),
                    visiting | {target},
                )
            identity = external_identity(binding.get_object())
            for attribute in remaining:
                identity = member(identity, attribute)
            return identity

        def external_reference(
            target: str,
            attributes: t.StrTuple,
            visiting: frozenset[str] = frozenset(),
        ) -> str:
            module = project.get_module(target)
            resource = project.find_module(target)
            if resource is not None:
                module = FlextInfraUtilitiesRopeCore.resolve_pymodule(project, resource)
            return provider_reference(module, attributes, visiting)

        object_id = external_reference("builtins", ("object",))

        def resolve(
            reference: m.Infra.SourceClassReference,
            visiting: frozenset[str] = frozenset(),
        ) -> str:
            target = reference.target
            key = ".".join((target, *reference.attributes))
            if key in visiting:
                message = f"Cyclic class alias: {key}"
                raise ValueError(message)
            attributes = list(reference.attributes)
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
                        message = f"Unresolved planned base: {module}.{name}"
                        raise ValueError(message)
                    target = resolve(binding, visiting | {key})
                else:
                    target = external_reference(
                        target, tuple(attributes), visiting,
                    )
                    attributes.clear()
            for attribute in attributes:
                target = member(target, attribute)
            return target

        def bases(identity: str) -> t.StrTuple:
            if identity == object_id:
                return ()
            if identity in definitions:
                declared = definitions[identity].bases
                parents: list[str] = []
                for base in declared:
                    try:
                        parents.append(resolve(base))
                    except ValueError as error:
                        # A cross-package facade attribute the lazy namespace
                        # machinery exposes only at runtime (PEP 562) is
                        # invisible to rope's static lookup, third-party
                        # bases (libcst) have no source module resource, and
                        # a planned module binding that is not a class
                        # (helper modules re-exported through test support
                        # trees) has no class identity to contribute: the
                        # base cannot participate in the derivation, and the
                        # remaining bases still describe the lineage.
                        message = str(error)
                        if message.startswith(
                            "Unresolved external base:",
                        ) or message.startswith("No source module for required base:"):
                            continue
                        if message.startswith("Unresolved planned base:"):
                            continue
                        raise
                return tuple(parents) if parents else (object_id,)
            value = external[identity]
            if not isinstance(value, p.Infra.RopeBuiltinClass):
                message = f"External class has no declared source or native identity: {identity}"
                raise ValueError(message)
            return tuple(
                resolve(m.Infra.SourceClassReference(
                    target=base.__module__,
                    attributes=tuple(base.__qualname__.split(".")),
                    qualified_base=f"{base.__module__}.{base.__qualname__}",
                ))
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

        def member(identity: str, name: str) -> str:
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
                    return resolve(reference)
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
                target=".".join(parts[:index]), attributes=tuple(parts[index:]),
                qualified_base=root,
            )

        root_ids = frozenset(resolve(root_reference(root)) for root in roots)
        derived = set(roots)
        # A resolved namespace parent inserts its own definition mid-loop;
        # iterate a worklist snapshot so the derivation covers definitions
        # the loop itself adds without mutating the dict during iteration.
        pending_definitions = list(definitions.values())
        seen_identities = {definition.identity for definition in pending_definitions}
        while pending_definitions:
            definition = pending_definitions.pop(0)
            queued = [
                item
                for item in definitions.values()
                if item.identity not in seen_identities
            ]
            for item in queued:
                seen_identities.add(item.identity)
                pending_definitions.append(item)
            try:
                linearize(definition.identity)
            except ValueError as error:
                # A definition whose own lineage cannot be derived — an
                # unresolved external attribute (PEP 562 lazy namespace: a
                # facade class inheriting flext_infra.m), a required base
                # with no source module, or a member missing because an
                # ancestor's lineage was degraded — does not qualify as
                # runtime-evaluated, and its declared bases are skipped with
                # it. Structural defects (cycles, duplicates, inconsistent
                # MRO, shadowing) keep raising.
                message = str(error)
                if message.startswith(
                    "Unresolved external base:",
                ) or message.startswith("No source module for required base:"):
                    continue
                if message.startswith("Unresolved planned base:"):
                    continue
                if message.startswith("Missing inherited class member:"):
                    continue
                raise
            for reference in definition.bases:
                try:
                    lineage = linearize(resolve(reference))
                except ValueError as error:
                    # A base whose lineage crosses an unresolved external
                    # attribute (PEP 562 lazy namespace) or a planned module
                    # binding that is not a class cannot be derived; the
                    # class simply does not qualify as runtime-evaluated.
                    if str(error).startswith(
                        "Unresolved external base:",
                    ) or str(error).startswith(
                        "No source module for required base:",
                    ):
                        continue
                    if str(error).startswith("Unresolved planned base:"):
                        continue
                    raise
                if root_ids.intersection(lineage):
                    derived.add(reference.qualified_base)
        return tuple(sorted(derived))


__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBases"]
