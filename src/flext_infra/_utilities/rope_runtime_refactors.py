"""Rope refactor and occurrence boundary methods."""

from __future__ import annotations

from typing import ClassVar

from rope.base import codeanalyze, simplify

from flext_infra import m, p, t

from .rope_runtime_base import FlextInfraUtilitiesRopeRuntimeBase


class FlextInfraUtilitiesRopeRuntimeRefactors(FlextInfraUtilitiesRopeRuntimeBase):
    """Load Rope refactor helpers behind protocols."""

    _WORD_RANGE_SIZE: ClassVar[int] = 2

    @staticmethod
    def unwrap_class_rewrites(
        source: str,
        *,
        header_start: int,
        header_end: int,
        body_end: int,
        indentation: int,
    ) -> t.VariadicTuple[m.Infra.SourceRewrite]:
        """Remove one Rope-resolved header without changing literal payloads."""
        lines = codeanalyze.SourceLinesAdapter(source)
        regions = tuple(simplify.ignored_regions(source))
        start = lines.get_line_start(header_start)
        end = min(lines.get_line_end(header_end) + 1, len(source))
        comments = "".join(
            source[begin:finish] + "\n"
            for begin, finish, _metadata in regions
            if start <= begin < end and source[begin:finish].startswith("#")
        )
        prefix = lines.get_line(header_start)
        prefix = prefix[: len(prefix) - len(prefix.lstrip())]
        edits = [
            m.Infra.SourceRewrite(
                start=start,
                end=end,
                text="".join(prefix + line for line in comments.splitlines(True)),
            )
        ]
        for number in range(header_end + 1, body_end + 1):
            offset = lines.get_line_start(number)
            line = lines.get_line(number)
            if not line.strip() or any(
                begin < offset < finish
                for begin, finish, _metadata in regions
                if not source[begin:finish].startswith("#")
            ):
                continue
            if len(line) - len(line.lstrip()) < indentation:
                msg = "Rope wrapper body has inconsistent indentation"
                raise ValueError(msg)
            edits.append(
                m.Infra.SourceRewrite(start=offset, end=offset + indentation, text="")
            )
        return tuple(edits)

    @classmethod
    def content_change(
        cls,
        resource: p.Infra.RopeResource,
        source: str,
        rewrites: t.SequenceOf[m.Infra.SourceRewrite],
    ) -> p.Infra.RopeChangeContents:
        """Preview checked, disjoint edits through Rope's change machinery."""
        collector = cls._runtime_callable("rope.base.codeanalyze", "ChangeCollector")(
            source
        )
        add = getattr(collector, "add_change", None)
        changed = getattr(collector, "get_changed", None)
        if not callable(add) or not callable(changed):
            msg = "Rope ChangeCollector has an invalid contract"
            raise TypeError(msg)
        end = 0
        for rewrite in sorted(rewrites, key=lambda item: (item.start, item.end)):
            if rewrite.start < end or not 0 <= rewrite.start <= rewrite.end <= len(
                source
            ):
                msg = "Rope source edits overlap or escape their snapshot"
                raise ValueError(msg)
            add(rewrite.start, rewrite.end, rewrite.text)
            end = rewrite.end
        updated = changed()
        if updated is None:
            updated = source
        if not isinstance(updated, str):
            msg = "Rope ChangeCollector returned a non-source result"
            raise TypeError(msg)
        change = cls._runtime_callable("rope.base.change", "ChangeContents")(
            resource, updated
        )
        if not isinstance(change, p.Infra.RopeChangeContents):
            msg = "Rope ChangeContents returned an invalid content plan"
            raise TypeError(msg)
        return change

    @classmethod
    def restructure_changes(
        cls,
        rope_project: p.Infra.RopeProject,
        pattern: str,
        goal: str,
        *,
        arguments: t.MappingKV[str, str],
        resources: t.SequenceOf[p.Infra.RopeResource],
    ) -> p.Infra.RopeChangeSet:
        """Plan Rope 1.14 semantic changes without invoking Project.do."""
        factory = cls._runtime_callable("rope.refactor.restructure", "Restructure")
        restructuring = factory(rope_project, pattern, goal, args=dict(arguments))
        if not isinstance(restructuring, p.Infra.RopeRestructure):
            msg = "rope Restructure does not satisfy its public planning contract"
            raise TypeError(msg)
        return restructuring.get_changes(resources=list(resources))

    @classmethod
    def create_move(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        offset: int,
    ) -> t.Infra.RopeMoveGlobal:
        create = cls._runtime_callable("rope.refactor.move", "create_move")
        mover = create(rope_project, resource, offset)
        if not isinstance(mover, p.Infra.RopeMoveGlobal):
            msg = "rope create_move did not return MoveGlobal-compatible object"
            raise TypeError(msg)
        return mover

    @classmethod
    def rename_changes(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        offset: int,
        new_name: str,
        *,
        resources: t.SequenceOf[t.Infra.RopeResource],
    ) -> t.Infra.RopeChangeSet:
        renamer_factory = cls._runtime_callable("rope.refactor.rename", "Rename")
        renamer = renamer_factory(rope_project, resource, offset)
        get_changes = getattr(renamer, "get_changes", None)
        if not callable(get_changes):
            msg = "rope Rename does not expose callable get_changes"
            raise TypeError(msg)
        changes = get_changes(new_name, resources=list(resources))
        if not isinstance(changes, p.Infra.RopeChangeSet):
            msg = "rope Rename returned invalid ChangeSet"
            raise TypeError(msg)
        return changes

    @classmethod
    def create_occurrence_finder(
        cls,
        rope_project: t.Infra.RopeProject,
        name: str,
        pyname: t.Infra.RopePyName,
        *,
        imports: bool,
        in_hierarchy: bool,
    ) -> t.Infra.RopeOccurrenceFinder:
        create_finder = cls._runtime_callable(
            "rope.refactor.occurrences", "create_finder"
        )
        finder = create_finder(
            rope_project, name, pyname, imports=imports, in_hierarchy=in_hierarchy
        )
        if not isinstance(finder, p.Infra.RopeOccurrenceFinder):
            msg = "rope occurrence finder does not satisfy p.Infra.RopeOccurrenceFinder"
            raise TypeError(msg)
        return finder

    @classmethod
    def word_primary_range(cls, source: str, offset: int) -> t.Pair[int, int]:
        word_finder = cls._word_finder(source)
        primary_range = getattr(word_finder, "get_primary_range", None)
        if not callable(primary_range):
            msg = "rope Worder does not expose callable get_primary_range"
            raise TypeError(msg)
        value = primary_range(offset)
        if (
            not isinstance(value, tuple)
            or len(value) != cls._WORD_RANGE_SIZE
            or not all(isinstance(item, int) for item in value)
        ):
            msg = "rope Worder returned invalid primary range"
            raise TypeError(msg)
        return value

    @classmethod
    def word_primary_at(cls, source: str, offset: int) -> str:
        word_finder = cls._word_finder(source)
        primary_at = getattr(word_finder, "get_primary_at", None)
        if not callable(primary_at):
            msg = "rope Worder does not expose callable get_primary_at"
            raise TypeError(msg)
        return str(primary_at(offset))

    @classmethod
    def word_is_function_call(cls, source: str, offset: int) -> bool:
        """Return Rope's syntactic call fact for the primary at ``offset``."""
        word_finder = cls._word_finder(source)
        is_called = getattr(word_finder, "is_a_function_being_called", None)
        if not callable(is_called):
            msg = "rope Worder does not expose callable is_a_function_being_called"
            raise TypeError(msg)
        value = is_called(offset)
        if not isinstance(value, bool):
            msg = "rope Worder returned a non-boolean function-call fact"
            raise TypeError(msg)
        return value

    @classmethod
    def _word_finder(cls, source: str) -> p.AttributeProbe:
        worder_module = cls._module("rope.base.worder")
        worder_factory = getattr(worder_module, "Worder", None)
        if not callable(worder_factory):
            msg = "rope Worder factory is not callable"
            raise TypeError(msg)
        finder: p.AttributeProbe = worder_factory(source, True)
        return finder


__all__: list[str] = ["FlextInfraUtilitiesRopeRuntimeRefactors"]
