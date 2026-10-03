"""Rope export-name resolution, scopes, and docstring summaries.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from typing import ClassVar

from flext_infra import c, m, t
from flext_infra._utilities._rope_analysis.asthelpers import (
    FlextInfraUtilitiesRopeAnalysisAstHelpers,
)
from flext_infra._utilities._rope_analysis.sourcescan import (
    FlextInfraUtilitiesRopeAnalysisSourceScan,
)
from flext_infra._utilities.rope_core import FlextInfraUtilitiesRopeCore
from flext_infra._utilities.rope_runtime import FlextInfraUtilitiesRopeRuntime


class FlextInfraUtilitiesRopeAnalysisExports:
    """Rope export-name resolution, scopes, and docstring summaries."""

    _EXPORT_NAMES_CACHE: ClassVar[
        MutableMapping[
            tuple[str, str, int, bool, bool, bool, bool, bool],
            t.StrSequence,
        ]
    ] = {}

    @staticmethod
    def scope_definitions(
        pymodule: t.Infra.RopePyModule,
    ) -> t.SequenceOf[m.Infra.ScopeDefinition]:
        """Return every def/class scope in a module via rope's semantic tree.

        Uses ``PyModule.get_scope()`` and recursive ``PyScope.get_scopes()`` —
        never ``get_ast``/``ast.walk``. Each entry carries the scope kind
        (Function/Class/Comprehension), its 1-based start line, and whether it
        is a direct child of the module (global) scope.

        Returns:
            Every def/class scope in a module via rope's semantic tree.

        """
        root_scope = pymodule.get_scope()
        if root_scope is None:
            return ()
        definitions: t.MutableSequenceOf[m.Infra.ScopeDefinition] = []
        FlextInfraUtilitiesRopeAnalysisExports._collect_scope_definitions(
            scope=root_scope,
            is_module_level=True,
            definitions=definitions,
        )
        return tuple(definitions)

    @staticmethod
    def _collect_scope_definitions(
        *,
        scope: t.Infra.RopeScope,
        is_module_level: bool,
        definitions: t.MutableSequenceOf[m.Infra.ScopeDefinition],
    ) -> None:
        """Recurse the rope scope tree, appending one entry per child scope."""
        for child in scope.get_scopes():
            start = child.get_start()
            # RopeScope.get_start() is
            # declared int in p.Infra; the old isinstance guard was dead code.
            definitions.append(
                m.Infra.ScopeDefinition(
                    name=FlextInfraUtilitiesRopeAnalysisExports._scope_name(child),
                    kind=FlextInfraUtilitiesRopeAnalysisExports._scope_kind(child),
                    line=start if start > 0 else 1,
                    is_module_level=is_module_level,
                ),
            )
            FlextInfraUtilitiesRopeAnalysisExports._collect_scope_definitions(
                scope=child,
                is_module_level=False,
                definitions=definitions,
            )

    @staticmethod
    def _scope_kind(scope: t.Infra.RopeScope) -> c.Infra.RopeScopeKind:
        """Map rope's ``get_kind()`` to the typed enum.

        Rope documents ``None`` for comprehension scopes, which maps to
        ``UNKNOWN``; any other undeclared kind raises its ``ValueError``.

        Returns:
            The resulting ``c.Infra.RopeScopeKind``.

        """
        raw_kind = scope.get_kind()
        if raw_kind is None:
            return c.Infra.RopeScopeKind.UNKNOWN
        return c.Infra.RopeScopeKind(raw_kind)

    @staticmethod
    def _scope_name(scope: t.Infra.RopeScope) -> str:
        """Return the def/class name backing one rope scope.

        Returns:
            The def/class name backing one rope scope.

        """
        name: str = scope.pyobject.get_name()
        return name

    @staticmethod
    def resolve_module_export_names(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        *,
        export_options: m.Infra.ExportOptions | None = None,
    ) -> t.StrSequence:
        """Return module-local export names from Rope metadata.

        Returns:
            Module-local export names from Rope metadata.

        """
        resolved_export_options = export_options or m.Infra.ExportOptions()
        cache_key = (
            *FlextInfraUtilitiesRopeAnalysisAstHelpers.resource_cache_key(
                rope_project,
                resource,
            ),
            resolved_export_options.include_dunder,
            resolved_export_options.allow_main,
            resolved_export_options.allow_assignments,
            resolved_export_options.allow_functions,
            resolved_export_options.require_explicit_all,
        )
        cached = FlextInfraUtilitiesRopeAnalysisExports._EXPORT_NAMES_CACHE.get(
            cache_key,
        )
        export_names: t.StrSequence
        if cached is not None:
            export_names = cached
        else:
            pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(
                rope_project,
                resource,
            )
            export_names = FlextInfraUtilitiesRopeAnalysisExports._module_export_names(
                export_options=resolved_export_options,
                pymodule=pymodule,
                resource=resource,
            )
            FlextInfraUtilitiesRopeAnalysisExports._EXPORT_NAMES_CACHE[cache_key] = (
                export_names
            )
        return export_names

    @staticmethod
    def module_export_names_source(
        source: str,
        *,
        export_options: m.Infra.ExportOptions | None = None,
    ) -> t.StrSequence:
        """Return module-local exports from one parsed source snapshot.

        Returns:
            Module-local exports from one parsed source snapshot.

        """
        resolved_options = export_options or m.Infra.ExportOptions()
        module = ast.parse(source)
        assignments: t.MutableSequenceOf[str] = []
        definitions: t.MutableSequenceOf[t.Pair[str, bool]] = []
        explicit_all = False

        def bound_names(target: ast.expr) -> t.StrSequence:
            if isinstance(target, ast.Name):
                return (target.id,)
            if isinstance(target, (ast.List, ast.Tuple)):
                return tuple(
                    name for element in target.elts for name in bound_names(element)
                )
            return ()

        def collect(statements: t.SequenceOf[ast.stmt]) -> None:
            nonlocal explicit_all
            for statement in statements:
                if isinstance(
                    statement,
                    (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    definitions.append((
                        statement.name,
                        isinstance(statement, ast.ClassDef),
                    ))
                    continue
                names: t.StrSequence
                if isinstance(statement, ast.Assign):
                    names = tuple(
                        name
                        for target in statement.targets
                        for name in bound_names(target)
                    )
                elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
                    names = bound_names(statement.target)
                else:
                    names = ()
                if names:
                    explicit_all = explicit_all or c.Infra.DUNDER_ALL in names
                    assignments.extend(
                        name for name in names if name != c.Infra.DUNDER_ALL
                    )
                    continue
                if isinstance(statement, (ast.Import, ast.ImportFrom)):
                    continue
                if isinstance(statement, ast.If):
                    sides = (
                        (statement.test.left, statement.test.comparators[0])
                        if isinstance(statement.test, ast.Compare)
                        and len(statement.test.ops) == 1
                        and isinstance(statement.test.ops[0], ast.Eq)
                        and len(statement.test.comparators) == 1
                        else ()
                    )
                    names_in_test = {
                        side.id for side in sides if isinstance(side, ast.Name)
                    }
                    values_in_test = {
                        side.value for side in sides if isinstance(side, ast.Constant)
                    }
                    if names_in_test == {"__name__"} and values_in_test == {"__main__"}:
                        continue
                    collect(statement.body)
                    collect(statement.orelse)
                    continue
                if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
                    collect(statement.body)
                    collect(statement.orelse)
                    continue
                if isinstance(statement, (ast.With, ast.AsyncWith)):
                    collect(statement.body)
                    continue
                if isinstance(statement, (ast.Try, ast.TryStar)):
                    collect(statement.body)
                    for handler in statement.handlers:
                        collect(handler.body)
                    collect(statement.orelse)
                    collect(statement.finalbody)
                    continue
                if isinstance(statement, ast.Match):
                    for case in statement.cases:
                        collect(case.body)

        collect(module.body)
        if resolved_options.include_dunder:
            return tuple(
                dict.fromkeys(
                    name
                    for name in assignments
                    if name.startswith("__") and name.endswith("__")
                ),
            )
        if explicit_all:
            return tuple(
                dict.fromkeys(
                    FlextInfraUtilitiesRopeAnalysisSourceScan.module_assignment_strings_source(
                        source,
                        c.Infra.DUNDER_ALL,
                    ),
                ),
            )
        if resolved_options.require_explicit_all:
            return ()
        implicit_names: t.MutableSequenceOf[str] = [
            name
            for name, is_class in definitions
            if is_class
            or resolved_options.allow_functions
            or (resolved_options.allow_main and name == "main")
        ]
        if resolved_options.allow_assignments:
            implicit_names.extend(assignments)
        return tuple(dict.fromkeys(implicit_names))

    @staticmethod
    def _module_export_names(
        *,
        export_options: m.Infra.ExportOptions,
        pymodule: t.Infra.RopePyModule,
        resource: t.Infra.RopeResource,
    ) -> t.StrSequence:
        """Return export names for one resolved Rope module.

        Returns:
            Export names for one resolved Rope module.

        """
        attributes = pymodule.get_attributes()
        if export_options.include_dunder:
            return FlextInfraUtilitiesRopeAnalysisExports._dunder_export_names(
                attributes=attributes,
                resource=resource,
            )
        explicit_all = FlextInfraUtilitiesRopeAnalysisExports._explicit_export_names(
            attributes=attributes,
            pymodule=pymodule,
            resource=resource,
        )
        if explicit_all is not None:
            return tuple(dict.fromkeys(explicit_all))
        if export_options.require_explicit_all:
            return ()
        return FlextInfraUtilitiesRopeAnalysisExports._implicit_export_names(
            attributes=attributes,
            export_options=export_options,
            resource=resource,
            pymodule=pymodule,
        )

    @staticmethod
    def _dunder_export_names(
        *,
        attributes: t.MappingKV[str, t.Infra.RopePyName],
        resource: t.Infra.RopeResource,
    ) -> t.StrSequence:
        """Return locally assigned dunder export names.

        Returns:
            Locally assigned dunder export names.

        """
        return tuple(
            dict.fromkeys(
                name
                for name, pyname in attributes.items()
                if name != c.Infra.DUNDER_ALL
                and name.startswith("__")
                and name.endswith("__")
                and FlextInfraUtilitiesRopeRuntime.assigned_name(pyname)
                and FlextInfraUtilitiesRopeAnalysisAstHelpers.local_name(
                    pyname,
                    resource,
                )
            ),
        )

    @staticmethod
    def _explicit_export_names(
        *,
        attributes: t.MappingKV[str, t.Infra.RopePyName],
        pymodule: t.Infra.RopePyModule,
        resource: t.Infra.RopeResource,
    ) -> t.StrSequence | None:
        """Return explicit ``__all__`` export names when declared locally.

        Returns:
            Explicit ``__all__`` export names when declared locally.

        """
        explicit_all_name = attributes.get(c.Infra.DUNDER_ALL)
        if (
            explicit_all_name is None
            or not FlextInfraUtilitiesRopeRuntime.assigned_name(explicit_all_name)
        ):
            return None
        assigned_all: t.Infra.RopeAssignedName = explicit_all_name
        if not FlextInfraUtilitiesRopeAnalysisAstHelpers.local_name(
            assigned_all,
            resource,
        ):
            return None
        return FlextInfraUtilitiesRopeAnalysisExports._explicit_all_names(
            assigned_all,
            pymodule,
        )

    @staticmethod
    def _implicit_export_names(
        *,
        attributes: t.MappingKV[str, t.Infra.RopePyName],
        export_options: m.Infra.ExportOptions,
        resource: t.Infra.RopeResource,
        pymodule: t.Infra.RopePyModule,
    ) -> t.StrSequence:
        """Return implicit export names accepted by the export options.

        Returns:
            Implicit export names accepted by the export options.

        """
        guard_spans = FlextInfraUtilitiesRopeAnalysisExports._script_guard_spans(
            pymodule,
        )
        names: t.MutableSequenceOf[str] = []
        for name, pyname in attributes.items():
            if name == c.Infra.DUNDER_ALL:
                continue
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.local_name(
                pyname,
                resource,
            ):
                continue
            if FlextInfraUtilitiesRopeAnalysisExports._is_export_name(
                export_options=export_options,
                name=name,
                pyname=pyname,
                guard_spans=guard_spans,
            ):
                names.append(name)
        return tuple(dict.fromkeys(names))

    @staticmethod
    def _script_guard_spans(
        pymodule: t.Infra.RopePyModule,
    ) -> t.SequenceOf[t.Pair[int, int]]:
        """Return the line spans of top-level ``if __name__ == "__main__":`` blocks.

        Names bound there exist only when the module runs as a script; a
        package facade that re-exported them (flext-core's examples exported
        ``result`` and ``msg``) failed every importer.

        Returns:
            The line spans of top-level ``if __name__ == "__main__":`` blocks.

        """
        module_ast = pymodule.get_ast()
        body = getattr(module_ast, "body", ())
        spans: t.MutableSequenceOf[t.Pair[int, int]] = []
        for node in body:
            if not isinstance(node, ast.If):
                continue
            test = node.test
            if not (
                isinstance(test, ast.Compare)
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Eq)
                and len(test.comparators) == 1
            ):
                continue
            sides = (test.left, test.comparators[0])
            names = {side.id for side in sides if isinstance(side, ast.Name)}
            values = {side.value for side in sides if isinstance(side, ast.Constant)}
            if names == {"__name__"} and values == {"__main__"}:
                spans.append((node.lineno, node.end_lineno or node.lineno))
        return tuple(spans)

    @staticmethod
    def _is_export_name(
        *,
        export_options: m.Infra.ExportOptions,
        name: str,
        pyname: t.Infra.RopePyName,
        guard_spans: t.SequenceOf[t.Pair[int, int]] = (),
    ) -> bool:
        """Return whether one Rope name is exportable under the options.

        Returns:
            Whether one Rope name is exportable under the options.

        """
        if FlextInfraUtilitiesRopeRuntime.imported_name(pyname):
            return False
        if FlextInfraUtilitiesRopeRuntime.assigned_name(pyname):
            allow_assignments: bool = export_options.allow_assignments
            if not allow_assignments:
                return False
            lines = tuple(
                line
                for assignment in pyname.assignments
                if (line := getattr(assignment.ast_node, "lineno", None)) is not None
            )
            return not lines or not all(
                any(start <= line <= end for start, end in guard_spans)
                for line in lines
            )
        if not FlextInfraUtilitiesRopeRuntime.defined_name(pyname):
            return False
        obj = pyname.get_object()
        if FlextInfraUtilitiesRopeRuntime.abstract_class(obj):
            return True
        if not FlextInfraUtilitiesRopeRuntime.py_function(obj):
            return False
        allow_main: bool = export_options.allow_main
        allow_functions: bool = export_options.allow_functions
        return (allow_main and name == "main") or allow_functions

    @staticmethod
    def _explicit_all_names(
        pyname: t.Infra.RopeAssignedName,
        pymodule: t.Infra.RopePyModule,
    ) -> t.StrSequence | None:
        """Return literal ``__all__`` names from a Rope-cached source slice.

        Reads the assignment's source range via the module's ``source_code``
        and extracts string literals with ``c.Infra.STRING_LITERAL_RE`` —
        avoiding ``ast`` walking entirely.

        Returns:
            Literal ``__all__`` names from a Rope-cached source slice.

        """
        for assignment in pyname.assignments:
            node = assignment.ast_node
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None) or start
            if start is None:
                continue
            lines = pymodule.source_code.splitlines()
            slice_text = "\n".join(lines[start - 1 : end])
            return tuple(dict.fromkeys(c.Infra.STRING_LITERAL_RE.findall(slice_text)))
        return None

    @staticmethod
    def public_export_names_source(source: str) -> t.StrSequence:
        """Return the explicit public ABI declared by one module source.

        Returns:
            The explicit public ABI declared by one module source.

        """
        return (
            FlextInfraUtilitiesRopeAnalysisSourceScan.module_assignment_strings_source(
                source,
                c.Infra.DUNDER_ALL,
            )
        )

    @staticmethod
    def module_has_docstring_source(source: str) -> bool:
        """Return whether ``source`` starts with a module docstring (rope-parsed).

        Returns:
            Whether ``source`` starts with a module docstring (rope-parsed).

        """
        pymodule = FlextInfraUtilitiesRopeAnalysisAstHelpers.parse_string_module(source)
        return bool(pymodule.get_doc())

    @staticmethod
    def module_docstring_summary_source(source: str) -> str:
        """Return the PEP 257 summary line of the module docstring (rope-parsed).

        Returns:
            The PEP 257 summary line of the module docstring (rope-parsed).

        """
        pymodule = FlextInfraUtilitiesRopeAnalysisAstHelpers.parse_string_module(source)
        doc = pymodule.get_doc() or ""
        summary = next((line for line in doc.splitlines() if line.strip()), "")
        # The summary is rendered verbatim into generated markdown, where runs
        # of spaces are a lint failure nobody can hand-fix in a generated file.
        # Collapsing them here keeps the summary faithful and renderable.
        return " ".join(summary.split())

    @staticmethod
    def symbol_has_docstring_source(source: str, symbol_name: str) -> bool:
        """Check a locally defined symbol; imported docs need module context.

        Returns:
            The resulting ``bool``.

        """
        pymodule = FlextInfraUtilitiesRopeAnalysisAstHelpers.parse_string_module(source)
        pyname = pymodule.get_attributes().get(symbol_name)
        if pyname is None or not FlextInfraUtilitiesRopeRuntime.defined_name(pyname):
            return False
        obj = pyname.get_object()
        get_doc = getattr(obj, "get_doc", None)
        if not callable(get_doc):
            # Plain PyObjects (assignments, imports) carry no docstring.
            return False
        return bool(get_doc())

    @staticmethod
    def assignment_docstrings_source(source: str) -> t.StrSequence:
        """Return assignment names followed by a string literal (rope-parsed).

        Iterates the parsed module's body via ``_fields`` access and pairs each
        ``Assign``/``AnnAssign``/PEP-695 ``TypeAlias`` target with the next
        sibling ``Expr(Constant(str))``.

        Returns:
            Assignment names followed by a string-literal expression (rope-parsed).

        """
        pymodule = FlextInfraUtilitiesRopeAnalysisAstHelpers.parse_string_module(source)
        module_ast = pymodule.get_ast()
        body = getattr(module_ast, "body", []) or []
        names: list[str] = []
        previous_targets: list[str] = []
        for statement in body:
            kind = FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(statement)
            if kind in {"Assign", "AnnAssign", "TypeAlias"}:
                previous_targets = (
                    FlextInfraUtilitiesRopeAnalysisAstHelpers.statement_target_names(
                        statement,
                    )
                )
                continue
            if kind == "Expr" and previous_targets:
                value = getattr(statement, "value", None)
                if (
                    value is not None
                    and FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(value)
                    == "Constant"
                    and isinstance(getattr(value, "value", None), str)
                ):
                    names.extend(previous_targets)
            previous_targets = []
        return tuple(dict.fromkeys(names))

    @staticmethod
    def module_body_nodes_source(source: str) -> t.SequenceOf[t.Infra.RopeAstNode]:
        """Return top-level parsed statements for one source module.

        Returns:
            Top-level parsed statements for one source module.

        """
        _ = source
        return ()

    @staticmethod
    def module_reachable_nodes_source(source: str) -> t.SequenceOf[t.Infra.RopeAstNode]:
        """Return parsed nodes reachable from one source module.

        Returns:
            Parsed nodes reachable from one source module.

        """
        _ = source
        return ()
