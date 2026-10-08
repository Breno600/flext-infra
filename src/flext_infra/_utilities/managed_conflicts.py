"""Owner-declared managed document conflict recovery utilities.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import u

from flext_infra import c, config, m, p, r, t
from flext_infra._utilities import FlextInfraUtilitiesBase


class FlextInfraUtilitiesManagedConflicts:
    """Recover only merge blocks authorized by the document owner."""

    @staticmethod
    def _toml_quote_after_line(line: str, quote: str | None) -> str | None:
        """Track TOML strings so apparent headers inside strings remain data.

        Returns:
            The delimiter of an open string, or None outside a string.
        """
        index = 0
        while index < len(line):
            character = line[index]
            if quote is None:
                if character == "#":
                    break
                if character in {"'", '"'}:
                    quote = (
                        character * c.Infra.TOML_MULTILINE_QUOTE_LENGTH
                        if line.startswith(
                            character * c.Infra.TOML_MULTILINE_QUOTE_LENGTH,
                            index,
                        )
                        else character
                    )
                    index += len(quote)
                    continue
            elif quote.startswith('"') and character == "\\":
                index += 2
                continue
            elif line.startswith(quote, index):
                length = len(quote)
                if length == c.Infra.TOML_MULTILINE_QUOTE_LENGTH:
                    while line.startswith(quote[0], index + length):
                        length += 1
                index += length
                quote = None
                continue
            index += 1
        return quote

    @classmethod
    def pyproject_regeneration_source(cls, source: str) -> p.Result[str]:
        """Keep custom TOML while declared tool tables regenerate from their owner.

        Returns:
            Custom source bytes, or the original ownership declaration failure.
        """
        spec = cls.pyproject_managed_file()
        if spec.failure:
            return r[str].from_failure(spec)
        owned = tuple(f"tool.{name}" for name in spec.value.managed_tool_tables)
        preserved: list[str] = []
        quote: str | None = None
        managed = False
        for line in source.splitlines(keepends=True):
            header = c.Infra.TOML_SECTION_HEADER_RE.match(line)
            if quote is None and header is not None:
                managed = cls.toml_section_is_owned(header.group(1), owned)
            if not managed:
                preserved.append(line)
            quote = cls._toml_quote_after_line(line, quote)
        return r[str].ok("".join(preserved))

    @staticmethod
    def recover_managed_assignments(
        content: str,
        *,
        conflict_sections: t.StrSequence,
    ) -> p.Result[str]:
        """Recover identical generated assignments without choosing between values.

        Returns:
            The resulting ``p.Result[str]``.
        """
        if u.Cli.toml_mapping_from_text(content) is not None:
            return r[str].ok(content)
        recovered: list[str] = []
        pending: list[str] = []
        assignments: t.MutableMappingKV[str, str] = {}
        section = ""
        for line in content.splitlines(keepends=True):
            header = c.Infra.TOML_SECTION_HEADER_RE.fullmatch(line.rstrip("\r\n"))
            array_header = line.strip()
            is_array_header = array_header.startswith("[[") and array_header.endswith(
                "]]",
            )
            if not pending and (header is not None or is_array_header):
                section = header.group(1) if header is not None else array_header[2:-2]
                assignments.clear()
                recovered.append(line)
                continue
            if not FlextInfraUtilitiesManagedConflicts.toml_section_is_owned(
                section,
                conflict_sections,
            ) or (not pending and (not line.strip() or line.lstrip().startswith("#"))):
                recovered.append(line)
                continue
            pending.append(line)
            assignment = "".join(pending)
            parsed = u.Cli.toml_mapping_from_text(assignment)
            if parsed is None:
                continue
            if len(parsed) != 1:
                return r[str].fail(f"invalid managed TOML assignment in {section}")
            key = next(iter(parsed))
            previous = assignments.get(key)
            if previous is not None and previous != assignment:
                return r[str].fail(
                    f"divergent managed TOML assignment: {section}.{key}",
                )
            if previous is None:
                assignments[key] = assignment
                recovered.extend(pending)
            pending.clear()
        if pending:
            return r[str].fail(f"incomplete managed TOML assignment in {section}")
        return r[str].ok("".join(recovered))

    @staticmethod
    def toml_section_is_owned(section: str, owned: t.StrSequence) -> bool:
        """True when ``section`` is an owned table or a child of one.

        Returns:
            The resulting ``bool``.

        """
        return any(section == item or section.startswith(f"{item}.") for item in owned)

    @staticmethod
    def pyproject_managed_file() -> p.Result[m.Infra.ManagedFileSpec]:
        """Return the pyproject ManagedFileSpec. Missing declaration is a bug.

        Returns:
            The pyproject ManagedFileSpec. Missing declaration is a bug.

        """
        for item in config.Infra.codegen.managed_files:
            if item.path.as_posix() == c.PYPROJECT_FILENAME:
                return r[m.Infra.ManagedFileSpec].ok(item)
        return r[m.Infra.ManagedFileSpec].fail(
            f"codegen.yaml templates.managed_files must declare {c.PYPROJECT_FILENAME}",
        )

    @classmethod
    def pyproject_section_markers(cls, section_header: str) -> p.Result[t.StrSequence]:
        """Render CUSTOM/MANAGED comments from the pyproject ManagedFileSpec.

        Returns:
            The resulting ``p.Result[t.StrSequence]``.

        """
        spec_result = cls.pyproject_managed_file()
        if spec_result.failure:
            return r[t.StrSequence].from_failure(spec_result)
        spec = spec_result.value
        if not (section_header.startswith("[") and section_header.endswith("]")):
            return r[t.StrSequence].ok(())
        inner = section_header[1:-1]
        if inner == c.Infra.PROJECT:
            custom = ", ".join(spec.preserve_project_keys)
            managed = ", ".join(spec.overwrite_project_keys)
            markers = (
                *((f"# [CUSTOM] {custom}",) if custom else ()),
                *((f"# [MANAGED] {managed}",) if managed else ()),
            )
            return r[t.StrSequence].ok(markers)
        owned = next(
            (
                item
                for item in spec.conflict_sections
                if cls.toml_section_is_owned(inner, (item,))
            ),
            None,
        )
        if owned is not None:
            return r[t.StrSequence].ok((f"# [MANAGED] {owned}",))
        if inner.startswith("tool.") and not cls.toml_section_is_owned(
            inner,
            spec.conflict_sections,
        ):
            tool_table = ".".join(inner.split(".")[:2])
            return r[t.StrSequence].ok((f"# [CUSTOM] {tool_table}",))
        return r[t.StrSequence].ok(())

    @staticmethod
    def recover_managed_toml(
        content: str,
        *,
        conflict_sections: t.StrSequence,
    ) -> p.Result[str]:
        """Choose current TOML bytes only inside explicitly owned sections.

        Returns:
            The resulting ``p.Result[str]``.

        """
        if FlextInfraUtilitiesBase.first_merge_conflict_marker(content) is None:
            return FlextInfraUtilitiesManagedConflicts.recover_managed_assignments(
                content,
                conflict_sections=conflict_sections,
            )
        lines = content.splitlines(keepends=True)
        recovered: list[str] = []
        section = ""
        index = 0
        while index < len(lines):
            line = lines[index]
            control = FlextInfraUtilitiesBase.merge_conflict_control(line)
            if control is None:
                section = FlextInfraUtilitiesManagedConflicts._advanced_section(
                    section,
                    line,
                )
                recovered.append(line)
                index += 1
                continue
            if control != "current":
                return r[str].fail("orphan TOML merge-control marker")
            if not FlextInfraUtilitiesManagedConflicts.toml_section_is_owned(
                section,
                conflict_sections,
            ):
                return r[str].fail(
                    "merge conflict is outside owner-declared TOML sections: "
                    f"{section or '<document-root>'}",
                )
            resolved = FlextInfraUtilitiesManagedConflicts._resolved_conflict_block(
                lines,
                index + 1,
            )
            if resolved.failure:
                return r[str].from_failure(resolved)
            current, index = resolved.value
            for current_line in current:
                section = FlextInfraUtilitiesManagedConflicts._advanced_section(
                    section,
                    current_line,
                )
            recovered.extend(current)
        return FlextInfraUtilitiesManagedConflicts.recover_managed_assignments(
            "".join(recovered),
            conflict_sections=conflict_sections,
        )

    @staticmethod
    def _advanced_section(section: str, line: str) -> str:
        """Return the owning section after one content line.

        Returns:
            The resulting ``str``.

        """
        section_match = c.Infra.TOML_SECTION_HEADER_RE.fullmatch(
            line.rstrip("\r\n"),
        )
        if section_match is not None:
            return section_match.group(1)
        return section

    @staticmethod
    def _skipped_ancestor_side(lines: t.SequenceOf[str], index: int) -> p.Result[int]:
        """Skip the ancestor side of a diff3 conflict to its separator.

        Returns:
            The resulting index of the separator line.

        """
        while index < len(lines):
            control = FlextInfraUtilitiesBase.merge_conflict_control(lines[index])
            if control == "separator":
                return r[int].ok(index)
            if control is not None:
                return r[int].fail("nested or malformed TOML merge conflict")
            index += 1
        return r[int].fail("TOML merge conflict has no separator")

    @staticmethod
    def _resolved_conflict_block(
        lines: t.SequenceOf[str],
        index: int,
    ) -> p.Result[t.Pair[list[str], int]]:
        """Consume one full conflict block; return its current side and cursor.

        Returns:
            The resulting ``(current lines, next index)`` pair.

        """
        pair = r[t.Pair[list[str], int]]
        current: list[str] = []
        control = ""
        while index < len(lines):
            control = FlextInfraUtilitiesBase.merge_conflict_control(lines[index])
            if control in {"ancestor", "separator"}:
                break
            if control is not None:
                return pair.fail("nested or malformed TOML merge conflict")
            current.append(lines[index])
            index += 1
        if index >= len(lines):
            return pair.fail("TOML merge conflict has no separator")
        if control == "ancestor":
            skipped = FlextInfraUtilitiesManagedConflicts._skipped_ancestor_side(
                lines,
                index + 1,
            )
            if skipped.failure:
                return pair.from_failure(skipped)
            index = skipped.value
        index += 1
        scanned = FlextInfraUtilitiesManagedConflicts._incoming_side_end(
            lines,
            index,
        )
        if scanned.failure:
            return pair.from_failure(scanned)
        return pair.ok((current, scanned.value + 1))

    @staticmethod
    def _incoming_side_end(lines: t.SequenceOf[str], index: int) -> p.Result[int]:
        """Scan the incoming side to its closing marker.

        Returns:
            The resulting index of the closing ``incoming`` marker line.

        """
        while index < len(lines):
            control = FlextInfraUtilitiesBase.merge_conflict_control(lines[index])
            if control == "incoming":
                return r[int].ok(index)
            if control is not None:
                return r[int].fail("nested or malformed TOML merge conflict")
            index += 1
        return r[int].fail("TOML merge conflict has no closing marker")


__all__: t.VariadicTuple[str] = ("FlextInfraUtilitiesManagedConflicts",)
