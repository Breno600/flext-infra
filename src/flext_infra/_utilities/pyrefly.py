"""Canonical Pyrefly target selection utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_cli import u

from flext_infra import c

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraUtilitiesPyrefly:
    """Own target selection shared by quality gates and refactor automation."""

    @staticmethod
    def pyrefly_target_args(
        project_dir: Path, discovered_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Preserve explicit files; use configured includes for discovered roots."""
        if any((project_dir / target).is_file() for target in discovered_dirs):
            return discovered_dirs
        document = u.Cli.toml_read(project_dir / c.PYPROJECT_FILENAME)
        if document is None:
            return discovered_dirs
        tool = u.Cli.toml_table_child(document, c.Infra.TOOL)
        pyrefly = (
            None if tool is None else u.Cli.toml_table_child(tool, c.Infra.PYREFLY)
        )
        if pyrefly is None:
            return discovered_dirs
        includes = u.Cli.toml_item_child(pyrefly, c.Infra.PROJECT_INCLUDES)
        return () if includes is not None else discovered_dirs


__all__: list[str] = ["FlextInfraUtilitiesPyrefly"]
