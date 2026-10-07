"""Phase: Inject managed/custom markers into pyproject.toml.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra.constants import c
from flext_infra.typings import t
from flext_infra.utilities import u


class FlextInfraInjectCommentsPhase:
    """Inject managed/custom markers into pyproject.toml."""

    _STRIP_PREFIXES: t.StrSequence = (
        "# [MANAGED]",
        "# [CUSTOM]",
        "# [AUTO]",
        "# Sections with [",
    )

    @staticmethod
    def _is_section_header(line: str) -> bool:
        """Is section header.

        Returns:
            The resulting ``bool``.

        """
        stripped = line.strip()
        return stripped.startswith("[") and stripped.endswith("]")

    @staticmethod
    def _managed_marker_lines() -> t.Infra.StrSet:
        """Return banner lines to strip.

        Returns:
            Banner lines to strip.

        """
        markers = {c.Infra.LEGACY_AUTO_BANNER_LINE}
        markers.update(c.Infra.BANNER.splitlines())
        return markers

    @classmethod
    def _strip_managed_lines(
        cls,
        lines: t.StrSequence,
    ) -> t.Pair[t.StrSequence, t.StrSequence]:
        """Strip managed lines.

        Returns:
            The resulting ``t.Pair[t.StrSequence, t.StrSequence]``.

        """
        changes: t.MutableSequenceOf[str] = []
        managed_lines = cls._managed_marker_lines()
        cleaned: t.MutableSequenceOf[str] = []
        skip_broken_group_section = False
        broken_removed = False
        for line in lines:
            stripped = line.strip()
            if skip_broken_group_section:
                if cls._is_section_header(line):
                    skip_broken_group_section = False
                else:
                    continue
            if stripped.startswith(tuple(cls._STRIP_PREFIXES)):
                continue
            if stripped == "[group.dev.dependencies]":
                skip_broken_group_section = True
                broken_removed = True
                continue
            if stripped in managed_lines:
                continue
            cleaned.append(line)
        if broken_removed:
            changes.append("broken [group.dev.dependencies] section removed")
        return cleaned, changes

    @staticmethod
    def _collapse_blank_lines(lines: t.StrSequence) -> t.StrSequence:
        """Collapse repeated blank lines into a single canonical separator.

        Returns:
            The resulting ``t.StrSequence``.

        """
        normalized: t.MutableSequenceOf[str] = []
        previous_blank = False
        for line in lines:
            is_blank = not line.strip()
            if is_blank and previous_blank:
                continue
            normalized.append(line)
            previous_blank = is_blank
        return normalized

    def apply(self, rendered: str) -> t.Pair[str, t.StrSequence]:
        """Inject managed banner/markers and return updated TOML plus change messages.

        Returns:
            The resulting ``t.Pair[str, t.StrSequence]``.

        Raises:
            RuntimeError: If ``markers_result.failure``.

        """
        changes: t.MutableSequenceOf[str] = []
        lines = rendered.splitlines()
        cleaned_lines, cleanup_changes = self._strip_managed_lines(lines)
        changes.extend(cleanup_changes)
        banner_lines = c.Infra.BANNER.splitlines()
        first_content = next(
            (index for index, line in enumerate(cleaned_lines) if line.strip()),
            len(cleaned_lines),
        )
        content_lines = cleaned_lines[first_content:]
        out: t.MutableSequenceOf[str] = [*banner_lines, ""]
        if lines[: len(banner_lines)] != banner_lines:
            changes.append("managed banner injected")
        emitted_markers: set[str] = set()
        for line in content_lines:
            stripped = line.strip()
            markers_result = u.Infra.pyproject_section_markers(stripped)
            if markers_result.failure:
                raise RuntimeError(
                    markers_result.error or "pyproject section markers failed",
                )
            for marker in markers_result.value:
                if marker not in emitted_markers:
                    out.append(marker)
                    changes.append(f"marker injected for {stripped}")
                    emitted_markers.add(marker)
            out.append(line)
        updated = "\n".join(self._collapse_blank_lines(out)).rstrip() + "\n"
        original = rendered.rstrip() + "\n"
        if updated == original:
            return (updated, [])
        return (updated, changes)


__all__: list[str] = ["FlextInfraInjectCommentsPhase"]
