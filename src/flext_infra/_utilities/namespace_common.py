"""Shared text/path helpers for namespace refactor utilities.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c
from flext_infra._utilities.rope_source import FlextInfraUtilitiesRopeSource

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesRefactorNamespaceCommon:
    """Shared text and path helpers for namespace refactor utilities."""

    @staticmethod
    def _parse_simple_from_import_line(line: str) -> t.Infra.TransformResult | None:
        """Parse simple from import line.

        Returns:
            The resulting ``t.Infra.TransformResult | None``.

        """
        stripped = line.strip()
        if (
            not stripped.startswith("from ")
            or "(" in stripped
            or ")" in stripped
            or " as " in stripped
        ):
            return None
        module_name, separator, imported_names = stripped.removeprefix(
            "from ",
        ).partition(" import ")
        if not separator or not module_name or not imported_names:
            return None
        names = [name.strip() for name in imported_names.split(",") if name.strip()]
        return (module_name, names)

    @staticmethod
    def insert_import_lines(
        *,
        lines: t.StrSequence,
        imports: t.StrSequence,
    ) -> t.StrSequence:
        """Insert import lines.

        Returns:
            The resulting ``t.StrSequence``.

        """
        if not imports:
            return list(lines)
        insert_idx = (
            FlextInfraUtilitiesRopeSource.index_after_docstring_and_future_imports(
                lines,
            )
        )
        return [*lines[:insert_idx], *imports, *lines[insert_idx:]]

    @staticmethod
    def canonical_target_file(
        *,
        project_root: Path,
        source_file: Path,
        filename: str,
    ) -> Path:
        """Canonical target file.

        Returns:
            The resulting ``Path``.

        """
        parts = source_file.parts
        src_dir: str = c.Infra.DEFAULT_SRC_DIR
        if src_dir in parts:
            src_index = parts.index(src_dir)
            if src_index + 1 < len(parts):
                package_name = parts[src_index + 1]
                return project_root / src_dir / package_name / filename
        return source_file.parent / filename

    @staticmethod
    def find_top_level_block(
        *,
        lines: t.StrSequence,
        header: str,
    ) -> t.Pair[int, int] | None:
        """Find top level block.

        Returns:
            The resulting ``t.Pair[int, int] | None``.

        """
        start_idx = -1
        for idx, line in enumerate(lines):
            if line.startswith(header):
                start_idx = idx
                break
        if start_idx < 0:
            return None
        end_idx = len(lines)
        for idx in range(start_idx + 1, len(lines)):
            line = lines[idx]
            if line and not line.startswith((" ", "\t")) and not line.startswith("#"):
                end_idx = idx
                break
        return (start_idx, end_idx)


__all__: list[str] = ["FlextInfraUtilitiesRefactorNamespaceCommon"]
