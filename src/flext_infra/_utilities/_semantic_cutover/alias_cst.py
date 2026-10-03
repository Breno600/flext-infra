"""Concrete-syntax rewrites for compatibility-alias cutovers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra._utilities.qualified_names import FlextInfraUtilitiesQualifiedNames

if TYPE_CHECKING:
    import libcst as cst

    from flext_infra import m


class FlextInfraUtilitiesSemanticCutoverAliasCst:
    """Preserve formatting while alias ownership is cut over."""

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
        import libcst as cst
        from libcst.metadata import (
            MetadataWrapper,
            ParentNodeProvider,
            QualifiedNameProvider,
        )

        class _AliasTransformer(cst.CSTTransformer):
            METADATA_DEPENDENCIES = (ParentNodeProvider, QualifiedNameProvider)

            def __init__(self, plan: m.Infra.CompatibilityAliasRewritePlan) -> None:
                self.plan = plan

            @override
            def leave_Name(
                self,
                original_node: cst.Name,
                updated_node: cst.Name,
            ) -> cst.Name:
                targets = {
                    target
                    for qualified_name in self.get_metadata(
                        QualifiedNameProvider,
                        original_node,
                        (),
                    )
                    if (target := self.plan.qualified_aliases.get(qualified_name.name))
                    is not None
                }
                if not targets:
                    return updated_node
                if len(targets) != 1:
                    msg = (
                        f"ambiguous qualified alias {original_node.value}: "
                        f"{sorted(targets)}"
                    )
                    raise ValueError(msg)
                parent = self.get_metadata(ParentNodeProvider, original_node)
                if FlextInfraUtilitiesQualifiedNames.rebinds_name_in_place(
                    parent,
                    original_node,
                ):
                    return updated_node
                return updated_node.with_changes(value=targets.pop())

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
                        FlextInfraUtilitiesQualifiedNames.dotted_name(imported.name)
                        or "",
                    )
                    if target is None:
                        retained.append(imported)
                    elif (
                        imported.asname is None and target in self.plan.target_bindings
                    ):
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
                owner = (
                    FlextInfraUtilitiesQualifiedNames.dotted_name(original_node.value)
                    or ""
                )
                target = self.plan.attribute_aliases.get((
                    owner,
                    original_node.attr.value,
                ))
                return (
                    updated_node.with_changes(attr=cst.Name(target))
                    if target
                    else updated_node
                )

        return (
            MetadataWrapper(cst.parse_module(source))
            .visit(_AliasTransformer(plan))
            .code
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverAliasCst"]
