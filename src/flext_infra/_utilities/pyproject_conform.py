"""Autonomous library pyproject conformance through the flext-cli TOML facade."""

from __future__ import annotations

from flext_infra._utilities._pyproject.base import (
    FlextInfraUtilitiesPyprojectConformBase,
)


class FlextInfraUtilitiesPyprojectConform(FlextInfraUtilitiesPyprojectConformBase):
    """Render root workspace and autonomous library metadata deterministically."""


__all__: list[str] = ["FlextInfraUtilitiesPyprojectConform"]
