"""Module-owner derivation for class nesting of loose modules.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import typing
from typing import TYPE_CHECKING

from flext_cli import u

from flext_infra import r, t
from flext_infra._utilities import FlextInfraUtilitiesCodegenNamespace

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import m, p


class FlextInfraUtilitiesSemanticCutoverNestingOwner:
    """Derive one module owner and the loose members it absorbs.

    A family module holds exactly one class, its facade-family owner. The
    owner's name is never listed: it is the declared owner when the module
    declares one, otherwise the project class stem (the source of
    ``require-project-class-stem``) followed by the family suffix and, for a
    module of a private family package, the module stem. Everything else at
    module level that ``ban-loose-module-object`` reports — a function other
    than ``main``, a value binding that is not a name alias or a typing
    declaration, any further class — is a member of that owner.
    """

    @staticmethod
    def _tail_name(node: ast.expr) -> str:
        """Return the last dotted segment of a name or attribute expression.

        Returns:
            The trailing identifier, or an empty string for other shapes.

        """
        if isinstance(node, ast.Subscript):
            node = node.value
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Name):
            return node.id
        return ""

    @classmethod
    def _is_typing_declaration(
        cls,
        value: ast.expr,
        annotation: ast.expr | None,
    ) -> bool:
        """Whether a binding is a typing declaration, not a module value.

        Typing declarations belong to ban-manual-typing-alias-outside-typings:
        an explicit ``TypeAlias`` binding, or a binding constructed by a class
        the ``typing`` module exports (TypeVar, ParamSpec, NewType...).

        Returns:
            The resulting ``bool``.

        """
        if (
            annotation is not None
            and getattr(typing, cls._tail_name(annotation), None) is typing.TypeAlias
        ):
            return True
        return isinstance(value, ast.Call) and isinstance(
            getattr(typing, cls._tail_name(value.func), None),
            type,
        )

    @classmethod
    def _is_pure_reference(cls, value: ast.expr) -> bool:
        """Whether ``value`` only names another binding (``A`` or ``A.B.C``).

        A pure reference is a compatibility alias the compat-alias phase owns
        (inline every consumer, then delete it); nesting it under the facade
        owner would publish the alias instead of removing it.

        Returns:
            The resulting ``bool``.

        """
        if isinstance(value, ast.Attribute):
            return cls._is_pure_reference(value.value)
        return isinstance(value, ast.Name)

    @classmethod
    def _loose_value_name(cls, node: ast.stmt) -> str | None:
        """Return the bound name when ``node`` is a loose module value binding.

        Returns:
            The bound identifier, or ``None`` for an allowed or foreign shape.

        """
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value, annotation = node.targets[0], node.value, None
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value, annotation = node.target, node.value, node.annotation
        else:
            return None
        loose = (
            isinstance(target, ast.Name)
            and not (target.id.startswith("__") and target.id.endswith("__"))
            and not cls._is_pure_reference(value)
            and not cls._is_typing_declaration(value, annotation)
        )
        return target.id if loose and isinstance(target, ast.Name) else None

    @classmethod
    def _loose_members(
        cls,
        tree: ast.Module,
        *,
        values: bool,
    ) -> t.VariadicTuple[str]:
        """Return loose functions and value bindings in module order.

        Returns:
            Every loose member name, in source order.

        """
        names: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name != "main" and not (
                    node.name.startswith("__") and node.name.endswith("__")
                ):
                    names.append(node.name)
            elif values and (name := cls._loose_value_name(node)) is not None:
                names.append(name)
        return tuple(dict.fromkeys(names))

    @staticmethod
    def _declared_names(tree: ast.Module) -> frozenset[str]:
        """Return the names the module declares in a literal ``__all__``.

        Returns:
            The declared export names, empty without a literal declaration.

        """
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], node.value
            elif isinstance(node, ast.AnnAssign):
                target, value = node.target, node.value
            else:
                continue
            if (
                isinstance(target, ast.Name)
                and target.id == "__all__"
                and isinstance(value, ast.List | ast.Tuple)
            ):
                return frozenset(
                    item.value
                    for item in value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                )
        return frozenset()

    @staticmethod
    def _definition_time_names(node: ast.stmt) -> frozenset[str]:
        """Names a member reads while its own definition executes.

        Returns:
            The identifiers loaded by decorators, defaults and bound values.

        """
        roots: list[ast.AST] = []
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            roots.extend(node.decorator_list)
            roots.extend(node.args.defaults)
            roots.extend(
                default for default in node.args.kw_defaults if default is not None
            )
        elif isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
            roots.append(node.value)
        return frozenset(
            name.id
            for root in roots
            for name in ast.walk(root)
            if isinstance(name, ast.Name)
        )

    @classmethod
    def _movable_members(
        cls,
        tree: ast.Module,
        members: t.VariadicTuple[str],
        *,
        owner: str,
        module_name: str,
    ) -> p.Result[t.VariadicTuple[str]]:
        """Return the loose members the owner body can hold, in module order.

        A member that reads the owner while it is being defined (an alias of
        an owner member, a decorator or default built from it) cannot live in
        the owner's body, exactly like a class bound to the owner by
        inheritance: it stays at module level. A member the owner reads while
        ITSELF is being created (a base, or a ``metaclass=`` factory call)
        stays module level too: the owner does not exist while its creation
        expressions evaluate. Every member such a bound member references in
        its body stays module level as well, so the bound member's bare-name
        resolution keeps resolving at module scope. A function rebinding
        module state through ``global`` would lose that state as a static
        method, so it fails the plan naming the module and the member.

        Returns:
            The movable members, or a failure naming the module and member.

        """
        checked = r[t.VariadicTuple[str]]
        selected = frozenset(members)
        nodes_by_member: dict[str, ast.stmt] = {}
        for node in tree.body:
            name = (
                node.name
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                else cls._loose_value_name(node)
            )
            if name is not None and name in selected:
                nodes_by_member[name] = node
        bound: set[str] = cls._creation_bound(tree, nodes_by_member, selected, owner)
        for node in tree.body:
            name = (
                node.name
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                else cls._loose_value_name(node)
            )
            if name is None or name not in selected or name in bound:
                continue
            if owner in cls._definition_time_names(node):
                bound.add(name)
                continue
            if any(isinstance(inner, ast.Global) for inner in ast.walk(node)):
                return checked.fail(
                    f"class-nesting cannot move {module_name}.{name} under "
                    f"{owner}: it rebinds module state through global",
                )
        return checked.ok(tuple(name for name in members if name not in bound))

    @classmethod
    def _creation_bound(
        cls,
        tree: ast.Module,
        nodes_by_member: t.MappingKV[str, ast.stmt],
        selected: frozenset[str],
        owner: str,
    ) -> set[str]:
        """Members the owner creation expressions and their closure read.

        The seed binds every selected member the owner reads while being
        created (a base, or a ``metaclass=`` factory call); the closure keeps
        every member such a bound member loads, so the bound member's
        bare-name resolution keeps resolving at module scope.

        Returns:
            The members that must stay at module level.

        """
        owner_node = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == owner
            ),
            None,
        )
        bound: set[str] = set()
        if owner_node is not None:
            creation_roots: tuple[ast.AST, ...] = (
                *owner_node.decorator_list,
                *owner_node.bases,
                *owner_node.keywords,
            )
            creation_reads = frozenset(
                name.id
                for root in creation_roots
                for name in ast.walk(root)
                if isinstance(name, ast.Name)
            )
            bound.update(creation_reads & selected)
        while True:
            loaded_by_bound: set[str] = set()
            for name in bound:
                member_node = nodes_by_member.get(name)
                if member_node is not None:
                    loaded_by_bound |= cls._body_load_names(member_node)
            newly_bound = (loaded_by_bound & selected) - bound
            if not newly_bound:
                break
            bound.update(newly_bound)
        return bound

    @staticmethod
    def _body_load_names(node: ast.stmt) -> frozenset[str]:
        """Names a member's whole body loads.

        Returns:
            Every identifier read anywhere inside the member, including the
            definition-time reads (decorators, defaults, bound values).

        """
        return frozenset(
            name.id
            for name in ast.walk(node)
            if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Load)
        )

    @staticmethod
    def _module_owner(
        convention: m.Infra.RopeModuleConvention,
        file_path: Path,
        classes: t.MappingKV[str, ast.ClassDef],
        exports: frozenset[str],
    ) -> p.Result[str]:
        """Return the declared owner, or the owner the family derivation names.

        Returns:
            The owner class name, or a failure when the derivation is ambiguous.

        """
        derived = r[str]
        policy = convention.module_policy
        namespace = FlextInfraUtilitiesCodegenNamespace
        families = namespace.facade_families()
        directory_family = namespace.facade_family_of_directory(file_path.parent.name)
        file_family = namespace.facade_family_of_file(file_path.name)
        if directory_family is not None:
            suffix_root = families[directory_family].suffix
            suffix = suffix_root + u.derive_class_stem(file_path.stem.strip("_"))
        elif file_family is not None:
            suffix_root = suffix = families[file_family].suffix
        else:
            return derived.fail(
                f"class-nesting found no facade family for {convention.module_name}",
            )
        prefix = policy.project_prefix
        if not prefix:
            return derived.fail(
                "class-nesting cannot derive a module owner without a project "
                f"class stem for {convention.module_name}",
            )
        family_prefix = f"{prefix}{suffix_root}"
        declared = policy.expected_family
        # The declared owner is the published facade class, or a class the
        # module declares that carries the family name; a record or sentinel
        # the module happens to export alone is never the module's owner.
        if (
            declared is not None
            and declared in classes
            and (
                policy.expected_alias is not None or declared.startswith(family_prefix)
            )
        ):
            return derived.ok(declared)
        owner = f"{prefix}{suffix}"
        if owner in classes:
            return derived.ok(owner)
        # A rival is a class the module itself publishes as a family owner:
        # declared in ``__all__`` and named by the project stem plus the family
        # suffix. Any other class (a record, a sentinel, an unpublished
        # helper) is a member, whatever its name.
        rivals = sorted(
            name
            for name in classes
            if name.startswith(family_prefix) and name in exports
        )
        if rivals:
            return derived.fail(
                "class-nesting requires exactly one declared module owner for "
                f"{convention.module_name}; discovered: {', '.join(rivals)} "
                f"(derived owner {owner})",
            )
        return derived.ok(owner)


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverNestingOwner"]
