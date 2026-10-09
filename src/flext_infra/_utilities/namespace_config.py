"""Namespace enforcement configuration helpers for flext-infra utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, config
from flext_infra._utilities import FlextInfraUtilitiesGit, FlextInfraUtilitiesPyproject

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraUtilitiesNamespaceConfig:
    """Static helpers for reading namespace enforcement configuration."""

    @staticmethod
    def namespace_meta(project_root: Path) -> t.JsonMapping:
        """Return optional ``tool.flext.namespace`` metadata for one project.

        Returns:
            Optional ``tool.flext.namespace`` metadata for one project.

        Raises:
            TypeError: If [tool.flext.namespace] must be a table in.

        """
        flext_meta = FlextInfraUtilitiesPyproject.tool_flext_meta(project_root)
        if "namespace" not in flext_meta:
            return {}
        namespace = flext_meta["namespace"]
        if not isinstance(namespace, dict):
            msg = f"[tool.flext.namespace] must be a table in {project_root}"
            raise TypeError(msg)
        return namespace

    @staticmethod
    def _namespace_flag(project_root: Path, key: str, *, absent: bool) -> bool:
        """Return one boolean ``[tool.flext.namespace]`` flag; a non-bool fails.

        Returns:
            One boolean ``[tool.flext.namespace]`` flag; a non-bool fails.

        Raises:
            TypeError: If [tool.flext.namespace].

        """
        meta = FlextInfraUtilitiesNamespaceConfig.namespace_meta(project_root)
        if key not in meta:
            return absent
        value = meta[key]
        if not isinstance(value, bool):
            msg = f"[tool.flext.namespace] {key} must be a boolean in {project_root}"
            raise TypeError(msg)
        return value

    @staticmethod
    def namespace_enabled(project_root: Path) -> bool:
        """Return whether namespace enforcement is enabled (enabled when unset).

        Returns:
            Whether namespace enforcement is enabled (enabled when unset).

        """
        return FlextInfraUtilitiesNamespaceConfig._namespace_flag(
            project_root,
            "enabled",
            absent=True,
        )

    @staticmethod
    def namespace_scan_dirs(project_root: Path) -> frozenset[str]:
        """Return configured scan dirs for namespace enforcement.

        Priority:
        1. Explicit ``[tool.flext.namespace] scan_dirs`` in pyproject.toml.
        2. Git-tracked top-level directories that exist on disk.
        3. Outside Git, the configured source-scan roots that exist on disk.

        Returns:
            Configured scan dirs for namespace enforcement.

        Raises:
            TypeError: If [tool.flext.namespace] scan_dirs must be a list of non-empty
                strings in.
            ValueError: If [tool.flext.namespace] scan_dirs is empty in; or if
                ``declared.failure``.

        """
        meta = FlextInfraUtilitiesNamespaceConfig.namespace_meta(project_root)
        if "scan_dirs" in meta:
            configured = meta["scan_dirs"]
            scan_dirs: list[str] = []
            if not isinstance(configured, list):
                msg = (
                    "[tool.flext.namespace] scan_dirs must be a list of "
                    f"non-empty strings in {project_root}"
                )
                raise TypeError(msg)
            for item in configured:
                if not isinstance(item, str) or not item.strip():
                    msg = (
                        "[tool.flext.namespace] scan_dirs must be a list of "
                        f"non-empty strings in {project_root}"
                    )
                    raise TypeError(msg)
                scan_dirs.append(item)
            if not scan_dirs:
                msg = f"[tool.flext.namespace] scan_dirs is empty in {project_root}"
                raise ValueError(msg)
            return frozenset(item.strip() for item in scan_dirs)
        tracked = FlextInfraUtilitiesGit.git_tracked_top_level_dir_names(project_root)
        if tracked is not None:
            declared = FlextInfraUtilitiesGit.git_submodule_declarations(project_root)
            if declared.failure:
                raise ValueError(declared.error)
            # A declared submodule is another repository, consumed as an
            # installed library and never scanned from here.
            excluded = (
                c.Infra.COMMON_EXCLUDED_DIRS
                | {name for name in tracked if name.startswith(".")}
                | {
                    item.path.as_posix()
                    for item in declared.value
                    if len(item.path.parts) == 1
                }
            )
            dynamic = frozenset(
                name
                for name in tracked
                if name not in excluded and (project_root / name).is_dir()
            )
            if dynamic:
                return dynamic
        return frozenset(
            name
            for name in config.Infra.source_scan.roots
            if (project_root / name).is_dir()
        )

    @staticmethod
    def namespace_include_dynamic_dirs(project_root: Path) -> bool:
        """Return whether namespace enforcement scans non-canonical dirs (off if unset).

        Returns:
            Whether namespace enforcement scans non-canonical dirs (off when unset).

        """
        return FlextInfraUtilitiesNamespaceConfig._namespace_flag(
            project_root,
            "include_dynamic_dirs",
            absent=False,
        )


__all__: list[str] = ["FlextInfraUtilitiesNamespaceConfig"]
