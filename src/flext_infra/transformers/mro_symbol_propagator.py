"""Symbol propagation transformer for MRO-migrated imports — rope-based."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra import c
from flext_infra.transformers.base import FlextInfraRopeTransformer

if TYPE_CHECKING:
    from collections.abc import Callable

    from flext_infra import t


class FlextInfraRefactorMROSymbolPropagator(FlextInfraRopeTransformer):
    """Rewrite imports and references after symbols move into facade namespaces.

    For each module_move entry, rewrites ``from old_module import Symbol``
    to ``from old_module import Facade`` and qualifies bare references
    as ``Facade.NestedPath``.
    """

    def __init__(
        self,
        *,
        module_moves: t.MappingKV[str, t.Pair[str, t.StrMapping]],
        on_change: t.Infra.ChangeCallback = None,
    ) -> None:
        """Initialize with module move configuration."""
        super().__init__(on_change=on_change)
        self._module_moves = module_moves

    def rewrite_source(self, source: str) -> t.Infra.TransformResult:
        """Rewrite one source string using the configured MRO move map."""
        self.changes.clear()
        rewritten_source = source
        for module_name, (facade_alias, symbol_paths) in self._module_moves.items():
            rewritten_source = self._rewrite_from_imports(
                rewritten_source,
                module_name=module_name,
                facade_alias=facade_alias,
                symbol_paths=symbol_paths,
            )
            rewritten_source = self._qualify_bare_references(
                rewritten_source, facade_alias=facade_alias, symbol_paths=symbol_paths
            )
            rewritten_source = self._qualify_type_annotations(
                rewritten_source, facade_alias=facade_alias, symbol_paths=symbol_paths
            )
            rewritten_source = self._qualify_return_annotations(
                rewritten_source, facade_alias=facade_alias, symbol_paths=symbol_paths
            )
        return (rewritten_source, list(self.changes))

    @override
    def apply_to_source(self, source: str) -> t.Infra.TransformResult:
        """Satisfy the base rope-transformer contract with the same rewrite flow."""
        return self.rewrite_source(source)

    @override
    def transform(
        self, rope_project: t.Infra.RopeProject, resource: t.Infra.RopeResource
    ) -> t.Infra.TransformResult:
        """Apply import and reference rewrites. Returns (new_source, changes)."""
        source = resource.read()
        rewritten_source, changes = self.rewrite_source(source)
        if rewritten_source != source and changes:
            resource.write(rewritten_source)
        return (rewritten_source, changes)

    def _apply_symbol_rewrites(
        self,
        source: str,
        symbol_paths: t.StrMapping,
        pattern_fn: Callable[[str, str], t.Infra.RegexPattern],
        replacement_fn: Callable[[str, str], str],
        message_fn: Callable[[str, str], str],
    ) -> str:
        """Apply regex rewrites for each symbol in *symbol_paths*."""
        for old_symbol, target_path in symbol_paths.items():
            pattern = pattern_fn(old_symbol, target_path)
            repl = replacement_fn(old_symbol, target_path)
            new_source = pattern.sub(repl, source)
            if new_source != source:
                self._record_change(message_fn(old_symbol, target_path))
                source = new_source
        return source

    def _rewrite_from_imports(
        self,
        source: str,
        *,
        module_name: str,
        facade_alias: str,
        symbol_paths: t.StrMapping,
    ) -> str:
        """Rewrite ``from module import OldSymbol`` to ``from module import Facade``."""
        return self._apply_symbol_rewrites(
            source,
            symbol_paths,
            pattern_fn=lambda old, _: c.Infra.compile_mro_import_rewrite(
                module_name, old
            ),
            replacement_fn=lambda _, __: rf"\1{facade_alias}",
            message_fn=lambda old, tp: (
                f"Rewired import: {module_name}.{old} -> {facade_alias}.{tp}"
            ),
        )

    def _qualify_bare_references(
        self, source: str, *, facade_alias: str, symbol_paths: t.StrMapping
    ) -> str:
        """Replace bare symbol references with qualified facade paths."""
        return self._apply_symbol_rewrites(
            source,
            symbol_paths,
            pattern_fn=lambda old, _: c.Infra.compile_mro_bare_qualify(old),
            replacement_fn=lambda _, tp: f"{facade_alias}.{tp}",
            message_fn=lambda old, tp: (
                f"Qualified reference: {old} -> {facade_alias}.{tp}"
            ),
        )

    def _qualify_prefixed_annotations(
        self,
        source: str,
        *,
        facade_alias: str,
        symbol_paths: t.StrMapping,
        prefix: str,
        message_prefix: str,
    ) -> str:
        """Replace prefixed annotations with qualified facade paths."""
        return self._apply_symbol_rewrites(
            source,
            symbol_paths,
            pattern_fn=lambda old, _: c.Infra.compile_mro_prefixed_annotation(
                prefix, old
            ),
            replacement_fn=lambda _, tp: rf"\1{facade_alias}.{tp}",
            message_fn=lambda old, tp: (
                f"{message_prefix}: {old} -> {facade_alias}.{tp}"
            ),
        )

    def _qualify_type_annotations(
        self, source: str, *, facade_alias: str, symbol_paths: t.StrMapping
    ) -> str:
        """Replace ``: Symbol`` with ``: Facade.Symbol``."""
        return self._qualify_prefixed_annotations(
            source,
            facade_alias=facade_alias,
            symbol_paths=symbol_paths,
            prefix=":",
            message_prefix="Qualified annotation",
        )

    def _qualify_return_annotations(
        self, source: str, *, facade_alias: str, symbol_paths: t.StrMapping
    ) -> str:
        """Replace ``-> Symbol`` with ``-> Facade.Symbol``."""
        return self._qualify_prefixed_annotations(
            source,
            facade_alias=facade_alias,
            symbol_paths=symbol_paths,
            prefix="->",
            message_prefix="Qualified return",
        )


__all__: list[str] = ["FlextInfraRefactorMROSymbolPropagator"]
