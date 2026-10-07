"""Atomic staging writes shared by generation phases.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraMiseArtifactsProcess:
    """Exact isolated-state writes through the canonical atomic owner."""

    @classmethod
    def write_new(
        cls,
        path: Path,
        content: bytes,
        mode: int,
    ) -> p.Result[bool]:
        """Create exact isolated state through the canonical atomic owner.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        before = u.Cli.atomic_read_binary_file_state(path, required=False)
        if before.failure:
            return r[bool].from_failure(before)
        return u.Cli.atomic_write_binary_file_guarded(
            before.value,
            content,
            permission_mode=mode,
        )


__all__: list[str] = ["FlextInfraMiseArtifactsProcess"]
