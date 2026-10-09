"""Invocation-scoped class identity and C3 resolution over captured bindings.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

from flext_infra import c, m, p, t
from flext_infra._utilities._rope_analysis.sourcescan import (
    FlextInfraUtilitiesRopeAnalysisSourceScan,
)
from flext_infra._utilities._rope_source_bases_inventory_collector import (
    FlextInfraUtilitiesRopeSourceBindingCollector,
)
from flext_infra._utilities.rope_core import FlextInfraUtilitiesRopeCore
from flext_infra._utilities.rope_runtime import FlextInfraUtilitiesRopeRuntime


class FlextInfraUtilitiesRopeSourceBasesRuntime(
    FlextInfraUtilitiesRopeSourceBindingCollector,
):
    """Borrow one inventory and own only its invocation's resolution caches."""

    def __init__(
        self,
        project: t.Infra.RopeProject,
        definitions: t.MutableMappingKV[str, m.Infra.SourceClassDefinition],
        modules: t.MappingKV[
            str, t.MappingKV[str, m.Infra.SourceClassReference | None]
        ],
        namespaces: set[str],
        module_aliases: t.StrMapping,
    ) -> None:
        """Retain shared maps and snapshot owned definitions before provider lookup."""
        self._project: t.Infra.RopeProject = project
        self._definitions: t.MutableMappingKV[str, m.Infra.SourceClassDefinition] = (
            definitions
        )
        self._modules: t.MappingKV[
            str, t.MappingKV[str, m.Infra.SourceClassReference | None]
        ] = modules
        self._namespaces: set[str] = namespaces
        self._module_aliases: t.StrMapping = module_aliases
        self._owned_definitions: t.SequenceOf[m.Infra.SourceClassDefinition] = tuple(
            definitions.values()
        )
        self._external: t.MutableMappingKV[str, t.Infra.RopePyObject] = {}
        self._linearizations: t.MutableMappingKV[str, t.StrTuple] = {}
        self._active: set[str] = set()
        self._object_id: str = self._external_reference("builtins", ("object",))
        # Cycle checks precede memo reads, including deep facade attribute chains.
        self._resolved_memo: t.MutableStrMapping = {}

    @classmethod
    def inventory(
        cls,
        request: m.Infra.SourceBindingInventoryRequest,
        definitions: t.MutableMappingKV[str, m.Infra.SourceClassDefinition],
        *,
        provider: t.Infra.RopePyModule | None = None,
    ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
        """Index lexical bindings without installing a cross-module Rope overlay.

        Returns:
            Explicit module bindings, including value shadowing.

        Raises:
            TypeError: If Rope returns a non-module AST.
            ValueError: If provider bytes differ or a lazy import remains unresolved.
        """
        if provider is not None:
            resource = provider.get_resource()
            if (
                resource is None
                or resource.real_path != str(request.path)
                or provider.source_code != request.source
            ):
                message = f"Provider does not match captured source: {request.path}"
                raise ValueError(message)
            parsed = provider.get_ast()
        else:
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
        bindings: t.MutableMappingKV[str, m.Infra.SourceClassReference | None] = {}
        spec = m.Infra.SourceBindingCollectorSpec(
            module=request.module,
            package=package,
            required_line=request.required_line,
            allow_conditional=request.allow_conditional,
            definitions=definitions,
            lexical=bindings,
        )
        cls.collect(spec, parsed.body, bindings, "")
        targets, references = (
            FlextInfraUtilitiesRopeAnalysisSourceScan.lazy_import_mapping_source(
                request.source,
            )
        )
        if references and not request.module.startswith("tests."):
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
                bindings[name] = m.Infra.SourceClassReference(
                    target=destination,
                    attributes=(name,),
                    qualified_base=f"{request.module}.{name}",
                )
        return bindings

    def discover_runtime_bases(self, roots: t.StrSequence) -> t.StrTuple:
        """Resolve roots before class lineages in captured declaration order.

        Returns:
            Sorted roots and derived Ruff-qualified base expressions.
        """
        root_ids = frozenset(
            self._resolve(self._root_reference(root)) for root in roots
        )
        derived = set(roots)
        for definition in self._owned_definitions:
            self._linearize(definition.identity)
            for reference in definition.bases:
                lineage = self._linearize(self._resolve(reference))
                if root_ids.intersection(lineage):
                    derived.add(reference.qualified_base)
        return tuple(sorted(derived))

    def _external_identity(self, value: t.Infra.RopePyObject) -> str:
        """Preserve source declarations and exact native wrapper identity.

        Returns:
            The unique declaration or invocation-local native identity.

        Raises:
            TypeError: If Rope does not resolve a required base to a class.
        """
        if not FlextInfraUtilitiesRopeRuntime.abstract_class(value):
            message = "Rope did not resolve a required base to a class"
            raise TypeError(message)
        if isinstance(
            value,
            FlextInfraUtilitiesRopeRuntime.runtime_type(
                "rope.base.pyobjectsdef", "PyClass"
            ),
        ):
            return self._source_identity(value)
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

    def _source_identity(self, value: t.Infra.RopePyObject) -> str:
        """Find the exact provider declaration without importing captured sources.

        Returns:
            The source declaration's identity.

        Raises:
            ValueError: If the source location or declaration is missing.
        """
        module = value.get_module()
        scope = value.get_scope()
        resource = module.get_resource() if module is not None else None
        if module is None or scope is None or resource is None:
            message = f"External class has no source declaration: {value.get_name()}"
            raise ValueError(message)
        name = module.get_name()
        line = scope.get_start()
        if name in self._modules:
            return self._planned_identity(module, name, line, value)
        identity = self._definition_identity(name, line)
        if identity is None:
            self.inventory(
                m.Infra.SourceBindingInventoryRequest(
                    project=self._project,
                    module=name,
                    path=Path(resource.real_path),
                    source=module.source_code,
                    required_line=line,
                    allow_conditional=True,
                ),
                self._definitions,
                provider=module,
            )
            identity = self._definition_identity(name, line)
        if identity is None:
            message = f"Missing external class declaration: {name}:{line}"
            raise ValueError(message)
        return identity

    def _planned_identity(
        self,
        module: t.Infra.RopePyModule,
        name: str,
        line: int,
        value: t.Infra.RopePyObject,
    ) -> str:
        """Resolve a provider location through its authoritative captured module.

        Returns:
            The captured declaration identity.

        Raises:
            TypeError: If the provider has no module AST.
            ValueError: If its nested declaration path is missing.
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

    def _definition_identity(self, name: str, line: int) -> str | None:
        """Locate an inventoried definition by its module and source line.

        Returns:
            The first matching identity, or None when absent.
        """
        return next(
            (
                identity
                for identity in self._definitions
                if identity.startswith(f"{name}:") and identity.endswith(f":{line}")
            ),
            None,
        )

    def _provider_module_name(self, imported: p.Infra.RopeImportedModule) -> str:
        """Follow the import's declared module and relative package level.

        Returns:
            The absolute provider module name.

        Raises:
            ValueError: If the location is missing or the relative import escapes.
        """
        if imported.module_name is None:
            if imported.resource is None:
                message = "Import has no declared module location"
                raise ValueError(message)
            return FlextInfraUtilitiesRopeCore.resolve_pymodule(
                self._project, imported.resource
            ).get_name()
        if not imported.level:
            return imported.module_name
        declaring = imported.importing_module.get_module()
        source = declaring.get_resource() if declaring is not None else None
        if declaring is None or source is None:
            message = "Import has no declared module location"
            raise ValueError(message)
        package = declaring.get_name()
        if Path(source.real_path).name != "__init__.py":
            package = package.rpartition(".")[0]
        parts = package.split(".") if package else []
        if imported.level > len(parts):
            message = (
                f"Relative import escapes package: {package}.{imported.module_name}"
            )
            raise ValueError(message)
        return ".".join(
            filter(
                None,
                (
                    ".".join(parts[: len(parts) - imported.level + 1]),
                    imported.module_name,
                ),
            ),
        )

    def _provider_module(
        self, imported: p.Infra.RopeImportedModule
    ) -> t.Infra.RopePyModule:
        """Resolve the provider resource after reading its import provenance.

        Returns:
            The provider's Rope module.
        """
        resource = imported.resource
        if resource is not None:
            return FlextInfraUtilitiesRopeCore.resolve_pymodule(self._project, resource)
        name = self._provider_module_name(imported)
        module = self._project.get_module(name)
        resource = self._project.find_module(name)
        if resource is not None:
            module = FlextInfraUtilitiesRopeCore.resolve_pymodule(
                self._project, resource
            )
        return module

    def _provider_reference(
        self,
        module: t.Infra.RopePyModule,
        attributes: t.StrTuple,
        visiting: frozenset[str] = frozenset(),
        depth: int = 0,
    ) -> str:
        """Follow provider imports before resolving class members.

        Returns:
            The referenced class identity.

        Raises:
            ValueError: If depth, module-as-base or reexport-cycle checks fail.
        """
        if depth > c.Infra.ROPE_WALK_DEPTH_BUDGET:
            message = f"Unresolved external base: {module.get_name()} at depth {depth}"
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
            return self._imported_reference(
                binding.imported_module,
                (binding.imported_name, *remaining),
                target,
                visiting,
                depth,
            )
        if isinstance(binding, p.Infra.RopeImportedModule):
            return self._imported_reference(
                binding, tuple(remaining), target, visiting, depth
            )
        identity = self._external_identity(binding.get_object())
        for attribute in remaining:
            identity = self._member(identity, attribute, depth + 1, visiting)
        return identity

    def _imported_reference(
        self,
        imported: p.Infra.RopeImportedModule,
        attributes: t.StrTuple,
        target: str,
        visiting: frozenset[str],
        depth: int,
    ) -> str:
        """Enter captured imports or continue the exact provider reexport edge.

        Returns:
            The class identity reached through the import.
        """
        imported_name = self._provider_module_name(imported)
        if imported_name in self._namespaces:
            return self._resolve(
                m.Infra.SourceClassReference(
                    target=imported_name,
                    attributes=attributes,
                    qualified_base=target,
                ),
                visiting | {target},
                depth + 1,
            )
        module = self._provider_module(imported)
        return self._provider_reference(
            module, attributes, visiting | {target}, depth + 1
        )

    def _external_reference(
        self,
        target: str,
        attributes: t.StrTuple,
        visiting: frozenset[str] = frozenset(),
        depth: int = 0,
    ) -> str:
        """Resolve a provider module without normalizing its original exceptions.

        Returns:
            The provider class identity.
        """
        module = self._project.get_module(target)
        resource = self._project.find_module(target)
        if resource is not None:
            module = FlextInfraUtilitiesRopeCore.resolve_pymodule(
                self._project, resource
            )
        return self._provider_reference(module, attributes, visiting, depth)

    def _reference_target(
        self, reference: m.Infra.SourceClassReference
    ) -> t.Pair[str, t.MutableSequenceOf[str]]:
        """Apply the existing module-alias precedence before forming a memo key.

        Returns:
            The target and mutable remaining attribute path.
        """
        target = reference.target
        attributes = list(reference.attributes)
        if target in self._module_aliases:
            attributes.insert(0, target.rpartition(".")[2])
            target = self._module_aliases[target]
        elif attributes:
            qualified_head = f"{target}.{attributes[0]}"
            if qualified_head in self._module_aliases:
                target = self._module_aliases[qualified_head]
        return target, attributes

    def _resolve(
        self,
        reference: m.Infra.SourceClassReference,
        visiting: frozenset[str] = frozenset(),
        depth: int = 0,
    ) -> str:
        """Resolve one lexical reference with cycle checks before memo lookup.

        Returns:
            The final class identity.

        Raises:
            ValueError: If depth or class-alias cycle checks fail.
        """
        if depth > c.Infra.ROPE_WALK_DEPTH_BUDGET:
            message = f"Unresolved external base: {reference.target}"
            raise ValueError(message)
        target, attributes = self._reference_target(reference)
        key = ".".join((target, *attributes))
        if key in visiting:
            message = f"Cyclic class alias: {key}"
            raise ValueError(message)
        memo = self._resolved_memo.get(key)
        if memo is not None:
            return memo
        if target not in self._definitions and target not in self._external:
            if target.split(".")[0] in self._namespaces:
                target, attributes = self._planned_reference(
                    reference, target, attributes, visiting | {key}, depth
                )
            else:
                target = self._external_reference(
                    target, tuple(attributes), visiting, depth + 1
                )
                attributes.clear()
        for attribute in attributes:
            target = self._member(target, attribute, 0, visiting | {key})
        self._resolved_memo[key] = target
        return target

    def _planned_reference(
        self,
        reference: m.Infra.SourceClassReference,
        target: str,
        attributes: t.MutableSequenceOf[str],
        visiting: frozenset[str],
        depth: int,
    ) -> t.Pair[str, t.MutableSequenceOf[str]]:
        """Resolve a captured package binding before remaining class members.

        Returns:
            The binding identity and unconsumed attribute path.

        Raises:
            ValueError: If a module is used as a base or its binding is missing.
        """
        parts = target.split(".")
        index = next(
            index
            for index in range(len(parts), 0, -1)
            if ".".join(parts[:index]) in self._namespaces
        )
        module = ".".join(parts[:index])
        attributes = [*parts[index:], *attributes]
        module = self._planned_namespace(module, attributes)
        if not attributes:
            message = f"Module used as a class base: {module}"
            raise ValueError(message)
        name = attributes.pop(0)
        if module not in self._modules:
            message = f"Planned namespace has no module binding: {module}.{name}"
            raise ValueError(message)
        binding = self._modules[module].get(name)
        if binding is None:
            message = (
                f"Unresolved planned base: {module}.{name} "
                f"(reference={reference.qualified_base!r}, "
                f"target={reference.target!r}, "
                f"attributes={reference.attributes!r})"
            )
            raise ValueError(message)
        return self._resolve(binding, visiting, depth + 1), attributes

    def _planned_namespace(
        self, module: str, attributes: t.MutableSequenceOf[str]
    ) -> str:
        """Consume captured child modules only while no explicit binding wins.

        Returns:
            The selected captured namespace, preserving current package rules.
        """
        while (
            attributes
            and (
                module not in self._modules
                or attributes[0] not in self._modules[module]
            )
            and f"{module}.{attributes[0]}" in self._namespaces
        ):
            module = f"{module}.{attributes.pop(0)}"
        return module

    def _bases(self, identity: str) -> t.StrTuple:
        """Read ordered declared bases or exact observed native ancestors.

        Returns:
            Parent identities in their original declaration order.

        Raises:
            TypeError: If an external class has neither source nor native identity.
        """
        if identity == self._object_id:
            return ()
        if identity in self._definitions:
            declared = self._definitions[identity].bases
            return (
                tuple(self._resolve(base) for base in declared)
                if declared
                else (self._object_id,)
            )
        value = self._external[identity]
        if not isinstance(value, p.Infra.RopeBuiltinClass):
            message = (
                f"External class has no declared source or native identity: {identity}"
            )
            raise TypeError(message)
        return tuple(
            self._external_identity(FlextInfraUtilitiesRopeRuntime.native_class(base))
            for base in value.builtin.__bases__
        )

    def _linearize(self, identity: str) -> t.StrTuple:
        """Compute C3 with the original active-set and cache publication order.

        Returns:
            The class identity followed by its ordered ancestors.

        Raises:
            ValueError: If inheritance is cyclic, duplicated or inconsistent.
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
        sequences = [list(self._linearize(parent)) for parent in parents]
        sequences.append(list(parents))
        result = self._merge_c3(identity, sequences)
        self._active.remove(identity)
        self._linearizations[identity] = tuple(result)
        return self._linearizations[identity]

    @staticmethod
    def _merge_c3(
        identity: str, sequences: t.SequenceOf[t.MutableSequenceOf[str]]
    ) -> t.MutableSequenceOf[str]:
        """Consume the leftmost valid C3 head without copying parent sequences.

        Returns:
            The merged identity sequence.

        Raises:
            ValueError: If no head satisfies C3 precedence.
        """
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
        return result

    def _member(
        self,
        identity: str,
        name: str,
        depth: int = 0,
        visiting: frozenset[str] = frozenset(),
    ) -> str:
        """Read the receiver's native descriptor before C3 member lookup.

        Returns:
            The selected member class identity.

        Raises:
            ValueError: If a member is missing or shadowed by a non-class value.
        """
        if name == "__base__" and identity in self._external:
            value = self._external[identity]
            if isinstance(value, p.Infra.RopeBuiltinClass):
                return self._external_identity(
                    FlextInfraUtilitiesRopeRuntime.native_class_primary_base(
                        value.builtin,
                    ),
                )
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
        """Select the configured root's longest declared or installed module prefix.

        Returns:
            The root's module binding and remaining class attributes.
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
