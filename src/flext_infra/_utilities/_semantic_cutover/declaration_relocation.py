"""Immutable, identity-bound relocation of nested payload declarations.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import builtins
from pathlib import Path

import libcst as cst

from flext_core import r
from flext_infra import c, m, p, t
from flext_infra._utilities import (
    FlextInfraUtilitiesCodegenNamespace,
    FlextInfraUtilitiesRopeRuntimeModules,
    FlextInfraUtilitiesRopeRuntimeRefactors,
    FlextInfraUtilitiesRopeRuntimeTypes,
    FlextInfraUtilitiesRopeSourceBases,
    FlextInfraUtilitiesSemanticCutoverNestingCst,
    FlextInfraUtilitiesSemanticNestingTypes,
)
from flext_infra._utilities._semantic_cutover.declaration_payload import (
    FlextInfraUtilitiesDeclarationPayload,
)
from flext_infra._utilities.codemod_project import FlextInfraUtilitiesCodemodProject


class FlextInfraUtilitiesSemanticDeclarationRelocation(
    FlextInfraUtilitiesDeclarationPayload,
    FlextInfraUtilitiesSemanticNestingTypes,
    FlextInfraUtilitiesSemanticCutoverNestingCst,
):
    """Move declarations only into an existing, uniquely composed model owner."""

    @classmethod
    def _plan_declaration_relocation(
        cls,
        workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        project = runtime.snapshot_project(workspace.rope_project, sources)
        working = dict(sources)
        try:
            for path in sorted(sources):
                if sources[path].startswith(c.Infra.AUTOGEN_HEADERS):
                    continue
                policy = workspace.convention(path).module_policy
                family = FlextInfraUtilitiesCodegenNamespace.facade_family_of_directory(
                    path.parent.name,
                )
                # Tests and config/settings are not production declaration owners.
                if family is None or family == "m" or "tests" in path.parts:
                    continue
                while True:
                    candidates = tuple(
                        (outer, node, binding)
                        for outer in ast.parse(working[path]).body
                        if isinstance(outer, ast.ClassDef)
                        for node in outer.body
                        if isinstance(node, ast.ClassDef)
                        if (binding := cls.payload_declaration(project, path, node))
                        is not None
                    )
                    if not candidates:
                        break
                    outer, node, binding = candidates[0]
                    if policy.expected_family != outer.name:
                        return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].fail(
                            "declaration-relocation: unresolved source owner "
                            f"{path}:{outer.name}",
                        )
                    target, owner, exposure = cls._declaration_target(
                        workspace,
                        project,
                        working,
                        path,
                    )
                    working = cls._relocate_payload(
                        project,
                        working,
                        (path, node, binding),
                        (target, owner, exposure),
                    )
                    # Subsequent candidates bind to the proposed graph and coordinates.
                    project.close()
                    project = runtime.snapshot_project(workspace.rope_project, working)
            cls._preflight_declaration_graph(workspace, sources, working)
            return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].ok(
                tuple(
                    m.Infra.SemanticMigrationEdit(
                        file_path=path,
                        original_source=source,
                        updated_source=working[path],
                        changes=("relocated bound payload declaration",),
                    )
                    for path, source in sources.items()
                    if source != working[path]
                ),
            )
        finally:
            project.close()

    @classmethod
    def _declaration_target(
        cls,
        workspace: p.Infra.RopeWorkspaceDsl,
        project: p.Infra.RopeProject,
        sources: t.MappingKV[Path, str],
        origin: Path,
    ) -> t.Triple[Path, str, str]:
        root = Path(project.root.real_path)
        packages = tuple(
            parent
            for parent in origin.parents
            if (parent / c.Infra.MODELS_PY) in sources
        )
        if len(packages) != 1:
            msg = f"declaration-relocation: unresolved model facade for {origin}"
            raise ValueError(msg)
        package = packages[0]
        routes = cls._public_model_routes(project, package)
        targets: list[t.Triple[Path, str, str]] = []
        for path, source in sources.items():
            if path.parent.parent != package or source.startswith(
                c.Infra.AUTOGEN_HEADERS,
            ):
                continue
            family = FlextInfraUtilitiesCodegenNamespace.facade_family_of_directory(
                path.parent.name,
            )
            if family is None or family != "m":
                continue
            owner = workspace.convention(path).module_policy.expected_family
            module = project.get_pymodule(
                project.get_resource(path.relative_to(root).as_posix()),
            )
            if owner is None or owner not in module.get_attributes():
                continue
            value = module.get_attribute(owner).get_object()
            for composed, route in routes:
                if value in cls._class_ancestry(composed):
                    targets.append((path, owner, route))
        if len(targets) != 1:
            msg = (
                "declaration-relocation: expected one authored composed model "
                f"owner for {origin}; found {targets}"
            )
            raise ValueError(msg)
        return targets[0]

    @staticmethod
    def _public_model_routes(
        project: p.Infra.RopeProject,
        package: Path,
    ) -> t.SequenceOf[t.Pair[p.Infra.RopePyObject, str]]:
        root = Path(project.root.real_path)
        facade = project.get_pymodule(
            project.get_resource(
                (package / c.Infra.MODELS_PY).relative_to(root).as_posix(),
            ),
        )
        initializer = package / c.Infra.INIT_PY
        resource = project.get_resource(initializer.relative_to(root).as_posix())
        exports = FlextInfraUtilitiesRopeSourceBases.lazy_module_aliases(
            project.get_pymodule(resource).get_name(),
            initializer,
            FlextInfraUtilitiesRopeRuntimeTypes.require_file_resource(
                resource,
                initializer,
            ).read(),
        )
        if exports.get("m") != facade.get_name():
            msg = (
                "declaration-relocation: unresolved public lazy model export "
                f"for {package}"
            )
            raise ValueError(msg)
        public = facade.get_attribute("m").get_object()
        routes: list[t.Pair[p.Infra.RopePyObject, str]] = [(public, "m")]
        scope = public.get_scope()
        if scope is not None:
            routes.extend(
                (child.pyobject, f"m.{child.pyobject.get_name()}")
                for child in scope.get_scopes()
                if child.get_kind() == "Class"
            )
        return routes

    @classmethod
    def _relocate_payload(
        cls,
        project: p.Infra.RopeProject,
        sources: t.MappingKV[Path, str],
        declaration: t.Triple[Path, ast.ClassDef, p.Infra.RopePyName],
        destination: t.Triple[Path, str, str],
    ) -> dict[Path, str]:
        origin, node, _binding = declaration
        target, _owner, exposure = destination
        root = Path(project.root.real_path)
        facade = (
            project
            .get_pymodule(
                project.get_resource(
                    (target.parent.parent / c.Infra.MODELS_PY)
                    .relative_to(root)
                    .as_posix(),
                ),
            )
            .get_attribute("m")
            .get_object()
        )
        for segment in exposure.split(".")[1:]:
            facade = facade.get_attribute(segment).get_object()
        if node.name in facade.get_attributes():
            msg = (
                "declaration-relocation: occupied public destination "
                f"{exposure}.{node.name}"
            )
            raise ValueError(msg)
        updated = dict(sources)
        for path, source in sources.items():
            resource = project.get_resource(path.relative_to(root).as_posix())
            rewrites = cls._payload_reference_rewrites(
                project,
                resource,
                source,
                declaration,
                f"{exposure}.{node.name}",
            )
            executable = FlextInfraUtilitiesRopeRuntimeRefactors.content_change(
                resource,
                source,
                rewrites,
            ).new_contents
            updated[path] = cls._import_payload_facade(
                project,
                resource,
                (source, executable),
                target,
            )
        cls._transfer_payload(
            updated,
            declaration,
            destination,
            cls._payload_imports(project, origin, target, node),
        )
        return updated

    @classmethod
    def _payload_reference_rewrites(
        cls,
        project: p.Infra.RopeProject,
        resource: p.Infra.RopeResource,
        source: str,
        declaration: t.Triple[Path, ast.ClassDef, p.Infra.RopePyName],
        expression: str,
    ) -> t.VariadicTuple[m.Infra.SourceRewrite]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        module = project.get_pymodule(resource)
        changes: list[m.Infra.SourceRewrite] = []
        finder = FlextInfraUtilitiesRopeRuntimeRefactors.create_occurrence_finder(
            project,
            declaration[1].name,
            declaration[2],
            imports=True,
            in_hierarchy=False,
        )
        protected = (
            declaration[1].lineno,
            declaration[1].end_lineno or declaration[1].lineno,
        )
        for occurrence in finder.find_occurrences(resource=resource):
            if occurrence.is_defined():
                continue
            if (
                Path(resource.real_path) == declaration[0]
                and protected[0] <= occurrence.lineno <= protected[1]
            ):
                msg = "declaration-relocation: self-dependent payload"
                raise ValueError(msg)
            start, end = FlextInfraUtilitiesRopeRuntimeRefactors.word_primary_range(
                source,
                occurrence.offset,
            )
            changes.append(
                m.Infra.SourceRewrite(
                    start=start,
                    end=end,
                    text=cls._checked_type_reference(
                        runtime.scope_at(module, start),
                        expression,
                    ),
                ),
            )

        def replacement(scope: p.Infra.RopeScope, item: ast.expr) -> str | None:
            return (
                cls._checked_type_reference(scope, expression)
                if runtime.same_name(
                    declaration[2],
                    runtime.resolve_symbol(scope, item),
                )
                else None
            )

        changes.extend(
            cls._quoted_type_rewrites(
                project,
                resource,
                source,
                replacement,
                protected=protected
                if Path(resource.real_path) == declaration[0]
                else None,
            ),
        )
        return tuple(changes)

    @staticmethod
    def _import_payload_facade(
        project: p.Infra.RopeProject,
        resource: p.Infra.RopeResource,
        content: t.Pair[str, str],
        target: Path,
    ) -> str:
        if content[0] == content[1]:
            return content[0]
        if content[0].startswith(c.Infra.AUTOGEN_HEADERS):
            msg = f"declaration-relocation: generated consumer {resource.path}"
            raise ValueError(msg)
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        scope = project.get_pymodule(resource).get_scope()
        existing = scope.get_names().get("m") if scope is not None else None
        expected = project.get_pymodule(
            project.get_resource(
                (target.parent.parent / c.Infra.MODELS_PY)
                .relative_to(Path(project.root.real_path))
                .as_posix(),
            ),
        ).get_attribute("m")
        if existing is not None and not runtime.same_name(expected, existing):
            msg = (
                f"declaration-relocation: conflicting model binding in {resource.path}"
            )
            raise ValueError(msg)
        imports = runtime.module_imports_for_pymodule(
            project,
            runtime.build_string_module(project, content[1], resource=resource),
        )
        imports.add_import(
            runtime.from_import(target.parent.parent.name, 0, (("m", None),)),
        )
        return imports.get_changed_source()

    @classmethod
    def _transfer_payload(
        cls,
        updated: t.MutableMappingKV[Path, str],
        declaration: t.Triple[Path, ast.ClassDef, p.Infra.RopePyName],
        target: t.Triple[Path, str, str],
        imports: t.VariadicTuple[cst.BaseStatement],
    ) -> None:
        origin, node, _binding = declaration
        moved = cst.parse_module(updated[origin])
        outer = next(
            item
            for item in moved.body
            if isinstance(item, cst.ClassDef)
            and isinstance(item.body, cst.IndentedBlock)
            and any(
                isinstance(child, cst.ClassDef) and child.name.value == node.name
                for child in item.body.body
            )
        )
        payload = next(
            child
            for child in outer.body.body
            if isinstance(child, cst.ClassDef) and child.name.value == node.name
        )
        kept = tuple(child for child in outer.body.body if child is not payload)
        updated[origin] = moved.with_changes(
            body=tuple(
                item.with_changes(
                    body=outer.body.with_changes(
                        body=kept or (cst.SimpleStatementLine(body=(cst.Pass(),)),),
                    ),
                )
                if item is outer
                else item
                for item in moved.body
            ),
        ).code
        destination = cst.parse_module(updated[target[0]])
        target_owner = next(
            item
            for item in destination.body
            if isinstance(item, cst.ClassDef) and item.name.value == target[1]
        )
        holder = cls._owner_holding(target_owner, (payload,))
        insertion = destination.body.index(target_owner)
        updated[target[0]] = destination.with_changes(
            body=(
                *destination.body[:insertion],
                *imports,
                holder,
                *destination.body[insertion + 1 :],
            ),
        ).code

    @classmethod
    def _payload_imports(
        cls,
        project: p.Infra.RopeProject,
        origin: Path,
        target: Path,
        node: ast.ClassDef,
    ) -> t.VariadicTuple[cst.BaseStatement]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        root = Path(project.root.real_path)
        source = FlextInfraUtilitiesRopeRuntimeTypes.require_file_resource(
            project.get_resource(origin.relative_to(root).as_posix()),
            origin,
        ).read()
        target_resource = project.get_resource(target.relative_to(root).as_posix())
        destination = project.get_pymodule(target_resource).get_scope()
        imports: dict[str, ast.Import | ast.ImportFrom] = {}
        for statement in ast.parse(source).body:
            if isinstance(statement, ast.Import | ast.ImportFrom):
                for alias in statement.names:
                    imports[alias.asname or alias.name.split(".")[0]] = statement
        required: list[cst.BaseStatement] = []
        module = project.get_pymodule(
            project.get_resource(origin.relative_to(root).as_posix()),
        )
        scope = module.get_scope()
        if scope is None or destination is None:
            msg = (
                f"declaration-relocation: missing module scope for {origin} or {target}"
            )
            raise ValueError(msg)
        for name in sorted(cls._payload_loaded_names(project, module, node, source)):
            if hasattr(builtins, name) and name not in scope.get_defined_names():
                continue
            statement = imports.get(name)
            if statement is None or (
                isinstance(statement, ast.ImportFrom) and statement.level
            ):
                msg = (
                    "declaration-relocation: unresolved/outer dependency "
                    f"{origin}:{node.name} -> {name}"
                )
                raise ValueError(msg)
            existing = destination.get_names().get(name)
            original = scope.get_names().get(name)
            if existing is not None and (
                original is None or not runtime.same_name(original, existing)
            ):
                msg = f"declaration-relocation: conflicting dependency {target}:{name}"
                raise ValueError(msg)
            if existing is None:
                aliases = [
                    alias
                    for alias in statement.names
                    if (alias.asname or alias.name.split(".")[0]) == name
                ]
                imported = (
                    ast.Import(names=aliases)
                    if isinstance(statement, ast.Import)
                    else ast.ImportFrom(module=statement.module, names=aliases, level=0)
                )
                required.append(cst.parse_statement(ast.unparse(imported) + "\n"))
        return tuple(required)

    @classmethod
    def _payload_loaded_names(
        cls,
        project: p.Infra.RopeProject,
        module: p.Infra.RopePyModule,
        node: ast.ClassDef,
        source: str,
    ) -> set[str]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        bound = {
            parameter.name
            for parameter in node.type_params
            if isinstance(parameter, ast.TypeVar | ast.ParamSpec | ast.TypeVarTuple)
        } | {
            statement.target.id
            for statement in node.body
            if isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
        }
        methods = tuple(
            statement
            for statement in node.body
            if isinstance(statement, ast.FunctionDef)
        )
        method_nodes = {item for method in methods for item in ast.walk(method)}
        loaded = {
            item.id
            for item in ast.walk(node)
            if item not in method_nodes
            and isinstance(item, ast.Name)
            and isinstance(item.ctx, ast.Load)
        } - bound
        for method in methods:
            loaded.update(cls._method_loaded_names(method))

        def quoted_names(annotation: ast.expr, lexical: p.Infra.RopeScope) -> set[str]:
            found: set[str] = set()
            for item in cls._type_nodes(annotation, project, lexical):
                if isinstance(item, ast.Name):
                    found.add(item.id)
                elif isinstance(item, ast.Constant) and isinstance(item.value, str):
                    found.update(
                        quoted_names(ast.parse(item.value, mode="eval").body, lexical),
                    )
            return found

        for annotation, declaration_line in cls._annotation_roots(
            ast.Module(body=[node], type_ignores=[]),
        ):
            lexical = runtime.scope_at(
                module,
                runtime.source_offset(source, annotation),
                declaration_line=declaration_line,
            )
            loaded.update(quoted_names(annotation, lexical) - bound)
        return loaded

    @staticmethod
    def _method_loaded_names(method: ast.FunctionDef) -> set[str]:
        if any(
            item is not method
            and isinstance(
                item,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Lambda,
                    ast.ListComp,
                    ast.SetComp,
                    ast.DictComp,
                    ast.GeneratorExp,
                ),
            )
            for item in ast.walk(method)
        ):
            msg = "declaration-relocation: unproven nested validator scope"
            raise ValueError(msg)
        arguments = (
            *method.args.posonlyargs,
            *method.args.args,
            *method.args.kwonlyargs,
            method.args.vararg,
            method.args.kwarg,
        )
        locals_ = {argument.arg for argument in arguments if argument is not None} | {
            item.id
            for item in ast.walk(method)
            if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)
        }
        return {
            item.id
            for item in ast.walk(method)
            if isinstance(item, ast.Name)
            and isinstance(item.ctx, ast.Load)
            and item.id not in locals_
        }

    @staticmethod
    def _preflight_declaration_graph(
        workspace: p.Infra.RopeWorkspaceDsl,
        original: t.MappingKV[Path, str],
        proposed: t.MappingKV[Path, str],
    ) -> None:
        """Reject new runtime cycles in the proposed immutable import graph.

        Raises:
            ValueError: If declaration-relocation.
        """
        before = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(
            workspace.rope_project,
            original,
        )
        after = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(
            workspace.rope_project,
            proposed,
        )
        try:
            old, _ = FlextInfraUtilitiesCodemodProject.snapshot_import_graph(before)
            new, _ = FlextInfraUtilitiesCodemodProject.snapshot_import_graph(after)
            cycles = FlextInfraUtilitiesCodemodProject.project_import_cycles(new)
            baseline = FlextInfraUtilitiesCodemodProject.project_import_cycles(old)
            introduced = {
                name: members
                for name, members in cycles.items()
                if baseline.get(name) != members
            }
            if introduced:
                edges = {
                    name: sorted(new[name] & members)
                    for name, members in introduced.items()
                }
                msg = (
                    "declaration-relocation: proposed runtime import cycle; "
                    f"nothing published: {edges}"
                )
                raise ValueError(msg)
        finally:
            before.close()
            after.close()


__all__: list[str] = ["FlextInfraUtilitiesSemanticDeclarationRelocation"]
