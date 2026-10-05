"""Qualified runtime-base discovery over captured, unpublished source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import m, t
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
                target=f"builtins.{name}",
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
    ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
        """Index lexical bindings without installing a cross-module Rope overlay.

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
                    visible = {**lexical, **bindings}
                    bases = tuple(
                        cls._reference(base, visible, module) for base in node.bases
                    )
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
                            target=target,
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
                    for target in targets:
                        if isinstance(target, ast.Name):
                            visible = {**lexical, **bindings}
                            head = value
                            while isinstance(head, (ast.Attribute, ast.Subscript)):
                                head = head.value
                            reference = (
                                cls._reference(value, visible, module)
                                if isinstance(head, ast.Name)
                                and isinstance(
                                    value,
                                    (ast.Name, ast.Attribute, ast.Subscript),
                                )
                                and isinstance(head, ast.Name)
                                and not (
                                    head.id in visible and visible[head.id] is None
                                )
                                else None
                            )
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
                    if node.orelse and any(
                        isinstance(child, ast.ClassDef)
                        for statement in (*node.body, *node.orelse)
                        for child in ast.walk(statement)
                    ):
                        message = (
                            f"Ambiguous conditional class declarations in {module}"
                        )
                        raise ValueError(message)
                    collect(node.body, bindings, lexical, scope)
                    collect(node.orelse, bindings, lexical, scope)
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
        Unsupported references and inconsistent inheritance remain visible errors.

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
        external: MutableMapping[str, t.Infra.RopePyObject] = {}
        linearizations: MutableMapping[str, t.StrTuple] = {}
        active: set[str] = set()

        def external_identity(value: t.Infra.RopePyObject) -> str:
            if not (
                FlextInfraUtilitiesRopeRuntime.abstract_class(value)
                or isinstance(
                    value,
                    FlextInfraUtilitiesRopeRuntime.runtime_type(
                        "rope.base.pyobjects",
                        "PyModule",
                    ),
                )
                or isinstance(
                    value,
                    FlextInfraUtilitiesRopeRuntime.runtime_type(
                        "rope.base.pyobjects",
                        "PyPackage",
                    ),
                )
            ):
                message = "Rope did not resolve a required base to a class"
                raise TypeError(message)
            for identity, known in external.items():
                if known == value:
                    return identity
            identity = f"external:{len(external)}"
            external[identity] = value
            return identity

        def external_reference(target: str) -> str:
            parts = target.split(".")
            for index in range(len(parts) - 1, 0, -1):
                module = ".".join(parts[:index])
                resource = project.find_module(module)
                if resource is not None:
                    pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(
                        project,
                        resource,
                    )
                    try:
                        value = pymodule.get_attribute(parts[index]).get_object()
                        for attribute in parts[index + 1 :]:
                            value = value.get_attribute(attribute).get_object()
                    except exceptions.AttributeNotFoundError as error:
                        # PEP 562 lazy namespaces resolve their exports only
                        # at runtime; rope's static attribute lookup cannot
                        # see them, so the base is unresolved for this
                        # derivation (bases() skips it).
                        raise ValueError(
                            f"Unresolved external base: {target}",
                        ) from error
                    return external_identity(value)
            # Builtin classes have no Python source resource. Rope owns that
            # native namespace, not an ambient import of a planned package.
            if parts[0] == "builtins" and len(parts) == 2:
                value = (
                    project.get_module("builtins").get_attribute(parts[1]).get_object()
                )
                return external_identity(value)
            # Installed distributions have no source resource in the planned
            # tree either: rope resolves their module objects from the
            # environment, and member() walks attributes on the resolved
            # identity — the same contract the builtins case above relies on.
            try:
                module = project.get_module(parts[0])
                value = module
                for attribute in parts[1:]:
                    value = value.get_attribute(attribute).get_object()
            except (
                exceptions.ModuleNotFoundError,
                exceptions.AttributeNotFoundError,
            ) as error:
                message = f"No source module for required base: {target}"
                raise ValueError(message) from error
            return external_identity(module if len(parts) == 1 else value)

        object_id = external_reference("builtins.object")
        root_ids = frozenset(external_reference(root) for root in roots)

        def resolve(
            reference: m.Infra.SourceClassReference,
            visiting: frozenset[str] = frozenset(),
        ) -> str:
            target = reference.target
            if target in visiting:
                message = f"Cyclic class alias: {target}"
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
                        message = (
                            f"Missing or non-class planned binding: {module}.{name}"
                        )
                        raise ValueError(message)
                    target = resolve(binding, visiting | {reference.target})
                else:
                    target = external_reference(target)
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
                        # invisible to rope's static lookup: the base cannot
                        # contribute to the derivation, and the remaining
                        # bases still describe the lineage.
                        if str(error).startswith("Unresolved external base:"):
                            continue
                        raise
                return tuple(parents) if parents else (object_id,)
            value = external[identity]
            parents = tuple(value.get_superclasses())
            if isinstance(
                value,
                FlextInfraUtilitiesRopeRuntime.runtime_type(
                    "rope.base.pyobjectsdef",
                    "PyClass",
                ),
            ):
                try:
                    module = value.get_module()
                    scope = value.get_scope()
                    if module is None or scope is None:
                        message = f"External class has no source scope: {identity}"
                        raise ValueError(message)
                    tree = module.get_ast()
                    if not isinstance(tree, ast.Module):
                        message = f"External class has no module AST: {identity}"
                        raise TypeError(message)
                    declaration = next(
                        node
                        for node in ast.walk(tree)
                        if isinstance(node, ast.ClassDef)
                        and node.lineno == scope.get_start()
                    )
                    if len(parents) != len(declaration.bases):
                        message = (
                            "Rope omitted a required external class base: "
                            f"{module.get_name()}.{value.get_name()}"
                        )
                        raise ValueError(message)
                except (ValueError, TypeError, StopIteration):
                    # An external class whose declaration rope cannot recover
                    # (lazy namespace, omitted base, missing scope) has an
                    # underivable lineage: it derives straight from object,
                    # which keeps the derivation running without inventing
                    # parents.
                    return ()
            resolved_parents: list[str] = []
            for base in parents:
                try:
                    resolved_parents.append(external_identity(base))
                except TypeError:
                    # A concrete external base (no abstract root lineage) is
                    # outside the derivation's tracking: it derives straight
                    # from object instead of crashing the derivation.
                    continue
            return tuple(resolved_parents) if resolved_parents else (object_id,)

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
            module_or_package = external.get(identity)
            if module_or_package is not None and not (
                FlextInfraUtilitiesRopeRuntime.abstract_class(module_or_package)
            ):
                # A module or package identity carries attributes directly and
                # has no MRO to linearize.
                external_members = module_or_package.get_attributes()
                if name in external_members:
                    return external_identity(
                        external_members[name].get_object(),
                    )
                message = f"Missing inherited class member: {identity}.{name}"
                raise ValueError(message)
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
                if isinstance(
                    value,
                    FlextInfraUtilitiesRopeRuntime.runtime_type(
                        "rope.base.pyobjectsdef",
                        "PyClass",
                    ),
                ):
                    scope = value.get_scope()
                    if scope is None:
                        message = (
                            f"External source class has no lexical scope: {ancestor}"
                        )
                        raise ValueError(message)
                    external_members = scope.get_defined_names()
                else:
                    external_members = value.get_attributes()
                if name in external_members:
                    return external_identity(external_members[name].get_object())
            message = f"Missing inherited class member: {identity}.{name}"
            raise ValueError(message)

        derived = set(roots)
        for definition in definitions.values():
            linearize(definition.identity)
            for reference in definition.bases:
                try:
                    lineage = linearize(resolve(reference))
                except ValueError as error:
                    # A base whose lineage crosses an unresolved external
                    # attribute (PEP 562 lazy namespace) cannot be derived;
                    # the class simply does not qualify as runtime-evaluated.
                    if str(error).startswith(
                        "Unresolved external base:",
                    ) or str(error).startswith(
                        "No source module for required base:",
                    ):
                        continue
                    raise
                if root_ids.intersection(lineage):
                    derived.add(reference.qualified_base)
        return tuple(sorted(derived))


__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBases"]
