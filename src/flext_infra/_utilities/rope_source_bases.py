"""Qualified runtime-base discovery over captured, unpublished source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import ast
from pathlib import Path

from flext_infra import m, t
from flext_infra._utilities._rope_source_bases_runtime import (
    FlextInfraUtilitiesRopeSourceBasesRuntime,
)


class FlextInfraUtilitiesRopeSourceBases(
    FlextInfraUtilitiesRopeSourceBasesRuntime,
):
    """Index captured lexical bindings and resolve their qualified runtime bases."""

    @classmethod
    def lazy_module_aliases(
        cls,
        module: str,
        path: Path,
        source: str,
    ) -> t.StrMapping:
        """Read the ``install_lazy_exports`` namespace alias map of one module.

        Returns:
            The module's facade alias names routed to their lazy module paths.

        """
        parsed = ast.parse(source, filename=str(path))
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        aliases: t.MutableStrMapping = {}
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
                    for arg in (
                        *node.args,
                        *(keyword.value for keyword in node.keywords),
                    )
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
                    base = ".".join(parts[: len(parts) - depth + 1])
                    value = ".".join(part for part in (base, remainder) if part)
                aliases[key_node.value] = value
        return aliases

    @classmethod
    def runtime_bases(
        cls,
        project: t.Infra.RopeProject,
        sources: t.MappingKV[str, t.Pair[Path, str]],
        roots: t.StrSequence,
        extra_module_aliases: t.MappingKV[str, str] | None = None,
    ) -> t.StrTuple:
        """Resolve owned classes in C3 order and external classes through Rope.

        Only configured roots mark model evaluation boundaries. No first-party
        module is imported or resolved from disk when its planned source exists.
        Provider reexports follow Rope's declared import provenance. Their source
        declarations, not Rope's possibly incomplete superclass inference, supply
        the ordered bases. Missing references and invalid inheritance fail
        loudly.

        Returns:
            Sorted configured roots and derived Ruff-qualified base expressions.

        """
        definitions: t.MutableMappingKV[str, m.Infra.SourceClassDefinition] = {}
        modules = {
            module: cls.inventory(
                m.Infra.SourceBindingInventoryRequest(
                    project=project,
                    module=module,
                    path=path,
                    source=source,
                ),
                definitions,
            )
            for module, (path, source) in sources.items()
        }
        namespaces = {
            ".".join(parts[:index])
            for module in modules
            for parts in (module.split("."),)
            for index in range(1, len(parts) + 1)
        }
        module_aliases: t.MutableStrMapping = {}
        for module, (path, source) in sources.items():
            for alias, absolute in cls.lazy_module_aliases(
                module, path, source
            ).items():
                qualified = f"{module}.{alias}"
                if qualified not in namespaces:
                    module_aliases.setdefault(qualified, absolute)
        for alias, absolute in (extra_module_aliases or {}).items():
            if alias not in namespaces:
                module_aliases.setdefault(alias, absolute)
        return FlextInfraUtilitiesRopeSourceBasesRuntime(
            project, definitions, modules, namespaces, module_aliases
        ).discover_runtime_bases(roots)


__all__: list[str] = ["FlextInfraUtilitiesRopeSourceBases"]
