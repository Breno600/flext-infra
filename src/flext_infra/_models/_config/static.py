"""Source discovery specification models."""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from ... import t
from .contract import FlextInfraConfigModelsContract


class FlextInfraConfigModelsStatic:
    """Source discovery specification models."""

    class SourceScanSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Canonical production roots and recursively ignored directories."""

        roots: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Ordered production source directory names"),
        ]
