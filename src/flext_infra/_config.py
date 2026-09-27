"""Typed, frozen config singleton for flext-infra (ADR-005/U18).

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import override

from flext_cli.config import FlextCliConfig

from ._constants.codegen_project import FlextInfraConstantsCodegenProject
from ._models._config.base import FlextInfraConfigModels


class FlextInfraConfig(FlextCliConfig):
    """Declarative flext-infra config loaded and validated once."""

    # NOTE (multi-agent, flext-wkii.9 + flext-wkii.17 / agent: codex): direct
    # config.Infra is the only codegen information surface; no accessor method.
    Infra: FlextInfraConfigModels.Infra

    @classmethod
    def ssot_config_dir(cls) -> Path:
        """Public resolution of the packaged/workspace ``config/`` directory."""
        return cls._config_dir()

    @classmethod
    @override
    def _config_files(cls) -> list[Path]:
        """Tracked configs and operator overlays first, the local file last.

        The sorted glob would discover the local override file in first
        position (``.local`` sorts before ``.yaml``), where it would lose
        every scalar collision; it is filtered out of the discovered set and
        appended explicitly exactly once so it merges with the highest
        precedence of any file source. The governed repository's tracked org
        layer is appended after it, so a checkout root always speaks with the
        last word on its own org data.
        """
        files = [
            item
            for item in super()._config_files()
            if item.name
            != FlextInfraConstantsCodegenProject.CODEGEN_LOCAL_OVERRIDES_FILENAME
        ]
        local = (
            cls._config_dir()
            / FlextInfraConstantsCodegenProject.CODEGEN_LOCAL_OVERRIDES_FILENAME
        )
        if local.is_file():
            files.append(local)
        org = (
            Path.cwd()
            / FlextInfraConstantsCodegenProject.CODEGEN_CONFIG_DIR
            / FlextInfraConstantsCodegenProject.CODEGEN_ORG_OVERRIDES_FILENAME
        )
        if org.is_file():
            files.append(org)
        return files


# The public singleton keeps its type through circular facade analysis.
config: FlextInfraConfig = FlextInfraConfig()
__all__: list[str] = ["FlextInfraConfig", "config"]
