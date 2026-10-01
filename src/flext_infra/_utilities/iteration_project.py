"""Project root resolution iteration utility facet.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraUtilitiesIterationProject:
    """Static helpers for resolving project roots from file paths."""

    @staticmethod
    def resolve_project_root(file_path: Path) -> Path | None:
        """Return the nearest ancestor of ``file_path`` holding pyproject.toml.

        Every ancestor up to the filesystem root is a candidate; no depth cap
        silently drops a deeply nested file.
        """
        return next(
            (
                parent
                for parent in file_path.parents
                if (parent / c.PYPROJECT_FILENAME).is_file()
            ),
            None,
        )


__all__: list[str] = ["FlextInfraUtilitiesIterationProject"]
