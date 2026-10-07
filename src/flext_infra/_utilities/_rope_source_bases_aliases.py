"""Alias and lazy-module resolution over the captured source inventory.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from flext_infra import m, t


class FlextInfraUtilitiesRopeSourceBasesAliases:
    """Alias and lazy-module resolution part of the source-bases composite."""

    @staticmethod
    def _is_type_checking_test(test: ast.expr) -> bool:
        """Return whether one condition gate is the TYPE_CHECKING constant.

        Returns:
            True for the bare name and for the ``typing`` /
            ``typing_extensions`` attribute forms.

        """
        if isinstance(test, ast.Name):
            return test.id == "TYPE_CHECKING"
        return (
            isinstance(test, ast.Attribute)
            and test.attr == "TYPE_CHECKING"
            and isinstance(test.value, ast.Name)
            and test.value.id in {"typing", "typing_extensions"}
        )

    @staticmethod
    def _reference(
        expression: ast.expr,
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
        module: str,
    ) -> m.Infra.SourceClassReference:
        """Capture the binding visible when a base expression is evaluated.

        Returns:
            The bound identity, attributes, and Ruff-qualified spelling.

        Raises:
            ValueError: If the expression or its lexical binding is not a class.

        """
        # Unwrap Subscript and Attribute in ONE loop: a chained form like
        # `_CLUSTERS[0].environment` is Attribute(Subscript(Name)) — consuming
        # attributes first left the inner Subscript unprocessed and raised
        # "Unsupported class reference" on every consumer whose SSOT-derived
        # constants subscript a module-level binding (cosmos-main
        # tests/constants.py, bead cosmos-gamnt).
        attributes: list[str] = []
        while isinstance(expression, ast.Subscript | ast.Attribute):
            if isinstance(expression, ast.Attribute):
                attributes.insert(0, expression.attr)
            expression = expression.value
        if not isinstance(expression, ast.Name):
            message = (
                f"Unsupported class reference in {module}: {ast.unparse(expression)}"
            )
            raise ValueError(message)
        name = expression.id
        if name in bindings:
            binding = bindings[name]
            if binding is None:
                message = f"Non-class binding used as a base in {module}: {name}"
                raise ValueError(message)
        else:
            binding = m.Infra.SourceClassReference(
                target="builtins",
                attributes=(name,),
                qualified_base=f"{module}.{name}",
            )
        return m.Infra.SourceClassReference(
            target=binding.target,
            attributes=(*binding.attributes, *attributes),
            qualified_base=".".join((binding.qualified_base, *attributes)),
        )

    @classmethod
    def _stdlib_backing_module(cls, target: str) -> str | None:
        """Return the importable real module backing one virtual stdlib module.

        Returns:
            The backing module name when the target imports at runtime and its
            declaration file is importable under its own stem; otherwise None.

        """
        if cls._stdlib_backing_cache is None:
            cls._stdlib_backing_cache = {}
        cached = cls._stdlib_backing_cache.get(target, "")
        if cached:
            return cached or None
        backing: str | None = None
        try:
            runtime = importlib.import_module(target)
        except Exception:
            runtime = None
        file = getattr(runtime, "__file__", None)
        if file:
            stem = Path(file).stem
            if stem != target.rpartition(".")[-1] and importlib.util.find_spec(stem):
                backing = stem
        cls._stdlib_backing_cache[target] = backing or ""
        return backing

    _stdlib_backing_cache: dict[str, str] | None = None

    @classmethod
    def lazy_module_aliases(
        cls,
        module: str,
        path: Path,
        source: str,
    ) -> dict[str, str]:
        """Read the ``install_lazy_exports`` namespace alias map of one module.

        The canonical package facade binds its public namespace names (``m``,
        ``p``, ``t`` and siblings) to provider modules through a lazy-exports
        call whose final argument is the alias mapping. Those names are module
        reexports, not lexical imports, so the lexical inventory cannot see
        them; base references qualified through the facade (``m.BaseModel``
        with ``from <pkg> import m``) must rewrite to the provider module
        before namespace resolution.

        Returns:
            Alias name to absolute provider module path.

        """
        try:
            parsed = ast.parse(source, filename=str(path))
        except SyntaxError:
            return {}
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        aliases: dict[str, str] = {}
        for node in ast.walk(parsed):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "install_lazy_exports"
            ):
                continue
            mapping = next(
                (
                    arg
                    for arg in (*node.args, *node.keywords)
                    if isinstance(arg, ast.Dict)
                    or (
                        isinstance(arg, ast.Call)
                        and isinstance(arg.func, ast.Name)
                        and arg.func.id == "MappingProxyType"
                    )
                ),
                None,
            )
            if isinstance(mapping, ast.Call):
                mapping = mapping.args[0] if mapping.args else None
            if not isinstance(mapping, ast.Dict):
                continue
            for key_node, value_node in zip(mapping.keys, mapping.values, strict=False):
                if not (
                    isinstance(key_node, ast.Constant)
                    and isinstance(key_node.value, str)
                    and isinstance(value_node, ast.Constant)
                    and isinstance(value_node.value, str)
                ):
                    continue
                value = value_node.value
                if value.startswith("."):
                    parts = package.split(".") if package else []
                    depth = len(value) - len(value.lstrip("."))
                    remainder = value.lstrip(".")
                    if depth > len(parts):
                        continue
                    base = (
                        ".".join(parts[: len(parts) - depth + 1]) if depth else package
                    )
                    value = ".".join(part for part in (base, remainder) if part)
                aliases[key_node.value] = value
        return aliases

    @staticmethod
    def _subscript_root_name(target: ast.Subscript) -> str:
        """Return the root name of a subscript target's value expression."""
        value = target.value
        if isinstance(value, ast.Attribute):
            value = value.value
        return value.id if isinstance(value, ast.Name) else ""
