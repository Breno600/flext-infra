"""Modernize workspace pyproject.toml files to standardized format."""

from __future__ import annotations

from ._modernizer.base import FlextInfraPyprojectModernizerBase


class FlextInfraPyprojectModernizer(FlextInfraPyprojectModernizerBase):
    """Modernize all workspace pyproject.toml files."""


__all__: list[str] = ["FlextInfraPyprojectModernizer"]
