"""Qualified runtime-base discovery over captured, unpublished source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

from collections.abc import MutableMapping
import ast
from pathlib import Path

from flext_infra import m, t
from flext_infra._utilities._rope_source_bases_runtime import (
    FlextInfraUtilitiesRopeSourceBasesRuntime,
from flext_infra import m, t
from flext_infra._utilities._rope_source_bases_aliases import (
    FlextInfraUtilitiesRopeSourceBasesAliases,
)
from flext_infra._utilities._rope_source_bases_inventory import (
    FlextInfraUtilitiesRopeSourceBasesInventory,
)
from flext_infra._utilities._rope_source_bases_runtime import (
    FlextInfraUtilitiesRopeSourceBasesRuntime,
)


class FlextInfraUtilitiesRopeSourceBases:
    """Source-bases composite facade over the inventory, aliases, and runtime parts."""


class FlextInfraUtilitiesRopeSourceBases(
    FlextInfraUtilitiesRopeSourceBasesRuntime,
):
    """Index captured lexical bindings and resolve their qualified runtime bases."""

    @classmethod
    def inventory(
        cls,
        request: m.Infra.SourceBindingInventoryRequest,
        definitions: MutableMapping[str, m.Infra.SourceClassDefinition],
    ) -> t.MappingKV[str, m.Infra.SourceClassReference | None]:
        """Index lexical bindings without installing a cross-module Rope overlay.

        Returns:
            The module's explicit lexical bindings, including value shadowing.

        """
        return FlextInfraUtilitiesRopeSourceBasesInventory.inventory(
            request,
            definitions,
        )

    @staticmethod
    def _module_table_target(
        target: ast.expr,
        bindings: t.MappingKV[str, m.Infra.SourceClassReference | None],
    ) -> bool:
        """Recognize a subscript store that cannot rebind a live class.

        Returns:
            The resulting ``bool``.
        """
        if not isinstance(target, ast.Subscript):
            return False
        expression = target.value
        attributes: list[str] = []
        while isinstance(expression, ast.Attribute):
            attributes.insert(0, expression.attr)
            expression = expression.value
        if not isinstance(expression, ast.Name):
            return False
        rebind = m.Infra.SubscriptRebind(
            root_name=expression.id,
            attribute=".".join(attributes) if attributes else None,
        )
        return rebind.is_module_table_mutation or bindings.get(rebind.root_name) is None

    @classmethod
    def _collect(
        cls,
        spec: m.Infra.SourceBindingCollectorSpec,
        statements: t.SequenceOf[ast.stmt],
        bindings: MutableMapping[str, m.Infra.SourceClassReference | None],
        scope: str,
    ) -> None:
        """Index lexical declarations in order, preserving provider conditionality.

        Raises:
            ValueError: If Relative import escapes package in; or if Star import has no
                explicit class binding in; or if Unsupported class binding mutation in;
                or if Conditional exception-backed class bindings in.
        """
        for node in statements:
            if (
                spec.required_line is not None
                and not scope
                and node.lineno > spec.required_line
            ):
                break
            if isinstance(node, ast.ClassDef):
                if (
                    spec.required_line is not None
                    and not scope
                    and not (
                        node.lineno
                        <= spec.required_line
                        <= (node.end_lineno or node.lineno)
                    )
                ):
                    bindings[node.name] = m.Infra.SourceClassReference(
                        target=spec.module,
                        attributes=tuple(f"{scope}{node.name}".split(".")),
                        qualified_base=f"{spec.module}.{scope}{node.name}",
                    )
                    continue
                visible = {**spec.lexical, **bindings}
                bases = tuple(
                    cls._reference(base, visible, spec.module) for base in node.bases
                )
                if node.type_params:
                    bases = (
                        *bases,
                        m.Infra.SourceClassReference(
                            target="typing",
                            attributes=("Generic",),
                            qualified_base="typing.Generic",
                        ),
                    )
                identity = f"{spec.module}:{scope}{node.name}:{node.lineno}"
                members: MutableMapping[str, m.Infra.SourceClassReference | None] = {}
                # Nested bases see class locals; nested bodies retain module lexical scope.
                cls._collect(spec, node.body, members, f"{scope}{node.name}.")
                spec.definitions[identity] = m.Infra.SourceClassDefinition(
                    identity=identity,
                    bases=bases,
                    members=members,
                )
                bindings[node.name] = m.Infra.SourceClassReference(
                    target=identity,
                    qualified_base=f"{spec.module}.{node.name}",
                )
            elif isinstance(node, ast.ImportFrom):
                parts = spec.package.split(".") if spec.package else []
                if node.level:
                    if node.level > len(parts):
                        message = f"Relative import escapes package in {spec.module}"
                        raise ValueError(message)
                    prefix = ".".join(parts[: len(parts) - node.level + 1])
                    imported = ".".join(part for part in (prefix, node.module) if part)
                else:
                    imported = node.module or ""
                for alias in node.names:
                    if alias.name == "*":
                        if spec.allow_conditional:
                            continue
                        message = f"Star import has no explicit class binding in {spec.module}"
                        raise ValueError(message)
                    bindings[alias.asname or alias.name] = m.Infra.SourceClassReference(
                        target=imported,
                        attributes=(alias.name,),
                        qualified_base=f"{imported}.{alias.name}",
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    target = (
                        alias.name if alias.asname else alias.name.partition(".")[0]
                    )
                    bindings[alias.asname or target] = m.Infra.SourceClassReference(
                        target=target,
                        qualified_base=target,
                    )
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                if any(not isinstance(target, ast.Name) for target in targets):
                    if spec.allow_conditional and all(
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id in bindings
                        and (
                            bindings[target.value.id] is None
                            or target.attr
                            in {"__module__", "__name__", "__qualname__", "__doc__"}
                        )
                        for target in targets
                    ):
                        # Class metadata does not rebind a class or its bases;
                        # providers may annotate imported and declared classes.
                        continue
                    if all(
                        cls._module_table_target(target, bindings) for target in targets
                    ):
                        continue
                    value = node.value
                    target = targets[0]
                    visible = {**spec.lexical, **bindings}
                    if (
                        spec.allow_conditional
                        and len(targets) == 1
                        and isinstance(value, ast.Name)
                        and isinstance(target, ast.Attribute)
                        and target.attr
                        not in {
                            "__bases__",
                            "__base__",
                            "__mro__",
                            "__class__",
                            "__dict__",
                        }
                        and isinstance(target.value, ast.Name)
                        and target.value.id in visible
                        and visible[target.value.id] is not None
                    ):
                        owner = cls._reference(target.value, visible, spec.module)
                        if (
                            owner.target in spec.definitions
                            and not owner.attributes
                            and value.id in visible
                        ):
                            definition = spec.definitions[owner.target]
                            spec.definitions[owner.target] = definition.model_copy(
                                update={
                                    "members": {
                                        **definition.members,
                                        target.attr: visible[value.id],
                                    },
                                },
                            )
                            continue
                    message = (
                        f"Unsupported class binding mutation in {spec.module}: "
                        f"{ast.unparse(node)}"
                    )
                    raise ValueError(message)
                value = node.value
                if value is None:
                    continue
                visible = {**spec.lexical, **bindings}
                head = value
                while isinstance(head, ast.Attribute | ast.Subscript):
                    head = head.value
                reference = (
                    m.Infra.SourceClassReference(
                        target="builtins",
                        attributes=(str(value.value),),
                    )
                    if isinstance(value, ast.Constant) and isinstance(value.value, bool)
                    else cls._reference(value, visible, spec.module)
                    if isinstance(head, ast.Name)
                    and isinstance(value, ast.Name | ast.Attribute | ast.Subscript)
                    and not (head.id in visible and visible[head.id] is None)
                    else None
                )
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = (
                            reference.model_copy(
                                update={"qualified_base": f"{spec.module}.{target.id}"},
                            )
                            if reference is not None
                            else None
                        )
            elif isinstance(node, ast.AugAssign | ast.Delete):
                if not spec.allow_conditional:
                    message = (
                        f"Unsupported class binding mutation in {spec.module}: "
                        f"{ast.unparse(node)}"
                    )
                    raise ValueError(message)
                if isinstance(node, ast.AugAssign):
                    if isinstance(node.target, ast.Name):
                        bindings[node.target.id] = None
                elif all(isinstance(target, ast.Name) for target in node.targets):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            bindings.pop(target.id, None)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                bindings[node.name] = None
            elif isinstance(node, ast.If):
                match node.test:
                    case ast.Compare(
                        left=ast.Name(id="__name__"),
                        ops=[ast.Eq()],
                        comparators=[ast.Constant(value="__main__")],
                    ):
                        cls._collect(
                            spec,
                            node.body if spec.module == "__main__" else node.orelse,
                            bindings,
                            scope,
                        )
                        continue
                    case ast.Constant(value=bool(value)):
                        cls._collect(
                            spec,
                            node.body if value else node.orelse,
                            bindings,
                            scope,
                        )
                        continue
                    case _:
                        pass
                head = (
                    node.test.value
                    if isinstance(node.test, ast.Attribute)
                    else node.test
                )
                visible = {**spec.lexical, **bindings}
                if (
                    isinstance(node.test, ast.Name | ast.Attribute)
                    and isinstance(head, ast.Name)
                    and head.id in visible
                    and visible[head.id] is not None
                ):
                    guard = cls._reference(node.test, visible, spec.module)
                    if (
                        guard.target in {"typing", "typing_extensions"}
                        and guard.attributes == ("TYPE_CHECKING",)
                    ) or (
                        guard.target == "builtins"
                        and guard.attributes in {("True",), ("False",)}
                    ):
                        cls._collect(
                            spec,
                            node.body if guard.attributes == ("True",) else node.orelse,
                            bindings,
                            scope,
                        )
                        continue
                conditional = {
                    child.name
                    for statement in (*node.body, *node.orelse)
                    for child in ast.walk(statement)
                    if isinstance(child, ast.ClassDef)
                }
                left = dict(bindings)
                right = dict(bindings)
                for name in conditional:
                    left[name] = None
                    right[name] = None
                cls._collect(spec, node.body, left, scope)
                cls._collect(spec, node.orelse, right, scope)
                for name in left.keys() | right.keys():
                    bindings[name] = (
                        left[name]
                        if name in left and name in right and left[name] == right[name]
                        else None
                    )
            elif isinstance(node, ast.Try | ast.TryStar):
                if not spec.allow_conditional:
                    message = (
                        f"Conditional exception-backed class bindings in {spec.module}"
                    )
                    raise ValueError(message)
                conditional_bindings: MutableMapping[
                    str, m.Infra.SourceClassReference | None
                ] = {}
                cls._collect(spec, node.body, conditional_bindings, scope)
                cls._collect(spec, node.orelse, conditional_bindings, scope)
                for handler in node.handlers:
                    cls._collect(spec, handler.body, conditional_bindings, scope)
                for name in conditional_bindings:
                    bindings[name] = None

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
