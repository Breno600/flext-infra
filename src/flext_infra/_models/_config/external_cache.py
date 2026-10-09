"""Shared external-cache directory pair for tool cache specs.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Self

from flext_cli import m

from flext_infra._models._config.contract import FlextInfraConfigModelsContract


class FlextInfraExternalCacheDirectorySpec(
    FlextInfraConfigModelsContract.ConfigContract,
):
    """External-cache path pair every tool cache spec owns identically."""

    home_cache_directory: Annotated[
        Path,
        m.Field(description="Standard cache directory below the user home"),
    ]
    external_storage_directory: Annotated[
        Path,
        m.Field(description="FLEXT-owned directory below the cache home"),
    ]

    @m.model_validator(mode="after")
    def require_relative_cache_directories(self) -> Self:
        """Keep both cache directories normalized and repository-relative.

        Returns:
            The resulting ``Self``.

        Raises:
            ValueError: If cache.

        """
        for name, path in (
            ("home_cache_directory", self.home_cache_directory),
            ("external_storage_directory", self.external_storage_directory),
        ):
            if path.is_absolute() or any(
                part in {"", ".", ".."} for part in path.parts
            ):
                msg = f"cache {name} must be normalized and relative"
                raise ValueError(msg)
        return self


__all__: list[str] = ["FlextInfraExternalCacheDirectorySpec"]
