"""Transaction and session models for the codegen pipeline.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m, p

from flext_infra import t
from flext_infra._models._codegen.journal import FlextInfraModelsCodegenJournalModels
from flext_infra._models.codegen_toolchain import FlextInfraModelsCodegenToolchain
from flext_infra._models.rope import FlextInfraModelsRope


class FlextInfraModelsCodegenTransactionModels:
    """Transaction and session models for the codegen pipeline."""

    class CodegenPhasePublicationPolicy(m.ArbitraryTypesModel):
        """Caller-owned directories and final validation for one publication."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")
        directories: t.VariadicTuple[Path] = m.Field(
            description="Exact generated directories requested by the caller",
        )
        validator: Callable[[], p.Result[bool]] = m.Field(
            description="Caller validation required before committing the phase",
        )

    class StagePackagePlan(m.ArbitraryTypesModel):
        """Pinned package/dependency inputs and the declared public facade contract."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")
        package: str = m.Field(description="Selected canonical package namespace")
        module: str = m.Field(description="Selected public facade module")
        classname: str = m.Field(description="Published class preserved by projection")
        owner_module: str = m.Field(description="Canonical complete private owner")
        upstream: t.VariadicTuple[t.Pair[str, str]] = m.Field(
            description="Declared upstream base imports"
        )
        members: t.StrSequence = m.Field(
            description="Owner declarations inherited by the public facade"
        )
        layouts: t.VariadicTuple[FlextInfraModelsRope.RopeProjectLayout] = m.Field(
            description="Pinned package layouts"
        )
        inputs: t.VariadicTuple[m.Cli.AtomicFileState] = m.Field(
            description="Pinned source/resource/metadata states"
        )
        workspace_packages: t.StrSequence = m.Field(
            description="Workspace namespaces requiring sealed origins"
        )

    class StagePackageView(m.ArbitraryTypesModel):
        """Journal-owned materialized package view, never another source of truth."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")
        plan: FlextInfraModelsCodegenTransactionModels.StagePackagePlan = m.Field(
            description="Pinned input and public-feature contract"
        )
        root: Path = m.Field(
            description="Runtime artifact inside a registered transaction root"
        )
        layouts: t.VariadicTuple[FlextInfraModelsRope.RopeProjectLayout] = m.Field(
            description="Actual materialized package origins"
        )
        manifest: m.Cli.AtomicPhysicalTreeManifest = m.Field(
            description="Descriptor-authenticated candidate tree"
        )
        target: m.Cli.AtomicPhysicalTreeEntry = m.Field(
            description="Exact desired facade bytes and physical identity"
        )

    class CodegenTransactionJournal(m.ArbitraryTypesModel):
        """Persisted recovery contract for one workspace-wide generation."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        version: Annotated[
            Literal[8],
            m.Field(description="Exact journal schema version"),
        ]
        transaction_id: Annotated[
            str,
            m.Field(
                pattern=r"^[0-9a-f]{32}$",
                description="Unpredictable generation transaction identity",
            ),
        ]
        scope_device: Annotated[
            int,
            m.Field(ge=0, strict=True, description="Scope directory device"),
        ]
        scope_inode: Annotated[
            int,
            m.Field(gt=0, strict=True, description="Scope directory inode"),
        ]
        state: Annotated[
            Literal["staging", "prepared", "recovering", "committed"],
            m.Field(description="Durable publication transition state"),
        ]
        projects: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegenJournalModels.CodegenJournalProject],
            m.Field(description="Ordered project selectors owned by this transaction"),
        ]
        file_participants: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegenToolchain.CodegenFileParticipant],
            m.Field(description="Exact physical file publication capabilities"),
        ] = ()
        sources: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegenJournalModels.CodegenJournalSource],
            m.Field(description="Source identities used by staging"),
        ]
        directories: Annotated[
            t.VariadicTuple[
                FlextInfraModelsCodegenJournalModels.CodegenJournalDirectory
            ],
            m.Field(description="Directories whose prior absence authorizes creation"),
        ]
        entries: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegenJournalModels.CodegenJournalEntry],
            m.Field(description="Recoverable artifact transitions"),
        ]
        staging_intents: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegenJournalModels.CodegenStagingIntent],
            m.Field(description="Durable authority for staging bytes before creation"),
        ] = ()

        @m.model_validator(mode="after")
        def _validate_lifecycle(self) -> Self:
            """Bind staging and publication payloads to one safe project set.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If generation journal requires an explicit participant; or
                    if Mise root selector must be first when present; or if Mise journal
                    project selectors must be unique; or if staging codegen journal must
                    not authorize live transitions; or if staging codegen journal cannot
                    generate a transaction root; or if codegen journal destination paths
                    must be unique; or if codegen journal entry has no project
                    participant; or if codegen journal directory paths must be unique;
                    or if codegen journal directory has no project participant; or if
                    recovering codegen journal lacks rollback identities; or if
                    non-recovering codegen journal contains rollback identities.

            """
            participants: t.VariadicTuple[
                FlextInfraModelsCodegenJournalModels.CodegenJournalProject
                | FlextInfraModelsCodegenToolchain.CodegenFileParticipant
            ] = (*self.projects, *self.file_participants)
            selectors = tuple(project.selector for project in participants)
            if not selectors:
                msg = "generation journal requires an explicit participant"
                raise ValueError(msg)
            if selectors[0] != "." and "." in selectors:
                msg = "Mise root selector must be first when present"
                raise ValueError(msg)
            if len(set(selectors)) != len(selectors):
                msg = "Mise journal project selectors must be unique"
                raise ValueError(msg)
            self._validate_staging_authority()
            self._validate_participant_coverage(selectors)
            self._validate_recovery_state()
            staging_paths = tuple(intent.before.path for intent in self.staging_intents)
            if len(set(staging_paths)) != len(staging_paths):
                msg = "staging intention paths must have unique authority"
                raise ValueError(msg)
            return self

        def _validate_staging_authority(self) -> None:
            """Reject live transitions a staging journal may never authorize.

            Raises:
                ValueError: If staging codegen journal must not authorize live
                    transitions; or if staging codegen journal cannot generate a
                    transaction root.

            """
            if self.state == "staging" and self.entries:
                msg = "staging codegen journal must not authorize live transitions"
                raise ValueError(msg)
            if self.state == "staging" and any(
                directory.disposition == "generated"
                and directory.phase == "transaction"
                for directory in self.directories
            ):
                # A staging journal authorizes no live transition — that is the
                # `entries` rule above. It must still authorize the destination
                # directory of a file phase: staging snapshots the live target,
                # which requires a physical parent, so a generated destination
                # can never be recorded after the entries it makes possible.
                # Rollback removes them with the temporary roots
                # (`include_generated` for any non-committed journal). Only the
                # transaction's own roots stay restricted to `temporary`.
                msg = "staging codegen journal cannot generate a transaction root"
                raise ValueError(msg)

        def _validate_participant_coverage(self, selectors: t.StrSequence) -> None:
            """Require unique destination paths covered by declared participants.

            Raises:
                ValueError: If codegen journal destination paths must be unique; or
                    if codegen journal entry has no project participant; or if codegen
                    journal directory paths must be unique; or if codegen journal
                    directory has no project participant.

            """
            entry_paths = tuple(entry.path for entry in self.entries)
            if len(set(entry_paths)) != len(entry_paths):
                msg = "codegen journal destination paths must be unique"
                raise ValueError(msg)
            if any(entry.project not in selectors for entry in self.entries):
                msg = "codegen journal entry has no project participant"
                raise ValueError(msg)
            directory_paths = tuple(directory.path for directory in self.directories)
            if len(set(directory_paths)) != len(directory_paths):
                msg = "codegen journal directory paths must be unique"
                raise ValueError(msg)
            if any(
                directory.project not in selectors for directory in self.directories
            ):
                msg = "codegen journal directory has no project participant"
                raise ValueError(msg)

        def _validate_recovery_state(self) -> None:
            """Bind rollback identities to the journal's recovery state.

            Raises:
                ValueError: If recovering codegen journal lacks rollback identities; or
                    if non-recovering codegen journal contains rollback identities.

            """
            recovery_declared = tuple(
                entry.rollback_exists is not None for entry in self.entries
            )
            if self.state == "recovering" and not all(recovery_declared):
                msg = "recovering codegen journal lacks rollback identities"
                raise ValueError(msg)
            if self.state != "recovering" and any(recovery_declared):
                msg = "non-recovering codegen journal contains rollback identities"
                raise ValueError(msg)

    class CodegenFootprint(m.Value):
        """Effect-free observed journal and requested publication footprint."""

        scope_root: Path = m.Field(description="Authenticated coordination root")
        journal_path: Path = m.Field(description="Canonical journal anchor")
        snapshot_identity: str = m.Field(
            description="Normalized canonical file-state fields excluding raw content",
        )
        snapshot_sha256: str | None = m.Field(
            description="Digest of the exact observed journal bytes, or absent",
        )
        journal_version: int | None = m.Field(
            description="Schema version read from the typed journal, or absent",
        )
        transaction_id: str | None = m.Field(
            description="Transaction identity read from the typed journal, or absent",
        )
        normalized_journal_sha256: str | None = m.Field(
            description="Digest of the parsed journal representation, not disk bytes",
        )
        authorized_roots: t.VariadicTuple[Path] = m.Field(
            default=(),
            description="Physical roots authorized by current topology",
        )
        journal_state: Literal[
            "absent", "staging", "prepared", "recovering", "committed"
        ] = m.Field(
            description="Observed durable state, never a readiness or green receipt",
        )
        pending_roots: t.VariadicTuple[Path] = m.Field(
            description="Actual recorded participant roots",
        )
        pending_destinations: t.VariadicTuple[str] = m.Field(
            description="Journal-relative destination selectors",
        )
        pending_directories: t.VariadicTuple[str] = m.Field(
            description="Journal-relative directory selectors",
        )
        pending_staging: t.VariadicTuple[Path] = m.Field(
            description="Absolute recorded staging paths",
        )
        planned_roots: t.VariadicTuple[Path] = m.Field(
            default=(),
            description="Roots selected by the public conform plan",
        )
        planned_destinations: t.VariadicTuple[Path] = m.Field(
            default=(),
            description="Absolute requested publication paths",
        )
        journal: (
            FlextInfraModelsCodegenTransactionModels.CodegenTransactionJournal | None
        ) = m.Field(
            default=None,
            exclude=True,
            description="Typed observed recovery authority",
        )
        snapshot: m.Cli.AtomicFileState = m.Field(
            exclude=True,
            description="Exact journal observation retained for revalidation",
        )

    class CodegenFileSessionPlan(m.ArbitraryTypesModel):
        """File-only transaction topology; contains no Mise artifact snapshot."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        layout: Annotated[
            FlextInfraModelsCodegenToolchain.MiseToolchainWorkspaceLayout,
            m.Field(description="Locked explicit file participant topology"),
        ]

        @m.model_validator(mode="after")
        def _validate_file_only(self) -> Self:
            if self.layout.projects or not self.layout.file_participants:
                msg = "file-only session must contain only file capabilities"
                raise ValueError(msg)
            return self

    class CodegenTransactionSession(m.ArbitraryTypesModel):
        """Immutable cursor for one live prepared generation transaction."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        plan: Annotated[
            FlextInfraModelsCodegenToolchain.MiseToolchainWorkspacePlan
            | FlextInfraModelsCodegenTransactionModels.CodegenFileSessionPlan,
            m.Field(description="Locked generation plan and physical layout"),
        ]
        journal: Annotated[
            FlextInfraModelsCodegenTransactionModels.CodegenTransactionJournal,
            m.Field(description="Latest durable prepared journal payload"),
        ]
        journal_state: Annotated[
            m.Cli.AtomicFileState,
            m.Field(description="Exact journal CAS state for the next transition"),
        ]
        written_files: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Ordered destinations published by completed phases"),
        ] = ()

        @m.model_validator(mode="after")
        def _validate_cursor(self) -> Self:
            if self.journal.state != "prepared":
                msg = "active codegen transaction session must remain prepared"
                raise ValueError(msg)
            if self.plan.layout.transaction_id != self.journal.transaction_id:
                msg = "codegen session layout and journal transaction ids differ"
                raise ValueError(msg)
            return self
