"""Alias and lazy-module resolution over the captured source inventory.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


class FlextInfraUtilitiesRopeSourceBasesAliases:
    """Alias and lazy-module resolution part of the source-bases composite."""

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
        except ImportError:
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
        # A generated module that does not parse is a defect to surface, never
        # an empty alias map (fail loud).
        parsed = ast.parse(source, filename=str(path))
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


__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBasesAliases"]
