"""Workspace-scoped Python file iteration utility facet.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, config, t

from ._git.scope import FlextInfraUtilitiesGitScopeMixin
from .iteration_directory import FlextInfraUtilitiesIterationDirectory

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesIterationWorkspace(FlextInfraUtilitiesIterationDirectory):
    """Static helpers for discovering Python files across workspace projects."""

    @classmethod
    def iter_python_files(
        cls, request: p.Infra.SourceScanRequest
    ) -> p.Result[t.SequenceOf[Path]]:
        """Return Python files from the exact production roots in ``request``.

        Args:
            request: Field-only request containing already-resolved project roots.

        Returns:
            Result[t.SequenceOf[Path]] - Success contains sorted unique file paths.
            Failure if: workspace inaccessible, discovery fails, or OSError.

        """
        invalid_root = next(
            (root for root in request.project_roots if not root.is_dir()), None
        )
        if invalid_root is not None:
            return r[t.SequenceOf[Path]].fail(
                f"python file iteration failed: project root is not a directory: {invalid_root}"
            )
        try:
            files = {
                file_path
                for project_root in request.project_roots
                for file_path in cls._project_python_files(project_root)
            }
            return r[t.SequenceOf[Path]].ok(tuple(sorted(files)))
        except OSError as exc:
            return r[t.SequenceOf[Path]].fail_op("python file iteration", exc)

    @classmethod
    def _project_python_files(cls, project_root: Path) -> t.SequenceOf[Path]:
        """Return configured Python sources with one Git inventory per project."""
        source_roots = tuple(
            path
            for directory_name in config.Infra.source_scan.roots
            if (path := (project_root / directory_name).resolve()).is_dir()
        )
        tracked_files = FlextInfraUtilitiesGitScopeMixin.git_tracked_scope_paths(
            project_root
        )
        if tracked_files is None:
            return tuple(
                file_path
                for source_root in source_roots
                for file_path in FlextInfraUtilitiesIterationDirectory.iter_directory_python_files(
                    source_root
                )
            )
        ignored = frozenset(config.Infra.codegen.source_scan_ignored)
        return tuple(
            file_path
            for file_path in tracked_files
            if file_path.suffixes == [c.Infra.EXT_PYTHON]
            and any(
                file_path.is_relative_to(source_root) for source_root in source_roots
            )
            and not ignored.intersection(file_path.relative_to(project_root).parts)
        )


__all__: list[str] = ["FlextInfraUtilitiesIterationWorkspace"]
