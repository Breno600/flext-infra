"""Project candidate discovery for flext-infra utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, t
from flext_infra._utilities import FlextInfraUtilitiesGit
from flext_infra._utilities._project_discovery_shape import (
    FlextInfraUtilitiesProjectDiscoveryShapeMixin,
)


class FlextInfraUtilitiesProjectDiscoveryCandidatesMixin(
    FlextInfraUtilitiesProjectDiscoveryShapeMixin,
):
    """Private candidate enumeration for workspace project discovery."""

    @classmethod
    def discover_project_candidates(
        cls,
        repository_root: Path,
        *,
        scan_dirs: frozenset[str] | None = None,
    ) -> t.SequenceOf[Path]:
        """Return the root and projects declared by its own ``.gitmodules``.

        Returns:
            The root and projects declared by its own ``.gitmodules``.

        Raises:
            ValueError: If ``declared_paths.failure``.

        """
        roots: t.MutableSequenceOf[Path] = []
        effective_scan_dirs = scan_dirs or frozenset()
        declared = FlextInfraUtilitiesGit.git_submodule_declarations(repository_root)
        if declared.failure:
            raise ValueError(declared.error or "invalid .gitmodules")
        configured_projects = tuple(item.path.as_posix() for item in declared.value)
        configured_project_set = frozenset(configured_projects)
        resolved_repository_root = repository_root.resolve()
        configured_entries: set[Path] = set()
        for project in configured_projects:
            entry = (resolved_repository_root / project).resolve()
            if entry.is_dir() and entry.is_relative_to(resolved_repository_root):
                configured_entries.add(entry)
        if cls._looks_like_project(
            resolved_repository_root,
            effective_scan_dirs=effective_scan_dirs,
            configured_project_set=configured_project_set,
        ):
            roots.append(resolved_repository_root)
        if configured_projects:
            candidate_entries: t.SequenceOf[Path] = sorted(
                configured_entries,
                key=Path.as_posix,
            )
            roots.extend([
                entry.resolve()
                for entry in candidate_entries
                if entry.is_dir()
                and not entry.name.startswith(".")
                and cls._looks_like_project(
                    entry.resolve(),
                    effective_scan_dirs=effective_scan_dirs,
                    configured_project_set=configured_project_set,
                )
            ])
        if not roots and (resolved_repository_root / c.Infra.DEFAULT_SRC_DIR).is_dir():
            return [resolved_repository_root]
        return roots


__all__: list[str] = ["FlextInfraUtilitiesProjectDiscoveryCandidatesMixin"]
