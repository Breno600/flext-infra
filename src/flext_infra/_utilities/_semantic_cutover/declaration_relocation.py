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
    FlextInfraUtilitiesSemanticCutoverNestingCst,
    FlextInfraUtilitiesSemanticNestingTypes,
)
from flext_infra._utilities.codemod_project import FlextInfraUtilitiesCodemodProject
from flext_infra._utilities._semantic_cutover.declaration_payload import (
    FlextInfraUtilitiesDeclarationPayload,
)


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
            for path, source in sorted(sources.items()):
                if source.startswith(c.Infra.AUTOGEN_HEADERS):
                    continue
                policy = workspace.convention(path).module_policy
                family = FlextInfraUtilitiesCodegenNamespace.facade_family_of_directory(path.parent.name)
                # Tests and config/settings are not production declaration owners.
                if family is None or family == "m" or "tests" in path.parts:
                    continue
                for outer in ast.parse(source).body:
                    if not isinstance(outer, ast.ClassDef):
                        continue
                    for node in outer.body:
                        if not isinstance(node, ast.ClassDef):
                            continue
                        binding = cls.payload_declaration(project, path, node)
                        if binding is None:
                            continue
                        if policy.expected_family != outer.name:
                            return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].fail(
                                f"declaration-relocation: unresolved source owner {path}:{outer.name}",
                            )
                        target, owner, exposure = cls._declaration_target(workspace, project, sources, path)
                        working = cls._relocate_payload(project, working, path, node, binding,
                                                        target, owner, exposure)
                        # Subsequent candidates must bind to the proposed graph.
                        project.close()
                        project = runtime.snapshot_project(workspace.rope_project, working)
            cls._preflight_declaration_graph(workspace, sources, working)
            return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].ok(tuple(
                m.Infra.SemanticMigrationEdit(file_path=path, original_source=source,
                    updated_source=working[path], changes=("relocated bound payload declaration",))
                for path, source in sources.items() if source != working[path]
            ))
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
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        root = Path(project.root.real_path)
        package = next(parent for parent in origin.parents if (parent / "models.py") in sources)
        facade = project.get_pymodule(project.get_resource((package / "models.py").relative_to(root).as_posix()))
        public = facade.get_attribute("m").get_object()
        routes: list[t.Pair[p.Infra.RopePyObject, str]] = [(public, "m")]
        scope = public.get_scope()
        if scope is not None:
            routes.extend((child.pyobject, f"m.{child.pyobject.get_name()}")
                          for child in scope.get_scopes() if child.get_kind() == "Class")
        targets: list[t.Triple[Path, str, str]] = []
        for path, source in sources.items():
            if path.parent.parent != package or source.startswith(c.Infra.AUTOGEN_HEADERS):
                continue
            family = FlextInfraUtilitiesCodegenNamespace.facade_family_of_directory(path.parent.name)
            if family is None or family != "m":
                continue
            owner = workspace.convention(path).module_policy.expected_family
            module = project.get_pymodule(project.get_resource(path.relative_to(root).as_posix()))
            if owner is None or owner not in module.get_attributes():
                continue
            value = module.get_attribute(owner).get_object()
            for composed, route in routes:
                if value in cls._class_ancestry(composed):
                    targets.append((path, owner, route))
        if len(targets) != 1:
            msg = f"declaration-relocation: expected one authored composed model owner for {origin}; found {targets}"
            raise ValueError(msg)
        return targets[0]

    @classmethod
    def _relocate_payload(
        cls, project: p.Infra.RopeProject, sources: t.MappingKV[Path, str],
        origin: Path, node: ast.ClassDef, binding: p.Infra.RopePyName,
        target: Path, owner: str, exposure: str,
    ) -> dict[Path, str]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        refactors = FlextInfraUtilitiesRopeRuntimeRefactors
        root = Path(project.root.real_path)
        package = target.parent.parent.name
        expression = f"{exposure}.{node.name}"
        updated = dict(sources)
        for path, source in sources.items():
            resource = project.get_resource(path.relative_to(root).as_posix())
            changes: list[m.Infra.SourceRewrite] = []
            finder = refactors.create_occurrence_finder(project, node.name, binding,
                                                       imports=True, in_hierarchy=False)
            for occurrence in finder.find_occurrences(resource=resource):
                if occurrence.is_defined():
                    continue
                start, end = refactors.word_primary_range(source, occurrence.offset)
                if path == origin and node.lineno <= occurrence.lineno <= (node.end_lineno or node.lineno):
                    msg = f"declaration-relocation: self-dependent payload {origin}:{node.name}"
                    raise ValueError(msg)
                changes.append(m.Infra.SourceRewrite(start=start, end=end, text=expression))
            def replacement(scope: p.Infra.RopeScope, item: ast.expr) -> str | None:
                return expression if runtime.same_name(binding, runtime.resolve_symbol(scope, item)) else None
            changes.extend(cls._quoted_type_rewrites(project, resource, source, replacement,
                protected=(node.lineno, node.end_lineno or node.lineno) if path == origin else None))
            executable = refactors.content_change(resource, source, changes).new_contents
            if executable != source:
                if source.startswith(c.Infra.AUTOGEN_HEADERS):
                    msg = f"declaration-relocation: generated consumer {path}"
                    raise ValueError(msg)
                module = runtime.build_string_module(project, executable, resource=resource)
                scope = project.get_pymodule(resource).get_scope()
                existing = scope.get_names().get("m") if scope is not None else None
                expected = project.get_pymodule(project.get_resource((target.parent.parent / "models.py").relative_to(root).as_posix())).get_attribute("m")
                if existing is not None and not runtime.same_name(expected, existing):
                    msg = f"declaration-relocation: conflicting model binding in {path}"
                    raise ValueError(msg)
                imports = runtime.module_imports_for_pymodule(project, module)
                imports.add_import(runtime.from_import(package, 0, (("m", None),)))
                updated[path] = imports.get_changed_source()
        moved = cst.parse_module(updated[origin])
        outer = next(item for item in moved.body if isinstance(item, cst.ClassDef)
                     and isinstance(item.body, cst.IndentedBlock)
                     and any(isinstance(child, cst.ClassDef) and child.name.value == node.name for child in item.body.body))
        payload = next(child for child in outer.body.body if isinstance(child, cst.ClassDef) and child.name.value == node.name)
        kept = tuple(child for child in outer.body.body if child is not payload)
        updated[origin] = moved.with_changes(body=tuple(
            item.with_changes(body=outer.body.with_changes(body=kept or (cst.SimpleStatementLine(body=(cst.Pass(),)),)))
            if item is outer else item for item in moved.body)).code
        destination = cst.parse_module(updated[target])
        target_owner = next(item for item in destination.body if isinstance(item, cst.ClassDef) and item.name.value == owner)
        if node.name in project.get_pymodule(project.get_resource(target.relative_to(root).as_posix())).get_attribute(owner).get_object().get_attributes():
            msg = f"declaration-relocation: occupied destination {target}:{node.name}"
            raise ValueError(msg)
        imports = cls._payload_imports(project, origin, target, node)
        holder = cls._owner_holding(target_owner, (payload,))
        updated[target] = destination.with_changes(body=(*imports, *(holder if item is target_owner else item for item in destination.body))).code
        return updated

    @staticmethod
    def _payload_imports(
        project: p.Infra.RopeProject, origin: Path, target: Path, node: ast.ClassDef,
    ) -> t.VariadicTuple[cst.BaseStatement]:
        root = Path(project.root.real_path)
        source = project.get_resource(origin.relative_to(root).as_posix()).read()
        target_resource = project.get_resource(target.relative_to(root).as_posix())
        destination = project.get_pymodule(target_resource).get_scope()
        imports: dict[str, ast.Import | ast.ImportFrom] = {}
        for statement in ast.parse(source).body:
            if isinstance(statement, ast.Import | ast.ImportFrom):
                for alias in statement.names:
                    imports[alias.asname or alias.name.split(".")[0]] = statement
        required: list[cst.BaseStatement] = []
        seen: set[int] = set()
        parameters = {parameter.name for parameter in node.type_params}
        fields = {statement.target.id for statement in node.body
                  if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)}
        module = project.get_pymodule(project.get_resource(origin.relative_to(root).as_posix()))
        for name in sorted({item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)} - fields - parameters):
            if hasattr(builtins, name):
                continue
            statement = imports.get(name)
            if statement is None or isinstance(statement, ast.ImportFrom) and statement.level:
                msg = f"declaration-relocation: unresolved/outer dependency {origin}:{node.name} -> {name}"
                raise ValueError(msg)
            existing = destination.get_names().get(name) if destination is not None else None
            original = module.get_scope().get_names().get(name)
            if existing is not None and (original is None or not runtime.same_name(original, existing)):
                msg = f"declaration-relocation: conflicting dependency {target}:{name}"
                raise ValueError(msg)
            if existing is None and id(statement) not in seen:
                seen.add(id(statement))
                required.append(cst.parse_statement(ast.get_source_segment(source, statement) + "\n"))
        return tuple(required)

    @staticmethod
    def _preflight_declaration_graph(
        workspace: p.Infra.RopeWorkspaceDsl, original: t.MappingKV[Path, str],
        proposed: t.MappingKV[Path, str],
    ) -> None:
        """Reject new runtime cycles in the proposed immutable import graph."""
        before = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(workspace.rope_project, original)
        after = FlextInfraUtilitiesRopeRuntimeModules.snapshot_project(workspace.rope_project, proposed)
        try:
            old, _ = FlextInfraUtilitiesCodemodProject.snapshot_import_graph(before)
            new, _ = FlextInfraUtilitiesCodemodProject.snapshot_import_graph(after)
            cycles = FlextInfraUtilitiesCodemodProject.project_import_cycles(new)
            baseline = FlextInfraUtilitiesCodemodProject.project_import_cycles(old)
            introduced = {name: members for name, members in cycles.items() if baseline.get(name) != members}
            if introduced:
                msg = f"declaration-relocation: proposed runtime import cycle; nothing published: {introduced}; edges={new}"
                raise ValueError(msg)
        finally:
            before.close()
            after.close()


__all__: list[str] = ["FlextInfraUtilitiesSemanticDeclarationRelocation"]
