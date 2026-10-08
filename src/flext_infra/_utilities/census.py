"""Census and introspection utilities for the refactor subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import shutil
from collections import defaultdict
from collections.abc import Callable as _CensusCallable, MutableMapping
from pathlib import Path
from typing import ClassVar

from flext_cli import u

from flext_infra import c, m, p, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesProtectedEdit,
    FlextInfraUtilitiesRopeAnalysis,
    FlextInfraUtilitiesRopeCore,
    FlextInfraUtilitiesRopeHelpers,
    FlextInfraUtilitiesRopeImports,
    FlextInfraUtilitiesRopeRuntime,
)


class FlextInfraUtilitiesRefactorCensus:
    """Census and source introspection helpers for refactor tools."""

    _census_log: ClassVar[p.Logger] = u.fetch_logger(__name__)

    @staticmethod
    def export_pydantic_json(model_payload: m.BaseModel, export_path: Path) -> None:
        """Serialize any Pydantic model payload to a JSON file."""
        export_path.write_text(
            model_payload.model_dump_json(indent=2),
            encoding=c.Cli.ENCODING_DEFAULT,
        )

    @staticmethod
    def _source_snapshot(
        rope: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        *,
        source_cache: MutableMapping[Path, str] | None = None,
    ) -> str:
        """Return one original source snapshot, optionally cached by path.

        Returns:
            One original source snapshot, optionally cached by path.

        """
        resolved_path = file_path.resolve()
        if source_cache is None:
            source_text: str = rope.source(resolved_path)
            return source_text
        cached_source = source_cache.get(resolved_path)
        if cached_source is not None:
            return cached_source
        source: str = rope.source(resolved_path)
        source_cache[resolved_path] = source
        return source

    @staticmethod
    def plan_simple_removal_edits(
        rope: p.Infra.RopeWorkspaceDsl,
        candidate: m.Infra.RemovalCandidate,
        *,
        source_cache: MutableMapping[Path, str] | None = None,
    ) -> t.MappingKV[Path, t.VariadicTuple[t.IntPair]] | None:
        """Plan safe line-range removals for simple top-level removal candidates.

        Returns:
            The resulting ``t.MappingKV[Path, t.VariadicTuple[t.IntPair]] | None``.

        """
        if candidate.scope_path != candidate.object_name:
            return None
        if candidate.object_kind not in {"class", "function"}:
            return None
        definition_path = Path(candidate.file_path).resolve()
        definition_range = FlextInfraUtilitiesRefactorCensus._definition_line_range(
            FlextInfraUtilitiesRefactorCensus._source_snapshot(
                rope,
                definition_path,
                source_cache=source_cache,
            ),
            candidate,
        )
        if definition_range is None:
            return None
        ranges_by_file: MutableMapping[Path, list[t.IntPair]] = defaultdict(list)
        ranges_by_file[definition_path].append(definition_range)
        sites_by_path: MutableMapping[Path, list[m.Infra.ReferenceSite]] = defaultdict(
            list,
        )
        for site in FlextInfraUtilitiesRefactorCensus._supporting_reference_sites(
            candidate,
        ):
            sites_by_path[Path(site.file_path).resolve()].append(site)
        for site_path, file_sites in sites_by_path.items():
            site_source = FlextInfraUtilitiesRefactorCensus._source_snapshot(
                rope,
                site_path,
                source_cache=source_cache,
            )
            planned_ranges = (
                FlextInfraUtilitiesRefactorCensus._supporting_reference_ranges(
                    rope,
                    site_path,
                    site_source,
                    candidate,
                    sites=tuple(file_sites),
                )
            )
            if planned_ranges is None:
                return None
            ranges_by_file[site_path].extend(planned_ranges)
        return {
            file_path: FlextInfraUtilitiesRefactorCensus.merge_line_ranges(ranges)
            for file_path, ranges in ranges_by_file.items()
        }

    @staticmethod
    def _supporting_reference_ranges(
        rope: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        source: str,
        candidate: m.Infra.RemovalCandidate,
        *,
        sites: t.VariadicTuple[m.Infra.ReferenceSite],
    ) -> t.VariadicTuple[t.IntPair] | None:
        """Plan removable top-level ranges for one support file.

        Returns:
            The resulting ``t.VariadicTuple[t.IntPair] | None``.

        """
        planned_ranges: list[t.IntPair] = []
        for site in sites:
            site_range = FlextInfraUtilitiesRefactorCensus._reference_line_range(
                source,
                site,
            )
            if site_range is None:
                rewritten_source, disqualified = (
                    FlextInfraUtilitiesRefactorCensus._strip_class_base(
                        source,
                        candidate.object_name,
                    )
                )
                if not disqualified and rewritten_source != source:
                    continue
                return None
            planned_ranges.append(site_range)
        for (
            occurrence_line
        ) in FlextInfraUtilitiesRefactorCensus._aliased_import_occurrence_lines(
            rope,
            file_path,
            source,
            imported_name=candidate.object_name,
        ):
            occurrence_range = (
                FlextInfraUtilitiesRefactorCensus._reference_line_range_for_line(
                    source,
                    occurrence_line,
                )
            )
            if occurrence_range is None:
                return None
            planned_ranges.append(occurrence_range)
        return FlextInfraUtilitiesRefactorCensus.merge_line_ranges(planned_ranges)

    @staticmethod
    def _aliased_import_occurrence_lines(
        rope: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        source: str,
        *,
        imported_name: str,
    ) -> t.VariadicTuple[int]:
        """Return same-file occurrence lines for local aliases of ``imported_name``.

        Returns:
            Same-file occurrence lines for local aliases of ``imported_name``.

        """
        resource = rope.resource(file_path)
        if resource is None:
            return ()
        declared_imports = (
            FlextInfraUtilitiesRopeAnalysis.resolve_declared_module_imports(
                rope.rope_project,
                resource,
            )
        )
        alias_names = tuple(
            local_name
            for local_name, declared_path in declared_imports.items()
            if local_name != imported_name
            and declared_path.rsplit(".", maxsplit=1)[-1] == imported_name
        )
        if not alias_names:
            return ()
        lines = source.splitlines(keepends=True)
        occurrence_lines: set[int] = set()
        for alias_name in alias_names:
            alias_offset = None
            for line_number in range(1, len(lines) + 1):
                alias_offset = (
                    FlextInfraUtilitiesRopeCore.find_identifier_offset_in_lines(
                        lines,
                        line=line_number,
                        symbol=alias_name,
                    )
                )
                if alias_offset is not None:
                    break
            if alias_offset is None:
                continue
            hits = FlextInfraUtilitiesRopeImports.find_occurrences(
                rope.rope_project,
                resource,
                alias_offset,
                resources=(resource,),
            )
            for hit in hits:
                line = getattr(hit, "lineno", None)
                if isinstance(line, int) and line > 0:
                    occurrence_lines.add(line)
        return tuple(sorted(occurrence_lines))

    @staticmethod
    def _supports_simple_removal_candidate(candidate: m.Infra.RemovalCandidate) -> bool:
        """Whether ``candidate`` is eligible for the simple-removal pipeline.

        Returns:
            The resulting ``bool``.

        """
        return (
            candidate.scope_path == candidate.object_name
            and candidate.object_kind in {"class", "function"}
        )

    @classmethod
    def _simple_removal_sources_result(
        cls,
        rope: p.Infra.RopeWorkspaceDsl,
        candidate: m.Infra.RemovalCandidate,
        *,
        source_cache: MutableMapping[Path, str] | None = None,
    ) -> p.Result[t.MappingKV[Path, str]]:
        """Return projected sources or a loud failure for broken planning.

        Supported top-level class/function candidates must either produce
        concrete source updates or fail loudly; they must not silently collapse
        into an empty projection.

        Returns:
            Projected sources or a loud failure for broken planning.

        """
        updates = cls.build_simple_removal_sources(
            rope,
            candidate,
            source_cache=source_cache,
        )
        if updates is not None:
            return r[t.MappingKV[Path, str]].ok(updates)
        return r[t.MappingKV[Path, str]].fail(
            "simple removal planning failed for "
            f"{candidate.file_path}:{candidate.line} {candidate.object_name}",
        )

    @staticmethod
    def build_simple_removal_sources(
        rope: p.Infra.RopeWorkspaceDsl,
        candidate: m.Infra.RemovalCandidate,
        *,
        source_cache: MutableMapping[Path, str] | None = None,
    ) -> t.MappingKV[Path, str] | None:
        """Build updated sources for a simple removal candidate without writing.

        Returns:
            The resulting ``t.MappingKV[Path, str] | None``.

        """
        edit_plan = FlextInfraUtilitiesRefactorCensus.plan_simple_removal_edits(
            rope,
            candidate,
            source_cache=source_cache,
        )
        if edit_plan is None:
            return None
        definition_path = Path(candidate.file_path).resolve()
        updates: MutableMapping[Path, str] = {}
        for file_path, ranges in edit_plan.items():
            original_source = FlextInfraUtilitiesRefactorCensus._source_snapshot(
                rope,
                file_path,
                source_cache=source_cache,
            )
            source = FlextInfraUtilitiesRefactorCensus.apply_line_ranges(
                original_source,
                ranges,
            )
            for alias_name in FlextInfraUtilitiesRefactorCensus._removed_alias_names(
                rope,
                file_path,
                target_name=candidate.object_name,
                removed_ranges=ranges,
            ):
                source = FlextInfraUtilitiesRefactorCensus.strip_module_all_entry(
                    source,
                    alias_name,
                )
            if file_path.resolve() == definition_path:
                source = FlextInfraUtilitiesRefactorCensus.strip_module_all_entry(
                    source,
                    candidate.object_name,
                )
            updates[file_path] = (
                FlextInfraUtilitiesRefactorCensus.normalize_top_level_spacing(source)
            )
        facade_cascade = (
            FlextInfraUtilitiesRefactorCensus.build_facade_base_cascade_updates(
                rope,
                candidate,
                source_cache=source_cache,
            )
        )
        if facade_cascade is None:
            return None
        for file_path, source in facade_cascade.items():
            existing_source = updates.get(file_path)
            if existing_source is None:
                updates[file_path] = (
                    FlextInfraUtilitiesRefactorCensus.normalize_top_level_spacing(
                        source,
                    )
                )
                continue
            rewritten_source, disqualified = (
                FlextInfraUtilitiesRefactorCensus._strip_class_base(
                    existing_source,
                    candidate.object_name,
                )
            )
            if disqualified:
                return None
            updates[file_path] = (
                FlextInfraUtilitiesRefactorCensus.normalize_top_level_spacing(
                    rewritten_source,
                )
            )
        return updates

    @staticmethod
    def _removed_alias_names(
        rope: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        *,
        target_name: str,
        removed_ranges: t.SequenceOf[t.IntPair],
    ) -> t.StrSequence:
        """Return simple alias names removed together with ``target_name``.

        Returns:
            Simple alias names removed together with ``target_name``.

        """
        if not removed_ranges:
            return ()
        resource = rope.resource(file_path)
        if resource is None:
            return ()
        attributes = FlextInfraUtilitiesRopeCore.resolve_pymodule(
            rope.rope_project,
            resource,
        ).get_attributes()
        target_pyname = attributes.get(target_name)
        if target_pyname is None or FlextInfraUtilitiesRopeRuntime.imported_name(
            target_pyname,
        ):
            return ()
        target_object = target_pyname.get_object()
        alias_names: set[str] = set()
        for name, pyname in attributes.items():
            if name == target_name or FlextInfraUtilitiesRopeRuntime.imported_name(
                pyname,
            ):
                continue
            line = FlextInfraUtilitiesRefactorCensus.pyname_definition_line(
                pyname,
                resource,
            )
            if line is None or not FlextInfraUtilitiesRefactorCensus._line_in_ranges(
                line,
                removed_ranges=removed_ranges,
            ):
                continue
            alias_object = pyname.get_object()
            if id(alias_object) == id(target_object):
                alias_names.add(name)
        return tuple(sorted(alias_names))

    @staticmethod
    def pyname_definition_line(
        pyname: t.Infra.RopePyName,
        resource: t.Infra.RopeResource,
    ) -> int | None:
        """Return the local definition line for one Rope symbol.

        ``None`` when the symbol is defined in another module, so a caller never
        attributes an imported name to the file under inspection.

        Returns:
            The local definition line for one Rope symbol.

        """
        location = pyname.get_definition_location()
        module, line = location
        origin = module.get_resource() if module is not None else None
        if not isinstance(line, int) or line < 1 or origin is None:
            return None
        return line if origin.path == resource.path else None

    @staticmethod
    def _line_in_ranges(line: int, *, removed_ranges: t.SequenceOf[t.IntPair]) -> bool:
        """Return whether ``line`` falls inside any removed range.

        Returns:
            Whether ``line`` falls inside any removed range.

        """
        return any(start <= line <= end for start, end in removed_ranges)

    @staticmethod
    def build_facade_base_cascade_updates(
        rope: p.Infra.RopeWorkspaceDsl,
        candidate: m.Infra.RemovalCandidate,
        *,
        source_cache: MutableMapping[Path, str] | None = None,
    ) -> t.MappingKV[Path, str] | None:
        """Drop ``candidate`` from class-base lists in facade modules.

        Returns an empty mapping when no facade references the candidate, a
        populated mapping with rewritten sources otherwise, or ``None`` when
        removing the base would leave a facade class with no bases at all
        (unsafe — candidate must be handled manually).

        Returns:
            The resulting ``t.MappingKV[Path, str] | None``.

        """
        target_name = candidate.object_name
        definition_path = Path(candidate.file_path).resolve()
        updates: MutableMapping[Path, str] = {}
        definition_resource = rope.resource(definition_path)
        if definition_resource is None:
            return None
        offset = FlextInfraUtilitiesRopeAnalysis.find_definition_offset(
            rope.rope_project,
            definition_resource,
            target_name,
        )
        if offset is None:
            return None
        search_resources = FlextInfraUtilitiesRopeImports.indexed_search_resources(
            rope,
            resource=definition_resource,
            name=target_name,
            definition_path=definition_path,
        )
        candidate_paths = tuple(
            resolved_path
            for hit in FlextInfraUtilitiesRopeImports.find_occurrences(
                rope.rope_project,
                definition_resource,
                offset,
                resources=search_resources,
            )
            if (resolved_path := FlextInfraUtilitiesRopeImports.location_file_path(hit))
            is not None
            and resolved_path != definition_path
            and resolved_path.name != c.Infra.INIT_PY
        )
        seen_paths: set[str] = set()
        for file_path in candidate_paths:
            resolved_path = file_path.resolve()
            cache_key = str(resolved_path)
            if cache_key in seen_paths:
                continue
            seen_paths.add(cache_key)
            if resolved_path.name == c.Infra.INIT_PY:
                continue
            if resolved_path == definition_path:
                continue
            source = FlextInfraUtilitiesRefactorCensus._source_snapshot(
                rope,
                resolved_path,
                source_cache=source_cache,
            )
            if target_name not in source:
                continue
            rewritten, disqualified = (
                FlextInfraUtilitiesRefactorCensus._strip_class_base(source, target_name)
            )
            if disqualified:
                return None
            if rewritten == source:
                continue
            updates[resolved_path] = rewritten
        return updates

    @staticmethod
    def _strip_class_base(source: str, base_name: str) -> t.Pair[str, bool]:
        """Return (new_source, disqualified) after removing ``base_name`` from bases.

        Handles both single-line and multi-line class declarations. The header
        of each class spans from its ``class`` line to the line before its
        first body statement (or that line itself for a one-line class). When
        the removed base was the sole entry, the candidate is flagged as
        disqualified so the caller can abort the cascade safely.

        Returns:
            (new_source, disqualified) after removing ``base_name`` from bases.

        """
        rewritten_lines = source.splitlines(keepends=True)
        headers = sorted(
            (
                (
                    node.lineno,
                    max(
                        node.lineno,
                        FlextInfraUtilitiesRopeHelpers.statement_line_span(
                            node.body[0],
                        )[0]
                        - 1,
                    ),
                )
                for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.ClassDef)
            ),
            reverse=True,
        )
        changed = False
        for header_start, header_end in headers:
            header = "".join(rewritten_lines[header_start - 1 : header_end])
            rewritten_header, header_changed, disqualified = (
                FlextInfraUtilitiesRefactorCensus._rewrite_class_header_bases(
                    header,
                    base_name,
                )
            )
            if disqualified:
                return source, True
            if header_changed:
                changed = True
                rewritten_lines[header_start - 1 : header_end] = (
                    rewritten_header.splitlines(keepends=True)
                )
        return ("".join(rewritten_lines) if changed else source, False)

    @staticmethod
    def _rewrite_class_header_bases(
        header: str,
        base_name: str,
    ) -> t.Triple[str, bool, bool]:
        """Rewrite one class header block after removing ``base_name`` from bases.

        Returns:
            The resulting ``t.Triple[str, bool, bool]``.

        """
        stripped_header = header.rstrip("\n")
        if "(" not in stripped_header or ")" not in stripped_header:
            return header, False, False
        prefix, _, remainder = stripped_header.partition("(")
        bases_raw, _, suffix = remainder.rpartition(")")
        if not prefix.lstrip().startswith("class "):
            return header, False, False
        base_with_generic = c.Infra.compile_class_base_with_generic(base_name)
        entries = [
            entry.strip()
            for entry in bases_raw.replace("\n", " ").split(",")
            if entry.strip()
        ]
        remaining = [
            entry
            for entry in entries
            if entry != base_name and not base_with_generic.fullmatch(entry)
        ]
        if len(remaining) == len(entries):
            return header, False, False
        if not remaining:
            return header, False, True
        trailing_newline = "\n" if header.endswith("\n") else ""
        if "\n" not in stripped_header:
            return (
                f"{prefix}({', '.join(remaining)}){suffix}{trailing_newline}",
                True,
                False,
            )
        indent = prefix[: len(prefix) - len(prefix.lstrip())]
        nested_indent = f"{indent}    "
        rewritten = "".join([
            f"{prefix}(\n",
            *(f"{nested_indent}{entry},\n" for entry in remaining),
            f"{indent}){suffix}{trailing_newline}",
        ])
        return rewritten, True, False

    @staticmethod
    def strip_module_all_entry(source: str, name: str) -> str:
        """Remove ``name`` from a module-level ``__all__`` list declaration.

        Handles both single-line and multi-line ``__all__`` forms. The list is
        normalised to single-line ``[...]`` when all remaining entries fit on
        one line; otherwise each remaining entry stays on its own line. When
        the removed entry was the only element, the list is collapsed to
        ``[]``.

        Returns:
            The resulting ``str``.

        """
        single_line = c.Infra.DUNDER_ALL_SINGLE_LINE_RE
        multi_line = c.Infra.DUNDER_ALL_MULTI_LINE_RE
        quoted_target = {f'"{name}"', f"'{name}'"}

        def _rewrite_single(match: t.RegexMatch) -> str:
            """Rewrite single.

            Returns:
                The resulting ``str``.

            """
            body: str = t.Infra.STR_ADAPTER.validate_python(match.group("body"))
            entries = [entry.strip() for entry in body.split(",") if entry.strip()]
            remaining = [entry for entry in entries if entry not in quoted_target]
            result: str
            if len(remaining) == len(entries):
                original_text: str = t.Infra.STR_ADAPTER.validate_python(match.group(0))
                result = original_text
            else:
                prefix: str = t.Infra.STR_ADAPTER.validate_python(match.group("prefix"))
                result = f"{prefix}[{', '.join(remaining)}]"
            return result

        def _rewrite_multi(match: t.RegexMatch) -> str:
            """Rewrite multi.

            Returns:
                The resulting ``str``.

            """
            body: str = t.Infra.STR_ADAPTER.validate_python(match.group("body"))
            if "\n" not in body:
                original_text: str = t.Infra.STR_ADAPTER.validate_python(match.group(0))
                result = original_text
            else:
                entries = [entry.strip() for entry in body.split(",") if entry.strip()]
                remaining = [entry for entry in entries if entry not in quoted_target]
                if len(remaining) == len(entries):
                    original_text = t.Infra.STR_ADAPTER.validate_python(match.group(0))
                    result = original_text
                else:
                    prefix: str = t.Infra.STR_ADAPTER.validate_python(
                        match.group("prefix"),
                    )
                    if not remaining:
                        result = f"{prefix}[]"
                    else:
                        lines = ",\n".join(f"    {entry}" for entry in remaining)
                        result = f"{prefix}[\n{lines},\n]"
            return result

        first = single_line.sub(_rewrite_single, source)
        rewritten_source: str = multi_line.sub(_rewrite_multi, first)
        if rewritten_source == source:
            return source
        return rewritten_source

    @staticmethod
    def _cleanup_written_paths(
        rope: p.Infra.RopeWorkspaceDsl,
        *,
        candidate: m.Infra.RemovalCandidate,
        file_paths: t.SequenceOf[Path],
    ) -> None:
        """Run one centralized post-write Rope cleanup for touched files.

        Raises:
            RuntimeError: If ``cleanup_result.failure``.

        """
        try:
            rope.rope_project.validate()
        except RecursionError as exc:
            FlextInfraUtilitiesRefactorCensus._census_log.warning(
                "rope_validate_recursion_limit",
                candidate=candidate.file_path,
                error=str(exc),
            )
        cleanup_result = FlextInfraUtilitiesRopeImports.normalize_imports(
            rope.rope_project,
            file_paths=file_paths,
        )
        if cleanup_result.failure:
            msg = cleanup_result.error or "rope import cleanup failed"
            raise RuntimeError(msg)

    @staticmethod
    def _planned_simple_removal(
        rope: p.Infra.RopeWorkspaceDsl,
        candidate: m.Infra.RemovalCandidate,
        *,
        source_cache: MutableMapping[Path, str] | None = None,
    ) -> p.Result[t.Pair[t.MappingKV[Path, str], _CensusCallable[[], None]]]:
        """Plan one simple removal and bind its post-write Rope cleanup.

        A candidate outside the simple-removal contract yields a typed
        failure carrying ``c.Infra.CENSUS_UNSUPPORTED_SIMPLE_REMOVAL_CODE`` — never a
        ``None`` payload, which success results forbid. The preview and
        apply paths translate that code into their own "unsupported"
        outcome so both report the same result from one owner.

        Returns:
            The resulting ``p.Result[t.Pair[t.MappingKV[Path, str], _CensusCallable[[],
                None]]]``.

        """
        planned = r[t.Pair[t.MappingKV[Path, str], _CensusCallable[[], None]]]
        if not FlextInfraUtilitiesRefactorCensus._supports_simple_removal_candidate(
            candidate,
        ):
            return planned.fail(
                "candidate is outside the simple-removal contract: "
                f"{candidate.file_path}:{candidate.line} {candidate.object_name}",
                error_code=c.Infra.CENSUS_UNSUPPORTED_SIMPLE_REMOVAL_CODE,
            )
        updates_result = (
            FlextInfraUtilitiesRefactorCensus._simple_removal_sources_result(
                rope,
                candidate,
                source_cache=source_cache,
            )
        )
        if updates_result.failure:
            return planned.from_failure(updates_result)
        updates = updates_result.unwrap()
        file_paths = tuple(sorted(updates))

        def _cleanup() -> None:
            """Post write."""
            FlextInfraUtilitiesRefactorCensus._cleanup_written_paths(
                rope,
                candidate=candidate,
                file_paths=file_paths,
            )

        return planned.ok((updates, _cleanup))

    @staticmethod
    def preview_simple_removal_candidate(
        rope: p.Infra.RopeWorkspaceDsl,
        workspace: Path,
        candidate: m.Infra.RemovalCandidate,
        *,
        gates: t.StrSequence,
        source_cache: MutableMapping[Path, str] | None = None,
    ) -> p.Result[bool]:
        """Preview one simple removal candidate, requiring clean gates.

        ``r.ok(True)`` when the simulated removal cleared the gate
        snapshot. ``r.ok(False)`` when the candidate is outside the
        simple-removal contract. ``r.fail(...)`` when planning or
        ``preview_source_writes`` failed — the message lists the reason.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        planned = FlextInfraUtilitiesRefactorCensus._planned_simple_removal(
            rope,
            candidate,
            source_cache=source_cache,
        )
        if planned.failure:
            if planned.error_code == c.Infra.CENSUS_UNSUPPORTED_SIMPLE_REMOVAL_CODE:
                return r[bool].ok(value=False)
            return r[bool].from_failure(planned)
        updates, post_write = planned.unwrap()
        try:
            applied, reports = FlextInfraUtilitiesProtectedEdit.preview_source_writes(
                updates,
                workspace=workspace,
                gates=gates,
                post_write=post_write,
            )
        except RuntimeError as exc:
            FlextInfraUtilitiesRefactorCensus._census_log.warning(
                "census_preview_candidate_rejected",
                candidate=candidate.file_path,
                object_name=candidate.object_name,
                error=str(exc),
            )
            return r[bool].fail(str(exc), exception=exc)
        finally:
            rope.refresh(preserve_indexes=True, validate_project=False)
        if applied:
            return r[bool].ok(value=True)
        return r[bool].fail(
            "; ".join(reports) if reports else "preview gates rejected removal",
        )

    @staticmethod
    def apply_simple_removal_candidate(
        rope: p.Infra.RopeWorkspaceDsl,
        workspace: Path,
        candidate: m.Infra.RemovalCandidate,
        *,
        gates: t.StrSequence,
        post_apply_hook: _CensusCallable[[Path], None] | None = None,
    ) -> p.Result[bool]:
        """Apply one simple removal candidate permanently, gates-validated.

        ``post_apply_hook`` is executed **after** sources are written and rope
        imports are organised, but **before** the gate snapshot runs. Callers
        that need to regenerate governance artefacts (e.g. ``__init__.py``
        lazy maps via ``FlextInfraCodegenLazyInit``) pass the regeneration
        routine here. This keeps ``flext_infra._utilities.census`` outside
        the ``flext_infra.codegen.lazy_init`` import cycle while still
        giving gates a chance to verify post-cascade correctness.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        source_cache: MutableMapping[Path, str] = {}
        planned = FlextInfraUtilitiesRefactorCensus._planned_simple_removal(
            rope,
            candidate,
            source_cache=source_cache,
        )
        if planned.failure:
            if planned.error_code == c.Infra.CENSUS_UNSUPPORTED_SIMPLE_REMOVAL_CODE:
                return r[bool].ok(value=False)
            return r[bool].from_failure(planned)
        updates, cleanup = planned.unwrap()

        def _post_write() -> None:
            """Post write."""
            cleanup()
            if post_apply_hook is not None:
                post_apply_hook(workspace)

        applied, reports = FlextInfraUtilitiesProtectedEdit.protected_source_writes(
            updates,
            request=m.Infra.ProtectedSourceWritesRequest(
                workspace=workspace,
                expected_sources={path: source_cache[path] for path in updates},
                gates=gates,
                post_write=_post_write,
                skip_pytest=True,
            ),
        )
        rope.reload()
        if applied:
            return r[bool].ok(value=True)
        return r[bool].fail(
            "; ".join(reports) if reports else "apply gates rejected removal",
        )

    @staticmethod
    def apply_line_ranges(source: str, ranges: t.SequenceOf[t.IntPair]) -> str:
        """Remove one or more 1-based inclusive line ranges from Python source.

        Returns:
            The resulting ``str``.

        """
        merged_ranges = FlextInfraUtilitiesRefactorCensus.merge_line_ranges(ranges)
        if not merged_ranges:
            return source
        removed_lines = {
            line_number
            for start, end in merged_ranges
            for line_number in range(start, end + 1)
        }
        lines = source.splitlines(keepends=True)
        return "".join(
            line
            for index, line in enumerate(lines, start=1)
            if index not in removed_lines
        )

    @staticmethod
    def normalize_top_level_spacing(source: str) -> str:
        """Collapse blank-line runs left behind by top-level removals.

        Returns:
            The resulting ``str``.

        """
        normalized: str = c.Infra.BLANK_LINE_RUN_RE.sub("\n\n\n", source)
        return normalized

    @staticmethod
    def clone_project_for_validation(source: Path, destination: Path) -> Path:
        """Copy a project tree into a scratch directory for post-apply validation.

        Skips cache and virtual-env directories so the clone is minimal and the
        downstream rope workspace opens on source-only state. Returns the
        resolved destination path.

        Returns:
            The resulting ``Path``.

        Raises:
            NotADirectoryError: If clone source is not a directory.

        """
        resolved_source = source.resolve()
        resolved_destination = destination.resolve()
        if not resolved_source.is_dir():
            msg = f"clone source is not a directory: {resolved_source}"
            raise NotADirectoryError(msg)
        if resolved_destination.exists():
            shutil.rmtree(resolved_destination)
        shutil.copytree(
            resolved_source,
            resolved_destination,
            ignore=shutil.ignore_patterns(*c.Infra.VALIDATION_CLONE_EXCLUDES),
            symlinks=False,
        )
        return resolved_destination

    @staticmethod
    def merge_line_ranges(
        ranges: t.SequenceOf[t.IntPair],
    ) -> t.VariadicTuple[t.IntPair]:
        """Merge overlapping or adjacent 1-based inclusive line ranges.

        Returns:
            The resulting ``t.VariadicTuple[t.IntPair]``.

        """
        if not ranges:
            return ()
        ordered_ranges = sorted(ranges)
        merged: list[t.IntPair] = [ordered_ranges[0]]
        for start, end in ordered_ranges[1:]:
            previous_start, previous_end = merged[-1]
            if start <= previous_end + 1:
                merged[-1] = (previous_start, max(previous_end, end))
                continue
            merged.append((start, end))
        return tuple(merged)

    @staticmethod
    def _supporting_reference_sites(
        candidate: m.Infra.RemovalCandidate,
    ) -> t.VariadicTuple[m.Infra.ReferenceSite]:
        """Supporting reference sites.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.ReferenceSite]``.

        """
        sites: t.VariadicTuple[m.Infra.ReferenceSite] = tuple(
            candidate.script_reference_sites,
        )
        return sites

    @staticmethod
    def _definition_line_range(
        source: str,
        candidate: m.Infra.RemovalCandidate,
    ) -> t.IntPair | None:
        """Definition line range.

        Returns:
            The resulting ``t.IntPair | None``.

        """
        return FlextInfraUtilitiesRopeHelpers.top_level_definition_span(
            source,
            candidate.object_name,
            kind=candidate.object_kind,
        )

    @staticmethod
    def _reference_line_range(
        source: str,
        site: m.Infra.ReferenceSite,
    ) -> t.IntPair | None:
        """Compute the line range for a reference site.

        Returns:
            The resulting ``t.IntPair | None``.

        """
        return FlextInfraUtilitiesRefactorCensus._reference_line_range_for_line(
            source,
            site.line,
        )

    @staticmethod
    def _reference_line_range_for_line(source: str, line: int) -> t.IntPair | None:
        """Top-level removable statement range containing ``line``.

        A class statement is never removed as a reference site; ``None`` also
        answers a line outside every top-level statement.

        Returns:
            The resulting ``t.IntPair | None``.

        """
        for statement in ast.parse(source).body:
            start, end = FlextInfraUtilitiesRopeHelpers.statement_line_span(statement)
            if start <= line <= end:
                return None if isinstance(statement, ast.ClassDef) else (start, end)
        return None


__all__: list[str] = ["FlextInfraUtilitiesRefactorCensus"]
