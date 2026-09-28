"""Shared Rope lifecycle helpers."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from flext_infra import config, t

from ._rope_core_pymodule import FlextInfraUtilitiesRopeCorePyModuleMixin
from ._rope_core_resources import FlextInfraUtilitiesRopeCoreResourcesMixin
from .project_discovery import FlextInfraUtilitiesProjectDiscovery
from .rope_runtime import FlextInfraUtilitiesRopeRuntime


class FlextInfraUtilitiesRopeCore(
    FlextInfraUtilitiesRopeCoreResourcesMixin, FlextInfraUtilitiesRopeCorePyModuleMixin
):
    """Core Rope lifecycle helpers."""

    @staticmethod
    def init_rope_project(repository_root: Path) -> t.Infra.RopeProject:
        """Create a project-scoped Rope session with no disk artifacts."""
        resolved_root = repository_root.resolve()
        return FlextInfraUtilitiesRopeCore._new_project(
            resolved_root, project_roots=(resolved_root,)
        )

    @staticmethod
    def init_rope_workspace(repository_root: Path) -> t.Infra.RopeProject:
        """Create a Rope session spanning every project below a workspace root."""
        resolved_root = repository_root.resolve()
        project_roots = tuple(
            project_root
            for project_root in FlextInfraUtilitiesProjectDiscovery.discover_rope_project_roots(
                resolved_root
            )
            if project_root.resolve().is_relative_to(resolved_root)
        )
        return FlextInfraUtilitiesRopeCore._new_project(
            resolved_root, project_roots=project_roots
        )

    @staticmethod
    def _new_project(
        resolved_root: Path, *, project_roots: t.SequenceOf[Path]
    ) -> t.Infra.RopeProject:
        """Create one Rope project from validated source roots."""
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
            ignored_resources=sorted(config.Infra.codegen.source_scan_ignored),
            source_folders=source_folders,
        )

    @staticmethod
    @contextmanager
    def open_project(repository_root: Path) -> Generator[t.Infra.RopeProject]:
        """Open one Rope project and always close it through the core boundary."""
        rope_project = FlextInfraUtilitiesRopeCore.init_rope_project(repository_root)
        try:
            yield rope_project
        finally:
            rope_project.close()


__all__: list[str] = ["FlextInfraUtilitiesRopeCore"]
