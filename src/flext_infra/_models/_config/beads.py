"""Beads projection and workspace environment models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from flext_cli import m, u

from flext_infra import t
from flext_infra._models._config.contract import FlextInfraConfigModelsContract


class FlextInfraConfigModelsBeads:
    """Beads projection and workspace environment models."""

    class BeadsProjectSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Repository-local Beads identity from ``config/beads.yaml``."""

        version: Annotated[
            Literal[1],
            m.Field(description="Beads project configuration schema version"),
        ]
        workspace: Annotated[
            t.NonEmptyStr,
            m.Field(description="Stable workspace identity"),
        ]
        database: Annotated[
            t.NonEmptyStr,
            m.Field(description="Repository-owned Dolt database"),
        ]
        issue_prefix: Annotated[
            t.NonEmptyStr,
            m.Field(description="Repository-owned issue prefix"),
        ]
        custom_issue_types: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Repository-owned custom types beyond the Gas City baseline"
                ),
            ),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_custom_issue_types(self) -> Self:
            """Reject duplicate project extensions before projection.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If beads custom_issue_types must be unique.

            """
            if len(set(self.custom_issue_types)) != len(self.custom_issue_types):
                msg = "beads custom_issue_types must be unique"
                raise ValueError(msg)
            return self

    class BeadsConfigRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Field-only render input for the generated Beads ledger config."""

        issue_prefix: Annotated[
            t.NonEmptyStr,
            m.Field(description="Issue prefix from local config/beads.yaml"),
        ]
        endpoint_origin: Annotated[
            Literal["inherited_city"],
            m.Field(description="Gas City endpoint ownership projection"),
        ]
        endpoint_status: Annotated[
            Literal["verified"],
            m.Field(description="Gas City inherited endpoint status"),
        ]
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Gas City runtime-contract participation; False drops the "
                    "gc endpoint keys and makes Beads own a repository-local "
                    "Dolt server (dolt.auto-start: true)."
                ),
            ),
        ] = True
        custom_issue_types: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Union of project and required custom bead types"),
        ] = ()
        dolt_mode: Annotated[
            t.NonEmptyStr,
            m.Field(description="From toolchain.beads.dolt_mode"),
        ]
        export_auto: Annotated[
            bool,
            m.Field(description="From toolchain.beads.export_auto"),
        ]
        backup_enabled: Annotated[
            bool,
            m.Field(description="From toolchain.beads.backup_enabled"),
        ]
        dolt_disable_event_flush: Annotated[
            bool,
            m.Field(description="From toolchain.beads.dolt_disable_event_flush"),
        ]

    class BeadsMetadataRenderSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Field-only render input for the generated Beads ledger marker.

        The marker carries portable storage and database identity plus the
        checkout's ledger identity. ``project_id`` is NOT invented here: it is
        read back from the checkout's own ``.beads/identity.toml`` so a
        regeneration preserves it. Omitting it made every ``make gen`` strip the
        key, and Beads then minted a fresh identity on next access — observed in
        a consumer rig, where the ledger identity changed on regeneration.
        ``None`` means the checkout has no ledger
        identity yet, and Beads mints the first one.
        """

        database: Annotated[
            t.NonEmptyStr,
            m.Field(description="Dolt database from local config/beads.yaml"),
        ]
        dolt_mode: Annotated[
            t.NonEmptyStr,
            m.Field(description="Storage mode from toolchain.beads.dolt_mode"),
        ]
        project_id: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                default=None,
                description=(
                    "Ledger identity read back from .beads/identity.toml; "
                    "None only before Beads has minted one"
                ),
            ),
        ] = None

    class WorkspaceEnvironmentCliRequest(FlextInfraConfigModelsContract.ConfigContract):
        """CLI-safe request for one Python workspace environment sync."""

        repository_root: Annotated[
            Path,
            m.Field(description="Repository root receiving the sync"),
        ]
        apply: Annotated[
            bool,
            m.Field(description="Write changes instead of reporting them"),
        ] = True
        force: Annotated[
            bool,
            m.Field(description="Replace custom files with generated content"),
        ] = False
        allow_direnv: Annotated[
            bool,
            m.Field(description="Authorize the rendered .envrc after an applied sync"),
        ] = True

    class WorkspaceEnvironmentSyncRequest(
        FlextInfraConfigModelsContract.ConfigContract,
    ):
        """Validated internal request for one workspace environment sync."""

        repository_root: Annotated[
            Path,
            m.Field(description="Repository root receiving the sync"),
        ]
        apply: Annotated[
            bool,
            m.Field(description="Write changes instead of reporting them"),
        ] = True
        force: Annotated[
            bool,
            m.Field(description="Replace custom files with generated content"),
        ] = False
        allow_direnv: Annotated[
            bool,
            m.Field(
                description=(
                    "Run `direnv allow` for the workspace after a successful "
                    "applied sync so managed roots never carry a stale allow"
                ),
            ),
        ] = True

    class WorkspaceEnvironmentSyncResult(FlextInfraConfigModelsContract.ConfigContract):
        """Outcome of one workspace environment sync."""

        changed_files: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Environment files created, updated, or removed"),
        ] = ()

        @m.computed_field
        @property
        def changed(self) -> bool:
            """Whether the sync altered any environment file."""
            return bool(self.changed_files)
