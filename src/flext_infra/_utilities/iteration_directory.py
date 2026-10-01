"""Directory-scoped Python file iteration utility facet.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, config

from ._git.scope import FlextInfraUtilitiesGitScopeMixin

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraUtilitiesIterationDirectory(FlextInfraUtilitiesGitScopeMixin):
    """Static helpers for iterating Python files within a single directory tree."""

    @classmethod
    def iter_directory_python_files(cls, directory: Path) -> t.SequenceOf[Path]:
        """Iterate production Python files in one configured source tree.

        Scoped to one directory (project src, subdirectory, etc.) — unlike
        ``iter_python_files`` which discovers across the whole workspace.

        Args:
            directory: Root directory to scan.

        Returns:
            Sorted list of matching file paths. Empty list if directory
            does not exist.

        """
        resolved_directory = directory.resolve()
        if not resolved_directory.is_dir():
            return []
        tracked_files = FlextInfraUtilitiesGitScopeMixin.git_tracked_scope_paths(
            resolved_directory
        )
        files = (
            sorted(resolved_directory.rglob(c.Infra.EXT_PYTHON_GLOB))
            if tracked_files is None
            else [
                file_path
                for file_path in tracked_files
                if file_path.suffixes == [c.Infra.EXT_PYTHON]
            ]
        )
        return [
            file_path
            for file_path in files
            if file_path.is_file()
            and file_path.suffixes == [c.Infra.EXT_PYTHON]
            and not frozenset(config.Infra.codegen.source_scan_ignored).intersection(
                file_path.relative_to(resolved_directory).parts
            )
        ]


__all__: list[str] = ["FlextInfraUtilitiesIterationDirectory"]
