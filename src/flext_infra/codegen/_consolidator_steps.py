"""Constants-consolidation steps for FlextInfraCodegenConsolidator.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from flext_infra import c, m, p, r, t, u

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraCodegenConsolidatorStepsMixin:
    """Value-map build + per-file scan/match/apply for constants consolidation.

    Composed into FlextInfraCodegenConsolidator via FLEXT; self-contained (no
    facade state), so the facade's ``execute`` orchestrator only sequences
    these workers across selected projects.
    """

    _ALL_LINT_GATES: ClassVar[t.StrSequence] = tuple(
        entry[0] for entry in c.Infra.LINT_TOOLS
    )

    @classmethod
    def _build_value_map_from_constants_file(
        cls,
        constants_file: Path,
    ) -> p.Result[t.StrMapping]:
        """Build value map from a constants file.

        Missing file → empty map (nothing to consolidate); an existing-but-unreadable
        file is surfaced as a failure (never silently treated as empty).

        Returns:
            The resulting ``p.Result[t.StrMapping]``.

        """
        if not constants_file.is_file():
            return r[t.StrMapping].ok({})
        read = u.Cli.files_read_text(constants_file)
        if read.failure:
            return r[t.StrMapping].from_failure(read)
        value_map: t.MutableStrMapping = {}
        for name, _, raw, class_path, _ in u.Infra.parse_final_constant_definitions(
            read.value.splitlines(),
        ):
            if not raw:
                continue
            canonical = f"{class_path}.{name}" if class_path else name
            value_map[raw] = canonical
            if (
                len(raw) >= c.Infra.DETECTION_MIN_QUOTED_LITERAL_LEN
                and raw[0] in {'"', "'"}
                and raw[-1] == raw[0]
            ):
                inner = raw[1:-1]
                value_map[f"'{inner}'"] = canonical
                value_map[f'"{inner}"'] = canonical
        return r[t.StrMapping].ok(value_map)

    def _scan_file(
        self,
        rope_project: t.Infra.RopeProject,
        python_file: Path,
        value_map: t.StrMapping,
    ) -> m.Infra.ConsolidatorScannedFile | None:
        """Scan file.

        Returns:
            The resulting ``m.Infra.ConsolidatorScannedFile | None``.

        """
        resource = u.Infra.resolve_resource_from_path(rope_project, python_file)
        if resource is None:
            return None
        symbols = u.Infra.resolve_module_symbols(rope_project, resource)
        assignments = [symbol for symbol in symbols if symbol.kind == "assignment"]
        if not assignments:
            return None
        source = resource.read()
        matches = self._match_assignments(assignments, source.splitlines(), value_map)
        if not matches:
            return None
        return m.Infra.ConsolidatorScannedFile(
            resource=resource,
            source=source,
            matches=matches,
        )

    @staticmethod
    def _match_assignments(
        symbols: t.SequenceOf[m.Infra.SymbolInfo],
        # Use the canonical scalar sequence alias directly.
        source_lines: t.StrSequence,
        value_to_ref: t.StrMapping,
    ) -> t.SequenceOf[t.Triple[m.Infra.SymbolInfo, str, str]]:
        """Match assignments.

        Returns:
            The resulting ``t.SequenceOf[t.Triple[m.Infra.SymbolInfo, str, str]]``.

        """
        matches: t.MutableSequenceOf[t.Triple[m.Infra.SymbolInfo, str, str]] = []
        for symbol in symbols:
            # Widen the validated constrained int for indexing.
            line_number: int = symbol.line
            if line_number < 1 or line_number > len(source_lines):
                continue
            line: str = source_lines[line_number - 1]
            eq = line.find("=")
            if eq < 0:
                continue
            raw = line[eq + 1 :].strip()
            if raw in c.Infra.DETECTION_TRIVIAL_VALUES:
                continue
            canonical = value_to_ref.get(raw)
            if canonical is None or canonical == symbol.name:
                continue
            canonical_key = canonical.lower().replace("_", "")
            symbol_key = symbol.name.lower().replace("_", "")
            if canonical_key == symbol_key or symbol_key in canonical_key:
                matches.append((symbol, f"c.{canonical}", raw))
        return tuple(matches)

    @classmethod
    def _apply_and_validate(
        cls,
        rope_project: t.Infra.RopeProject,
        scanned: m.Infra.ConsolidatorScannedFile,
        py_file: Path,
        workspace: Path,
        pkg_name: str,
    ) -> t.Infra.EditResultWithDescs:
        """Apply and validate.

        Returns:
            The resulting ``t.Infra.EditResultWithDescs``.

        Raises:
            TypeError: If the scanned resource is not a Rope file resource.

        """
        resource = scanned.resource
        if not u.Infra.file_resource(resource):
            msg = f"expected a Rope file resource: {py_file}"
            raise TypeError(msg)
        original_source = scanned.source
        src_lines = original_source.splitlines(keepends=True)
        rel = py_file.relative_to(workspace)
        edits: t.MutableSequenceOf[t.Triple[int, int, str]] = []
        descs: t.MutableSequenceOf[str] = []
        for symbol, ref, value in scanned.matches:
            line_number = symbol.line
            if line_number < 1 or line_number > len(src_lines):
                continue
            line = src_lines[line_number - 1]
            eq = line.find("=")
            if eq < 0:
                continue
            base = sum(len(src_lines[i]) for i in range(line_number - 1))
            edits.append((
                base + eq + 1,
                base + eq + 1 + len(line[eq + 1 :].rstrip()),
                f" {ref}",
            ))
            descs.append(f"{symbol.name} = {value} -> {ref}")
        if not edits:
            return (True, [], [])

        ok, report = u.Infra.protected_file_edit(
            py_file,
            request=m.Infra.ProtectedFileEditRequest(
                workspace=workspace,
                before_source=original_source,
                edit_fn=lambda: (
                    u.Infra.rewrite_source_at_offsets(
                        rope_project,
                        resource,
                        edits,
                        apply=True,
                    ),
                    u.Infra.add_import(
                        rope_project,
                        resource,
                        pkg_name,
                        ["c"],
                        apply=True,
                    ),
                    None,
                )[-1],
                restore_fn=lambda: resource.write(original_source),
                gates=cls._ALL_LINT_GATES,
            ),
        )
        if ok:
            return (True, list(descs), [f"  APPLIED {rel}: {item}" for item in descs])
        return (False, list(descs), report)


__all__: list[str] = ["FlextInfraCodegenConsolidatorStepsMixin"]
