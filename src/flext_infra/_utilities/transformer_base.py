"""Base class for rope-based transformers with change-tracking."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraRopeTransformer:
    """Base for rope transformers with change tracking and callback delivery."""

    def __init__(self, *, on_change: t.Infra.ChangeCallback = None) -> None:
        """Initialize change tracking with an optional callback."""
        self._on_change = on_change
        self.changes: t.MutableSequenceOf[str] = []

    def _record_change(self, message: str) -> None:
        """Record change."""
        self.changes.append(message)
        if self._on_change is not None:
            self._on_change(message)
    _description: str = "transformation"

    @abstractmethod
    def apply_to_source(self, source: str) -> t.Infra.TransformResult:
        """Apply transformation to in-memory source."""
        ...

    def transform(
        self, rope_project: t.Infra.RopeProject, resource: t.Infra.RopeResource
    ) -> t.Infra.TransformResult:
        """Read → apply_to_source → write if changed. Override for custom logic."""
        _ = rope_project
        source = resource.read()
        updated, changes = self.apply_to_source(source)
        if updated != source and changes:
            resource.write(updated)
        return updated, changes


__all__: list[str] = ["FlextInfraRopeTransformer"]
