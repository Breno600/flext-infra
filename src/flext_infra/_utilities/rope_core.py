"""Shared Rope lifecycle helpers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from flext_infra import config, t
from flext_infra._utilities import (
    FlextInfraUtilitiesProjectDiscovery,
    FlextInfraUtilitiesRopeCorePyModuleMixin,
    FlextInfraUtilitiesRopeCoreResourcesMixin,
    FlextInfraUtilitiesRopeRuntime,
)


class FlextInfraUtilitiesRopeCore(
    FlextInfraUtilitiesRopeCoreResourcesMixin,
    FlextInfraUtilitiesRopeCorePyModuleMixin,
):
    """Core Rope lifecycle helpers."""

    @staticmethod
    def init_rope_project(repository_root: Path) -> t.Infra.RopeProject:
        """Create a project-scoped Rope session with no disk artifacts.

        Returns:
            The resulting ``t.Infra.RopeProject``.

        """
        resolved_root = repository_root.resolve()
        return FlextInfraUtilitiesRopeCore._new_project(
            resolved_root,
            project_roots=(resolved_root,),
        )

    @staticmethod
    def init_rope_workspace(repository_root: Path) -> t.Infra.RopeProject:
        """Create a Rope session spanning every project below a workspace root.

        Returns:
            The resulting ``t.Infra.RopeProject``.

        """
        resolved_root = repository_root.resolve()
        project_roots = tuple(
            project_root
            for project_root in (
                FlextInfraUtilitiesProjectDiscovery.discover_rope_project_roots
            )(
                resolved_root,
            )
            if project_root.resolve().is_relative_to(resolved_root)
        )
        return FlextInfraUtilitiesRopeCore._new_project(
            resolved_root,
            project_roots=project_roots,
        )

    @staticmethod
    def _new_project(
        resolved_root: Path,
        *,
        project_roots: t.SequenceOf[Path],
    ) -> t.Infra.RopeProject:
        """Create one Rope project from validated source roots.

        Returns:
            The resulting ``t.Infra.RopeProject``.

        """
        source_folders = sorted({
            str(scan_path.relative_to(resolved_root))
            for project_root in project_roots
            for dir_name in config.Infra.source_scan.roots
            if (scan_path := project_root / dir_name).is_dir()
            and scan_path.resolve().is_relative_to(resolved_root)
        })
        return FlextInfraUtilitiesRopeRuntime.new_project(
            str(resolved_root),
            ropefolder="",
            save_objectdb=False,
            filter_lists=(
                sorted(config.Infra.codegen.source_scan_ignored),
                source_folders,
                sorted(
                    name
                    for name, module in tuple(sys.modules.items())
                    if name.partition(".")[0] in sys.stdlib_module_names
                    and module is not None
                    and module.__spec__ is not None
                    and module.__spec__.origin == "frozen"
                ),
            ),
        )

    @staticmethod
    @contextmanager
    def open_project(
        repository_root: Path,
        *,
        project_roots: t.SequenceOf[Path] | None = None,
    ) -> Generator[t.Infra.RopeProject]:
        """Open one Rope project and always close it through the core boundary.

        Yields:
            Each ``t.Infra.RopeProject``.

        Raises:
            ValueError: If Rope project roots must be nonempty and remain inside the
                declared workspace.

        """
        resolved = repository_root.resolve()
        roots = (
            (resolved,)
            if project_roots is None
            else tuple(path.resolve() for path in project_roots)
        )
        if not roots or any(not path.is_relative_to(resolved) for path in roots):
            msg = (
                "Rope project roots must be nonempty and remain "
                "inside the declared workspace"
            )
            raise ValueError(msg)
        rope_project = FlextInfraUtilitiesRopeCore._new_project(
            resolved,
            project_roots=roots,
        )
        try:
            yield rope_project
        finally:
            rope_project.close()


__all__: list[str] = ["FlextInfraUtilitiesRopeCore"]
