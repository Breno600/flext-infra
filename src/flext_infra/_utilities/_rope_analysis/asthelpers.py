"""Shared rope parsing and AST traversal primitives."""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path
from typing import ClassVar, TypeGuard

from flext_infra import m, p, t

from ..rope_core import FlextInfraUtilitiesRopeCore
from ..rope_runtime import FlextInfraUtilitiesRopeRuntime


class FlextInfraUtilitiesRopeAnalysisAstHelpers:
    """Shared rope parsing and AST traversal primitives."""

    _parse_project: ClassVar[t.Infra.RopeProject | None] = None

    @staticmethod
    def is_ast_node(obj: p.AttributeProbe) -> TypeGuard[t.Infra.RopeAstNode]:
        """Narrow a rope-provided object to an AST node."""
        return isinstance(obj, ast.AST)

    @staticmethod
    def ensure_ast_node(obj: p.AttributeProbe) -> t.Infra.RopeAstNode:
        """Ensure an object is an AST node, narrowing the type."""
        if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(obj):
            msg = f"Expected AST node, got {type(obj).__name__}"
            raise TypeError(msg)
        return obj

    @staticmethod
    def resource_cache_key(
        rope_project: t.Infra.RopeProject, resource: t.Infra.RopeResource
    ) -> t.Triple[str, str, int]:
        """Resource cache key."""
        file_path = FlextInfraUtilitiesRopeCore.resource_file_path(
            rope_project, resource
        )
        mtime_ns = (
            file_path.stat().st_mtime_ns
            if file_path is not None and file_path.exists()
            else 0
        )
        project_root = getattr(getattr(rope_project, "root", None), "real_path", "")
        return (str(project_root), resource.path, mtime_ns)

    @staticmethod
    def local_name(pyname: t.Infra.RopePyName, resource: t.Infra.RopeResource) -> bool:
        """Return whether one Rope name is defined in ``resource``."""
        if isinstance(pyname, (p.Infra.RopeImportedName, p.Infra.RopeImportedModule)):
            return False
        # NOTE (multi-agent, flext-f8vk / kimi): p.Infra declares
        # get_definition_location() as tuple-always (every other caller
        # unpacks directly); the old None guard was dead code.
        module, line = pyname.get_definition_location()
        origin = module.get_resource() if module is not None else None
        return line is not None and origin is not None and origin.path == resource.path

    @staticmethod
    def statement_target_names(statement: t.Infra.RopeAstNode) -> list[str]:
        """Extract target names from an Assign/AnnAssign/PEP-695 TypeAlias."""
        kind = FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(statement)
        if kind == "AnnAssign":
            target = getattr(statement, "target", None)
            name = getattr(target, "id", "") if target is not None else ""
            return [name] if name else []
        if kind == "TypeAlias":
            name_node = getattr(statement, "name", None)
            name = getattr(name_node, "id", "")
            return [name] if isinstance(name, str) and name else []
        targets = getattr(statement, "targets", []) or []
        names: list[str] = []
        for target in targets:
            name = getattr(target, "id", "")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    @staticmethod
    def parse_string_module(source: str) -> t.Infra.RopePyModule:
        """Parse ``source`` to a rope ``PyModule`` via a shared parsing project.

        Uses rope's ``libutils.get_string_module`` so callers don't need to
        manage temporary files. Parse failures raise; rope contract failures
        escape — the function never returns ``None``.
        """
        rope_project = FlextInfraUtilitiesRopeAnalysisAstHelpers._shared_parse_project()
        result: t.Infra.RopePyModule = FlextInfraUtilitiesRopeRuntime.get_string_module(
            rope_project, source
        )
        return result

    @staticmethod
    def _shared_parse_project() -> t.Infra.RopeProject:
        """Return a process-wide rope project usable for string parsing."""
        cached = FlextInfraUtilitiesRopeAnalysisAstHelpers._parse_project
        if cached is None:
            # flext-o6h5 (agent: kimi) — root-cause fix: the anchor was a hardcoded
            # operator path that crashed CI (FileNotFoundError) and silently bound
            # the parse project to the wrong tree locally. Anchor on the validated
            # settings SSOT, with cwd as last resort — both exist where CLI runs.
            # Path() coercion keeps this correct while settings migrates the
            # field from str to Path (both accepted).
            from flext_infra import settings

            repository_root = settings.Infra.repository_root
            anchor = Path(repository_root) if repository_root else Path.cwd()
            cached = FlextInfraUtilitiesRopeCore.init_rope_project(anchor)
            FlextInfraUtilitiesRopeAnalysisAstHelpers._parse_project = cached
        return cached

    @staticmethod
    def decorator_names(pyfunction: t.Infra.RopePyObject) -> t.StrSequence:
        """Extract decorator names from a rope ``PyFunction`` (no ast import)."""
        decorators = getattr(pyfunction, "decorators", None) or ()
        names: list[str] = []
        for decorator in decorators:
            name = getattr(decorator, "id", None) or getattr(decorator, "attr", None)
            if isinstance(name, str) and name:
                names.append(name)
                continue
            func = getattr(decorator, "func", None)
            inner = getattr(func, "id", None) or getattr(func, "attr", None)
            if isinstance(inner, str) and inner:
                names.append(inner)
        return names

    @staticmethod
    def first_decorator_line(
        pyfunction: t.Infra.RopePyObject, *, default_line: int
    ) -> int:
        """Return the lowest line number among ``pyfunction``'s decorators."""
        decorators = getattr(pyfunction, "decorators", None) or ()
        candidate_lines = [
            decorator.lineno
            for decorator in decorators
            if isinstance(getattr(decorator, "lineno", None), int)
        ]
        return min(candidate_lines) if candidate_lines else default_line

    @staticmethod
    def node_kind(node: p.AttributeProbe) -> str:
        """Return an AST node's class name (e.g. ``"AnnAssign"``) without importing ast."""
        return type(node).__name__

    @staticmethod
    def walk_ast_nodes(root: t.Infra.RopeAstNode) -> t.SequenceOf[t.Infra.RopeAstNode]:
        """Return every AST node reachable from ``root``, ``root`` included."""
        if not isinstance(root, ast.AST):
            return []
        return [
            FlextInfraUtilitiesRopeAnalysisAstHelpers.ensure_ast_node(node)
            for node in ast.walk(root)
        ]

    @staticmethod
    def ast_parent_map(
        root: p.AttributeProbe,
    ) -> MutableMapping[int, t.Infra.RopeAstNode]:
        """Return a child-id -> parent map for the full AST reachable from ``root``.

        The shared SSOT for parent lookups across every rope detector.
        """
        parent_map: MutableMapping[int, t.Infra.RopeAstNode] = {}
        if not isinstance(root, ast.AST):
            return parent_map
        for parent in ast.walk(root):
            owner = FlextInfraUtilitiesRopeAnalysisAstHelpers.ensure_ast_node(parent)
            for child in ast.iter_child_nodes(parent):
                parent_map[id(child)] = owner
        return parent_map

    @classmethod
    def is_module_level_node(
        cls,
        node: t.Infra.RopeAstNode,
        parent_map: t.MappingKV[int, t.Infra.RopeAstNode],
    ) -> bool:
        """Return True when ``node`` is a direct child of the module body.

        Walks the parent chain; a node nested inside any ClassDef/FunctionDef is
        NOT module-level. Shared SSOT for placement detectors.
        """
        current = node
        while True:
            parent = parent_map.get(id(current))
            if parent is None:
                return False
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(parent):
                return False
            parent_kind = cls.node_kind(parent)
            if parent_kind in {"ClassDef", "FunctionDef", "AsyncFunctionDef"}:
                return False
            if parent_kind == "Module":
                return True
            current = parent

    @staticmethod
    def name_of(node: p.AttributeProbe) -> str:
        """Return ``node.id`` (Name) or ``node.attr`` (Attribute) or ``""``."""
        if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(node):
            return ""
        identifier = getattr(node, "id", None)
        if isinstance(identifier, str) and identifier:
            return identifier
        attr = getattr(node, "attr", None)
        if isinstance(attr, str) and attr:
            return attr
        return ""

    @staticmethod
    def line_col_range(node: p.AttributeProbe) -> t.Quad[int, int, int, int] | None:
        """Return ``(lineno, col_offset, end_lineno, end_col_offset)`` for an AST node."""
        if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(node):
            return None
        lineno = getattr(node, "lineno", None)
        col_offset = getattr(node, "col_offset", None)
        end_lineno = getattr(node, "end_lineno", None) or lineno
        end_col_offset = getattr(node, "end_col_offset", None) or col_offset
        if not (
            isinstance(lineno, int)
            and isinstance(col_offset, int)
            and isinstance(end_lineno, int)
            and isinstance(end_col_offset, int)
        ):
            return None
        return (lineno, col_offset, end_lineno, end_col_offset)

    @staticmethod
    def _body_nodes(node: p.AttributeProbe) -> t.SequenceOf[t.Infra.RopeAstNode]:
        """Return direct AST body children for a Rope AST node."""
        if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(node):
            return ()
        body = getattr(node, "body", ())
        if not isinstance(body, (list, tuple)):
            return ()
        nodes: list[t.Infra.RopeAstNode] = [
            child
            for child in body
            if FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(child)
        ]
        return tuple(nodes)

    @staticmethod
    def class_body_nodes(
        tree: p.AttributeProbe, *, class_name: str
    ) -> t.SequenceOf[t.Infra.RopeAstNode]:
        """Return direct body nodes for a top-level class name."""
        if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(tree):
            return ()
        for node in FlextInfraUtilitiesRopeAnalysisAstHelpers._body_nodes(tree):
            if FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(node) != "ClassDef":
                continue
            if getattr(node, "name", "") == class_name:
                return FlextInfraUtilitiesRopeAnalysisAstHelpers._body_nodes(node)
        return ()

    @staticmethod
    def assignment_target_names(node: p.AttributeProbe) -> t.StrSequence:
        """Return direct assignment target names represented by one AST node."""
        return FlextInfraUtilitiesRopeAnalysisAstHelpers._assignment_target_names(node)

    @staticmethod
    def _assignment_target_names(node: p.AttributeProbe) -> t.StrSequence:
        """Return direct assignment target names represented by one AST node."""
        if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(node):
            return ()
        node_kind = FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(node)
        if node_kind == "AnnAssign":
            target = getattr(node, "target", None)
            if (
                target is not None
                and FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(target)
            ):
                target_name = FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(target)
                return (target_name,) if target_name else ()
            return ()
        if node_kind != "Assign":
            return ()
        targets = getattr(node, "targets", ())
        if not isinstance(targets, (list, tuple)):
            return ()
        names: list[str] = []
        for target in targets:
            if FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(target):
                target_name = FlextInfraUtilitiesRopeAnalysisAstHelpers.name_of(target)
                if target_name:
                    names.append(target_name)
        return tuple(names)

    @staticmethod
    def class_symbol_names(class_body: t.SequenceOf[p.AttributeProbe]) -> t.StrSequence:
        """Return direct method, nested-class and attribute symbols for a class body."""
        names: set[str] = set()
        for node in class_body:
            if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(node):
                continue
            node_kind = FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(node)
            if node_kind in {"AsyncFunctionDef", "ClassDef", "FunctionDef"}:
                node_name = getattr(node, "name", "")
                if isinstance(node_name, str) and node_name:
                    names.add(node_name)
                continue
            names.update(
                FlextInfraUtilitiesRopeAnalysisAstHelpers._assignment_target_names(node)
            )
        return tuple(sorted(names))

    @staticmethod
    def class_info_from_source(source: str) -> t.SequenceOf[m.Infra.ClassInfo]:
        """Return class info from the current source text without Rope resource cache."""
        pymodule = FlextInfraUtilitiesRopeAnalysisAstHelpers.parse_string_module(source)
        body = getattr(pymodule.get_ast(), "body", ())
        if not isinstance(body, (list, tuple)):
            return ()
        return tuple(
            class_info
            for node in body
            if FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(node)
            and (
                class_info
                := FlextInfraUtilitiesRopeAnalysisAstHelpers._class_info_from_ast(node)
            )
            is not None
        )

    @staticmethod
    def _class_info_from_ast(node: p.AttributeProbe) -> m.Infra.ClassInfo | None:
        """Return ClassInfo for one top-level ClassDef AST node."""
        if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(node):
            return None
        if FlextInfraUtilitiesRopeAnalysisAstHelpers.node_kind(node) != "ClassDef":
            return None
        name = getattr(node, "name", "")
        if not isinstance(name, str) or not name:
            return None
        line = getattr(node, "lineno", 1)
        raw_bases = getattr(node, "bases", ())
        if not isinstance(raw_bases, (list, tuple)):
            raw_bases = ()
        return m.Infra.ClassInfo(
            name=name,
            line=line if isinstance(line, int) and line > 0 else 1,
            bases=tuple(
                base_name
                for base in raw_bases
                if (
                    base_name
                    := FlextInfraUtilitiesRopeAnalysisAstHelpers._class_base_name(base)
                )
            ),
        )

    @staticmethod
    def class_base_name(node: p.AttributeProbe) -> str:
        """Return terminal base name from an AST base expression."""
        return FlextInfraUtilitiesRopeAnalysisAstHelpers._class_base_name(node)

    @staticmethod
    def _class_base_name(node: p.AttributeProbe) -> str:
        """Return terminal base name from an AST base expression."""
        if not FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(node):
            return ""
        for attr_name in ("id", "attr", "name"):
            value = getattr(node, attr_name, "")
            if isinstance(value, str) and value:
                return value
        subscript_value = getattr(node, "value", None)
        if (
            subscript_value is not None
            and FlextInfraUtilitiesRopeAnalysisAstHelpers.is_ast_node(subscript_value)
        ):
            return FlextInfraUtilitiesRopeAnalysisAstHelpers._class_base_name(
                subscript_value
            )
        return ""
