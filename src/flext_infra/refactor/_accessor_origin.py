"""Origin resolution for automated accessor renames — extracted concern.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraAccessorOriginResolver:
    """Prove each rename occurrence is defined inside the rule's origin package.

    The rename catalog's ``origin`` names the owning distribution package
    (for example ``flext_core``). A rewrite may only touch occurrences whose
    defining module lives under that package: a homonym defined by the scanned
    repository, another library, or a builtin stays untouched and is reported
    as a skipped warning instead.
    """

    def __init__(self, rope_project: t.Infra.RopeProject) -> None:
        """Initialize with the shared Rope project of the migration run."""
        self._rope_project = rope_project
        self._pymodules: dict[str, t.Infra.RopePyModule] = {}

    @staticmethod
    def within_origin(definition_path: str, *, origin: str) -> bool:
        """Return whether ``definition_path`` lives inside the origin package.

        Returns:
            The resulting ``bool``.

        """
        return f"/{origin}/" in definition_path

    def occurrence_origin(
        self,
        py_file: Path,
        offset: int,
    ) -> str | None:
        """Resolve the defining module path of the name at ``offset``.

        Returns:
            The resulting ``str | None`` — ``None`` marks an unresolvable,
            builtin, or out-of-project definition.

        """
        resource = u.Infra.resolve_resource_from_path(self._rope_project, py_file)
        if resource is None:
            return None
        cache_key = str(py_file)
        if cache_key not in self._pymodules:
            self._pymodules[cache_key] = u.Infra.resolve_pymodule(
                self._rope_project,
                resource,
            )
        return u.Infra.name_definition_resource_path(
            self._pymodules[cache_key],
            offset,
        )


__all__: list[str] = ["FlextInfraAccessorOriginResolver"]
