"""Concrete-syntax rewrites for compatibility-alias cutovers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

import libcst as cst
from libcst.metadata import (
    MetadataWrapper,
    ParentNodeProvider,
    QualifiedName,
    QualifiedNameProvider,
    QualifiedNameSource,
)

from flext_infra._utilities import FlextInfraUtilitiesQualifiedNames

if TYPE_CHECKING:
    from flext_infra import m


class FlextInfraUtilitiesSemanticCutoverAliasCst:
    """Preserve formatting while alias ownership is cut over."""

    class _AliasTransformer(cst.CSTTransformer):
        """Rewrite qualified alias reads and retire retired local bindings."""

        METADATA_DEPENDENCIES = (ParentNodeProvider, QualifiedNameProvider)

        def __init__(self, plan: m.Infra.CompatibilityAliasRewritePlan) -> None:
            self.plan = plan

        def _qualified_names(self, node: cst.CSTNode) -> frozenset[QualifiedName]:
            """Verify the lexical receiver before trusting dotted import metadata.

            Returns:
                Qualified identities consistent with the lexical receiver.

            """
            names = tuple(self.get_metadata(QualifiedNameProvider, node, ()))
            if isinstance(node, cst.Attribute) and any(
                name.name in self.plan.qualified_aliases
                or any(
                    name.name == alias.rpartition(".")[0]
                    for alias in self.plan.qualified_aliases
                )
                or name.name
                in {
                    "builtins.getattr",
                    "builtins.hasattr",
                    "builtins.setattr",
                    "builtins.delattr",
                }
                for name in names
            ):
                return FlextInfraUtilitiesQualifiedNames.prove_import_root(
                    names,
                    tuple(
                        self.get_metadata(
                            QualifiedNameProvider,
                            FlextInfraUtilitiesQualifiedNames.lexical_root(node),
                            (),
                        ),
                    ),
                )
            return frozenset(names)

        def _alias_target(self, node: cst.Name | cst.Attribute) -> str | None:
            """Require all possible bindings to agree before changing a reference.

            Returns:
                The unique alias destination, or None for an unrelated reference.

            Raises:
                ValueError: If a retiring binding has competing identities.

            """
            names = self._qualified_names(node)
            matched = [
                name
                for name in names
                if name.name in self.plan.qualified_aliases
                and (
                    name.source is QualifiedNameSource.IMPORT
                    or (
                        isinstance(node, cst.Name)
                        and name.source is QualifiedNameSource.LOCAL
                        and name.name in self.plan.local_aliases
                    )
                )
            ]
            if not matched:
                return None
            targets = {self.plan.qualified_aliases[name.name] for name in matched}
            if len(matched) != len(names) or len(targets) != 1:
                msg = (
                    "ambiguous qualified alias bindings: "
                    f"{sorted(name.name for name in names)}"
                )
                raise ValueError(msg)
            return targets.pop()

        def _require_module_access(self, node: cst.Name | cst.Attribute) -> None:
            """Refuse opaque escapes of modules whose alias exports are retiring.

            Raises:
                ValueError: If reflection or an opaque escape prevents closure.

            """
            retired = {
                alias.rpartition(".")[2]
                for name in self._qualified_names(node)
                if name.source is QualifiedNameSource.IMPORT
                for alias in self.plan.qualified_aliases
                if alias.rpartition(".")[0] == name.name
            }
            if not retired:
                return
            parent = self.get_metadata(ParentNodeProvider, node)
            if isinstance(parent, cst.ImportAlias | cst.ImportFrom):
                return
            if isinstance(parent, cst.Attribute) and parent.value is node:
                return
            call = (
                self.get_metadata(ParentNodeProvider, parent)
                if isinstance(parent, cst.Arg)
                else None
            )
            if isinstance(call, cst.Call) and call.args[0] is parent:
                reflectors = self._qualified_names(call.func)
                if reflectors and all(
                    name.source
                    in {
                        QualifiedNameSource.BUILTIN,
                        QualifiedNameSource.IMPORT,
                    }
                    and name.name
                    in {
                        "builtins.getattr",
                        "builtins.hasattr",
                        "builtins.setattr",
                        "builtins.delattr",
                    }
                    for name in reflectors
                ):
                    attribute = (
                        call.args[1].value
                        if len(call.args) > 1 and not call.args[1].star
                        else None
                    )
                    attribute_name = (
                        attribute.evaluated_value
                        if isinstance(
                            attribute,
                            cst.SimpleString | cst.ConcatenatedString,
                        )
                        else None
                    )
                    if not isinstance(attribute_name, str):
                        msg = "unresolved reflective attribute on retiring alias module"
                        raise ValueError(msg)
                    if attribute_name in retired:
                        msg = (
                            f"reflective alias access blocks cutover: {attribute_name}"
                        )
                        raise ValueError(msg)
                    return
            msg = "retiring module escape blocks alias cutover"
            raise ValueError(msg)

        @override
        def leave_Name(
            self,
            original_node: cst.Name,
            updated_node: cst.Name,
        ) -> cst.Name:

            parent = self.get_metadata(ParentNodeProvider, original_node)
            if FlextInfraUtilitiesQualifiedNames.rebinds_name_in_place(
                parent,
                original_node,
            ):
                return updated_node
            self._require_module_access(original_node)
            target = self._alias_target(original_node)
            return updated_node.with_changes(value=target) if target else updated_node

        @override
        def leave_Assign(
            self,
            original_node: cst.Assign,
            updated_node: cst.Assign,
        ) -> cst.BaseSmallStatement | cst.RemovalSentinel:

            if (
                len(original_node.targets) == 1
                and isinstance(original_node.targets[0].target, cst.Name)
                and isinstance(original_node.value, cst.Name)
                and self.plan.local_aliases.get(
                    original_node.targets[0].target.value,
                )
                == original_node.value.value
            ):
                return cst.RemoveFromParent()
            return FlextInfraUtilitiesQualifiedNames.filter_exports(
                updated_node,
                self.plan.local_aliases,
            )

        @override
        def leave_AnnAssign(
            self,
            original_node: cst.AnnAssign,
            updated_node: cst.AnnAssign,
        ) -> cst.BaseSmallStatement:

            return FlextInfraUtilitiesQualifiedNames.filter_exports(
                updated_node,
                self.plan.local_aliases,
            )

        @override
        def leave_ImportFrom(
            self,
            original_node: cst.ImportFrom,
            updated_node: cst.ImportFrom,
        ) -> cst.BaseSmallStatement | cst.RemovalSentinel:

            rewrites = self.plan.import_aliases.get(
                FlextInfraUtilitiesQualifiedNames.dotted_name(original_node.module)
                or "",
            )
            if not rewrites or isinstance(updated_node.names, cst.ImportStar):
                return updated_node
            retained: list[cst.ImportAlias] = []
            for imported in updated_node.names:
                target = rewrites.get(
                    FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name) or "",
                )
                if target is None:
                    retained.append(imported)
                elif imported.asname is None and target in self.plan.target_bindings:
                    continue
                else:
                    retained.append(imported.with_changes(name=cst.Name(target)))
            return (
                updated_node.with_changes(names=retained)
                if retained
                else cst.RemoveFromParent()
            )

        @override
        def leave_Attribute(
            self,
            original_node: cst.Attribute,
            updated_node: cst.Attribute,
        ) -> cst.BaseExpression:

            self._require_module_access(original_node)
            target = self._alias_target(original_node)
            return (
                updated_node.with_changes(attr=cst.Name(target))
                if target
                else updated_node
            )

    @classmethod
    def _rewrite_compatibility_alias_source(
        cls,
        source: str,
        plan: m.Infra.CompatibilityAliasRewritePlan,
    ) -> str:
        """Return the structurally rewritten source without changing its layout.

        Returns:
            The structurally rewritten source without changing its layout.

        """
        return (
            MetadataWrapper(cst.parse_module(source))
            .visit(cls._AliasTransformer(plan))
            .code
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverAliasCst"]
