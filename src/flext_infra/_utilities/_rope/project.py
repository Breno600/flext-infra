"""Warning-free Rope project boundary.

Rope 1.14.0 and its current upstream branch decorate
``Project._init_source_folders`` as deprecated while still calling it
unconditionally from ``Project.__init__``.  A strict warnings-as-errors runtime
therefore cannot construct the documented public ``Project`` at all.  The
boundary below preserves Rope's initializer semantics without filtering the
warning or weakening the process warning policy.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Self, override

from rope.base.project import Project

from flext_infra import t


class FlextInfraRopeProject(Project):
    """Rope project with the upstream self-warning initializer repaired."""

    class SnapshotFiles:
        """Closed, read-only input inventory for a semantic planning project.

        Deliberately exposes no filesystem mutation operations. Missing inputs
        are errors, never an invitation to consult a newer disk version.
        """

        def __init__(self, sources: Mapping[Path, str]) -> None:
            self._sources = {
                path.resolve(): source.encode("utf-8")
                for path, source in sources.items()
            }

        def read(self, path: str) -> bytes:
            """Read the exact captured source, including proposed edits.

            Returns:
                The resulting ``bytes``.

            """
            return self._sources[Path(path).resolve()]

    @classmethod
    def from_snapshot(
        cls,
        root: str,
        sources: Mapping[Path, str],
        source_folders: t.SequenceOf[str],
        ignored_resources: t.SequenceOf[str] = (),
    ) -> Self:
        """Construct a fresh Rope identity graph without persistent state.

        Args:
            root: The snapshot root directory.
            sources: The closed source inventory Rope may read.
            source_folders: The declared importable source folders.
            ignored_resources: The scan-ignore SSOT patterns; without them
                Rope enumerates real disk files the closed inventory does not
                hold (tool hooks under ignored resources) and every such
                read dies in the snapshot mapping.

        Returns:
            The resulting ``Self``.

        Raises:
            ValueError: If Rope snapshot root must already exist.

        """
        if not Path(root).is_dir():
            msg = f"Rope snapshot root must already exist: {root}"
            raise ValueError(msg)
        return cls(
            root,
            fscommands=cls.SnapshotFiles(sources),
            ropefolder=None,
            save_objectdb=False,
            save_history=False,
            ignored_resources=list(ignored_resources),
            source_folders=source_folders,
        )

    @override
    def _init_source_folders(self) -> None:
        """Initialize configured source roots without Rope's warning wrapper.

        Raises:
            ValueError: If rope preference 'source_folders' is None; expected a list of
                source folder paths.

        """
        source_folders = self.prefs.get("source_folders", [])
        if source_folders is None:
            msg = (
                "rope preference 'source_folders' is None; "
                "expected a list of source folder paths"
            )
            raise ValueError(msg)
        for path in source_folders:
            self._custom_source_folders.append(self.get_resource(path))


__all__: list[str] = ["FlextInfraRopeProject"]
