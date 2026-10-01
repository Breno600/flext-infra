"""Base class for rope-based transformers with change-tracking.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraRopeTransformer:
    """Base for all rope transformers — tracks changes and invokes callback.

    Subclasses that follow the ``read → apply_to_source → write`` pattern
    need only implement ``apply_to_source`` and set ``_description``.
    The default ``transform()`` handles the boilerplate.
    """

    _description: str = "transformation"

    def __init__(self, *, on_change: t.Infra.ChangeCallback = None) -> None:
        """Initialize change tracking with an optional callback."""
        self._on_change = on_change
        self.changes: t.MutableSequenceOf[str] = []

    @abstractmethod
    def apply_to_source(self, source: str) -> t.Infra.TransformResult:
        """Apply transformation to in-memory source."""
        ...

    def transform(
        self,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
    ) -> t.Infra.TransformResult:
        """Read → apply_to_source → write if changed. Override for custom logic.

        Returns:
            The resulting ``t.Infra.TransformResult``.

        """
        _ = rope_project
        source = resource.read()
        updated, changes = self.apply_to_source(source)
        if updated != source and changes:
            resource.write(updated)
        return updated, changes


__all__: list[str] = ["FlextInfraRopeTransformer"]
