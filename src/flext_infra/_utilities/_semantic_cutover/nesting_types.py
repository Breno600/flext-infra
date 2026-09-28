"""Identity-preserving quoted type edits for class movement and nesting."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import override

from flext_infra import m, p, t

from ..rope_runtime_modules import FlextInfraUtilitiesRopeRuntimeModules
from ..rope_runtime_refactors import FlextInfraUtilitiesRopeRuntimeRefactors
from .family_type_references import FlextInfraUtilitiesSemanticFamilyTypeReferences


class FlextInfraUtilitiesSemanticNestingTypes(
    FlextInfraUtilitiesSemanticFamilyTypeReferences
):
    """Share the canonical type-position selector and original Rope scope."""

    @classmethod
    def _rewrite_quoted_types(
        cls,
        project: p.Infra.RopeProject,
        resource: p.Infra.RopeResource,
        source: str,
        replacement: Callable[[p.Infra.RopeScope, ast.expr], str | None],
        *,
        protected: t.Pair[int, int] | None = None,
    ) -> str:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        module = project.get_pymodule(resource)
        edits: list[m.Infra.SourceRewrite] = []
        for annotation, declaration_line in cls._annotation_roots(ast.parse(source)):
            if (
                protected is not None
                and protected[0] <= annotation.lineno <= protected[1]
            ):
                continue
            start, _ = cls._expression_range(source, annotation)
            scope = runtime.scope_at(module, start, declaration_line=declaration_line)
            for node in cls._type_nodes(annotation, project, scope):
                if not isinstance(node, ast.Constant) or not isinstance(
                    node.value, str
                ):
                    continue
                updated = cls._quoted_replacement(
                    project, resource, scope, node.value, replacement
                )
                if updated != node.value:
                    start, end = cls._expression_range(source, node)
                    edits.append(
                        m.Infra.SourceRewrite(start=start, end=end, text=repr(updated))
                    )
        return FlextInfraUtilitiesRopeRuntimeRefactors.content_change(
            resource, source, edits
        ).new_contents

    @classmethod
    def _quoted_replacement(
        cls,
        project: p.Infra.RopeProject,
        resource: p.Infra.RopeResource,
        scope: p.Infra.RopeScope,
        source: str,
        replacement: Callable[[p.Infra.RopeScope, ast.expr], str | None],
    ) -> str:
        edits: list[m.Infra.SourceRewrite] = []
        for node in cls._type_nodes(
            ast.parse(source, mode="eval").body, project, scope
        ):
            start, end = cls._expression_range(source, node)
            if any(edit.start <= start and end <= edit.end for edit in edits):
                continue
            text = replacement(scope, node)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                updated = cls._quoted_replacement(
                    project, resource, scope, node.value, replacement
                )
                if updated != node.value:
                    text = repr(updated)
            if text is not None and text != source[start:end]:
                edits.append(m.Infra.SourceRewrite(start=start, end=end, text=text))
        return FlextInfraUtilitiesRopeRuntimeRefactors.content_change(
            resource, source, edits
        ).new_contents

    @classmethod
    def _nesting_quoted_sources(
        cls,
        project: p.Infra.RopeProject,
        sources: t.MappingKV[Path, str],
        definitions: t.MappingKV[Path, t.StrMapping],
    ) -> t.MappingKV[Path, str]:
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        root = Path(project.root.real_path)
        bindings = tuple(
            (
                path.relative_to(root).with_suffix("").as_posix().replace("/", "."),
                name,
                owner,
                project.get_pymodule(
                    project.get_resource(path.relative_to(root).as_posix())
                ).get_attribute(name),
            )
            for path, names in definitions.items()
            for name, owner in names.items()
        )

        def replacement(scope: p.Infra.RopeScope, node: ast.expr) -> str | None:
            actual = runtime.resolve_symbol(scope, node)
            for module_name, name, owner, expected in bindings:
                if not runtime.same_name(expected, actual):
                    continue
                if isinstance(actual, p.Infra.RopeImportedName):
                    module = scope.pyobject.get_module()
                    if module is None:
                        msg = "quoted type scope has no declaring module"
                        raise ValueError(msg)
                    _, destination = runtime.import_binding(
                        project, module, module_name, owner
                    )
                    expression = f"{destination}.{name}"
                else:
                    expression = cls._nested_type_expression(node, actual, name, owner)
                if expression is not None:
                    return cls._checked_type_reference(scope, expression)
            return None

        return {
            path: cls._rewrite_quoted_types(
                project,
                project.get_resource(path.relative_to(root).as_posix()),
                source,
                replacement,
            )
            for path, source in sources.items()
        }

    @classmethod
    def _captured_names(cls, module: p.Infra.RopePyModule) -> frozenset[str]:
        """Collect identifiers any nested scope binds over the module level."""
        captured: set[str] = set()

        class Visitor(ast.NodeVisitor):
            depth = 0

            def bind(self, name: str) -> None:
                if self.depth:
                    captured.add(name)

            @override
            def visit_Name(self, node: ast.Name) -> None:
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    self.bind(node.id)

            def _visit_scoped(
                self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            ) -> None:
                self.bind(node.name)
                self.depth += 1
                for stmt in node.body:
                    self.visit(stmt)
                self.depth -= 1

            @override
            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._visit_scoped(node)

            @override
            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._visit_scoped(node)

            @override
            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._visit_scoped(node)

            @override
            def visit_Lambda(self, node: ast.Lambda) -> None:
                self.depth += 1
                self.visit(node.body)
                self.depth -= 1

        Visitor().visit(ast.parse(cls._module_source(module)))
        return frozenset(captured)

    @staticmethod
    def _module_source(module: p.Infra.RopePyModule) -> str:
        resource = getattr(module, "resource", None)
        if resource is not None:
            return Path(resource.real_path).read_text(encoding="utf-8")
        return module.source_code

    @staticmethod
    def _nested_type_expression(
        node: ast.expr, actual: p.Infra.RopePyName | None, name: str, owner: str
    ) -> str | None:
        if isinstance(node, ast.Attribute):
            return f"{ast.unparse(node.value)}.{owner}.{name}"
        if not isinstance(node, ast.Name):
            return None
        if isinstance(actual, p.Infra.RopeImportedName):
            parent = node.id if node.id != actual.imported_name else owner
            return f"{parent}.{name}"
        return f"{owner}.{name}" if node.id == name else None

    @classmethod
    def _checked_type_reference(cls, scope: p.Infra.RopeScope, expression: str) -> str:
        """Reject a destination import captured by an existing lexical binding."""
        runtime = FlextInfraUtilitiesRopeRuntimeModules
        node = ast.parse(expression, mode="eval").body
        while isinstance(node, ast.Attribute):
            node = node.value
        if not isinstance(node, ast.Name):
            msg = f"quoted type destination is not an identifier chain: {expression}"
            raise TypeError(msg)
        module = scope.pyobject.get_module()
        if module is None:
            msg = "quoted type scope has no declaring module"
            raise ValueError(msg)
        module_scope = module.get_scope()
        if module_scope is None:
            msg = "quoted type scope has no declaring module"
            raise ValueError(msg)
        cap = cls._captured_names(module)
        if node.id in cap:
            msg = f"shadowed quoted type destination: {expression}"
            raise ValueError(msg)
        local = runtime.resolve_symbol(scope, node)
        global_binding = runtime.resolve_symbol(module_scope, node)
        if local is not None and (
            global_binding is None or not runtime.same_name(global_binding, local)
        ):
            msg = f"shadowed quoted type destination: {expression}"
            raise ValueError(msg)
        return expression


__all__: list[str] = ["FlextInfraUtilitiesSemanticNestingTypes"]
