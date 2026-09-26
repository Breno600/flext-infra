"""Shared Rope-AST primitives for namespace governance rules."""

from __future__ import annotations

from ast import Import, ImportFrom
from typing import TYPE_CHECKING

from flext_infra import c, u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraNamespaceRulesBase:
    """Provide deterministic AST and layer operations to every rule family."""

    @staticmethod
    def kind(node: p.AttributeProbe) -> str:
        """Return the Rope-compatible AST node kind."""
        return u.Infra.node_kind(u.Infra.ensure_ast_node(node))

    @staticmethod
    def walk(node: p.AttributeProbe) -> t.SequenceOf[t.Infra.RopeAstNode]:
        """Walk a Rope-provided AST without reparsing source text."""
        return tuple(u.Infra.walk_ast_nodes(u.Infra.ensure_ast_node(node)))

    @classmethod
    def outer_classes(cls, tree: p.AttributeProbe) -> t.SequenceOf[t.Infra.RopeAstNode]:
        """Return top-level class declarations."""
        return tuple(
            node
            for node in (getattr(tree, "body", ()) or ())
            if cls.kind(node) == "ClassDef"
        )

    @classmethod
    def name_of(cls, node: p.AttributeProbe) -> str:
        """Return the final identifier represented by an AST expression."""
        if node is None:
            return ""
        kind = cls.kind(node)
        if kind == "Name":
            value = getattr(node, "id", "")
            return value if isinstance(value, str) else ""
        if kind == "Attribute":
            value = getattr(node, "attr", "")
            return value if isinstance(value, str) else ""
        if kind == "Call":
            return cls.name_of(getattr(node, "func", None))
        if kind in {"FunctionDef", "AsyncFunctionDef", "ClassDef"}:
            # Why (cosmos-3flk9): definition nodes carry their identifier on
            # ``.name``; without this branch every name-based structure
            # exemption (the ``cli.py`` ``main`` entrypoint, facade classes,
            # alias publishes) silently resolved to "" and flagged as a
            # violation.
            value = getattr(node, "name", "")
            return value if isinstance(value, str) else ""
        return ""

    @classmethod
    def dotted_name(cls, node: p.AttributeProbe) -> str:
        """Return a dotted Name/Attribute expression."""
        if node is None:
            return ""
        if cls.kind(node) == "Name":
            return cls.name_of(node)
        if cls.kind(node) != "Attribute":
            return ""
        parent = cls.dotted_name(getattr(node, "value", None))
        leaf = cls.name_of(node)
        return f"{parent}.{leaf}" if parent else leaf

    @classmethod
    def is_type_checking_guard(cls, node: p.AttributeProbe) -> bool:
        """Return whether a statement is exactly ``if TYPE_CHECKING``."""
        return (
            cls.kind(node) == "If"
            and cls.name_of(getattr(node, "test", None)) == "TYPE_CHECKING"
        )

    @classmethod
    def imports_with_context(
        cls, tree: p.AttributeProbe
    ) -> t.SequenceOf[t.Pair[t.Infra.PythonImportNode, bool]]:
        """Return every import with its TYPE_CHECKING-only state."""
        guarded = {
            id(child)
            for node in cls.walk(tree)
            if cls.is_type_checking_guard(node)
            for child in cls.walk(node)
            if cls.kind(child) in {"Import", "ImportFrom"}
        }
        return tuple(
            (node, id(node) in guarded)
            for node in cls.walk(tree)
            if isinstance(node, (Import, ImportFrom))
        )

    @classmethod
    def imported_callable_names(
        cls, tree: p.AttributeProbe
    ) -> t.MappingKV[t.Pair[int, int], frozenset[str]]:
        """Index imported call/decorator names from the existing Rope AST."""
        bindings: t.MutableMappingKV[str, str] = {}
        for node in cls.walk(tree):
            kind = cls.kind(node)
            if kind == "Import":
                for alias in getattr(node, "names", ()) or ():
                    imported = getattr(alias, "name", "")
                    local = getattr(alias, "asname", None) or str(imported).split(".")[0]
                    if isinstance(imported, str) and isinstance(local, str):
                        bindings[local] = imported if getattr(alias, "asname", None) else local
            elif kind == "ImportFrom":
                module = getattr(node, "module", "")
                if not isinstance(module, str):
                    continue
                for alias in getattr(node, "names", ()) or ():
                    imported = getattr(alias, "name", "")
                    local = getattr(alias, "asname", None) or imported
                    if isinstance(imported, str) and isinstance(local, str):
                        bindings[local] = f"{module}.{imported}"
        resolved: t.MutableMappingKV[t.Pair[int, int], frozenset[str]] = {}
        for node in cls.walk(tree):
            callable_node = getattr(node, "func", None) if cls.kind(node) == "Call" else node
            if cls.kind(callable_node) not in {"Name", "Attribute"}:
                continue
            dotted = cls.dotted_name(callable_node)
            root, separator, suffix = dotted.partition(".")
            imported = bindings.get(root)
            if imported is None:
                continue
            qualified = f"{imported}.{suffix}" if separator else imported
            resolved[cls.line(callable_node), getattr(callable_node, "col_offset", 0)] = frozenset({qualified})
        return resolved

    @staticmethod
    def violations(code: str, messages: t.StrSequence) -> t.StrSequence:
        """Prefix ordered violations with stable rule identifiers."""
        return tuple(
            f"[{code}-{index:03d}] {message}"
            for index, message in enumerate(messages, start=1)
        )

    @staticmethod
    def layer_of_path(filepath: Path) -> str | None:
        """Resolve a module's architectural layer from canonical path data."""
        direct = c.Infra.NAMESPACE_LAYER_BY_FILE.get(filepath.name)
        if direct is not None:
            return direct
        for part in filepath.parts:
            if layer := c.Infra.NAMESPACE_LAYER_BY_FAMILY.get(part):
                return layer
        return None

    @staticmethod
    def layer_of_module(module: str, package_name: str) -> str | None:
        """Resolve an imported local module's canonical architectural layer."""
        if module == package_name:
            return None
        prefix = f"{package_name}."
        if not module.startswith(prefix):
            return None
        parts = module.removeprefix(prefix).split(".")
        first = parts[0]
        direct = c.Infra.NAMESPACE_LAYER_BY_FILE.get(f"{first}.py")
        return direct or c.Infra.NAMESPACE_LAYER_BY_FAMILY.get(first)

    @staticmethod
    def line(node: p.AttributeProbe) -> int:
        """Return a stable source line for one AST node."""
        value = getattr(node, "lineno", 1)
        return value if isinstance(value, int) else 1


__all__: list[str] = ["FlextInfraNamespaceRulesBase"]
