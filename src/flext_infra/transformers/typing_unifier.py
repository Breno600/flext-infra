"""Unify proven type expressions while preserving runtime data and bindings.

Only concrete-syntax type positions participate. Imported aliases and builtin names
are resolved in their lexical scope; Literal values and Annotated metadata are data.
Broad Any/object annotations retain their original consumer contract and findings.
Container parameters widen only when every lexical use is a supported read or a
proven direct alias. Escapes, destructuring, concrete methods and unknown uses retain
their declared contract. Container element types never inherit the outer proof.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

import libcst as cst
from libcst.metadata import (
    GlobalScope,
    MetadataWrapper,
    ParentNodeProvider,
    Scope,
    ScopeProvider,
)

from flext_infra import c, t, u

from ._canonical_t_import import FlextInfraEnsureCanonicalTImportMixin
from ._import_facades import FlextInfraRefactorImportFacades
from ._typing_mutation import FlextInfraTypingMutation
from ._typing_rewrite import FlextInfraRefactorTypingUnifierRewriteMixin
from .rope_transformer import FlextInfraRopeTransformer

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraRefactorTypingUnifier(
    FlextInfraEnsureCanonicalTImportMixin,
    FlextInfraRopeTransformer,
    FlextInfraRefactorTypingUnifierRewriteMixin,
):
    """Unify bound type expressions and modernize module TypeAlias declarations."""

    _description = "canonicalize types and modernize TypeAlias"

    class _Annotations(cst.CSTTransformer):
        METADATA_DEPENDENCIES = (ParentNodeProvider, ScopeProvider)

        def __init__(
            self,
            canonical_map: t.MappingKV[frozenset[str], str],
            readonly: frozenset[str],
        ) -> None:
            self.canonical_map = canonical_map
            self.readonly = readonly
            self.changes: list[str] = []
            self.requires_t = False
            self.facades = FlextInfraRefactorImportFacades()

        def _expression(
            self,
            original: cst.BaseExpression,
            *,
            widen: bool,
        ) -> cst.BaseExpression:
            scope = self.get_metadata(ScopeProvider, original)
            if not isinstance(scope, Scope):
                msg = "type expression has no lexical scope"
                raise TypeError(msg)
            rewriter = FlextInfraRefactorTypingUnifierRewriteMixin.TypeExpression(
                scope,
                canonical_map=self.canonical_map,
                replacements={},
                containers=True,
                widen=widen,
            )
            updated = rewriter.rewrite(original)
            if rewriter.requires_t:
                self.facades.require_available(scope, "t")
            self.changes.extend(rewriter.changes)
            self.requires_t = self.requires_t or rewriter.requires_t
            return updated

        @override
        def visit_Annotation(self, node: cst.Annotation) -> bool:
            return False

        @override
        def leave_Annotation(
            self,
            original_node: cst.Annotation,
            updated_node: cst.Annotation,
        ) -> cst.Annotation:
            parent = self.get_metadata(ParentNodeProvider, original_node)
            widen = False
            if isinstance(parent, cst.Param):
                scope = self.get_metadata(ScopeProvider, parent.name)
                if not isinstance(scope, Scope):
                    msg = "parameter annotation has no lexical scope"
                    raise TypeError(msg)
                bindings = frozenset(
                    name.name for name in scope.get_qualified_names_for(parent.name)
                )
                widen = bool(bindings) and bindings.issubset(self.readonly)
            return updated_node.with_changes(
                annotation=self._expression(original_node.annotation, widen=widen),
            )

        @override
        def leave_AnnAssign(
            self,
            original_node: cst.AnnAssign,
            updated_node: cst.AnnAssign,
        ) -> cst.BaseSmallStatement:
            scope = self.get_metadata(ScopeProvider, original_node)
            if not isinstance(scope, GlobalScope) or original_node.value is None:
                return updated_node
            names = {
                name.name
                for name in scope.get_qualified_names_for(
                    original_node.annotation.annotation,
                )
            }
            if names not in ({"typing.TypeAlias"}, {"typing_extensions.TypeAlias"}):
                return updated_node
            if not isinstance(original_node.target, cst.Name):
                msg = "module TypeAlias declaration must bind one identifier"
                raise TypeError(msg)
            self.changes.append(
                f"Converted legacy TypeAlias assignment: {original_node.target.value}",
            )
            return cst.TypeAlias(
                name=original_node.target,
                value=self._expression(original_node.value, widen=False),
                semicolon=updated_node.semicolon,
            )

        @override
        def leave_TypeAlias(
            self,
            original_node: cst.TypeAlias,
            updated_node: cst.TypeAlias,
        ) -> cst.TypeAlias:
            return updated_node.with_changes(
                value=self._expression(original_node.value, widen=False),
            )

    def __init__(
        self,
        *,
        canonical_map: t.MappingKV[frozenset[str], str],
        file_path: Path | None = None,
    ) -> None:
        """Initialize the declared union map and the consumer's source location."""
        super().__init__()
        self._canonical_map = canonical_map
        self._file_path = file_path
        self._is_definition_file = self._is_typing_definition_file(file_path)

    @override
    def apply_to_source(self, source: str) -> t.Infra.TransformResult:
        """Transform syntax owned by type annotations; parse failures escape."""
        self.changes.clear()
        if self._is_definition_file:
            return source, list(self.changes)
        wrapper = MetadataWrapper(cst.parse_module(source))
        mutations = FlextInfraTypingMutation()
        wrapper.visit(mutations)
        visitor = self._Annotations(self._canonical_map, mutations.readonly_bindings())
        updated = wrapper.visit(visitor).code
        changes = list(visitor.changes)
        if visitor.requires_t:
            module_name = self.canonical_import_module(self._file_path)
            if (
                self._file_path is not None
                and self._file_path.exists()
                and u.Infra.package_name(self._file_path).split(".", maxsplit=1)[0]
                == module_name
                and not u.Infra.has_runtime_alias_import(source, "t")
                and not u.Infra.has_runtime_alias_import(source)
            ):
                msg = (
                    "typing unification requires proven runtime availability of its "
                    "owning package facade before introducing a self import"
                )
                raise ValueError(msg)
            updated, did_add = self._ensure_t_import(updated, module_name)
            if did_add:
                changes.append(f"Added canonical t import from {module_name}")
        for change in changes:
            self._record_change(change)
        return updated, list(self.changes)

    @staticmethod
    def _is_typing_definition_file(file_path: Path | None) -> bool:
        """Keep facade type-definition owners outside consumer canonicalization."""
        if file_path is None:
            return False
        return any(part in c.Infra.TYPING_DEFINITION_FILES for part in file_path.parts)


__all__: list[str] = ["FlextInfraRefactorTypingUnifier"]
