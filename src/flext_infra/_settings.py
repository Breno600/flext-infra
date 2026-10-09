"""Runtime settings for flext-infra — namespaced under ``settings.Infra``.

Layer-0 style: universal fields via FLEXT; all project fields in the ``Infra``
namespace group with simple scalar types (env-settable).

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os as _os
from typing import ClassVar

from flext_core import FlextSettings, m
from flext_infra._models.settings import FlextInfraSettingsModels


class FlextInfraSettings(FlextSettings):
    """Environment-backed infra settings; fields under ``settings.Infra.*``."""

    model_config: ClassVar[m.SettingsConfigDict] = m.SettingsConfigDict(
        env_prefix="FLEXT_INFRA_",
        env_nested_delimiter="__",
        extra="ignore",
        frozen=True,
    )

    # Composition only; declaration and env validation stay private.
    Infra: FlextInfraSettingsModels.Infra = m.Field(
        default_factory=FlextInfraSettingsModels.Infra,
        description="Namespaced infra settings.",
    )

    @staticmethod
    def env_lookup(name: str) -> str | None:
        """Return one raw environment value through the settings boundary.

        The only sanctioned raw-environment read in the package: keys that are
        dynamic by contract (caller-named CLI parameters, CI passthrough
        variables, subprocess environment merges). Static values must be typed
        ``settings.Infra.*`` fields instead; ambient ``os.environ`` reads
        elsewhere are banned by the ``ban-ambient-environ-read`` rule.

        Returns:
            One raw environment value through the settings boundary.

        """
        return _os.environ.get(name)

    @staticmethod
    def env_required(name: str) -> str:
        """Read a required dynamic key, preserving native missing-key semantics.

        Returns:
            The resulting ``str``.

        """
        return _os.environ[name]


settings: FlextInfraSettings = FlextInfraSettings.fetch_global()
"""Process-wide infra settings singleton — ``from flext_infra import settings``."""


__all__: list[str] = ["FlextInfraSettings", "settings"]
