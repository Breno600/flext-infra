"""Identity-bound consumer edits for one pure namespace wrapper."""

from __future__ import annotations

from flext_infra import c, m, p, t

from ..rope_runtime_refactors import FlextInfraUtilitiesRopeRuntimeRefactors
from ..rope_structure import FlextInfraUtilitiesRopeStructure
from .family_type_references import FlextInfraUtilitiesSemanticFamilyTypeReferences


class FlextInfraUtilitiesSemanticFamilyReferences(
    FlextInfraUtilitiesSemanticFamilyTypeReferences
):
    """Use Rope occurrences, never textual wrapper-name substitutions."""

    @classmethod
    def _family_consumer_rewrites(
        cls,
        project: p.Infra.RopeProject,
        resource: p.Infra.RopeResource,
        source: str,
        *,
        owner_name: str,
        wrapper_name: str,
        wrapper: p.Infra.RopePyName,
        names: t.MappingKV[str, str],
    ) -> t.Pair[bool, t.VariadicTuple[m.Infra.SourceRewrite]]:
        runtime = FlextInfraUtilitiesRopeRuntimeRefactors
        finder = runtime.create_occurrence_finder(
            project, wrapper_name, wrapper, imports=True, in_hierarchy=False
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
                project, name, member, imports=True, in_hierarchy=False
            )
            for occurrence in members.find_occurrences(resource=resource):
                start, end = occurrence.get_word_range()
                primary_start, primary_end = runtime.word_primary_range(
                    source, occurrence.offset
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
                        parent = owner_name if in_function else ""
                    text = f"{parent}.{replacement}" if parent else replacement
                    edits.append(
                        m.Infra.SourceRewrite(
                            start=primary_start, end=primary_end, text=text
                        )
                    )
                elif name != replacement:
                    edits.append(
                        m.Infra.SourceRewrite(start=start, end=end, text=replacement)
                    )
        blocked, quoted = cls._family_quoted_rewrites(
            project,
            resource,
            source,
            owner_name=owner_name,
            wrapper=wrapper,
            names=names,
        )
        return (True, ()) if blocked else (False, (*edits, *quoted))


__all__: list[str] = ["FlextInfraUtilitiesSemanticFamilyReferences"]
