"""Warning-free Rope project boundary.

Rope 1.14.0 and its current upstream branch decorate
``Project._init_source_folders`` as deprecated while still calling it
unconditionally from ``Project.__init__``.  A strict warnings-as-errors runtime
therefore cannot construct the documented public ``Project`` at all.  The
boundary below preserves Rope's initializer semantics without filtering the
warning or weakening the process warning policy.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Self, override

if TYPE_CHECKING:
    from flext_infra import t

from rope.base.project import Project


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
            """Read the exact captured source, including proposed edits."""
            return self._sources[Path(path).resolve()]

    @classmethod
    def from_snapshot(
        cls, root: str, sources: Mapping[Path, str], source_folders: t.SequenceOf[str]
    ) -> Self:
        """Construct a fresh Rope identity graph without persistent state."""
        if not Path(root).is_dir():
            msg = f"Rope snapshot root must already exist: {root}"
            raise ValueError(msg)
        return cls(
            root,
            fscommands=cls.SnapshotFiles(sources),
            ropefolder=None,
            save_objectdb=False,
            save_history=False,
            source_folders=source_folders,
        )

    @override
    def _init_source_folders(self) -> None:
        """Initialize configured source roots without Rope's warning wrapper."""
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
