"""Shared future-import rewrites for namespace refactors.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_cli import u

from flext_infra import c, t
from flext_infra._utilities import FlextInfraUtilitiesDiscovery
from flext_infra._utilities.namespace_common import (
    FlextInfraUtilitiesRefactorNamespaceCommon,
)


class FlextInfraUtilitiesRefactorNamespaceFlext(
    FlextInfraUtilitiesRefactorNamespaceCommon,
):
    """Helpers for future-import rewrites."""

    @staticmethod
    def rewrite_missing_future_annotations(*, py_files: t.SequenceOf[Path]) -> None:
        """Rewrite missing future annotations.

        Raises:
            RuntimeError: If ``write_result.failure``.
            ValueError: If refusing future-annotations rewrite outside project.

        """
        for file_path in py_files:
            project_root = FlextInfraUtilitiesDiscovery.project_root(file_path)
            resolved_file = file_path.resolve()
            if project_root is None or not resolved_file.is_relative_to(
                project_root.resolve(),
            ):
                msg = (
                    f"refusing future-annotations rewrite outside project: {file_path}"
                )
                raise ValueError(msg)
            if resolved_file.name == c.Infra.PY_TYPED:
                continue
            source = resolved_file.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            if c.Infra.FUTURE_ANNOTATIONS in source:
                continue
            lines = source.splitlines()
            if not lines:
                continue
            rewritten = FlextInfraUtilitiesRefactorNamespaceFlext.insert_import_lines(
                lines=lines,
                imports=["", c.Infra.FUTURE_ANNOTATIONS, ""],
            )
            write_result = u.Cli.files_write_text(
                resolved_file,
                "\n".join(rewritten).rstrip() + "\n",
            )
            if write_result.failure:
                msg = write_result.error or f"failed to rewrite {resolved_file}"
                raise RuntimeError(msg)


__all__: list[str] = ["FlextInfraUtilitiesRefactorNamespaceFlext"]
