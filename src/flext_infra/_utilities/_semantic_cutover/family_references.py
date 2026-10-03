"""Identity-bound consumer edits for one pure namespace wrapper.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra import c, m, p, t
from flext_infra._utilities._semantic_cutover.family_type_references import (
    FlextInfraUtilitiesSemanticFamilyTypeReferences,
)
from flext_infra._utilities.rope_runtime_refactors import (
    FlextInfraUtilitiesRopeRuntimeRefactors,
)
from flext_infra._utilities.rope_structure import FlextInfraUtilitiesRopeStructure


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
        runtime = FlextInfraUtilitiesRopeRuntimeRefactors
        project, wrapper, names = flatten.project, flatten.wrapper, flatten.names
        wrapper_name = flatten.wrapper_name
        finder = runtime.create_occurrence_finder(
            project,
            wrapper_name,
            wrapper,
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
                return (True, ())
            suffix = source[end:]
            member_offset = end + len(suffix) - len(suffix.lstrip()) + 1
            while source[member_offset].isspace():
                member_offset += 1
            member_end = member_offset
            while member_end < len(source) and (
                source[member_end].isalnum() or source[member_end] == "_"
            ):
                member_end += 1
            member_name = source[member_offset:member_end]
            if member_name not in names:
                # The consumer reaches a member the flatten does not own
                # (e.g. inherited); preserving the wrapper keeps the reference.
                return (True, ())
        statements = FlextInfraUtilitiesRopeStructure.logical_statements(source)
        edits: list[m.Infra.SourceRewrite] = []
        for name, replacement in names.items():
            member = wrapper.get_object().get_attribute(name)
            members = runtime.create_occurrence_finder(
                project,
                name,
                member,
                imports=True,
                in_hierarchy=False,
            )
            for occurrence in members.find_occurrences(resource=resource):
                start, end = occurrence.get_word_range()
                primary_start, primary_end = runtime.word_primary_range(
                    source,
                    occurrence.offset,
                )
                primary = source[primary_start:primary_end]
                qualifier, dot, _member = primary.rpartition(".")
                parent, separator, last = qualifier.rpartition(".")
                if dot and (last if separator else qualifier) == wrapper_name:
                    if not separator:
                        in_function = any(
                            statement.line <= occurrence.lineno <= statement.end_line
                            and statement.enclosing_kind
                            == c.Infra.RopeScopeKind.FUNCTION
                            for statement in statements
                        )
                        parent = flatten.owner_name if in_function else ""
                    text = f"{parent}.{replacement}" if parent else replacement
                    edits.append(
                        m.Infra.SourceRewrite(
                            start=primary_start,
                            end=primary_end,
                            text=text,
                        ),
                    )
                elif name != replacement:
                    edits.append(
                        m.Infra.SourceRewrite(start=start, end=end, text=replacement),
                    )
        blocked, quoted = cls._family_quoted_rewrites(resource, source, flatten=flatten)
        return (True, ()) if blocked else (False, (*edits, *quoted))


__all__: list[str] = ["FlextInfraUtilitiesSemanticFamilyReferences"]
