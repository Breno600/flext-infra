"""Accessor token rewriting + manual-warning detection — extracted concern.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import io
from operator import itemgetter
from tokenize import NAME, generate_tokens
from typing import TYPE_CHECKING, ClassVar

from flext_infra import c, m, u
from flext_infra.refactor._accessor_origin import FlextInfraAccessorOriginResolver

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraAccessorMigrationRewriteMixin:
    """Origin-aware get_/set_/is_ rewriting plus public-accessor warning scan.

    Composed into FlextInfraAccessorMigrationOrchestrator via inheritance; owns
    the automated-rename catalog, the Rope-proven token rewrite, and the manual
    review-warning detection over loose public accessors.
    """

    # Rename rules sourced from c.ENFORCEMENT_ACCESSOR_RENAMES (flext-core SSOT).
    # All entries target flext-core surface (origin="flext_core"); adding a
    # rename = one entry in flext-core's enforcement constant, never duplicated
    # here. The rewrite only renames an occurrence whose defining module
    # resolves inside the rule's origin package — homonyms owned by the scanned
    # repository, by another library, or by a builtin are skipped with a
    # warning, so the verb stays safe on non-flext consumers. Once a source
    # name has been renamed, subsequent passes find zero matching tokens.
    _AUTOMATED_RULES: ClassVar[t.VariadicTuple[m.Infra.AccessorMigrationRule]] = tuple(
        m.Infra.AccessorMigrationRule(
            source_name=src,
            replacement_name=repl,
            reason=reason,
            origin="flext_core",
        )
        for src, (repl, reason) in c.ENFORCEMENT_ACCESSOR_RENAMES.items()
    )
    _AUTOMATED_NAMES: ClassVar[frozenset[str]] = frozenset(
        c.ENFORCEMENT_ACCESSOR_RENAMES,
    )
    _MANUAL_WARNING_REASON: ClassVar[str] = (
        "Public {prefix}-prefixed accessor: rename to canonical verb "
        "(drop the prefix or use resolve_/fetch_/build_/etc.)"
    )
    _SKIPPED_ORIGIN_REASON: ClassVar[str] = (
        "Skipped homonym: resolves to {definition}; only {origin}-owned "
        "definitions are renamed automatically"
    )

    def _apply_automated_rewrites(
        self,
        rope_project: t.Infra.RopeProject,
        py_file: Path,
        source: str,
    ) -> t.Pair[str, t.SequenceOf[m.Infra.AccessorMigrationChange]]:
        """Apply automated rewrites.

        Returns:
            The resulting ``t.Pair[str,
                t.SequenceOf[m.Infra.AccessorMigrationChange]]``.

        """
        resource = u.Infra.resolve_resource_from_path(rope_project, py_file)
        if resource is None:
            return source, ()
        resolver = FlextInfraAccessorOriginResolver(rope_project)
        updated_source = source
        changes: t.MutableSequenceOf[m.Infra.AccessorMigrationChange] = []
        for rule in self._AUTOMATED_RULES:
            updated_source, rule_changes = self._rename_symbol_tokens(
                updated_source,
                rule=rule,
                file_path=py_file,
                resolver=resolver,
            )
            changes.extend(rule_changes)
        return updated_source, tuple(changes)

    @classmethod
    def _rename_symbol_tokens(
        cls,
        source: str,
        *,
        rule: m.Infra.AccessorMigrationRule,
        file_path: Path,
        resolver: FlextInfraAccessorOriginResolver,
    ) -> t.Pair[str, t.SequenceOf[m.Infra.AccessorMigrationChange]]:
        """Rename only origin-owned occurrences of one rule's source name.

        Returns:
            The resulting ``t.Pair[str,
                t.SequenceOf[m.Infra.AccessorMigrationChange]]``.

        """
        token_changes: t.MutableSequenceOf[m.Infra.AccessorMigrationChange] = []
        rewrite_ranges: t.MutableSequenceOf[t.Triple[int, int, str]] = []
        skipped_by_definition: dict[str, int] = {}
        for token in generate_tokens(io.StringIO(source).readline):
            if token.type != NAME or token.string != rule.source_name:
                continue
            line, column = token.start
            start = cls._offset_from_position(source, line, column)
            end = start + len(rule.source_name)
            definition = resolver.occurrence_origin(file_path, start)
            if definition is None or not resolver.within_origin(
                definition,
                origin=rule.origin,
            ):
                skipped_by_definition[definition or "an unresolved module"] = line
                continue
            rewrite_ranges.append((start, end, rule.replacement_name))
            token_changes.append(
                m.Infra.AccessorMigrationChange(
                    file=str(file_path),
                    line=line,
                    original_name=rule.source_name,
                    replacement_name=rule.replacement_name,
                    automated=True,
                    reason=rule.reason,
                ),
            )
        for definition, first_line in sorted(
            skipped_by_definition.items(),
            key=itemgetter(1),
        ):
            token_changes.append(
                m.Infra.AccessorMigrationChange(
                    file=str(file_path),
                    line=first_line,
                    original_name=rule.source_name,
                    replacement_name="",
                    automated=False,
                    reason=cls._SKIPPED_ORIGIN_REASON.format(
                        definition=definition,
                        origin=rule.origin,
                    ),
                ),
            )
        if not rewrite_ranges:
            return source, tuple(token_changes)
        updated_source = source
        for start, end, replacement in sorted(
            rewrite_ranges,
            key=itemgetter(0),
            reverse=True,
        ):
            updated_source = updated_source[:start] + replacement + updated_source[end:]
        return updated_source, tuple(token_changes)

    @staticmethod
    def _offset_from_position(source: str, line: int, column: int) -> int:
        """Offset from position.

        Returns:
            The resulting ``int``.

        """
        source_lines = source.splitlines(keepends=True)
        line_offset = sum(len(item) for item in source_lines[: line - 1])
        return line_offset + column

    @staticmethod
    def _declared_function_name(stripped: str) -> str | None:
        """Return the function name one source line declares, when any.

        Returns:
            The resulting ``str | None``.

        """
        function_prefix = ""
        if stripped.startswith("def "):
            function_prefix = "def "
        elif stripped.startswith("async def "):
            function_prefix = "async def "
        if not function_prefix:
            return None
        return (
            stripped
            .split(function_prefix, maxsplit=1)[1]
            .split("(", maxsplit=1)[0]
            .strip()
        )

    def _function_is_exempt(self, function_name: str) -> bool:
        """Whether one accessor function is already covered without a warning.

        Returns:
            The resulting ``bool``.

        """
        return (
            function_name.startswith("_")
            or function_name in self._AUTOMATED_NAMES
            or function_name in c.ENFORCEMENT_ACCESSOR_EXTERNAL_CONTRACTS
        )

    def _collect_manual_warnings(
        self,
        py_file: Path,
        source: str,
    ) -> t.SequenceOf[m.Infra.AccessorMigrationChange]:
        """Collect manual warnings.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AccessorMigrationChange]``.

        """
        lines = source.splitlines()
        warnings: t.MutableSequenceOf[m.Infra.AccessorMigrationChange] = []
        scope_stack: t.MutableSequenceOf[t.Pair[str, int]] = []
        for line_index, line_text in enumerate(lines, start=1):
            stripped = line_text.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line_text) - len(stripped)
            while scope_stack and indent <= scope_stack[-1][1]:
                scope_stack.pop()
            if stripped.startswith("class "):
                class_name = (
                    stripped
                    .split("class ", maxsplit=1)[1]
                    .split("(", maxsplit=1)[0]
                    .split(":", maxsplit=1)[0]
                    .strip()
                )
                scope_stack.append((f"class:{class_name}", indent))
                continue
            function_name = self._declared_function_name(stripped)
            if function_name is None:
                continue
            parent_scope = scope_stack[-1][0] if scope_stack else "module"
            scope_stack.append((f"def:{function_name}", indent))
            if parent_scope.startswith("def:") or self._function_is_exempt(
                function_name,
            ):
                continue
            matched_prefix = next(
                (
                    p
                    for p in c.Infra.ACCESSOR_WARNING_PREFIXES
                    if function_name.startswith(p)
                ),
                None,
            )
            if matched_prefix is None:
                continue
            warnings.append(
                m.Infra.AccessorMigrationChange(
                    file=str(py_file),
                    line=line_index,
                    original_name=function_name,
                    replacement_name=function_name[len(matched_prefix) :],
                    automated=False,
                    reason=self._MANUAL_WARNING_REASON.format(
                        prefix=matched_prefix.rstrip("_"),
                    ),
                ),
            )
        return warnings


__all__: list[str] = ["FlextInfraAccessorMigrationRewriteMixin"]
