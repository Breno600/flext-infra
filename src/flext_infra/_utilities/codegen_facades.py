"""Discovery-driven projection of utility owners onto the public facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from flext_infra import c
from flext_infra._utilities.namespace import FlextInfraUtilitiesCodegenNamespace
from flext_infra._utilities.rope_core import FlextInfraUtilitiesRopeCore
from flext_infra._utilities.rope_module_patch import FlextInfraUtilitiesRopeModulePatch
from flext_infra._utilities.rope_runtime import FlextInfraUtilitiesRopeRuntime

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesCodegenFacades:
    """Project utility owners required by real public-facade consumers."""

    @staticmethod
    def facade_module_path(pkg_dir: Path, family: str) -> Path | None:
        """Return the package module that declares facade letter ``family``.

        The owner of a facade letter is the module that publishes it in its own
        ``__all__`` (generator law p.1); it is derived from the package, never
        from a letter-to-filename table. ``None`` means no module declares it.

        Returns:
            The package module that declares facade letter ``family``.

        Raises:
            ValueError: If facade letter.

        """
        owners = tuple(
            module
            for module in sorted(pkg_dir.glob(c.Infra.EXT_PYTHON_GLOB))
            if module.name != c.Infra.INIT_PY
            and family
            in FlextInfraUtilitiesRopeModulePatch.facade_letter_names_source(
                module.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            )
        )
        if len(owners) > 1:
            message = (
                f"facade letter {family!r} is declared by more than one module "
                f"in {pkg_dir}: {[owner.name for owner in owners]}"
            )
            raise ValueError(message)
        return owners[0] if owners else None

    @classmethod
    def render_utility_facade(
        cls,
        pkg_dir: Path,
        *,
        family: Literal["u", "p"] = "u",
    ) -> str | None:
        """Render uniquely discovered utility or protocol owners without a registry.

        Real ``u.<Namespace>.<method>()`` consumers select methods. Definitions
        Protocol references ``p.<Namespace>.<Type>`` select nested declarations.
        The corresponding private family selects unique owners. Existing
        facade content remains unchanged except for missing imports and bases.

        Returns:
            The resulting ``str | None``.

        Raises:
            ValueError: If utility owners in; or if ambiguous.

        """
        facade_path = cls.facade_module_path(pkg_dir, family)
        owners_dir = (
            pkg_dir
            / FlextInfraUtilitiesCodegenNamespace.facade_families()[family].directory
        )
        owners_exist = owners_dir.is_dir()
        # Why: only owners-without-facade is incomplete -- the owners would have
        # no public surface at all. A facade with no owners directory is the
        # legitimate pure re-export shape this same generator emits for a package
        # that adds no local utilities (src/flext: `class FlextRootUtilities(u)`),
        # and there is simply nothing to project onto it.
        if not owners_exist:
            return None
        if facade_path is None:
            # Conform preflights its family directories before rendering files.
            # An empty directory contains no owner requiring a public surface.
            if not any(owners_dir.iterdir()):
                return None
            message = f"utility owners in {pkg_dir} have no public facade"
            raise ValueError(message)
        owners, ancestors = cls._utility_owners(owners_dir, family=family)
        source: str = facade_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        facade, namespace = cls._facade_classes(
            ast.parse(source, filename=str(facade_path)),
            facade_path,
        )
        nested_namespace = namespace is not facade
        reachable = cls._reachable_bases(
            tuple(cls._base_name(base) for base in namespace.bases),
            ancestors,
        )
        additions: list[t.Pair[str, str]] = []
        for method in sorted(
            cls._required_methods(
                pkg_dir,
                facade_path,
                nested_namespace=nested_namespace,
                namespace=namespace.name,
                family=family,
            ),
        ):
            candidates = tuple(
                (module, class_name)
                for module, class_name, methods in owners
                if method in methods
            )
            if not candidates or any(
                class_name in reachable for _module, class_name in candidates
            ):
                continue
            if len(candidates) != 1:
                detail = ", ".join(f"{module}:{name}" for module, name in candidates)
                message = (
                    f"ambiguous {family}.{namespace.name} owner for {method}: {detail}"
                )
                raise ValueError(message)
            module, class_name = candidates[0]
            additions.append((module, class_name))
            reachable.update(cls._reachable_bases((class_name,), ancestors))
        if not additions:
            return source
        updated = cls._insert_imports(
            source,
            facade,
            additions,
            package=pkg_dir.name,
            family=family,
        )
        _, namespace = cls._facade_classes(
            ast.parse(updated, filename=str(facade_path)),
            facade_path,
        )
        return cls._insert_bases(updated, namespace, additions)

    @staticmethod
    def _required_methods(
        pkg_dir: Path,
        facade_path: Path,
        *,
        nested_namespace: bool,
        namespace: str,
        family: Literal["u", "p"],
    ) -> frozenset[str]:
        methods: set[str] = set()
        with FlextInfraUtilitiesRopeCore.open_project(pkg_dir.parent) as project:
            for path in sorted(pkg_dir.rglob(f"*{c.Infra.EXT_PYTHON}")):
                if path == facade_path:
                    continue
                source = path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
                # Generated initializers propagate declarations; they are not
                # authored consumers and may await replacement in this plan.
                if path.name == c.Infra.INIT_PY and source.startswith(
                    c.Infra.AUTOGEN_HEADERS,
                ):
                    continue
                tree = ast.parse(source, filename=str(path))
                pymodule: t.Infra.RopePyModule | None = None
                lines = source.splitlines(keepends=True)
                for node in ast.walk(tree):
                    reference = node.func if isinstance(node, ast.Call) else node
                    if not isinstance(reference, ast.Attribute):
                        continue
                    if family == "u" and not isinstance(node, ast.Call):
                        continue
                    receiver = reference.value
                    if nested_namespace:
                        if (
                            not isinstance(receiver, ast.Attribute)
                            or receiver.attr != namespace
                        ):
                            continue
                        receiver = receiver.value
                    if not isinstance(receiver, ast.Name) or receiver.id != family:
                        continue
                    if pymodule is None:
                        resource = project.get_resource(
                            path.relative_to(pkg_dir.parent).as_posix(),
                        )
                        pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(
                            project,
                            resource,
                        )
                    offset = sum(map(len, lines[: receiver.lineno - 1]))
                    prefix = lines[receiver.lineno - 1].encode(c.Cli.ENCODING_DEFAULT)
                    offset += len(
                        prefix[: receiver.col_offset].decode(c.Cli.ENCODING_DEFAULT),
                    )
                    binding = FlextInfraUtilitiesRopeRuntime.imported_name_at(
                        pymodule,
                        offset,
                    )
                    if binding is None or binding.imported_name != family:
                        continue
                    declared = FlextInfraUtilitiesRopeRuntime.imported_module_path(
                        project,
                        binding,
                    )
                    if declared not in {
                        pkg_dir,
                        pkg_dir / c.Infra.INIT_PY,
                        facade_path,
                    }:
                        continue
                    methods.add(reference.attr)
        return frozenset(method for method in methods if not method.startswith("_"))

    @staticmethod
    def _utility_owners(
        owners_dir: Path,
        *,
        family: Literal["u", "p"],
    ) -> t.Pair[
        t.VariadicTuple[t.Triple[str, str, frozenset[str]]],
        t.MappingKV[str, frozenset[str]],
    ]:
        owners: list[t.Triple[str, str, frozenset[str]]] = []
        ancestors: MutableMapping[str, frozenset[str]] = {}
        for path in sorted(owners_dir.glob("*.py")):
            if path.name == c.Infra.INIT_PY:
                continue
            tree = ast.parse(
                path.read_text(encoding=c.Cli.ENCODING_DEFAULT),
                filename=str(path),
            )
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                if family == "u":
                    members = tuple(
                        member
                        for member in node.body
                        if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef)
                    )
                else:
                    members = tuple(
                        member
                        for member in node.body
                        if isinstance(member, ast.ClassDef)
                    )
                methods = frozenset(
                    member.name for member in members if not member.name.startswith("_")
                )
                owners.append((path.stem, node.name, methods))
                ancestors[node.name] = frozenset(
                    name
                    for base in node.bases
                    if (name := FlextInfraUtilitiesCodegenFacades._base_name(base))
                )
        return tuple(owners), ancestors

    @staticmethod
    def _facade_classes(
        tree: ast.Module,
        path: Path,
    ) -> t.Pair[ast.ClassDef, ast.ClassDef]:
        facades = tuple(node for node in tree.body if isinstance(node, ast.ClassDef))
        if len(facades) != 1:
            message = f"expected one utility facade class in {path}"
            raise ValueError(message)
        nested = tuple(
            node for node in facades[0].body if isinstance(node, ast.ClassDef)
        )
        if len(nested) > 1:
            message = f"expected at most one utility namespace class in {path}"
            raise ValueError(message)
        return facades[0], nested[0] if nested else facades[0]

    @classmethod
    def _base_name(cls, base: ast.expr) -> str:
        if isinstance(base, ast.Name):
            return base.id
        if isinstance(base, ast.Attribute):
            return base.attr
        # Why: a generic base carries the same owner as its unsubscripted form.
        # `class X(FlextLdifUtilitiesTransformer[m.Ldif.Entry])` names
        # FlextLdifUtilitiesTransformer exactly like the bare base does, and the
        # type argument decides nothing about facade reachability.
        if isinstance(base, ast.Subscript):
            return cls._base_name(base.value)
        message = f"unsupported utility facade base: {ast.dump(base)}"
        raise ValueError(message)

    @staticmethod
    def _reachable_bases(
        roots: t.SequenceOf[str],
        ancestors: t.MappingKV[str, frozenset[str]],
    ) -> set[str]:
        reachable = set(roots)
        pending = list(roots)
        while pending:
            for base in ancestors.get(pending.pop(), frozenset()):
                if base not in reachable:
                    reachable.add(base)
                    pending.append(base)
        return reachable

    @staticmethod
    def _insert_imports(
        source: str,
        facade: ast.ClassDef,
        additions: t.SequenceOf[t.Pair[str, str]],
        *,
        package: str,
        family: Literal["u", "p"],
    ) -> str:
        # The owner lives in the package being rendered. Naming this project
        # instead made every generated consumer facade import from flext-infra,
        # a module that does not exist in the consumer's own distribution.
        lines = source.splitlines(keepends=True)
        directory = FlextInfraUtilitiesCodegenNamespace.facade_families()[
            family
        ].directory
        rendered = [
            f"from {package}.{directory}.{module} import (\n    {class_name},\n)\n"
            for module, class_name in additions
        ]
        lines[facade.lineno - 1 : facade.lineno - 1] = [*rendered, "\n"]
        return "".join(lines)

    @staticmethod
    def _insert_bases(
        source: str,
        namespace: ast.ClassDef,
        additions: t.SequenceOf[t.Pair[str, str]],
    ) -> str:
        if not namespace.bases:
            message = "utility namespace has no canonical base chain"
            raise ValueError(message)
        last_base = namespace.bases[-1]
        if last_base.end_lineno is None or last_base.end_col_offset is None:
            message = "utility namespace base has no source span"
            raise ValueError(message)
        lines = source.encode(c.Cli.ENCODING_DEFAULT).splitlines(keepends=True)
        offset = sum(map(len, lines[: last_base.end_lineno - 1]))
        offset += last_base.end_col_offset
        separator = (
            ", "
            if last_base.lineno == namespace.lineno
            else ",\n" + " " * last_base.col_offset
        )
        inserted = "".join(separator + name for _module, name in additions)
        encoded = b"".join(lines)
        return (
            encoded[:offset]
            + inserted.encode(c.Cli.ENCODING_DEFAULT)
            + encoded[offset:]
        ).decode(c.Cli.ENCODING_DEFAULT)


__all__: list[str] = ["FlextInfraUtilitiesCodegenFacades"]
