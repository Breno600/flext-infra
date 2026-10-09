"""Qualified runtime-base resolution and linearization.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
from pathlib import Path

from rope.base import exceptions

from flext_infra import c, m, p, t
from flext_infra._utilities import (
    FlextInfraUtilitiesRopeCore,
    FlextInfraUtilitiesRopeRuntime,
    FlextInfraUtilitiesRopeSourceBasesAliases,
    FlextInfraUtilitiesRopeSourceBasesInventory,
)


class FlextInfraUtilitiesRopeSourceBasesRuntime:
    """Canonical namespace owner."""

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
                module: self.inventory(module, captured)
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
                    FlextInfraUtilitiesRopeSourceBasesAliases.lazy_module_aliases(
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

        def inventory(
            self,
            module: str,
            captured: t.Pair[Path, str],
            *,
            required_line: int | None = None,
            allow_conditional: bool = False,
            provider: t.Infra.RopePyModule | None = None,
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
                provider: Existing Rope module owning the same captured source.

            Returns:
                The module's explicit lexical bindings, including value
                shadowing.

            """
            request = m.Infra.SourceBindingInventoryRequest(
                project=self._project,
                module=module,
                path=captured[0],
                source=captured[1],
                required_line=required_line,
                allow_conditional=allow_conditional,
            )
            return FlextInfraUtilitiesRopeSourceBasesInventory.inventory(
                request,
                self._definitions,
                provider=provider,
            )

        def _external_identity(self, value: t.Infra.RopePyObject) -> str:
            """Return the declaration identity of one external Rope object.

            Raises:
                TypeError: If Rope resolves a required base to a non-class.

            """
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
                if resource is None:
                    message = f"Module has no declared resource: {name}"
                    raise ValueError(message)
                self.inventory(
                    name,
                    (Path(resource.real_path), module.source_code),
                    required_line=line,
                    allow_conditional=True,
                    provider=module,
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

        def _provider_module(
            self,
            imported: p.Infra.RopeImportedModule,
        ) -> t.Infra.RopePyModule:
            """Return the Rope module object one import points at.

            Returns:
                The resolved Rope module object.

            """
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
            # A provider attribute Rope cannot resolve escapes with Rope's own
            # failure; it never degrades into a synthetic identity.
            binding = module.get_attribute(name)
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
            value = binding.get_object()
            if remaining and FlextInfraUtilitiesRopeRuntime.instance_object(value):
                # Attribute access on a facade instance (``meltano.Tap``)
                # reaches the class attribute through the instance's type.
                value = value.get_type()
            identity = self._external_identity(value)
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
                RefactoringError: If Rope cannot resolve the target or its backing.
                ResourceNotFoundError: If Rope cannot locate the required resource.
                AttributeError: If the provider lacks a required module attribute.

            """
            try:
                module = self._project.get_module(target)
            except (
                exceptions.RefactoringError,
                exceptions.ResourceNotFoundError,
                exceptions.ModuleNotFoundError,
                AttributeError,
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
            if direct is not None and self._declaration_is_live(direct):
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

        def _declaration_is_live(self, identity: str) -> bool:
            """Return whether a nested declaration still answers its own path.

            A provider may write a different value onto an enclosing class
            member (``Owner.Name = replacement``); the dotted path then names
            that member, not the original nested declaration, at every level.

            An explicit package binding wins over a same-named submodule file
            in the same way (``document = 0`` in the package hides the
            ``document`` submodule from ``package.document``).

            Returns:
                False when any enclosing package binding or class member
                overrides the path.

            """
            module_name, qualified, _ = identity.split(":", 2)
            packages = module_name.split(".")
            for index in range(1, len(packages)):
                package = ".".join(packages[:index])
                name = packages[index]
                package_bindings = self._modules.get(package, {})
                if name not in package_bindings:
                    continue
                binding = package_bindings[name]
                if (
                    binding is None
                    or binding.target != package
                    or binding.attributes != (name,)
                ):
                    return False
            parts = qualified.split(".")
            for index in range(1, len(parts)):
                parent = self._definition_keys.get(
                    ".".join((module_name, *parts[:index])),
                )
                if parent is None:
                    continue
                member = self._definitions[parent].members.get(parts[index])
                child = self._definition_keys.get(
                    ".".join((module_name, *parts[: index + 1])),
                )
                if member is None or member.target != child:
                    return False
            return True

        def _alias_rewritten_target(
            self,
            reference: m.Infra.SourceClassReference,
        ) -> t.Pair[str, t.StrTuple]:
            """Rewrite facade-qualified targets through the lazy alias map.

            The alias map routes a published name to its provider module, so
            the name itself stays the first attribute looked up there.

            Returns:
                The rewritten target and its remaining attribute path.

            """
            target = reference.target
            attributes = reference.attributes
            if target in self._module_aliases:
                return (
                    self._module_aliases[target],
                    (target.rpartition(".")[2], *attributes),
                )
            if attributes:
                qualified_head = f"{target}.{attributes[0]}"
                if qualified_head in self._module_aliases:
                    return self._module_aliases[qualified_head], attributes
            return target, attributes

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
            # Import-from can bind a captured child module rather than a
            # package export; an explicit package binding still wins.
            while (
                remaining
                and (module not in self._modules or remaining[0] not in self._modules[module])
                and f"{module}.{remaining[0]}" in self._namespaces
            ):
                module = f"{module}.{remaining.pop(0)}"
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
            value = self._external[identity]
            if not isinstance(value, p.Infra.RopeBuiltinClass):
                message = (
                    "External class has no declared source or native identity: "
                    f"{identity}"
                )
                raise TypeError(message)
            builtin_class = FlextInfraUtilitiesRopeRuntime._runtime_callable(  # ruff: ignore[private-member-access] - same-runtime internal rope accessor
                "rope.base.builtins",
                "BuiltinClass",
            )
            return tuple(
                self._external_identity(
                    self._builtin_base_identity(builtin_class(base, {})),
                )
                for base in value.builtin.__bases__
            )

        @staticmethod
        def _builtin_base_identity(
            value: p.AttributeProbe,
        ) -> t.Infra.RopePyObject:
            """Narrow one constructed Rope builtin base to its object shape.

            Returns:
                The narrowed Rope object value.

            Raises:
                TypeError: If the constructed base is not a Rope class object.

            """
            if not FlextInfraUtilitiesRopeRuntime.abstract_class(value):
                message = "Rope builtin base did not resolve to a class object"
                raise TypeError(message)
            return value

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
            if name == "__base__" and identity in self._external:
                value = self._external[identity]
                if isinstance(value, p.Infra.RopeBuiltinClass):
                    # A native class's primary base is its type descriptor,
                    # never an inherited class member.
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

        _stdlib_backing_cache: dict[str, str] | None = None

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

        """
        return FlextInfraUtilitiesRopeSourceBasesRuntime._RuntimeBaseResolver(
            project,
            sources,
            roots,
            extra_module_aliases,
        ).run()


# The flat module-level re-export: the package lazy map and the
# internal from-import contract resolve this name at module scope
# (the S6 nesting moved the class inside the family facade).

__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBasesRuntime"]
