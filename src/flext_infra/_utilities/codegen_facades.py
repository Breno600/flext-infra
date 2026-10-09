"""Consumer-driven projection of utility, protocol and model facade owners.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections.abc import MutableMapping
from pathlib import Path
from typing import Literal

from libcst import Arg, ClassDef, Module, Name, parse_module
from libcst.metadata import MetadataWrapper, PositionProvider

from flext_infra import c, t
from flext_infra._utilities import (
    FlextInfraUtilitiesCodegenNamespace,
    FlextInfraUtilitiesRopeCore,
    FlextInfraUtilitiesRopeModulePatch,
    FlextInfraUtilitiesRopeRuntime,
)


class FlextInfraUtilitiesCodegenFacades:
    """Project local ``u``, ``p`` and ``m`` owners selected by package consumers."""

    @classmethod
    def render_type_facade(
        cls,
        pkg_dir: Path,
        facade_path: Path,
        sources: t.MappingKV[Path, str],
    ) -> str:
        """Project a complete exported type owner without duplicating its body.

        Only the existing class/t export contract is supported. Ambiguous owners
        or extra public declarations fail rather than being silently discarded.

        Returns:
            Generated facade source inheriting its complete declared type owner.

        Raises:
            ValueError: If the facade lacks module documentation, declares an
                unsupported class, exports, or declarations, or does not resolve
                to exactly one full exported type owner.
        """
        source = sources[facade_path]
        tree = ast.parse(source, filename=str(facade_path))
        if ast.get_docstring(tree) is None:
            msg = f"type facade has no module documentation: {facade_path}"
            raise ValueError(msg)
        facade, _namespace = cls._facade_classes(tree, facade_path)
        if facade.decorator_list or facade.type_params:
            msg = f"unsupported type facade class: {facade_path}"
            raise ValueError(msg)
        exports = tuple(
            node
            for node in tree.body
            if isinstance(node, ast.Assign | ast.AnnAssign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
            )
        )
        if (
            len(exports) != 1
            or exports[0].value is None
            or set(ast.literal_eval(exports[0].value)) != {facade.name, "t"}
        ):
            msg = f"unsupported type facade exports: {facade_path}"
            raise ValueError(msg)
        bindings = tuple(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "t"
            and isinstance(node.value, ast.Name)
            and node.value.id == facade.name
        )
        if len(bindings) != 1 or any(
            not isinstance(node, ast.Import | ast.ImportFrom)
            and not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            and not (
                isinstance(node, ast.If)
                and isinstance(node.test, ast.Name)
                and node.test.id == "TYPE_CHECKING"
                and not node.orelse
                and all(
                    isinstance(item, ast.Import | ast.ImportFrom) for item in node.body
                )
            )
            and node is not facade
            and node not in exports
            and node not in bindings
            for node in tree.body
        ):
            msg = f"unsupported type facade declarations: {facade_path}"
            raise ValueError(msg)
        directory = FlextInfraUtilitiesCodegenNamespace.facade_families()["t"].directory
        owners = tuple(
            path
            for path, content in sources.items()
            if path.is_relative_to(pkg_dir / directory)
            and path.name != c.Infra.INIT_PY
            and "t"
            in FlextInfraUtilitiesRopeModulePatch.facade_letter_names_source(content)
            and any(
                isinstance(binding, ast.Assign)
                and isinstance(binding.value, ast.Name)
                and binding.value.id == facade.name
                for binding in (
                    FlextInfraUtilitiesRopeModulePatch.runtime_alias_bindings(
                        content,
                        alias="t",
                    )
                )
            )
            and any(
                isinstance(node, ast.ClassDef) and node.name == facade.name
                for node in ast.parse(content, filename=str(path)).body
            )
        )
        if len(owners) != 1:
            msg = f"expected one full exported type owner: {facade_path}"
            raise ValueError(msg)
        module = (
            owners[0].relative_to(pkg_dir).with_suffix("").as_posix().replace("/", ".")
        )
        alias = f"_{facade.name}"
        return (
            f"{ast.get_source_segment(source, tree.body[0])}\n\n"
            "# Generated type facade; declarations belong to "
            f"{pkg_dir.name}.{module}.\n"
            f"from {pkg_dir.name}.{module} import {facade.name} as {alias}\n\n\n"
            f"class {facade.name}({alias}):\n"
            '    """Public type facade inheriting its '
            'complete canonical owner."""\n\n\n'
            f"t = {facade.name}\n\n"
            f"{ast.get_source_segment(source, exports[0])}\n"
        )

    @staticmethod
    def facade_module_path(pkg_dir: Path, family: str) -> Path | None:
        """Return the package module that declares facade letter ``family``.

        The owner of a facade letter is the module that publishes it in its own
        ``__all__`` (generator law p.1); it is derived from the package, never
        from a letter-to-filename table. ``None`` means no module declares it.

        Returns:
            The declaring package module, or ``None`` when none declares it.

        Raises:
            ValueError: If multiple package modules declare the same facade letter.

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
        family: Literal["u", "p", "m"] = "u",
    ) -> str | None:
        """Render uniquely discovered utility, protocol or model owners.

        Package consumers select called utility methods or referenced protocol
        and model members through imports resolved to this package's facade.
        Discovery scans Python modules recursively in the configured private
        family and follows owner base chains. Existing namespace runtime bindings,
        including simple assignment aliases, are retained rather than replaced.
        Missing owners contribute imports and bases only; a namespace without
        bases is updated through its unique concrete-syntax class span.
        Rendering returns source without publishing it.

        Returns:
            Rendered source, including unchanged source when no owner is added,
            or ``None`` when there is no private family to project or an empty
            owner directory has no declaring facade.

        Raises:
            ValueError: If facade declarations or required owners are ambiguous,
                a nonempty private family has no facade, the facade class shape
                or base expression is unsupported, import resolution fails, or
                base insertion cannot identify a valid source span.

        """
        facade_path = cls.facade_module_path(pkg_dir, family)
        owners_dir = (
            pkg_dir
            / FlextInfraUtilitiesCodegenNamespace.facade_families()[family].directory
        )
        # Why: only owners-without-facade is incomplete -- the owners would have
        # no public surface at all. A facade with no owners directory is the
        # legitimate pure re-export shape this same generator emits for a package
        # that adds no local utilities (src/flext: `class FlextRootUtilities(u)`),
        # and there is simply nothing to project onto it.
        if not owners_dir.is_dir():
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
        reachable = cls._reachable_bases(
            tuple(cls._base_name(base) for base in namespace.bases),
            ancestors,
        )
        additions: list[t.Pair[str, str]] = []
        declared = {
            member.name
            for member in namespace.body
            if isinstance(member, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        }
        declared.update(
            target.id
            for member in namespace.body
            if isinstance(member, ast.Assign | ast.TypeAlias)
            or (isinstance(member, ast.AnnAssign) and member.value is not None)
            for target in (
                member.targets
                if isinstance(member, ast.Assign)
                else [
                    member.name if isinstance(member, ast.TypeAlias) else member.target,
                ]
            )
            if isinstance(target, ast.Name)
        )
        for method in sorted(
            cls._required_methods(
                pkg_dir,
                facade_path,
                nested_namespace=namespace is not facade,
                namespace=namespace.name,
                family=family,
            ),
        ):
            if method in declared:
                continue
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
                message = (
                    f"ambiguous {family}.{namespace.name} owner for {method}: "
                    + ", ".join(f"{module}:{name}" for module, name in candidates)
                )
                raise ValueError(message)
            module, class_name = candidates[0]
            additions.append((module, class_name))
            reachable.update(cls._reachable_bases((class_name,), ancestors))
        if not additions:
            return source
        source = cls._insert_imports(
            source,
            facade,
            additions,
            package=pkg_dir.name,
            family=family,
        )
        _, namespace = cls._facade_classes(
            ast.parse(source, filename=str(facade_path)),
            facade_path,
        )
        return cls._insert_bases(source, namespace, additions)

    @staticmethod
    def _required_methods(
        pkg_dir: Path,
        facade_path: Path,
        *,
        nested_namespace: bool,
        namespace: str,
        family: Literal["u", "p", "m"],
    ) -> frozenset[str]:

        methods: set[str] = set()
        with FlextInfraUtilitiesRopeCore.open_project(pkg_dir.parent) as project:
            for path in (
                candidate
                for candidate in sorted(pkg_dir.rglob(f"*{c.Infra.EXT_PYTHON}"))
                if candidate != facade_path
            ):
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
                for reference in (
                    node.func if isinstance(node, ast.Call) else node
                    for node in ast.walk(tree)
                    if family != "u" or isinstance(node, ast.Call)
                ):
                    if not isinstance(reference, ast.Attribute):
                        continue
                    receiver = reference.value
                    if nested_namespace and (
                        not isinstance(receiver, ast.Attribute)
                        or receiver.attr != namespace
                    ):
                        continue
                    receiver = (
                        receiver.value
                        if nested_namespace and isinstance(receiver, ast.Attribute)
                        else receiver
                    )
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
        family: Literal["u", "p", "m"],
    ) -> t.Pair[
        t.VariadicTuple[t.Triple[str, str, frozenset[str]]],
        t.MappingKV[str, frozenset[str]],
    ]:
        owners: list[t.Triple[str, str, frozenset[str]]] = []
        ancestors: MutableMapping[str, frozenset[str]] = {}
        for path in sorted(owners_dir.rglob(c.Infra.EXT_PYTHON_GLOB)):
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
                module = path.relative_to(owners_dir).with_suffix("").as_posix()
                owners.append((module.replace("/", "."), node.name, methods))
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
        family: Literal["u", "p", "m"],
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

    @classmethod
    def _insert_bases(
        cls,
        source: str,
        namespace: ast.ClassDef,
        additions: t.SequenceOf[t.Pair[str, str]],
    ) -> str:
        if not namespace.bases:
            wrapper = MetadataWrapper(parse_module(source))
            positions = wrapper.resolve(PositionProvider)
            owners = tuple(
                node
                for node, span in positions.items()
                if isinstance(node, ClassDef)
                and span.start.line == namespace.lineno
                and span.start.column
                == len(
                    source
                    .splitlines()[namespace.lineno - 1]
                    .encode(c.Cli.ENCODING_DEFAULT)[: namespace.col_offset]
                    .decode(c.Cli.ENCODING_DEFAULT),
                )
            )
            if len(owners) != 1:
                message = "facade namespace has no unique concrete source span"
                raise ValueError(message)
            owner = owners[0]
            updated = wrapper.module.deep_replace(
                owner,
                owner.with_changes(
                    bases=tuple(Arg(Name(name)) for _module, name in additions),
                ),
            )
            if not isinstance(updated, Module):
                message = "facade base projection did not preserve the module"
                raise ValueError(message)
            return updated.code
        last_base = namespace.bases[-1]
        if last_base.end_lineno is None or last_base.end_col_offset is None:
            message = "utility namespace base has no source span"
            raise ValueError(message)
        # A base listed after Protocol has no consistent MRO, so owners
        # projected onto a protocol namespace go before its terminal Protocol.
        precede = cls._base_name(last_base) == c.Infra.PROTOCOL_BASE
        lines = source.encode(c.Cli.ENCODING_DEFAULT).splitlines(keepends=True)
        line, column = (
            (last_base.lineno, last_base.col_offset)
            if precede
            else (last_base.end_lineno, last_base.end_col_offset)
        )
        offset = sum(map(len, lines[: line - 1])) + column
        separator = (
            ", "
            if last_base.lineno == namespace.lineno
            else ",\n" + " " * last_base.col_offset
        )
        inserted = "".join(
            name + separator if precede else separator + name
            for _module, name in additions
        )
        encoded = b"".join(lines)
        return (
            encoded[:offset]
            + inserted.encode(c.Cli.ENCODING_DEFAULT)
            + encoded[offset:]
        ).decode(c.Cli.ENCODING_DEFAULT)


__all__: list[str] = ["FlextInfraUtilitiesCodegenFacades"]
