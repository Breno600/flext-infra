"""Identity-bound consumer edits for one pure namespace wrapper.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra import c, m, p, t
from flext_infra._utilities import (
    FlextInfraUtilitiesRopeRuntimeRefactors,
    FlextInfraUtilitiesRopeStructure,
)
from flext_infra._utilities._semantic_cutover.family_type_references import (
    FlextInfraUtilitiesSemanticFamilyTypeReferences,
)


class FlextInfraUtilitiesSemanticFamilyReferences(
    FlextInfraUtilitiesSemanticFamilyTypeReferences,
):
    """Use Rope occurrences, never textual wrapper-name substitutions."""

    @classmethod
    def _family_consumer_rewrites(
        cls,
        resource: p.Infra.RopeResource,
        source: str,
        *,
        flatten: m.Infra.FamilyWrapperFlatten,
    ) -> t.Pair[bool, t.VariadicTuple[m.Infra.SourceRewrite]]:

        if cls._wrapper_blocked_usages(resource, source, flatten=flatten):
            return (True, ())
        edits = cls._member_occurrence_edits(resource, source, flatten=flatten)
        blocked, quoted = cls._family_quoted_rewrites(resource, source, flatten=flatten)
        return (True, ()) if blocked else (False, (*edits, *quoted))

    @classmethod
    def _wrapper_blocked_usages(
        cls,
        resource: p.Infra.RopeResource,
        source: str,
        *,
        flatten: m.Infra.FamilyWrapperFlatten,
    ) -> bool:
        """Report a consumer usage only a real wrapper entity satisfies.

        Returns:
            The resulting ``bool``.

        """
        finder = FlextInfraUtilitiesRopeRuntimeRefactors.create_occurrence_finder(
            flatten.project,
            flatten.wrapper_name,
            flatten.wrapper,
            imports=True,
            in_hierarchy=False,
        )
        for occurrence in finder.find_occurrences(resource=resource):
            if occurrence.is_defined():
                continue
            _start, end = occurrence.get_word_range()
            if not source[end:].lstrip().startswith("."):
                # Used as a value or inheritance base: the wrapper is a real
                # entity class, preserved instead of flattened.
                return True
            if cls._member_name_at(source, end) not in flatten.names:
                # The consumer reaches a member the flatten does not own
                # (e.g. inherited); preserving the wrapper keeps the reference.
                return True
        return False

    @staticmethod
    def _member_name_at(source: str, end: int) -> str:
        """Return the attribute member name one wrapper reference selects.

        Returns:
            The resulting ``str``.

        """
        suffix = source[end:]
        member_offset = end + len(suffix) - len(suffix.lstrip()) + 1
        while source[member_offset].isspace():
            member_offset += 1
        member_end = member_offset
        while member_end < len(source) and (
            source[member_end].isalnum() or source[member_end] == "_"
        ):
            member_end += 1
        return source[member_offset:member_end]

    @staticmethod
    def _wrapper_qualified(
        primary: str,
        wrapper_name: str,
    ) -> t.Triple[str, bool, bool]:
        """Split one primary expression into its qualifier parent and match.

        Returns:
            The resulting ``(parent, separator present, wrapper-qualified)``
            triple.

        """
        qualifier, dot, _member = primary.rpartition(".")
        parent, separator, last = qualifier.rpartition(".")
        scope_name = last if separator else qualifier
        return parent, bool(separator), bool(dot and scope_name == wrapper_name)

    @staticmethod
    def _occurrence_in_function(
        statements: t.SequenceOf[m.Infra.LogicalStatement],
        occurrence: t.Infra.RopeOccurrence,
    ) -> bool:
        """Whether one occurrence sits inside a function scope.

        Returns:
            The resulting ``bool``.

        """
        return any(
            statement.line <= occurrence.lineno <= statement.end_line
            and statement.enclosing_kind == c.Infra.RopeScopeKind.FUNCTION
            for statement in statements
        )

    @classmethod
    def _occurrence_edit(
        cls,
        flatten: m.Infra.FamilyWrapperFlatten,
        statements: t.SequenceOf[m.Infra.LogicalStatement],
        source: str,
        occurrence: t.Infra.RopeOccurrence,
        name_replacement: t.Pair[str, str],
    ) -> m.Infra.SourceRewrite | None:
        """Build one member occurrence rewrite, or ``None`` when unrelated.

        Returns:
            The resulting ``m.Infra.SourceRewrite | None``.

        """
        name, replacement = name_replacement
        start, end = occurrence.get_word_range()
        primary_start, primary_end = (
            FlextInfraUtilitiesRopeRuntimeRefactors.word_primary_range(
                source,
                occurrence.offset,
            )
        )
        primary = source[primary_start:primary_end]
        parent, separator, qualified = cls._wrapper_qualified(
            primary,
            flatten.wrapper_name,
        )
        if qualified:
            if not separator and cls._occurrence_in_function(statements, occurrence):
                parent = flatten.owner_name
            return m.Infra.SourceRewrite(
                start=primary_start,
                end=primary_end,
                text=f"{parent}.{replacement}" if parent else replacement,
            )
        if name != replacement:
            return m.Infra.SourceRewrite(start=start, end=end, text=replacement)
        return None

    @classmethod
    def _member_occurrence_edits(
        cls,
        resource: p.Infra.RopeResource,
        source: str,
        *,
        flatten: m.Infra.FamilyWrapperFlatten,
    ) -> list[m.Infra.SourceRewrite]:
        """Rewrite every member occurrence to its prefixed flattened identity.

        Returns:
            The resulting ``list[m.Infra.SourceRewrite]``.

        """
        runtime = FlextInfraUtilitiesRopeRuntimeRefactors
        statements = FlextInfraUtilitiesRopeStructure.logical_statements(source)
        edits: list[m.Infra.SourceRewrite] = []
        for name, replacement in flatten.names.items():
            member = flatten.wrapper.get_object().get_attribute(name)
            members = runtime.create_occurrence_finder(
                flatten.project,
                name,
                member,
                imports=True,
                in_hierarchy=False,
            )
            for occurrence in members.find_occurrences(resource=resource):
                edit = cls._occurrence_edit(
                    flatten,
                    statements,
                    source,
                    occurrence,
                    (name, replacement),
                )
                if edit is not None:
                    edits.append(edit)
        return edits


__all__: list[str] = ["FlextInfraUtilitiesSemanticFamilyReferences"]
