"""Transaction and session models for the codegen pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m, u

from ... import t
from ..codegen_toolchain import FlextInfraModelsCodegenToolchain
from .journal import FlextInfraModelsCodegenJournalModels


class FlextInfraModelsCodegenTransactionModels:
    """Transaction and session models for the codegen pipeline."""

    class CodegenTransactionJournal(m.ArbitraryTypesModel):
        """Persisted recovery contract for one workspace-wide generation."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        version: Annotated[
            Literal[8], m.Field(description="Exact journal schema version")
        ]
        transaction_id: Annotated[
            str,
            m.Field(
                pattern=r"^[0-9a-f]{32}$",
                description="Unpredictable generation transaction identity",
            ),
        ]
        scope_device: Annotated[
            int, m.Field(ge=0, strict=True, description="Scope directory device")
        ]
        scope_inode: Annotated[
            int, m.Field(gt=0, strict=True, description="Scope directory inode")
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

        @u.model_validator(mode="after")
        def _validate_lifecycle(self) -> Self:
            """Bind staging and publication payloads to one safe project set."""
            selectors = tuple(
                project.selector
                for project in (*self.projects, *self.file_participants)
            )
            if not selectors:
                msg = "generation journal requires an explicit participant"
                raise ValueError(msg)
            if selectors[0] != "." and "." in selectors:
                msg = "Mise root selector must be first when present"
                raise ValueError(msg)
            if len(set(selectors)) != len(selectors):
                msg = "Mise journal project selectors must be unique"
                raise ValueError(msg)
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
            recovery_declared = tuple(
                entry.rollback_exists is not None for entry in self.entries
            )
            if self.state == "recovering" and not all(recovery_declared):
                msg = "recovering codegen journal lacks rollback identities"
                raise ValueError(msg)
            if self.state != "recovering" and any(recovery_declared):
                msg = "non-recovering codegen journal contains rollback identities"
                raise ValueError(msg)
            return self

    class CodegenFileSessionPlan(m.ArbitraryTypesModel):
        """File-only transaction topology; contains no Mise artifact snapshot."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        layout: Annotated[
            FlextInfraModelsCodegenToolchain.MiseToolchainWorkspaceLayout,
            m.Field(description="Locked explicit file participant topology"),
        ]

        @u.model_validator(mode="after")
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

        @u.model_validator(mode="after")
        def _validate_cursor(self) -> Self:
            if self.journal.state != "prepared":
                msg = "active codegen transaction session must remain prepared"
                raise ValueError(msg)
            if self.plan.layout.transaction_id != self.journal.transaction_id:
                msg = "codegen session layout and journal transaction ids differ"
                raise ValueError(msg)
            return self
