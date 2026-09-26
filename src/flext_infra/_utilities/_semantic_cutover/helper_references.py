"""Keep original type bindings alive through Rope's immutable class move."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from flext_infra import m, p, t

from ..rope_class_move import FlextInfraUtilitiesRopeClassMove
from ..rope_runtime_modules import FlextInfraUtilitiesRopeRuntimeModules
from .nesting_types import FlextInfraUtilitiesSemanticNestingTypes


class FlextInfraUtilitiesSemanticHelperReferences(
    FlextInfraUtilitiesSemanticNestingTypes
):
    """Plan quoted references while the declaration still has its original identity."""

    @classmethod
    def _helper_move_plan(
        cls, request: m.Infra.ClassMoveRequest, *, sources: t.MappingKV[Path, str]
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        project = request.rope_project
        root = Path(project.root.real_path)
        origin = project.get_pymodule(
            project.get_resource(request.source_file.relative_to(root).as_posix())
        )
        expected = origin.get_attribute(request.class_name)
        target = project.get_pymodule(
            project.get_resource(request.target_file.relative_to(root).as_posix())
        )
        declaration = next(
            node
            for node in ast.parse(sources[request.source_file]).body
            if isinstance(node, ast.ClassDef) and node.name == request.class_name
        )
        if declaration.end_lineno is None:
            msg = "shared helper declaration has no complete source range"
            raise ValueError(msg)
        prepared = dict(sources)
        quoted_imports: dict[Path, str] = {}
        for path, source in sources.items():
            resource = project.get_resource(path.relative_to(root).as_posix())
            module = project.get_pymodule(resource)
            updated, expression = cls._moved_quoted_source(
                request,
                resource,
                source,
                expected,
                target.get_name(),
                protected=(declaration.lineno, declaration.end_lineno)
                if path == request.source_file
                else None,
            )
            if expression is not None and path != request.target_file:
                changed = runtime.get_string_module(project, updated, resource=resource)
                updated, binding = runtime.import_binding(
                    project, changed, target.get_name(), request.class_name
                )
                if binding != expression:
                    msg = f"quoted helper import changed its elected binding: {path}"
                    raise ValueError(msg)
                quoted_imports[path] = expression
            prepared[path] = cls._original_helper_imports(
                project,
                resource,
                updated,
                module,
                expected,
                origin.get_name(),
                request.class_name,
            )
        cls._move_prepared_helper(request, prepared, quoted_imports, target.get_name())
        return tuple(
            m.Infra.SemanticMigrationEdit(
                file_path=path,
                original_source=source,
                updated_source=prepared[path],
                changes=(f"Rope moved {request.class_name} and its bound references",),
            )
            for path, source in sources.items()
            if source != prepared[path]
        )

    @staticmethod
    def _move_prepared_helper(
        request: m.Infra.ClassMoveRequest,
        prepared: t.MutableMappingKV[Path, str],
        quoted_imports: t.MappingKV[Path, str],
        target: str,
    ) -> None:
        """Move the declaration in a closed snapshot and retain quoted imports."""
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        root = Path(request.rope_project.root.real_path)
        snapshot = runtime.snapshot_project(request.rope_project, prepared)
        try:
            line = next(
                node.lineno
                for node in ast.parse(prepared[request.source_file]).body
                if isinstance(node, ast.ClassDef) and node.name == request.class_name
            )
            moved = FlextInfraUtilitiesRopeClassMove.plan_class_move(
                m.Infra.ClassMoveRequest(
                    rope_project=snapshot,
                    source_file=request.source_file,
                    target_file=request.target_file,
                    class_name=request.class_name,
                    line=line,
                    apply=False,
                ),
                sources=prepared,
            )
            for edit in moved:
                prepared[edit.file_path] = edit.updated_source
            target_resource = snapshot.get_resource(
                request.target_file.relative_to(root).as_posix()
            )
            prepared[request.target_file] = (
                FlextInfraUtilitiesSemanticHelperReferences._without_self_bindings(
                    snapshot, target_resource, prepared[request.target_file]
                )
            )
            for path, expression in quoted_imports.items():
                resource = snapshot.get_resource(path.relative_to(root).as_posix())
                module = runtime.get_string_module(
                    snapshot, prepared[path], resource=resource
                )
                prepared[path], binding = runtime.import_binding(
                    snapshot, module, target, request.class_name
                )
                if binding != expression:
                    msg = f"moved helper import changed its quoted binding: {path}"
                    raise ValueError(msg)
            FlextInfraUtilitiesSemanticHelperReferences._rebind_origin_imports(
                request, snapshot, prepared, quoted_imports, target
            )
        finally:
            snapshot.close()

    @staticmethod
    def _rebind_origin_imports(
        request: m.Infra.ClassMoveRequest,
        snapshot: p.Infra.RopeProject,
        prepared: t.MutableMappingKV[Path, str],
        quoted_imports: t.MappingKV[Path, str],
        target: str,
    ) -> None:
        """Point surviving origin imports at the moved declaration.

        Rope's move rewrites the references it can see, but a consumer binding
        of the form ``from origin import name as alias`` survives the nested
        move and dies the moment the origin module publishes without the
        declaration. Every surviving binding is re-bound to the elected
        destination expression; a consumer without a quoted reference takes the
        lazy ``from target import name`` form the materialized alias serves.
        """
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        root = Path(snapshot.root.real_path)
        origin = (
            request.source_file
            .relative_to(root)
            .with_suffix("")
            .as_posix()
            .replace("/", ".")
        )
        pattern = re.compile(
            rf"^from {re.escape(origin)} import {request.class_name}(?: as (\w+))?$",
            re.MULTILINE,
        )
        for path, source in prepared.items():
            if not pattern.search(source):
                continue
            expression = quoted_imports.get(path)
            if expression is None:
                resource = snapshot.get_resource(path.relative_to(root).as_posix())
                module = runtime.get_string_module(snapshot, source, resource=resource)
                _, expression = runtime.import_binding(
                    snapshot, module, target, request.class_name
                )

            def _rebind(match: re.Match[str], expression: str = expression) -> str:
                alias = match.group(1)
                if alias is not None:
                    return f"{alias} = {expression}"
                return f"from {target} import {request.class_name}"

            prepared[path] = pattern.sub(_rebind, source)

    @staticmethod
    def _without_self_bindings(
        project: p.Infra.RopeProject, resource: p.Infra.RopeResource, source: str
    ) -> str:
        """Drop imports a destination owner already declares for itself.

        MoveGlobal carries the helper's own imports into the destination. When
        the destination is the owner of an imported name (the tier utilities
        module binding ``u``), that import re-enters the module being defined
        and cycles at runtime; the destination's own declaration is the binding
        its moved code resolves.
        """
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        body = ast.parse(source).body
        declared = {
            target.id
            for node in body
            for target in (
                node.targets
                if isinstance(node, ast.Assign)
                else (node.target,)
                if isinstance(node, ast.AnnAssign)
                else ()
            )
            if isinstance(target, ast.Name)
        } | {
            node.name
            for node in body
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        }
        module = runtime.get_string_module(project, source, resource=resource)
        imports = runtime.module_imports_for_pymodule(project, module)
        changed = False
        for statement in tuple(imports.imports):
            info = statement.import_info
            if not isinstance(info, p.Infra.RopeFromImport):
                continue
            kept = [
                (imported, alias)
                for imported, alias in info.names_and_aliases
                if (alias or imported) not in declared
            ]
            if len(kept) != len(info.names_and_aliases):
                statement.import_info = runtime.from_import(
                    info.module_name, info.level, kept
                )
                changed = True
        return imports.get_changed_source() if changed else source

    @classmethod
    def _moved_quoted_source(
        cls,
        request: m.Infra.ClassMoveRequest,
        resource: p.Infra.RopeResource,
        source: str,
        expected: p.Infra.RopePyName,
        target: str,
        *,
        protected: t.Pair[int, int] | None,
    ) -> t.Pair[str, str | None]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        project = request.rope_project
        module = project.get_pymodule(resource)
        expression: str | None = None

        def replacement(scope: p.Infra.RopeScope, node: ast.expr) -> str | None:
            nonlocal expression
            if not runtime.same_name(expected, runtime.resolve_symbol(scope, node)):
                return None
            if expression is None:
                if Path(resource.real_path) == request.target_file:
                    expression = request.class_name
                else:
                    _, expression = runtime.import_binding(
                        project, module, target, request.class_name
                    )
            return cls._checked_type_reference(scope, expression)

        updated = cls._rewrite_quoted_types(
            project, resource, source, replacement, protected=protected
        )
        return (updated, expression)

    @classmethod
    def _original_helper_imports(
        cls,
        project: p.Infra.RopeProject,
        resource: p.Infra.RopeResource,
        source: str,
        original: p.Infra.RopePyModule,
        expected: p.Infra.RopePyName,
        origin: str,
        name: str,
    ) -> str:
        """Resolve reexports to the original declaration before MoveGlobal cuts it."""
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        module = runtime.get_string_module(project, source, resource=resource)
        imports = runtime.module_imports_for_pymodule(project, module)
        scope = original.get_scope()
        if scope is None:
            msg = f"shared helper consumer has no Rope scope: {resource.path}"
            raise ValueError(msg)
        names = scope.get_names()
        moved: list[t.Pair[str, str | None]] = []
        for statement in tuple(imports.imports):
            info = statement.import_info
            if not isinstance(info, p.Infra.RopeFromImport) or (
                info.module_name == origin and info.level == 0
            ):
                continue
            kept, matched = cls._partition_helper_import(info, names, expected, name)
            moved.extend(matched)
            if len(kept) != len(info.names_and_aliases):
                statement.import_info = runtime.from_import(
                    info.module_name, info.level, kept
                )
        if not moved:
            return source
        imports.add_import(runtime.from_import(origin, 0, moved))
        return imports.get_changed_source()

    @staticmethod
    def _partition_helper_import(
        info: p.Infra.RopeFromImport,
        names: t.MappingKV[str, p.Infra.RopePyName],
        expected: p.Infra.RopePyName,
        name: str,
    ) -> t.Pair[
        t.SequenceOf[t.Pair[str, str | None]], t.SequenceOf[t.Pair[str, str | None]]
    ]:
        """Separate imports of this declaration from unrelated bindings."""
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        kept: list[t.Pair[str, str | None]] = []
        moved: list[t.Pair[str, str | None]] = []
        for imported, alias in info.names_and_aliases:
            binding = names.get(alias or imported)
            if (
                isinstance(binding, p.Infra.RopeImportedName)
                and binding.imported_module.module_name == info.module_name
                and binding.imported_module.level == info.level
                and runtime.same_name(expected, binding)
            ):
                local = alias or imported
                moved.append((name, local if local != name else None))
            else:
                kept.append((imported, alias))
        return (kept, moved)


__all__: list[str] = ["FlextInfraUtilitiesSemanticHelperReferences"]
