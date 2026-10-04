"""Rope semantic import state, class discovery, and project-backed probes.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import importlib.util as _importlib_util
from collections.abc import MutableMapping
from pathlib import Path
from typing import ClassVar

from flext_infra import c, m, t
from flext_infra._utilities._rope_analysis.asthelpers import (
    FlextInfraUtilitiesRopeAnalysisAstHelpers,
)
from flext_infra._utilities._rope_analysis.exports import (
    FlextInfraUtilitiesRopeAnalysisExports,
)
from flext_infra._utilities.rope_core import FlextInfraUtilitiesRopeCore
from flext_infra._utilities.rope_runtime import FlextInfraUtilitiesRopeRuntime


class FlextInfraUtilitiesRopeAnalysisImportState:
    """Rope semantic import state, class discovery, and project-backed probes."""

    _SEMANTIC_STATE_CACHE: ClassVar[
        MutableMapping[t.Triple[str, str, int], m.Infra.ModuleSemanticState]
    ] = {}

    @staticmethod
    def package_name_for_module(
        module_name: str,
        resource: t.Infra.RopeResource,
    ) -> str:
        """Return the dotted package prefix for one Rope module.

        Returns:
            The dotted package prefix for one Rope module.

        """
        return FlextInfraUtilitiesRopeAnalysisImportState._package_name_for_module(
            module_name,
            resource,
        )

    @staticmethod
    def _package_name_for_module(
        module_name: str,
        resource: t.Infra.RopeResource,
    ) -> str:
        """Package name for module.

        Returns:
            The resulting ``str``.

        """
        if (
            resource.path.endswith(f"/{c.Infra.INIT_PY}")
            or resource.path == c.Infra.INIT_PY
        ):
            return module_name
        return module_name.rsplit(".", maxsplit=1)[0] if "." in module_name else ""

    @staticmethod
    def resolve_import_module(
        *,
        current_package: str,
        module_name: str,
        level: int,
    ) -> str:
        """Resolve one declared import to an absolute module name.

        Returns:
            The resulting ``str``.

        """
        return FlextInfraUtilitiesRopeAnalysisImportState._resolve_import_module(
            current_package=current_package,
            module_name=module_name,
            level=level,
        )

    @staticmethod
    def _resolve_import_module(
        *,
        current_package: str,
        module_name: str,
        level: int,
    ) -> str:
        """Resolve import module.

        Returns:
            The resulting ``str``.

        """
        if level <= 0:
            return module_name
        return _importlib_util.resolve_name(
            f"{'.' * level}{module_name}",
            current_package,
        )

    @classmethod
    def resolve_module_semantic_state(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
    ) -> m.Infra.ModuleSemanticState:
        """Return local classes plus declared and semantic imports in one pass.

        Uses rope's ``PyModule.get_attributes()`` for class discovery and
        ``rope.refactor.importutils.get_module_imports`` for import-table
        construction — no ``ast`` walking is performed.

        Returns:
            Local classes plus declared and semantic imports in one pass.

        """
        cache_key = FlextInfraUtilitiesRopeAnalysisAstHelpers.resource_cache_key(
            rope_project,
            resource,
        )
        cached = FlextInfraUtilitiesRopeAnalysisImportState._SEMANTIC_STATE_CACHE.get(
            cache_key,
        )
        if cached is not None:
            return cached
        pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(rope_project, resource)
        state = cls._module_semantic_state_from_pymodule(
            rope_project=rope_project,
            resource=resource,
            pymodule=pymodule,
        )
        FlextInfraUtilitiesRopeAnalysisImportState._SEMANTIC_STATE_CACHE[cache_key] = (
            state
        )
        return state

    @staticmethod
    def _empty_module_semantic_state() -> m.Infra.ModuleSemanticState:
        """Return an empty semantic state.

        Returns:
            An empty semantic state.

        """
        return m.Infra.ModuleSemanticState(
            class_infos=(),
            declared_imports={},
            semantic_imports={},
        )

    @staticmethod
    def _module_semantic_state_from_pymodule(
        *,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        pymodule: t.Infra.RopePyModule,
    ) -> m.Infra.ModuleSemanticState:
        """Build semantic state from one resolved Rope module.

        Returns:
            The resulting ``m.Infra.ModuleSemanticState``.

        """
        current_package = (
            FlextInfraUtilitiesRopeAnalysisImportState._package_name_for_module(
                pymodule.get_name(),
                resource,
            )
        )
        declared_imports, semantic_imports = (
            FlextInfraUtilitiesRopeAnalysisImportState._module_import_maps(
                rope_project=rope_project,
                resource=resource,
                current_package=current_package,
            )
        )
        return m.Infra.ModuleSemanticState(
            class_infos=tuple(
                FlextInfraUtilitiesRopeAnalysisImportState._module_class_infos(
                    pymodule=pymodule,
                    resource=resource,
                ),
            ),
            declared_imports=declared_imports,
            semantic_imports=semantic_imports,
        )

    @staticmethod
    def _module_class_infos(
        *,
        pymodule: t.Infra.RopePyModule,
        resource: t.Infra.RopeResource,
    ) -> t.SequenceOf[m.Infra.ClassInfo]:
        """Return local class infos for one resolved Rope module.

        Returns:
            Local class infos for one resolved Rope module.

        """
        class_infos: t.MutableSequenceOf[m.Infra.ClassInfo] = []
        ast_bases_by_class = {
            class_info.name: class_info.bases
            for class_info in (
                FlextInfraUtilitiesRopeAnalysisAstHelpers.class_info_from_source
            )(
                resource.read(),
            )
        }
        for name, pyname in pymodule.get_attributes().items():
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.local_name(
                pyname,
                resource,
            ):
                continue
            obj = pyname.get_object()
            if not FlextInfraUtilitiesRopeRuntime.abstract_class(obj):
                continue
            location = pyname.get_definition_location()
            line = location[1] if location and location[1] else 1
            bases: t.StrSequence = tuple(
                base_name
                for superclass in obj.get_superclasses()
                if (
                    base_name
                    := FlextInfraUtilitiesRopeAnalysisImportState._superclass_name(
                        superclass,
                    )
                )
            )
            if not bases:
                bases = ast_bases_by_class.get(name, ())
            class_infos.append(m.Infra.ClassInfo(name=name, line=line, bases=bases))
        return tuple(class_infos)

    @staticmethod
    def superclass_name(superclass: t.Infra.RopePyObject) -> str:
        """Return a superclass name from Rope objects with uneven public APIs.

        Returns:
            A superclass name from Rope objects with uneven public APIs.

        """
        return FlextInfraUtilitiesRopeAnalysisImportState._superclass_name(superclass)

    @staticmethod
    def _superclass_name(
        superclass: t.Infra.RopePyObject,
        *,
        visited: frozenset[int] | None = None,
    ) -> str:
        """Return a superclass name from Rope objects with uneven public APIs.

        Returns:
            A superclass name from Rope objects with uneven public APIs.

        """
        visited_ids = visited or frozenset()
        superclass_id = id(superclass)
        if superclass_id in visited_ids:
            return ""
        next_visited = visited_ids | {superclass_id}
        get_name = getattr(superclass, "get_name", None)
        if callable(get_name):
            name = get_name()
            if isinstance(name, str) and name:
                return name
        get_type = getattr(superclass, "get_type", None)
        if callable(get_type):
            superclass_type = get_type()
            if superclass_type is not None:
                type_name = FlextInfraUtilitiesRopeAnalysisImportState._superclass_name(
                    superclass_type,
                    visited=next_visited,
                )
                if type_name:
                    return type_name
        for attr_name in ("name", "_name"):
            name = getattr(superclass, attr_name, "")
            if isinstance(name, str) and name:
                return name
        return ""

    @staticmethod
    def _module_import_maps(
        *,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        current_package: str,
    ) -> t.Pair[MutableMapping[str, str], MutableMapping[str, str]]:
        """Return declared and semantic import maps for one module.

        Returns:
            Declared and semantic import maps for one module.

        """
        semantic_imports: MutableMapping[str, str] = {}
        declared_imports: MutableMapping[str, str] = {}
        module_imports = FlextInfraUtilitiesRopeCore.resolve_module_imports(
            rope_project,
            resource,
        )
        raw_imports = getattr(module_imports, "imports", ())
        import_stmts: t.VariadicTuple[t.Infra.RopeImportStatement] = tuple(raw_imports)
        for import_stmt in import_stmts:
            FlextInfraUtilitiesRopeAnalysisImportState._merge_import_statement(
                current_package=current_package,
                declared_imports=declared_imports,
                import_stmt=import_stmt,
                semantic_imports=semantic_imports,
            )
        return declared_imports, semantic_imports

    @staticmethod
    def _merge_import_statement(
        *,
        current_package: str,
        declared_imports: MutableMapping[str, str],
        import_stmt: t.Infra.RopeImportStatement,
        semantic_imports: MutableMapping[str, str],
    ) -> None:
        """Merge one Rope import statement into the import maps."""
        info = import_stmt.import_info
        module_name = getattr(info, "module_name", "") or ""
        resolved_module = (
            FlextInfraUtilitiesRopeAnalysisImportState._resolved_import_module(
                current_package=current_package,
                module_name=module_name,
                level=getattr(info, "level", 0) or 0,
            )
        )
        for alias_name, alias_as in info.names_and_aliases or ():
            FlextInfraUtilitiesRopeAnalysisImportState._merge_import_alias(
                alias_name=alias_name,
                alias_as=alias_as,
                declared_imports=declared_imports,
                resolved_module=resolved_module,
                semantic_imports=semantic_imports,
            )

    @staticmethod
    def _resolved_import_module(
        *,
        current_package: str,
        module_name: str,
        level: int,
    ) -> str:
        """Resolve from-imports, including bare dots; invalid levels propagate.

        Returns:
            The resulting ``str``.

        """
        return (
            FlextInfraUtilitiesRopeAnalysisImportState._resolve_import_module(
                current_package=current_package,
                module_name=module_name,
                level=level,
            )
            if module_name or level > 0
            else ""
        )

    @staticmethod
    def _merge_import_alias(
        *,
        alias_name: str,
        alias_as: str | None,
        declared_imports: MutableMapping[str, str],
        resolved_module: str,
        semantic_imports: MutableMapping[str, str],
    ) -> None:
        """Merge one import alias into declared and semantic maps."""
        if alias_name == "*":
            return
        if resolved_module:
            local_name = alias_as or alias_name
            target = f"{resolved_module}.{alias_name}"
        else:
            local_name = alias_as or alias_name.partition(".")[0]
            target = alias_name
        if not local_name:
            return
        declared_imports[local_name] = target
        semantic_imports[local_name] = target

    @staticmethod
    def find_definition_offset(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        symbol: str,
    ) -> int | None:
        """Return offset of symbol's definition via semantic analysis.

        Returns:
            Offset of symbol's definition via semantic analysis.

        """
        source = resource.read()
        pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(rope_project, resource)
        return (
            FlextInfraUtilitiesRopeAnalysisImportState._definition_offset_from_pymodule(
                pymodule=pymodule,
                source=source,
                symbol=symbol,
            )
        )

    @staticmethod
    def _definition_offset_from_pymodule(
        *,
        pymodule: t.Infra.RopePyModule,
        source: str,
        symbol: str,
    ) -> int | None:
        """Return identifier offset for one symbol from a resolved Rope module.

        Returns:
            Identifier offset for one symbol from a resolved Rope module.

        """
        attributes = pymodule.get_attributes()
        if symbol not in attributes:
            return None
        pyname = attributes[symbol]
        definition_module, definition_line = pyname.get_definition_location()
        if definition_module is not None:
            definition_resource = definition_module.get_resource()
            if definition_resource is not None:
                source = definition_resource.read()
        if definition_line is None:
            return None
        lines = source.splitlines(keepends=True)
        return FlextInfraUtilitiesRopeCore.find_identifier_offset_in_lines(
            lines,
            line=definition_line,
            symbol=symbol,
        )

    @staticmethod
    def resolve_semantic_module_imports(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
    ) -> t.StrMapping:
        """Return {local_name: fully_qualified_name} for all imports in a module.

        Returns:
            {local_name: fully_qualified_name} for all imports in a module.

        """
        imports: t.StrMapping = (
            FlextInfraUtilitiesRopeAnalysisImportState.resolve_module_semantic_state(
                rope_project,
                resource,
            ).semantic_imports
        )
        return imports

    @staticmethod
    def resolve_declared_module_imports(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
    ) -> t.StrMapping:
        """Return {local_name: declared import path} without resolving re-exports.

        Returns:
            {local_name: declared import path} without resolving re-exports.

        """
        module = FlextInfraUtilitiesRopeCore.resolve_pymodule(rope_project, resource)
        imports, _ = FlextInfraUtilitiesRopeAnalysisImportState._module_import_maps(
            rope_project=rope_project,
            resource=resource,
            current_package=FlextInfraUtilitiesRopeAnalysisImportState._package_name_for_module(
                module.get_name(),
                resource,
            ),
        )
        return imports

    @staticmethod
    def resolve_module_classes(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
    ) -> t.StrSequence:
        """Return names of all classes defined in a module.

        Returns:
            Names of all classes defined in a module.

        """
        return tuple(
            class_info.name
            for class_info in (
                FlextInfraUtilitiesRopeAnalysisImportState.resolve_module_semantic_state
            )(
                rope_project,
                resource,
            ).class_infos
        )

    @classmethod
    def declared_facade_owner(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
    ) -> t.StrPair | None:
        """Resolve declared or missing local aliases through actual inheritance.

        Returns:
            The resulting ``t.StrPair | None``.

        """
        return cls._facade_owner(rope_project, resource, infer_missing=True)

    @classmethod
    def published_facade_owner(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
    ) -> t.StrPair | None:
        """Return only an existing class alias suitable for publication.

        Returns:
            Only an existing class alias suitable for publication.

        """
        return cls._facade_owner(rope_project, resource, infer_missing=False)

    @classmethod
    def _facade_owner(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        *,
        infer_missing: bool,
    ) -> t.StrPair | None:
        """Resolve a published local class's alias from declarations and its MRO.

        The spelling of a module or class supplies no ownership information.
        An existing exported alias wins; otherwise the nearest declaring bases
        determine the missing declaration that the repair must publish locally.

        Returns:
            The resulting ``t.StrPair | None``.

        Raises:
            ValueError: If module has no declaration scope; or if ambiguous facade
                declaration in.

        """
        module = FlextInfraUtilitiesRopeCore.resolve_pymodule(rope_project, resource)
        exports = FlextInfraUtilitiesRopeAnalysisExports.public_export_names_source(
            resource.read(),
        )
        attributes = module.get_attributes()
        missing_aliases = frozenset(
            name
            for name in exports
            if name.islower() and not name.startswith("_") and name not in attributes
        )
        owners: set[t.Pair[str, str]] = set()
        scope = module.get_scope()
        if scope is None:
            msg = f"module has no declaration scope: {resource.path}"
            raise ValueError(msg)
        for child in scope.get_scopes():
            if child.get_kind() != "Class":
                continue
            target = child.pyobject
            name = target.get_name()
            binding = attributes.get(name)
            if name not in exports or binding is None:
                continue
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.local_name(
                binding,
                resource,
            ):
                continue
            if binding.get_object() is not target:
                continue
            # Rope can resolve an inherited class through its declaring module.
            # An alias owned by that module is not published by this resource.
            aliases = cls._declared_class_aliases(target) & frozenset(exports)
            if not aliases and infer_missing:
                aliases = missing_aliases or cls._inherited_class_aliases(
                    target,
                    visited=frozenset(),
                )
            owners.update((alias, name) for alias in aliases if alias in exports)
        if len(owners) > 1:
            message = (
                f"ambiguous facade declaration in {resource.path}: {sorted(owners)}"
            )
            raise ValueError(message)
        return next(iter(owners)) if owners else None

    @staticmethod
    def _declared_class_aliases(target: t.Infra.RopePyObject) -> frozenset[str]:
        """Return explicitly exported names bound to this exact class object.

        Returns:
            Explicitly exported names bound to this exact class object.

        """
        module = target.get_module()
        if module is None or (resource := module.get_resource()) is None:
            return frozenset()
        exports = FlextInfraUtilitiesRopeAnalysisExports.public_export_names_source(
            resource.read(),
        )
        return frozenset(
            name
            for name, binding in module.get_attributes().items()
            if name in exports
            and name != target.get_name()
            and name.islower()
            and not name.startswith("_")
            and FlextInfraUtilitiesRopeAnalysisAstHelpers.local_name(binding, resource)
            and binding.get_object() is target
        )

    @staticmethod
    def inherited_facade_namespaces(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        *,
        class_name: str,
    ) -> t.StrSequence:
        """Prove nested namespace inheritance by Rope scope and attribute identity.

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            ValueError: If cyclic facade namespace inheritance at.

        """
        module = FlextInfraUtilitiesRopeCore.resolve_pymodule(rope_project, resource)
        target = module.get_attribute(class_name).get_object()
        attributes = target.get_attributes()
        names: set[str] = set()
        pending = [
            (base, frozenset({id(target)})) for base in target.get_superclasses()
        ]
        while pending:
            base, ancestors = pending.pop()
            if id(base) in ancestors:
                message = f"cyclic facade namespace inheritance at {class_name}"
                raise ValueError(message)
            if (
                not FlextInfraUtilitiesRopeRuntime.abstract_class(base)
                or base.get_module() is None
            ):
                continue
            scope = base.get_scope()
            if scope is not None:
                for child in scope.get_scopes():
                    if child.get_kind() != "Class":
                        continue
                    nested = child.pyobject
                    name = nested.get_name()
                    binding = attributes.get(name)
                    if binding is not None and binding.get_object() is nested:
                        names.add(name)
            pending.extend(
                (parent, ancestors | {id(base)}) for parent in base.get_superclasses()
            )
        return tuple(sorted(names))

    @classmethod
    def _inherited_class_aliases(
        cls,
        target: t.Infra.RopePyObject,
        *,
        visited: frozenset[int],
    ) -> frozenset[str]:
        """Follow real base identities, stopping at each nearest declaration.

        Returns:
            The resulting ``frozenset[str]``.

        Raises:
            ValueError: If cyclic facade inheritance at.

        """
        identity = id(target)
        if identity in visited:
            message = f"cyclic facade inheritance at {target.get_name()}"
            raise ValueError(message)
        aliases: set[str] = set()
        for base in target.get_superclasses():
            if not FlextInfraUtilitiesRopeRuntime.abstract_class(base):
                continue
            declared = cls._declared_class_aliases(base)
            aliases.update(
                declared
                or cls._inherited_class_aliases(base, visited=visited | {identity}),
            )
        return frozenset(aliases)

    @staticmethod
    def resolve_class_info(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
    ) -> t.SequenceOf[m.Infra.ClassInfo]:
        """Return ClassInfo (name, line, bases) for all classes in a module.

        Returns:
            ClassInfo (name, line, bases) for all classes in a module.

        """
        class_infos: t.SequenceOf[m.Infra.ClassInfo] = (
            FlextInfraUtilitiesRopeAnalysisImportState.resolve_module_semantic_state(
                rope_project,
                resource,
            ).class_infos
        )
        return class_infos

    @staticmethod
    def resolve_class_bases(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        class_name: str,
    ) -> t.StrSequence:
        """Return base class names for a given class in a module.

        Returns:
            Base class names for a given class in a module.

        """
        for info in FlextInfraUtilitiesRopeAnalysisImportState.resolve_class_info(
            rope_project,
            resource,
        ):
            if info.name == class_name:
                return list(info.bases)
        return ()

    @staticmethod
    def resolve_class_methods(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        class_name: str,
        *,
        include_private: bool = False,
    ) -> t.StrMapping:
        """Return {method_name: kind} for methods of a class.

        Returns:
            {method_name: kind} for methods of a class.

        """
        pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(rope_project, resource)
        return FlextInfraUtilitiesRopeAnalysisImportState._class_methods_from_pymodule(
            class_name=class_name,
            include_private=include_private,
            pymodule=pymodule,
        )

    @staticmethod
    def _class_methods_from_pymodule(
        *,
        class_name: str,
        include_private: bool,
        pymodule: t.Infra.RopePyModule,
    ) -> t.StrMapping:
        """Return method symbols for a class from one resolved Rope module.

        Returns:
            Method symbols for a class from one resolved Rope module.

        """
        result: t.MutableStrMapping = {}
        attributes = pymodule.get_attributes()
        if class_name not in attributes:
            return result
        obj = attributes[class_name].get_object()
        if not FlextInfraUtilitiesRopeRuntime.abstract_class(obj):
            return result
        for name, pyname in obj.get_attributes().items():
            if not include_private and name.startswith("_"):
                continue
            child = pyname.get_object()
            if not FlextInfraUtilitiesRopeRuntime.py_function(child):
                continue
            result[name] = child.get_kind()
        return result

    @staticmethod
    def _open_pymodule(
        project_root: Path,
        file_path: Path,
    ) -> t.Pair[t.Infra.RopePyModule, t.Infra.RopeProject] | None:
        """Open a rope project and resolve ``file_path`` to a ``PyModule``.

        Returns:
            The resulting ``t.Pair[t.Infra.RopePyModule, t.Infra.RopeProject] | None``.

        """
        rope_project = FlextInfraUtilitiesRopeCore.init_rope_project(project_root)
        resource = FlextInfraUtilitiesRopeCore.fetch_python_resource(
            rope_project,
            file_path,
        )
        if resource is None:
            rope_project.close()
            return None
        pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(rope_project, resource)
        return pymodule, rope_project

    @classmethod
    def module_has_docstring(cls, project_root: Path, file_path: Path) -> bool:
        """Return whether ``file_path``'s module carries a docstring (rope).

        Returns:
            Whether ``file_path``'s module carries a docstring (rope).

        """
        opened = cls._open_pymodule(project_root, file_path)
        if opened is None:
            return False
        pymodule, rope_project = opened
        try:
            return bool(pymodule.get_doc())
        finally:
            rope_project.close()

    @classmethod
    def symbol_has_docstring(
        cls,
        project_root: Path,
        file_path: Path,
        symbol_name: str,
    ) -> bool:
        """Return whether ``symbol_name`` carries a docstring via rope.

        Returns:
            Whether ``symbol_name`` carries a docstring via rope.

        """
        opened = cls._open_pymodule(project_root, file_path)
        if opened is None:
            return False
        pymodule, rope_project = opened
        try:
            pyname = pymodule.get_attributes().get(symbol_name)
            if pyname is None:
                return False
            return bool(pyname.get_object().get_doc())
        finally:
            rope_project.close()

    @classmethod
    def export_target_modules(
        cls,
        project_root: Path,
        file_path: Path,
        package_name: str,
        exports: t.StrSequence,
    ) -> MutableMapping[str, str]:
        """Map exports → defining module via rope's import table.

        Returns:
            The resulting ``MutableMapping[str, str]``.

        """
        export_names = {name for name in exports if name}
        target_map: MutableMapping[str, str] = dict.fromkeys(export_names, package_name)
        opened = cls._open_pymodule(project_root, file_path)
        if opened is None:
            return target_map
        pymodule, rope_project = opened
        try:
            resource = pymodule.get_resource()
            if resource is None:
                return target_map
            declared = cls.resolve_declared_module_imports(rope_project, resource)
            for local_name, declared_path in declared.items():
                if local_name not in export_names:
                    continue
                module_name = (
                    declared_path.rsplit(".", maxsplit=1)[0]
                    if "." in declared_path
                    else declared_path
                )
                if module_name:
                    target_map[local_name] = module_name
        finally:
            rope_project.close()
        return target_map
