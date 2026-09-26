"""Migrate imported symbols through their lexical binding, preserving data."""

from __future__ import annotations

from typing import cast, override

import libcst as cst
from libcst.metadata import (
    CodeRange,
    ImportAssignment,
    MetadataWrapper,
    ParentNodeProvider,
    PositionProvider,
    QualifiedNameProvider,
    Scope,
    ScopeProvider,
)

from flext_infra import c, t, u

from .._utilities.transformer_base import FlextInfraRopeTransformer
from ._import_facades import FlextInfraRefactorImportFacades
from ._typing_rewrite import FlextInfraRefactorTypingUnifierRewriteMixin


class FlextInfraRefactorImportModernizer(FlextInfraRopeTransformer):
    """Rewrite imports and bound uses atomically, including quoted type positions."""

    class _ImportStatements(cst.CSTTransformer):
        """Publish the replacement chosen for each complete import statement."""

        def __init__(
            self,
            replacements: t.MappingKV[
                cst.BaseSmallStatement, t.SequenceOf[cst.BaseSmallStatement]
            ],
        ) -> None:
            """Retain replacements keyed by their original statement identity."""
            self.replacements = replacements

        @override
        def on_leave(
            self, original_node: cst.CSTNodeT, updated_node: cst.CSTNodeT
        ) -> cst.CSTNodeT | cst.RemovalSentinel | cst.FlattenSentinel[cst.CSTNodeT]:
            if (
                isinstance(original_node, cst.BaseSmallStatement)
                and original_node in self.replacements
            ):
                statements = self.replacements[original_node]
                return (
                    cast(
                        "cst.FlattenSentinel[cst.CSTNodeT]",
                        cst.FlattenSentinel(statements),
                    )
                    if statements
                    else cst.RemoveFromParent()
                )
            return updated_node

    class _Bindings(cst.CSTTransformer):
        METADATA_DEPENDENCIES = (
            ParentNodeProvider,
            QualifiedNameProvider,
            ScopeProvider,
            PositionProvider,
        )

        def __init__(self, replacements: t.StrMapping, source: str) -> None:
            self.replacements = replacements
            self.changes: list[str] = []
            self.aliases_by_import: t.MutableMappingKV[cst.CSTNode, set[str]] = {}
            self.imports: list[
                tuple[cst.Import | cst.ImportFrom, cst.Import | cst.ImportFrom, Scope]
            ] = []
            self.facades = FlextInfraRefactorImportFacades()
            self.exports = u.Infra.public_export_names_source(source)
            self.type_ranges = u.Infra.type_expression_ranges(source)
            self.line_offsets = [0]
            for line in source.splitlines(keepends=True):
                self.line_offsets.append(self.line_offsets[-1] + len(line))

        @override
        def on_leave(
            self, original_node: cst.CSTNodeT, updated_node: cst.CSTNodeT
        ) -> cst.CSTNodeT | cst.RemovalSentinel | cst.FlattenSentinel[cst.CSTNodeT]:
            updated = super().on_leave(original_node, updated_node)
            if isinstance(original_node, cst.Import | cst.ImportFrom) and isinstance(
                updated, cst.Import | cst.ImportFrom
            ):
                self.imports.append((
                    original_node,
                    updated,
                    self._scope(original_node),
                ))
            if not isinstance(original_node, cst.BaseExpression):
                return updated
            location = self.get_metadata(PositionProvider, original_node, None)
            if not isinstance(location, CodeRange):
                msg = "type-position migration has no source location"
                raise TypeError(msg)
            span = (
                self.line_offsets[location.start.line - 1] + location.start.column,
                self.line_offsets[location.end.line - 1] + location.end.column,
            )
            if span not in self.type_ranges:
                return updated
            if not isinstance(updated, cst.BaseExpression):
                msg = "type-position migration did not retain an expression"
                raise TypeError(msg)
            return cast("cst.CSTNodeT", self._type_expression(original_node, updated))

        def _scope(self, node: cst.CSTNode) -> Scope:
            scope = self.get_metadata(ScopeProvider, node)
            if not isinstance(scope, Scope):
                msg = "import migration has no lexical scope"
                raise TypeError(msg)
            return scope

        def _require_binding(
            self, scope: Scope, original: cst.BaseExpression, replacement: str
        ) -> None:
            name = u.Infra.dotted_name(original)
            if name is None:
                msg = "import migration requires a named lexical binding"
                raise ValueError(msg)
            assignments = scope[name.split(".", maxsplit=1)[0]]
            if len(assignments) != 1:
                msg = f"import migration has competing assignments for {name}"
                raise ValueError(msg)
            assignment = next(iter(assignments))
            if not isinstance(assignment, ImportAssignment):
                msg = f"import migration has no import declaration for {name}"
                raise TypeError(msg)
            alias = replacement.split(".", maxsplit=1)[0]
            self.facades.require_available(scope, alias)
            self.aliases_by_import.setdefault(assignment.node, set()).add(alias)

        def _replacement(
            self, original: cst.BaseExpression, updated: cst.BaseExpression
        ) -> cst.BaseExpression:
            names = self.get_metadata(QualifiedNameProvider, original, ())
            replacements = {
                self.replacements[name.name]
                for name in names
                if name.name in self.replacements
            }
            if not replacements:
                return updated
            if len(names) != 1 or len(replacements) != 1:
                msg = "import migration cannot resolve one symbol binding"
                raise ValueError(msg)
            replacement = replacements.pop()
            self._require_binding(self._scope(original), original, replacement)
            self.changes.append(f"Replaced imported symbol with {replacement}")
            return cst.parse_expression(replacement)

        @override
        def visit_Import(self, node: cst.Import) -> bool:
            return False

        @override
        def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
            return False

        @override
        def leave_Name(
            self, original_node: cst.Name, updated_node: cst.Name
        ) -> cst.BaseExpression:
            parent = self.get_metadata(ParentNodeProvider, original_node)
            if u.Infra.rebinds_name_in_place(parent, original_node):
                return updated_node
            return self._replacement(original_node, updated_node)

        @override
        def leave_Attribute(
            self, original_node: cst.Attribute, updated_node: cst.Attribute
        ) -> cst.BaseExpression:
            return self._replacement(original_node, updated_node)

        def _type_expression(
            self, original: cst.BaseExpression, updated: cst.BaseExpression
        ) -> cst.BaseExpression:
            scope = self._scope(original)
            rewriter = FlextInfraRefactorTypingUnifierRewriteMixin.TypeExpression(
                scope,
                canonical_map={},
                replacements=self.replacements,
                containers=False,
                widen=False,
            )
            annotation = rewriter.rewrite(updated)
            for symbol, replacement in rewriter.replaced_symbols:
                self._require_binding(scope, symbol, replacement)
            self.changes.extend(rewriter.changes)
            return annotation

        def _replacement_alias(
            self, imported: cst.ImportAlias, replacement: str
        ) -> str:
            """Require the removed binding's public consumers to have migrated."""
            bound = u.Infra.dotted_name(
                imported.asname.name if imported.asname else imported.name
            )
            if bound is None:
                msg = "import migration requires a static bound import name"
                raise TypeError(msg)
            if bound in self.exports:
                msg = f"import migration requires re-export consumers for {bound}"
                raise ValueError(msg)
            return replacement.split(".", maxsplit=1)[0]

        def _from_import(
            self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
        ) -> tuple[list[cst.BaseSmallStatement], set[str]]:
            module = u.Infra.dotted_name(original_node.module)
            if (
                original_node.relative
                or module is None
                or isinstance(original_node.names, cst.ImportStar)
            ):
                return [updated_node], set()
            retained: list[cst.ImportAlias] = []
            aliases: set[str] = set()
            for imported in original_node.names:
                name = u.Infra.dotted_name(imported.name)
                replacement = self.replacements.get(f"{module}.{name}")
                if replacement is None:
                    retained.append(imported)
                else:
                    aliases.add(self._replacement_alias(imported, replacement))
            if not aliases:
                return [updated_node], set()
            statements: list[cst.BaseSmallStatement] = []
            if retained:
                statements.append(
                    updated_node.with_changes(
                        names=u.Infra.normalized_import_aliases(
                            retained, parenthesized=bool(updated_node.lpar)
                        )
                    )
                )
            self.changes.append(
                f"Replaced import from {module} with its declared facade"
            )
            return statements, aliases

        @override
        def leave_Module(
            self, original_node: cst.Module, updated_node: cst.Module
        ) -> cst.Module:
            replacements: t.MutableMappingKV[
                cst.BaseSmallStatement, list[cst.BaseSmallStatement]
            ] = {}
            for original, updated, scope in self.imports:
                self._verify_string_consumers(original, scope)
                statements: list[cst.BaseSmallStatement]
                aliases: set[str]
                if isinstance(original, cst.ImportFrom) and isinstance(
                    updated, cst.ImportFrom
                ):
                    statements, aliases = self._from_import(original, updated)
                else:
                    statements = [updated]
                    aliases = self.aliases_by_import.get(original, set())
                for alias in sorted(aliases):
                    declaration = self._alias_import(scope, alias, original)
                    if declaration is not None:
                        statements.append(declaration)
                replacements[updated] = statements
            return updated_node.visit(
                FlextInfraRefactorImportModernizer._ImportStatements(replacements)
            )

        def _verify_string_consumers(
            self, declaration: cst.CSTNode, scope: Scope
        ) -> None:
            """Reject unsupported deferred typing-call consumers before import removal."""
            for assignment in scope.assignments:
                if (
                    not isinstance(assignment, ImportAssignment)
                    or assignment.node is not declaration
                ):
                    continue
                for access in assignment.references:
                    self._verify_typing_call_string(
                        access.node, access.scope, is_type_hint=access.is_type_hint
                    )

        def _verify_typing_call_string(
            self, node: cst.CSTNode, scope: Scope, *, is_type_hint: bool
        ) -> None:
            if not is_type_hint or not isinstance(
                node, cst.SimpleString | cst.ConcatenatedString
            ):
                return
            parent = self.get_metadata(ParentNodeProvider, node, None)
            while parent is not None and not isinstance(parent, cst.Call):
                parent = self.get_metadata(ParentNodeProvider, parent, None)
            if parent is None:
                return
            rewriter = FlextInfraRefactorTypingUnifierRewriteMixin.TypeExpression(
                scope,
                canonical_map={},
                replacements=self.replacements,
                containers=False,
                widen=False,
            )
            if not rewriter.rewrite(node).deep_equals(node):
                msg = "import migration cannot publish an unresolved deferred typing-call consumer"
                raise ValueError(msg)

        def _alias_import(
            self, scope: Scope, alias: str, original: cst.CSTNode
        ) -> cst.ImportFrom | None:
            """Reuse only an earlier declaration in the same straight-line suite."""
            bound = self.facades.require_available(scope, alias)
            module = c.Infra.PKG_CORE_UNDERSCORE
            if bound:
                identity = next(iter(scope.get_qualified_names_for(alias)))
                module = identity.name.rpartition(".")[0]
                if any(
                    isinstance(assignment, ImportAssignment)
                    and self._dominates(assignment.node, original)
                    for assignment in scope[alias]
                ):
                    return None
                self._reject_ancestral_capture(scope, alias)
            return cst.ImportFrom(
                module=u.Infra.module_expression(module),
                names=(cst.ImportAlias(cst.Name(alias)),),
            )

        @classmethod
        def _reject_ancestral_capture(cls, scope: Scope, alias: str) -> None:
            """A new local import must not rebind existing reads of an ancestor."""
            for assignment in scope[alias]:
                if assignment.scope is scope:
                    continue
                if any(
                    cls._contains_scope(scope, access.scope)
                    for access in assignment.references
                ):
                    msg = f"import migration would capture ancestral binding {alias!r}"
                    raise ValueError(msg)

        @staticmethod
        def _contains_scope(owner: Scope, candidate: Scope) -> bool:
            """Include descendant closures when checking lexical capture."""
            while candidate is not owner and candidate.parent is not candidate:
                candidate = candidate.parent
            return candidate is owner

        def _dominates(self, declaration: cst.CSTNode, consumer: cst.CSTNode) -> bool:
            """Different branches or TYPE_CHECKING suites provide no runtime proof."""
            left = self.get_metadata(ParentNodeProvider, declaration)
            right = self.get_metadata(ParentNodeProvider, consumer)
            if not isinstance(left, cst.SimpleStatementLine) or not isinstance(
                right, cst.SimpleStatementLine
            ):
                return False
            suite = self.get_metadata(ParentNodeProvider, left)
            if suite is not self.get_metadata(ParentNodeProvider, right):
                return False
            if not isinstance(suite, cst.Module | cst.IndentedBlock):
                return False
            return suite.body.index(left) < suite.body.index(right)

    def __init__(
        self,
        imports_to_remove: t.StrSequence,
        symbols_to_replace: t.StrMapping,
        runtime_aliases: t.Infra.StrSet,
        blocked_aliases: t.Infra.StrSet,
        on_change: t.Infra.ChangeCallback = None,
    ) -> None:
        """Retain the configured source modules and their public replacement paths."""
        super().__init__(on_change=on_change)
        self._replacements = {
            f"{module}.{symbol}": replacement
            for module in imports_to_remove
            for symbol, replacement in symbols_to_replace.items()
            if replacement.split(".", maxsplit=1)[0] not in blocked_aliases
        }
        for replacement in self._replacements.values():
            if replacement.split(".", maxsplit=1)[0] not in runtime_aliases:
                msg = f"undeclared runtime facade in import replacement: {replacement}"
                raise ValueError(msg)

    @override
    def transform(
        self, rope_project: t.Infra.RopeProject, resource: t.Infra.RopeResource
    ) -> t.Infra.TransformResult:
        """Publish a complete binding-proven rewrite to the owned resource."""
        source = resource.read()
        updated, changes = self.apply_to_source(source)
        if updated != source and changes:
            resource.write(updated)
        return updated, changes

    @override
    def apply_to_source(self, source: str) -> t.Infra.TransformResult:
        """Return migrated syntax; malformed or ambiguous input escapes unchanged."""
        self.changes.clear()
        visitor = self._Bindings(self._replacements, source)
        updated = MetadataWrapper(cst.parse_module(source)).visit(visitor).code
        for change in visitor.changes:
            self._record_change(change)
        return updated, list(self.changes)


__all__: list[str] = ["FlextInfraRefactorImportModernizer"]
