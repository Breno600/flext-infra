"""Derive a facade letter's class from the ``__all__`` that declares it.

The owner of a facade letter is the module that declares it in its own
``__all__`` next to the class it names (``__all__ = ["FlextCliModels", "m"]``).
Resolution follows the last module-scope binding of each name through imports
and plain or annotated aliases, reading editable and installed sources without
importing them. No class name is ever inferred from a package name.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from functools import lru_cache
from importlib.util import resolve_name
from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_infra import c
from flext_infra._utilities.private_import_facades import (
    FlextInfraUtilitiesPrivateImportFacades,
)
from flext_infra._utilities.rope_analysis import FlextInfraUtilitiesRopeAnalysis

if TYPE_CHECKING:
    from collections.abc import Iterator

    from flext_infra import t


class FlextInfraUtilitiesSemanticCutoverFacadeOwners:
    """Resolve facade letters to the class their declaring module names."""

    @classmethod
    def facade_classes(cls, package: str) -> t.StrMapping:
        """Map every letter ``package`` publishes to its declared facade class.

        Returns:
            The resulting ``t.StrMapping``.

        Raises:
            ValueError: If facade package is not importable for derivation.

        """
        modules = FlextInfraUtilitiesPrivateImportFacades.source_modules(
            {},
            (f"from {package} import *",),
        )
        indexed = modules.get(package)
        if indexed is None:
            msg = f"facade package is not importable for derivation: {package}"
            raise ValueError(msg)
        classes: MutableMapping[str, str] = {}
        for name in FlextInfraUtilitiesRopeAnalysis.public_export_names_source(
            indexed[0],
        ):
            owner = cls._facade_letter_class(modules, package, name)
            if owner is not None:
                classes[name] = owner
        return classes

    @classmethod
    def _facade_declared_owner(
        cls,
        modules: t.MappingKV[str, t.Pair[str, bool]],
        module: str,
        letter: str,
    ) -> str:
        """Return the class ``letter`` names, or raise with the missing proof.

        Returns:
            The class ``letter`` names, or raise with the missing proof.

        Raises:
            ValueError: If ``owner is None``.

        """
        owner = cls._facade_letter_class(modules, module, letter)
        if owner is None:
            msg = (
                f"{module}.{letter} is not declared with its facade class in the "
                "__all__ of the module that binds it"
            )
            raise ValueError(msg)
        return owner

    @classmethod
    def _facade_letter_class(
        cls,
        modules: t.MappingKV[str, t.Pair[str, bool]],
        module: str,
        letter: str,
    ) -> str | None:
        """Return the declared class of a letter that ``module`` publishes.

        Returns:
            The declared class of a letter that ``module`` publishes.

        Raises:
            ValueError: If ``cls._facade_declared_class(modules, module, owner,
                frozenset()) != resolved``.

        """
        resolved = cls._facade_declared_class(modules, module, letter, frozenset())
        if resolved is None:
            return None
        owner_module, owner = resolved
        if owner == letter:
            return None
        exports = FlextInfraUtilitiesRopeAnalysis.public_export_names_source(
            modules[owner_module][0],
        )
        if letter not in exports or owner not in exports:
            return None
        if cls._facade_declared_class(modules, module, owner, frozenset()) != resolved:
            msg = f"{module} does not publish {owner_module}.{owner} as {owner}"
            raise ValueError(msg)
        return owner

    @classmethod
    def _facade_declared_class(
        cls,
        modules: t.MappingKV[str, t.Pair[str, bool]],
        module: str,
        name: str,
        visiting: frozenset[str],
    ) -> t.Pair[str, str] | None:
        """Follow the last module-scope binding of ``name`` to its class.

        Returns:
            The resulting ``t.Pair[str, str] | None``.

        Raises:
            ValueError: If cyclic facade binding.

        """
        identity = f"{module}.{name}"
        if identity in visiting:
            msg = f"cyclic facade binding: {identity}"
            raise ValueError(msg)
        indexed = modules.get(module)
        if indexed is None:
            return None
        source, is_package = indexed
        package = module if is_package else module.rpartition(".")[0]
        target: t.Pair[str, str] | None = None
        declared = False
        # The generated lazy publication has one owner: the cached index.
        lazy = cls._facade_lazy_bindings(source, module)
        for node in cls._facade_module_statements(source, module):
            if isinstance(node, ast.AnnAssign) and node.value is None:
                # An annotation without a value does not rebind an existing name.
                continue
            if isinstance(node, ast.ClassDef) and node.name == name:
                target, declared = None, True
            elif isinstance(node, ast.Assign | ast.AnnAssign) and any(
                isinstance(bound, ast.Name) and bound.id == name
                for bound in (
                    node.targets if isinstance(node, ast.Assign) else (node.target,)
                )
            ):
                target = (
                    (module, node.value.id)
                    if isinstance(node.value, ast.Name)
                    else None
                )
                declared = False
            elif isinstance(node, ast.ImportFrom):
                for imported in node.names:
                    if (imported.asname or imported.name) == name:
                        source_module = (
                            resolve_name(
                                "." * node.level + (node.module or ""),
                                package,
                            )
                            if node.level
                            else node.module or ""
                        )
                        target, declared = (source_module, imported.name), False
        if declared:
            return module, name
        if target is None and name in lazy:
            # A lazy entry binds the name through its submodule; resolution
            # continues where the submodule defines it.
            sub = lazy[name]
            target = (f"{module}{sub}" if sub.startswith(".") else sub, name)
        # A submodule import binds a module, never a facade class.
        if target is None or ".".join(target) in modules:
            return None
        return cls._facade_declared_class(modules, *target, visiting | {identity})

    @staticmethod
    @lru_cache(maxsize=c.Infra.CONTENT_CACHE_MAXSIZE)
    def _facade_module_statements(
        source: str,
        module: str,
    ) -> t.VariadicTuple[ast.stmt]:
        """Parse one module source once per content; resolution only reads it.

        Every facade letter re-resolves its bindings through the same modules,
        and each conform plan derives the facades twice (plan and fixed-point
        replan), so the key is the exact source text: an edited module is a new
        key, never a stale tree.

        Returns:
            The resulting ``t.VariadicTuple[ast.stmt]``.

        """
        return tuple(
            FlextInfraUtilitiesSemanticCutoverFacadeOwners._facade_ordered_statements(
                ast.parse(source, filename=module).body,
            ),
        )

    @staticmethod
    @lru_cache(maxsize=256)
    def _facade_lazy_bindings(source: str, module: str) -> t.StrMapping:
        """Index the generated lazy publication of one module source once.

        The lazy publication IS a binding statement: every name it lists
        resolves through its submodule entry, exactly as install_lazy_exports
        resolves it at runtime. Walking that mapping once per name made every
        facade derivation quadratic in the package's export count; the key is
        the exact source text, so an edited module is a new key.

        Returns:
            The resulting ``t.StrMapping``.

        """
        bindings: MutableMapping[str, str] = {}
        for (
            node
        ) in FlextInfraUtilitiesSemanticCutoverFacadeOwners._facade_module_statements(
            source,
            module,
        ):
            if not (
                isinstance(node, ast.Assign | ast.AnnAssign)
                and node.value is not None
                and any(
                    isinstance(bound, ast.Name)
                    and bound.id == c.Infra.LAZY_IMPORTS_BINDING
                    for bound in (
                        node.targets if isinstance(node, ast.Assign) else (node.target,)
                    )
                )
            ):
                continue
            for dict_node in (
                d for d in ast.walk(node.value) if isinstance(d, ast.Dict)
            ):
                for key, value in zip(dict_node.keys, dict_node.values, strict=False):
                    if not (
                        isinstance(key, ast.Constant)
                        and isinstance(key.value, str)
                        and isinstance(value, ast.Tuple | ast.List)
                    ):
                        continue
                    for element in value.elts:
                        if isinstance(element, ast.Constant) and isinstance(
                            element.value,
                            str,
                        ):
                            bindings.setdefault(element.value, key.value)
        return MappingProxyType(bindings)

    @classmethod
    def _facade_ordered_statements(
        cls,
        body: t.SequenceOf[ast.stmt],
    ) -> Iterator[ast.stmt]:
        """Yield module-scope bindings in execution order, entering conditionals.

        Yields:
            Each ``ast.stmt``.

        """
        for node in body:
            if isinstance(node, ast.If):
                yield from cls._facade_ordered_statements(node.body)
                yield from cls._facade_ordered_statements(node.orelse)
            else:
                yield node


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverFacadeOwners"]
