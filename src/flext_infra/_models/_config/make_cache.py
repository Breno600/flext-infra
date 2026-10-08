"""Shared test and analysis cache policy models for Make workflows.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from flext_cli import m

from flext_infra import c, t
from flext_infra._models import (
    FlextInfraConfigModelsContract,
    FlextInfraExternalCacheDirectorySpec,
)


class FlextInfraConfigModelsMakeCache:
    """Testmon and Mypy cache policy models shared by Make workflows."""

    class TestmonCachePolicySpec(FlextInfraConfigModelsContract.ConfigContract):
        """Declarative Actions-cache policy for the shared testmon database.

        Implements the preserved #1001 delta (bead flext-j0u23): two-phase
        generations with per-mode caps, a per-repository byte budget with a
        three-stage quota ladder, a save-ref allowlist (never save from PRs)
        and a cache-key namespace.
        """

        mode: Annotated[
            Literal["bootstrap", "stable"],
            m.Field(description="Cache phase: bootstrap seeds, stable saves"),
        ] = "stable"
        save_enabled: Annotated[
            bool,
            m.Field(description="Master switch for cache publishes"),
        ] = False
        max_bootstrap_generations: Annotated[
            int,
            m.Field(gt=0, description="Retention cap for bootstrap generations"),
        ] = 3
        max_stable_generations: Annotated[
            int,
            m.Field(gt=0, description="Retention cap for stable generations"),
        ] = 3
        per_repo_budget_bytes: Annotated[
            int,
            m.Field(gt=0, description="Per-repository byte budget"),
        ] = 52_428_800
        warning_threshold_percent: Annotated[
            int,
            m.Field(ge=0, le=100, description="Quota-ladder warning stage"),
        ] = 80
        maintenance_threshold_percent: Annotated[
            int,
            m.Field(ge=0, le=100, description="Quota-ladder maintenance stage"),
        ] = 90
        block_threshold_percent: Annotated[
            int,
            m.Field(ge=0, le=100, description="Quota-ladder block stage"),
        ] = 95
        allowed_save_refs: Annotated[
            tuple[t.NonEmptyStr, ...],
            m.Field(description="Refs whose pushes may publish cache generations"),
        ] = ("main", "0.12.0-dev")
        key_prefix: Annotated[
            t.NonEmptyStr,
            m.Field(description="Actions cache key namespace"),
        ] = "flext-testmon"

        @m.model_validator(mode="after")
        def require_ascending_quota_ladder(self) -> Self:
            """Keep the quota ladder strictly ascending within the percent scale.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If testmon cache quota ladder must ascend warning <
                    maintenance < block <= 100.
            """
            full_scale = 100
            if not (
                self.warning_threshold_percent
                < self.maintenance_threshold_percent
                < self.block_threshold_percent
                <= full_scale
            ):
                msg = (
                    "testmon cache quota ladder must ascend "
                    "warning < maintenance < block <= 100"
                )
                raise ValueError(msg)
            return self

    class MypyCacheSpec(
        FlextInfraExternalCacheDirectorySpec,
        FlextInfraConfigModelsContract.ConfigContract,
    ):
        """Project-keyed shared Mypy cache, one analysis reused across relocks."""

        cache_environment_variable: Annotated[
            c.Infra.MypyCacheEnvironment,
            m.Field(
                default=c.Infra.MypyCacheEnvironment.CACHE_DIR,
                description="Mypy's cache-directory environment variable",
            ),
        ]
        data_home_environment_variable: Annotated[
            c.Infra.MypyCacheEnvironment,
            m.Field(
                default=c.Infra.MypyCacheEnvironment.DATA_HOME,
                description="XDG persistent cache-home variable",
            ),
        ]
        user_home_environment_variable: Annotated[
            c.Infra.MypyCacheEnvironment,
            m.Field(
                default=c.Infra.MypyCacheEnvironment.USER_HOME,
                description="User home variable for the XDG default",
            ),
        ]
        home_cache_directory: Annotated[
            Path,
            m.Field(
                default=Path(".cache"),
                description="Standard cache directory below the user home",
            ),
        ]
        external_storage_directory: Annotated[
            Path,
            m.Field(
                default=Path("flext/infra/mypy"),
                description="FLEXT-owned directory below the cache home",
            ),
        ]

        @m.model_validator(mode="after")
        def require_external_cache_contract(self) -> Self:
            """Keep the official cache variable and the external path policy exact.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If mypy cache.
            """
            for name, actual, expected in (
                (
                    "cache_environment_variable",
                    self.cache_environment_variable,
                    c.Infra.MypyCacheEnvironment.CACHE_DIR,
                ),
                (
                    "data_home_environment_variable",
                    self.data_home_environment_variable,
                    c.Infra.MypyCacheEnvironment.DATA_HOME,
                ),
                (
                    "user_home_environment_variable",
                    self.user_home_environment_variable,
                    c.Infra.MypyCacheEnvironment.USER_HOME,
                ),
            ):
                if actual != expected:
                    msg = f"mypy cache {name} must be {expected.value}"
                    raise ValueError(msg)
            return self


__all__: list[str] = ["FlextInfraConfigModelsMakeCache"]
