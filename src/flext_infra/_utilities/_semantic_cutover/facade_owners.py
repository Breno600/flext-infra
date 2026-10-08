"""Derive a facade letter's class from the ``__all__`` that declares it.

The owner of a facade letter is the module that declares it in its own
``__all__`` next to the class it names (``__all__ = ["FlextCliModels", "m"]``).
Resolution follows the last runtime module-scope binding of each name through imports
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
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_infra import c
from flext_infra._utilities import (
    FlextInfraUtilitiesPrivateImportFacades,
    FlextInfraUtilitiesRopeAnalysis,
    FlextInfraUtilitiesRopeSourceBases,
    FlextInfraUtilitiesRopeSourceBindingCollector,
)

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

    @staticmethod
    def _assigns_name(
        node: ast.Assign | ast.AnnAssign,
        name: str,
    ) -> bool:
        """Report whether one assignment statement binds ``name``.

        Returns:
            The resulting ``bool``.

        """
        return any(
            isinstance(bound, ast.Name) and bound.id == name
            for bound in (
                node.targets if isinstance(node, ast.Assign) else (node.target,)
            )
        )

    @staticmethod
    def _assigned_value_binding(
        node: ast.Assign | ast.AnnAssign,
        module: str,
    ) -> t.Pair[str, str] | None:
        """Return the ``module.name`` target of a plain-name value, else ``None``.

        Returns:
            The resulting ``t.Pair[str, str] | None``.

        """
        return (module, node.value.id) if isinstance(node.value, ast.Name) else None

    @staticmethod
    def _imported_binding(
        node: ast.ImportFrom,
        name: str,
        package: str,
    ) -> t.Pair[str, str] | None:
        """Resolve the import that binds ``name`` relative to ``package``.

        Returns:
            The resulting ``t.Pair[str, str] | None``.

        """
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
                return source_module, imported.name
        return None

    @classmethod
    def _facade_binding_state(
        cls,
        source: str,
        module: str,
        name: str,
        package: str,
    ) -> t.Pair[t.Pair[str, str] | None, bool]:
        """Follow module-scope execution order to the last binding of ``name``.

        Returns:
            The resulting ``(target, declared)`` binding state after the body.

        """
        target: t.Pair[str, str] | None = None
        declared = False
        for node in cls._facade_module_statements(source, module):
            if isinstance(node, ast.AnnAssign) and node.value is None:
                # An annotation without a value does not rebind an existing name.
                continue
            if isinstance(node, ast.ClassDef) and node.name == name:
                target, declared = None, True
            elif isinstance(node, ast.Assign | ast.AnnAssign) and cls._assigns_name(
                node,
                name,
            ):
                target = cls._assigned_value_binding(node, module)
                declared = False
            elif isinstance(node, ast.ImportFrom):
                binding = cls._imported_binding(node, name, package)
                if binding is not None:
                    target, declared = binding, False
        return target, declared

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
        target, declared = cls._facade_binding_state(source, module, name, package)
        if declared:
            return module, name
        # The generated lazy publication has one reader: the rope aliases owner.
        lazy = cls._facade_lazy_bindings(source, module, is_package=is_package)
        if target is None and name in lazy:
            # A lazy entry binds the name through its provider module;
            # resolution continues where that module defines it.
            target = (lazy[name], name)
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
        key, never a stale tree. TYPE_CHECKING declarations belong to the static
        source inventory, not this runtime publication view.

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
    def _facade_lazy_bindings(
        source: str,
        module: str,
        *,
        is_package: bool,
    ) -> t.StrMapping:
        """Index the generated lazy publication of one module source once.

        The lazy publication IS a binding statement: every name the
        ``install_lazy_exports`` map lists resolves through its provider
        module, exactly as it resolves at runtime. The map has one reader
        (``FlextInfraUtilitiesRopeSourceBases.lazy_module_aliases``),
        which understands the generated shape; the key is the exact source
        text, so an edited module is a new key.

        Returns:
            Published name to absolute provider module.

        """
        path = Path(
            c.Infra.INIT_PY if is_package else f"{module.rpartition('.')[2]}.py",
        )
        return MappingProxyType(
            FlextInfraUtilitiesRopeSourceBases.lazy_module_aliases(
                module,
                path,
                source,
            ),
        )

    @classmethod
    def _facade_ordered_statements(
        cls,
        body: t.SequenceOf[ast.stmt],
    ) -> Iterator[ast.stmt]:
        """Yield runtime bindings, excluding static-only TYPE_CHECKING bodies.

        Other conditions retain the existing conservative branch traversal.

        Yields:
            Each ``ast.stmt``.

        """
        for node in body:
            if isinstance(node, ast.If):
                is_static_only = (
                    FlextInfraUtilitiesRopeSourceBindingCollector.type_checking_test(
                        node.test,
                    )
                )
                if not is_static_only:
                    yield from cls._facade_ordered_statements(node.body)
                yield from cls._facade_ordered_statements(node.orelse)
            else:
                yield node


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverFacadeOwners"]
