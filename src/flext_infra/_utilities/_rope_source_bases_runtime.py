"""Qualified runtime-base resolution and linearization.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import sys
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, m, p, t


class FlextInfraUtilitiesRopeSourceBasesRuntime:
    """Runtime-base resolution part of the source-bases composite."""

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
        the ordered bases. Missing references and invalid inheritance fail loudly.

        Returns:
            Sorted configured roots and derived Ruff-qualified base expressions.

        Raises:
            TypeError: If Rope resolves a required base to a non-class.
            ValueError: If a source binding or inheritance order is invalid.

        """
        from flext_infra._utilities import (
            FlextInfraUtilitiesRopeCore,
            FlextInfraUtilitiesRopeRuntime,
        )

        definitions: MutableMapping[str, m.Infra.SourceClassDefinition] = {}
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 4096))
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
        module_aliases: dict[str, str] = {}
        for alias_module, (alias_path, alias_source) in sources.items():
            for alias, absolute in cls.lazy_module_aliases(
                alias_module,
                alias_path,
                alias_source,
            ).items():
                # A lazy re-export alias is a module-local binding, never a
                # global rename. When its name collides with a real analyzed
                # module (or namespace), the real module wins: an absolute
                # import elsewhere in the tree refers to the real module —
                # a facade re-exporting a subpackage named like the project
                # package must not shadow it (cosmos-docgen tests/unit
                # re-exports a `dcdoc` subpackage; class bases declared as
                # `from dcdoc import DcdocServiceBase` mean the project one).
                if alias in modules or alias in namespaces:
                    continue
                module_aliases.setdefault(alias, absolute)
        for alias, absolute in (extra_module_aliases or {}).items():
            if alias in modules or alias in namespaces:
                continue
            module_aliases.setdefault(alias, absolute)
        owned_definitions = tuple(definitions.values())
        definition_keys: dict[str, str] = {}
        for definition_identity, definition in definitions.items():
            module_name, qualified, _ = definition_identity.split(":", 2)
            definition_keys[f"{module_name}.{qualified}"] = definition_identity
        external: MutableMapping[str, t.Infra.RopePyObject] = {}
        linearizations: MutableMapping[str, t.StrTuple] = {}
        active: set[str] = set()
        native_module_type = FlextInfraUtilitiesRopeRuntime.runtime_type(
            "rope.base.builtins",
            "BuiltinModule",
        )

        def external_identity(value: t.Infra.RopePyObject) -> str:
            # TypedDict and NamedTuple build their classes through function
            # calls, so Rope resolves the declared base to a PyFunction; the
            # base identity is still the class that call constructs at
            # runtime.
            if isinstance(
                value,
                FlextInfraUtilitiesRopeRuntime.runtime_type(
                    "rope.base.pyobjectsdef",
                    "PyFunction",
                ),
            ) and value.get_name() in {"TypedDict", "NamedTuple"}:
                module = value.get_module()
                module_name = module.get_name() if module is not None else ""
                name = value.get_name()
                return f"{module_name}.{name}" if module_name else name
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
                        ),
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
                    cls._inventory(
                        project,
                        name,
                        Path(resource.real_path),
                        module.source_code,
                        definitions,
                        required_line=line,
                        allow_conditional=True,
                    )
                    for definition_identity in definitions:
                        module_name, qualified, _ = definition_identity.split(":", 2)
                        if module_name == name:
                            definition_keys[f"{module_name}.{qualified}"] = (
                                definition_identity
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

        def provider_module(
            imported: p.Infra.RopeImportedModule,
        ) -> t.Infra.RopePyModule:
            name = provider_module_name(imported)
            module = project.get_module(name)
            resource = imported.resource or project.find_module(name)
            if resource is not None and not isinstance(module, native_module_type):
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
                chain = " <- ".join(sorted(visiting))
                message = f"Cyclic provider reexport: {target} (visiting: {chain})"
                raise ValueError(message)
            try:
                binding = module.get_attribute(name)
            except Exception:
                # The provider cannot resolve the attribute statically (a
                # star re-export, a runtime-injected name): the base
                # degrades to its qualified name as a synthetic terminal
                # identity instead of failing the whole walk.
                return target
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
            try:
                module = project.get_module(target)
            except (
                *FlextInfraUtilitiesRopeRuntime.rope_runtime_errors(),
                ModuleNotFoundError,
            ):
                # Rope raises its own ModuleNotFoundError (not the builtin).
                # Virtual stdlib submodules (collections.abc since 3.13, and
                # aliases like os.path) exist only through runtime module
                # aliasing, so static file lookup cannot see them. Their
                # declarations live in the backing real module, which rope
                # resolves normally.
                real = cls._stdlib_backing_module(target)
                if real is None:
                    raise
                module = project.get_module(real)
            resource = project.find_module(target)
            if (
                resource is not None
                and not isinstance(module, native_module_type)
                and FlextInfraUtilitiesRopeCore.resolvable_module_resource(resource)
            ):
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
                message = (
                    f"Unresolved external base: {reference.target} at depth {depth}"
                )
                raise ValueError(message)
            rewrite_target = reference.target
            rewrite_attributes = reference.attributes
            if rewrite_attributes:
                qualified_head = f"{rewrite_target}.{rewrite_attributes[0]}"
                if qualified_head in module_aliases:
                    rewrite_target = module_aliases[qualified_head]
                    rewrite_attributes = rewrite_attributes[1:]
            target = module_aliases.get(rewrite_target, rewrite_target)
            key = ".".join((target, *rewrite_attributes))
            if key in visiting:
                message = f"Cyclic class alias: {key}"
                raise ValueError(message)
            memo = resolved_memo.get(key)
            if memo is not None:
                return memo
            direct = definition_keys.get(key)
            if direct is not None:
                resolved_memo[key] = direct
                return direct
            attributes = list(rewrite_attributes)
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
                target = member(target, attribute, 0, visiting)
            resolved_memo[key] = target
            return target

        def bases(identity: str) -> t.StrTuple:
            if identity == object_id:
                return ()
            if identity not in definitions and identity not in external:
                # Synthetic terminal identities (runtime-constructed bases
                # such as TypedDict) carry no ancestry of their own; they
                # linearize as direct object children.
                return (object_id,)
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
            builtin_class = FlextInfraUtilitiesRopeRuntime.runtime_type(
                "rope.base.builtins",
                "BuiltinClass",
            )
            return tuple(
                external_identity(builtin_class(base, {}))
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
