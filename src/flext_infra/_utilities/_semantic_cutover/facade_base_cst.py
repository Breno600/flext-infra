"""Concrete-syntax rewrite that extends a facade by its parent's class name."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

import libcst as cst

from ..qualified_names import FlextInfraUtilitiesQualifiedNames

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesSemanticCutoverFacadeBaseCst:
    """Preserve layout while a facade base moves from letter to class."""

    class _FacadeBaseTransformer(cst.CSTTransformer):
        """Swap the letter import and base for the parent's declared class."""

        def __init__(
            self, *, shape: t.Quad[str, str, str, str], owner: str, owner_bound: bool
        ) -> None:
            super().__init__()
            self.module, self.imported, self.local, self.facade = shape
            self.owner = owner
            self.owner_bound = owner_bound
            self.depth = 0

        @override
        def visit_ClassDef(self, node: cst.ClassDef) -> bool:
            self.depth += 1
            return True

        @override
        def leave_ClassDef(
            self, original_node: cst.ClassDef, updated_node: cst.ClassDef
        ) -> cst.ClassDef:
            self.depth -= 1
            if self.depth or original_node.name.value != self.facade:
                return updated_node
            return updated_node.with_changes(
                bases=[
                    base.with_changes(value=cst.Name(self.owner))
                    if isinstance(base.value, cst.Name)
                    and base.value.value == self.local
                    else base
                    for base in updated_node.bases
                ]
            )

        @override
        def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
            self.depth += 1
            return True

        @override
        def leave_FunctionDef(
            self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
        ) -> cst.FunctionDef:
            self.depth -= 1
            return updated_node

        @override
        def leave_Name(
            self, original_node: cst.Name, updated_node: cst.Name
        ) -> cst.Name:
            # A private import alias is never rebound, so every read of it is
            # the parent class; the letter itself keeps its deferred reads.
            if self.local != self.imported and original_node.value == self.local:
                return updated_node.with_changes(value=self.owner)
            return updated_node

        @override
        def leave_ImportFrom(
            self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
        ) -> cst.ImportFrom | cst.RemovalSentinel:
            if (
                self.depth
                or original_node.relative
                or isinstance(original_node.names, cst.ImportStar)
                or isinstance(updated_node.names, cst.ImportStar)
                or FlextInfraUtilitiesQualifiedNames.dotted_name(original_node.module)
                != self.module
            ):
                return updated_node
            retained: list[cst.ImportAlias] = []
            for original, updated in zip(
                original_node.names, updated_node.names, strict=True
            ):
                name = FlextInfraUtilitiesQualifiedNames.dotted_name(original.name)
                bound = (
                    FlextInfraUtilitiesQualifiedNames.dotted_name(original.asname.name)
                    if original.asname is not None
                    and isinstance(original.asname.name, cst.Name)
                    else name
                )
                if name != self.imported or bound != self.local:
                    retained.append(updated)
                elif not self.owner_bound:
                    retained.append(
                        updated.with_changes(name=cst.Name(self.owner), asname=None)
                    )
            if not retained:
                return cst.RemoveFromParent()
            return updated_node.with_changes(
                names=[
                    *retained[:-1],
                    retained[-1].with_changes(comma=cst.MaybeSentinel.DEFAULT),
                ]
            )

        @override
        def leave_AnnAssign(
            self, original_node: cst.AnnAssign, updated_node: cst.AnnAssign
        ) -> cst.AnnAssign | cst.Assign:
            # An annotated rebind declares a variable; the letter must stay the
            # implicit alias of its facade class for annotations to resolve.
            if (
                self.depth
                or not isinstance(original_node.target, cst.Name)
                or original_node.target.value != self.imported
                or not isinstance(original_node.value, cst.Name)
                or original_node.value.value != self.facade
            ):
                return updated_node
            return cst.Assign(
                targets=[cst.AssignTarget(target=cst.Name(self.imported))],
                value=cst.Name(self.facade),
            )

    @classmethod
    def _rewrite_facade_base_source(
        cls,
        source: str,
        *,
        shape: t.Quad[str, str, str, str],
        owner: str,
        owner_bound: bool,
    ) -> str:
        """Return the facade source extending ``owner`` with its layout kept."""
        return (
            cst
            .parse_module(source)
            .visit(
                cls._FacadeBaseTransformer(
                    shape=shape, owner=owner, owner_bound=owner_bound
                )
            )
            .code
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverFacadeBaseCst"]
