"""Canonical Pyrefly target selection utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_cli import u

from flext_infra import c, config

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraUtilitiesPyrefly:
    """Own target selection shared by quality gates and refactor automation."""

    @staticmethod
    def pyrefly_target_args(
        project_dir: Path,
        discovered_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Preserve explicit files; use configured includes for discovered roots.

        Pyrefly ignores the configured ``project-excludes`` whenever files are
        passed on the command line and reads them only from
        ``--project-excludes``. Explicit targets therefore carry the project's
        configured excludes, so a generated or vendored tree inside a target
        directory stays excluded exactly as in project-checking mode.

        Returns:
            The resulting ``t.StrSequence``.

        """
        document = u.Cli.toml_read(project_dir / c.PYPROJECT_FILENAME)
        tool = (
            None if document is None else u.Cli.toml_table_child(document, c.Infra.TOOL)
        )
        pyrefly = (
            None if tool is None else u.Cli.toml_table_child(tool, c.Infra.PYREFLY)
        )
        if any((project_dir / target).is_file() for target in discovered_dirs):
            excludes = (
                ()
                if pyrefly is None
                else u.Cli.toml_as_string_list(
                    u.Cli.toml_item_child(pyrefly, c.Infra.PROJECT_EXCLUDES),
                )
            )
            return (
                *discovered_dirs,
                *(
                    argument
                    for glob in excludes
                    for argument in (c.Infra.PYREFLY_PROJECT_EXCLUDES_FLAG, glob)
                ),
            )
        if pyrefly is None:
            return discovered_dirs
        includes = u.Cli.toml_item_child(pyrefly, c.Infra.PROJECT_INCLUDES)
        return () if includes is not None else discovered_dirs

    @staticmethod
    def pyrefly_project_excludes(declared_globs: t.StrSequence) -> t.StrSequence:
        """Compose the declared Pyrefly excludes with the generated-source globs.

        The generated-source trees come from their single codegen artifact
        key, so every Pyrefly projection excludes exactly the trees the other
        analyzers exclude.

        Returns:
            The sorted, deduplicated ``project-excludes`` values.

        """
        return sorted({*declared_globs, *config.Infra.codegen.generated_source_globs})


__all__: list[str] = ["FlextInfraUtilitiesPyrefly"]
