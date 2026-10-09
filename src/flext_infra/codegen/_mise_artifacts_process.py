"""Atomic staging writes shared by generation phases.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import r, u
from flext_infra.codegen._mise_artifacts_files import FlextInfraMiseArtifactsFiles

if TYPE_CHECKING:
    from flext_infra import m, p


class FlextInfraMiseArtifactsProcess:
    """Exact isolated-state writes through the canonical atomic owner."""

    @classmethod
    def write_new(
        cls,
        path: Path,
        content: bytes,
        mode: int,
        *,
        intent: m.Infra.CodegenStagingIntent | None = None,
    ) -> p.Result[bool]:
        """Create exact isolated state through the canonical atomic owner.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if intent is None:
            before = u.Cli.atomic_read_binary_file_state(path, required=False)
            if before.failure:
                return r[bool].from_failure(before)
            expected = before.value
        else:
            if (
                intent.before.path != path
                or intent.mode != mode
                or intent.sha256 != FlextInfraMiseArtifactsFiles.digest(content)
                or intent.created is not None
            ):
                return r[bool].fail(
                    f"staging write differs from durable intention: {path}",
                )
            expected = intent.before
        if expected.content is not None:
            return r[bool].fail(f"new staging destination already exists: {path}")
        return u.Cli.atomic_write_binary_file_guarded(
            expected,
            content,
            permission_mode=mode,
        )


__all__: list[str] = ["FlextInfraMiseArtifactsProcess"]
