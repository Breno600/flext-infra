"""Inject ``from __future__ import annotations`` when missing.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import override

from flext_infra import t, u

from .rope_transformer import FlextInfraRopeTransformer


class FlextInfraRefactorFutureImport(FlextInfraRopeTransformer):
    """Ensure the leading ``from __future__ import annotations`` line exists."""

    _description = "insert from __future__ import annotations"

    @override
    def apply_to_source(self, source: str) -> t.Infra.TransformResult:
        """Normalize the future import after the module docstring."""
        updated = u.Infra.ensure_future_annotations(source)
        if updated == source:
            return source, list(self.changes)
        self._record_change("Normalized from __future__ import annotations")
        return updated, list(self.changes)


__all__: list[str] = ["FlextInfraRefactorFutureImport"]
