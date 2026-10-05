"""Binding-aware reference rewrites for automatic class nesting.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import TYPE_CHECKING, override

import libcst as cst
from libcst.metadata import MetadataWrapper, ParentNodeProvider, QualifiedNameProvider

from flext_infra._utilities._semantic_cutover.nesting_module_aliases import (
    FlextInfraUtilitiesSemanticCutoverNestingModuleAliases,
)
from flext_infra._utilities.qualified_names import FlextInfraUtilitiesQualifiedNames

if TYPE_CHECKING:
    from flext_infra import m, t


class FlextInfraUtilitiesSemanticCutoverNestingReferences(
    FlextInfraUtilitiesSemanticCutoverNestingModuleAliases,
):
    """Rewrite imports and usages of classes moved below a module owner."""

    class _NestingTransformer(cst.CSTTransformer):
        """Rewrite one module's imports and references to the nested owners."""

        METADATA_DEPENDENCIES = (ParentNodeProvider, QualifiedNameProvider)

        def __init__(
            self,
            *,
            module_name: str,
            is_package_init: bool,
            bindings_by_module: t.MappingKV[str, t.StrMapping],
            definitions: t.StrMapping,
            scan: m.Infra.NestingModuleAliasScan,
            resolvers: t.Triple[
                Callable[..., str],
                Callable[..., str],
                Callable[[cst.BaseStatement], str | None],
            ],
        ) -> None:
            self.imported_module, self.resolved_relative, self.member_name = resolvers
            self.scan = scan
            # A nested module has exactly one owner (the planner rejects a
            # file with several), so its bindings name it once.
            self.owners_by_module = {
                module: next(iter(set(bindings.values())))
                for module, bindings in bindings_by_module.items()
                if bindings
            }
            self.module_aliases = {
                local: module
                for local, module in scan.aliases.items()
                if module in self.owners_by_module
            }
            self.module_name = module_name
            self.is_package_init = is_package_init
            self.bindings_by_module = bindings_by_module
            self.definitions = definitions
            self.qualified = {
                f"{module}.{name}": f"{owner}.{name}"
                for module, bindings in bindings_by_module.items()
                for name, owner in bindings.items()
            }
            self.qualified.update(
                (name, f"{owner}.{name}") for name, owner in definitions.items()
            )
            self.emitted_owner_imports: set[str] = set()
            self.local_expressions: MutableMapping[str, str] = {
                name: f"{owner}.{name}" for name, owner in definitions.items()
            }

        @staticmethod
        def _alias_name(asname: cst.AsName) -> str:
            """Return the bound alias identifier, rejecting impossible shapes.

            libcst types ``AsName.name`` as ``Name | Tuple | List``, but import
            aliases parsed from valid Python can only carry a ``Name``
            (``import x as (a, b)`` is a SyntaxError); Tuple/List belong to
            ``WithItem``/``ExceptHandler`` clauses only.

            Returns:
                The bound alias identifier, rejecting impossible shapes.

            Raises:
                TypeError: If unsupported import alias target.

            """
            if not isinstance(asname.name, cst.Name):
                msg = f"unsupported import alias target: {type(asname.name).__name__}"
                raise TypeError(msg)
            return asname.name.value

        def _import_module(self, node: cst.ImportFrom) -> str:
            return self.imported_module(
                node,
                module_name=self.module_name,
                is_package_init=self.is_package_init,
            )

        def _absolute_name(self, name: str) -> str:
            """Resolve a relative qualified name against the current module.

            Returns:
                The absolute dotted name.

            """
            relative = name.removeprefix(name.lstrip("."))
            if not relative:
                return name
            return self.resolved_relative(
                len(relative),
                name[len(relative) :],
                module_name=self.module_name,
                is_package_init=self.is_package_init,
            )

        @override
        def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
            bindings = self.bindings_by_module.get(self._import_module(node), {})
            if not bindings or isinstance(node.names, cst.ImportStar):
                return
            for imported in node.names:
                name = (
                    FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""
                )
                if name not in bindings:
                    continue
                local_name = (
                    self._alias_name(imported.asname) if imported.asname else name
                )
                owner_name = local_name if imported.asname else bindings[name]
                self.local_expressions[local_name] = f"{owner_name}.{name}"

        def _resolves_bare_after_nesting(self, node: cst.CSTNode) -> bool:
            """Report whether a moved class stays reachable by its bare name here.

            References are rewritten before the structural move, so the current
            tree cannot answer this; the plan can. After nesting, the owner's
            class body holds every moved class as a sibling, and a class body
            reaches its siblings by bare name while it is executing. A method
            body does not: the enclosing class scope is invisible from inside a
            function, so there the qualified form is the only one that resolves.
            Walking outward, a function boundary therefore means qualify, and a
            class that is the owner or is itself being moved under the owner
            means the reference will land in that shared class scope.

            Returns:
                The resulting ``bool``.

            """
            child: cst.CSTNode = node
            current: cst.CSTNode | None = self.get_metadata(
                ParentNodeProvider,
                node,
                None,
            )
            while current is not None:
                if isinstance(current, cst.FunctionDef | cst.Lambda):
                    # Decorators, defaults and annotations run in the
                    # enclosing scope; only the body is a function scope.
                    if child is current.body:
                        return False
                elif isinstance(
                    current,
                    cst.ListComp | cst.SetComp | cst.DictComp | cst.GeneratorExp,
                ):
                    return False
                elif isinstance(current, cst.ClassDef):
                    name = current.name.value
                    return name in self.definitions or name in set(
                        self.definitions.values(),
                    )
                elif isinstance(current, cst.Module):
                    # A moved module binding executes in the owner body.
                    return (
                        isinstance(child, cst.BaseStatement)
                        and self.member_name(child) in self.definitions
                    )
                child = current
                current = self.get_metadata(ParentNodeProvider, current, None)
            return False

        def _single_binding(
            self,
            original_node: cst.CSTNode,
            *,
            ambiguity: str,
        ) -> str | None:
            """Return the one class-nesting replacement bound to ``original_node``.

            ``None`` when the node carries no nesting binding; two competing
            bindings are ambiguous and raise with ``ambiguity`` naming the site.

            Returns:
                The one class-nesting replacement bound to ``original_node``.

            Raises:
                ValueError: If ambiguous class-nesting.

            """
            replacements = {
                replacement
                for qualified_name in self.get_metadata(
                    QualifiedNameProvider,
                    original_node,
                    (),
                )
                if (
                    replacement := self.qualified.get(
                        self._absolute_name(qualified_name.name),
                    )
                )
                is not None
            }
            if not replacements:
                return None
            if len(replacements) != 1:
                msg = f"ambiguous class-nesting {ambiguity}: {sorted(replacements)}"
                raise ValueError(msg)
            return replacements.pop()

        @override
        def leave_Name(
            self,
            original_node: cst.Name,
            updated_node: cst.Name,
        ) -> cst.BaseExpression:
            bound = self._single_binding(original_node, ambiguity="binding")
            if bound is None:
                return updated_node
            parent = self.get_metadata(ParentNodeProvider, original_node)
            if FlextInfraUtilitiesQualifiedNames.rebinds_name_in_place(
                parent,
                original_node,
            ):
                return updated_node
            if (
                isinstance(parent, cst.ClassDef | cst.FunctionDef)
                and parent.name is original_node
            ) or (
                isinstance(parent, cst.AssignTarget | cst.AnnAssign)
                and parent.target is original_node
            ):
                return updated_node
            if original_node.value in self.definitions and (
                self._resolves_bare_after_nesting(original_node)
            ):
                return updated_node
            replacement = self.local_expressions.get(original_node.value)
            if replacement is None:
                replacement = bound
            return cst.parse_expression(replacement)

        @override
        def leave_Attribute(
            self,
            original_node: cst.Attribute,
            updated_node: cst.Attribute,
        ) -> cst.BaseExpression:
            value = original_node.value
            module = (
                self.module_aliases.get(value.value)
                if isinstance(value, cst.Name)
                else None
            )
            if (
                module is not None
                and original_node.attr.value in self.bindings_by_module[module]
            ):
                return updated_node.with_changes(
                    value=cst.Name(self.owners_by_module[module]),
                )
            bound = self._single_binding(original_node, ambiguity="attribute")
            if bound is None:
                return updated_node
            owner, name = bound.split(".", maxsplit=1)
            return cst.Attribute(
                value=cst.Attribute(value=updated_node.value, attr=cst.Name(owner)),
                attr=cst.Name(name),
            )

        @override
        def leave_ImportFrom(
            self,
            original_node: cst.ImportFrom,
            updated_node: cst.ImportFrom,
        ) -> cst.BaseSmallStatement | cst.RemovalSentinel:
            if not isinstance(updated_node.names, cst.ImportStar):
                kept = tuple(
                    imported
                    for imported in updated_node.names
                    if not self._retires_module_binding(imported)
                )
                if not kept:
                    return cst.RemoveFromParent()
                if len(kept) != len(updated_node.names):
                    updated_node = updated_node.with_changes(
                        names=FlextInfraUtilitiesQualifiedNames.normalized_import_aliases(
                            kept,
                            parenthesized=bool(updated_node.lpar),
                        ),
                    )
            bindings = self.bindings_by_module.get(
                self._import_module(original_node),
                {},
            )
            if not bindings or isinstance(updated_node.names, cst.ImportStar):
                return updated_node
            aliases: list[cst.ImportAlias] = []
            seen: set[t.Pair[str, str]] = set()
            for imported in updated_node.names:
                name = (
                    FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""
                )
                owner = bindings.get(name)
                rewritten = (
                    imported.with_changes(name=cst.Name(owner)) if owner else imported
                )
                identity = (
                    FlextInfraUtilitiesQualifiedNames.dotted_name(rewritten.name) or "",
                    self._alias_name(rewritten.asname) if rewritten.asname else "",
                )
                if identity not in seen:
                    seen.add(identity)
                    aliases.append(rewritten)
            if not aliases:
                return cst.RemoveFromParent()
            return updated_node.with_changes(
                names=FlextInfraUtilitiesQualifiedNames.normalized_import_aliases(
                    aliases,
                    parenthesized=bool(updated_node.lpar),
                ),
            )

        def _retires_module_binding(self, imported: cst.ImportAlias) -> bool:
            """Whether an import only binds a module no longer read as one.

            Returns:
                The resulting ``bool``.

            """
            local = (
                self._alias_name(imported.asname)
                if imported.asname
                else FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""
            )
            return local in self.module_aliases and local not in self.scan.residual

        @override
        def leave_Import(
            self,
            original_node: cst.Import,
            updated_node: cst.Import,
        ) -> cst.BaseSmallStatement | cst.RemovalSentinel:
            kept = tuple(
                imported
                for imported in updated_node.names
                if not self._retires_module_binding(imported)
            )
            if not kept:
                return cst.RemoveFromParent()
            if len(kept) == len(updated_node.names):
                return updated_node
            return updated_node.with_changes(
                names=FlextInfraUtilitiesQualifiedNames.normalized_import_aliases(
                    kept,
                    parenthesized=False,
                ),
            )

        def _bound_locals(
            self,
            statement: cst.BaseSmallStatement,
        ) -> t.VariadicTuple[str]:
            """Return the local names one import statement binds.

            Returns:
                The bound names, or an empty tuple for other statements.

            """
            if not isinstance(statement, cst.Import | cst.ImportFrom):
                return ()
            names = statement.names
            if isinstance(names, cst.ImportStar):
                return ()
            return tuple(
                self._alias_name(imported.asname)
                if imported.asname
                else FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or ""
                for imported in names
            )

        @override
        def leave_SimpleStatementLine(
            self,
            original_node: cst.SimpleStatementLine,
            updated_node: cst.SimpleStatementLine,
        ) -> (
            cst.BaseStatement
            | cst.FlattenSentinel[cst.BaseStatement]
            | cst.RemovalSentinel
        ):
            bound = tuple(
                local
                for statement in original_node.body
                for local in self._bound_locals(statement)
            )
            modules = tuple(
                dict.fromkeys(
                    self.module_aliases[local]
                    for local in bound
                    if local in self.module_aliases and local in self.scan.read
                ),
            )
            owner_imports = tuple(
                cst.parse_statement(
                    f"from {module} import {self.owners_by_module[module]}\n",
                )
                for module in modules
                if module not in self.emitted_owner_imports
                and module not in self.scan.owner_imports
            )
            if not owner_imports:
                return updated_node
            self.emitted_owner_imports.update(modules)
            kept: tuple[cst.BaseStatement, ...] = (
                (updated_node,) if updated_node.body else ()
            )
            return cst.FlattenSentinel((*kept, *owner_imports))

        @override
        def leave_Assign(
            self,
            original_node: cst.Assign,
            updated_node: cst.Assign,
        ) -> cst.BaseSmallStatement:
            return FlextInfraUtilitiesQualifiedNames.filter_exports(
                updated_node,
                self.definitions,
            )

        @override
        def leave_AnnAssign(
            self,
            original_node: cst.AnnAssign,
            updated_node: cst.AnnAssign,
        ) -> cst.BaseSmallStatement:
            return FlextInfraUtilitiesQualifiedNames.filter_exports(
                updated_node,
                self.definitions,
            )

    @staticmethod
    def _assignment_targets(
        statement: cst.BaseSmallStatement,
    ) -> t.VariadicTuple[cst.BaseAssignTargetExpression]:
        """Return the targets one assignment statement binds.

        Returns:
            The bound targets, or an empty tuple for other statements.

        """
        targets: t.SequenceOf[cst.BaseAssignTargetExpression] = ()
        if isinstance(statement, cst.AnnAssign):
            targets = [statement.target]
        elif isinstance(statement, cst.Assign):
            targets = [item.target for item in statement.targets]
        return tuple(targets)

    @classmethod
    def _member_name(cls, node: cst.BaseStatement) -> str | None:
        """Return the name one module-level member statement defines.

        Returns:
            The class, function or single-target binding name, else ``None``.

        """
        if isinstance(node, cst.ClassDef | cst.FunctionDef):
            return node.name.value
        if not isinstance(node, cst.SimpleStatementLine) or len(node.body) != 1:
            return None
        statement = node.body[0]
        targets = cls._assignment_targets(statement)
        if (
            len(targets) != 1
            or not isinstance(targets[0], cst.Name)
            or (isinstance(statement, cst.AnnAssign) and statement.value is None)
        ):
            return None
        return targets[0].value

    @classmethod
    def _rewrite_class_nesting_references(
        cls,
        source: str,
        *,
        module_name: str,
        is_package_init: bool,
        bindings_by_module: t.MappingKV[str, t.StrMapping],
        definitions: t.StrMapping,
    ) -> str:
        """Return binding-proven import and usage rewrites without effects.

        Returns:
            Binding-proven import and usage rewrites without effects.

        """
        scan = cls._module_alias_scan(
            source,
            module_name=module_name,
            is_package_init=is_package_init,
            bindings_by_module=bindings_by_module,
        )
        return (
            MetadataWrapper(cst.parse_module(source))
            .visit(
                cls._NestingTransformer(
                    module_name=module_name,
                    is_package_init=is_package_init,
                    bindings_by_module=bindings_by_module,
                    definitions=definitions,
                    scan=scan,
                    resolvers=(
                        cls._imported_module,
                        cls._resolved_relative,
                        cls._member_name,
                    ),
                ),
            )
            .code
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverNestingReferences"]
