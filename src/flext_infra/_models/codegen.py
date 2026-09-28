"""Domain models for the codegen subpackage."""

from __future__ import annotations

import stat
from collections.abc import MutableSet
from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m, u

from flext_infra import c, p, t

from ._defaults import ImmutableEmptyMapping
from .codegen_render import FlextInfraModelsCodegenRender
from .config import FlextInfraConfigModels
from .mixins import FlextInfraModelsMixins as mm


class FlextInfraModelsCodegen(FlextInfraModelsCodegenRender):
    """Models for codegen census, scaffold, and auto-fix pipelines."""

    class MiseToolchainArtifactPaths(m.ArbitraryTypesModel):
        """Canonical live toolchain-bundle destinations for one project."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        config: Annotated[
            Path, m.Field(description="Generated Mise configuration destination")
        ]
        unix_launcher: Annotated[Path, m.Field(description="Unix launcher destination")]
        windows_launcher: Annotated[
            Path, m.Field(description="Windows launcher destination")
        ]

    class MiseToolchainProjectLayout(m.ArbitraryTypesModel):
        """Stable paths needed to validate and recover one project."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        selector: Annotated[
            t.NonEmptyStr, m.Field(description="Workspace-relative project selector")
        ]
        root: Annotated[Path, m.Field(description="Resolved project root")]
        transaction_root: Annotated[
            Path | None,
            m.Field(
                description="Persistent transaction root on this project filesystem"
            ),
        ] = None
        artifacts: Annotated[
            FlextInfraModelsCodegen.MiseToolchainArtifactPaths,
            m.Field(description="Canonical artifact destinations"),
        ]

    class MiseToolchainWorkspaceLayout(m.ArbitraryTypesModel):
        """Stable recovery topology independent of mutable source contents."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        scope_root: Annotated[Path, m.Field(description="Resolved transaction scope")]
        state_root: Annotated[
            Path, m.Field(description="Persistent scope transaction staging directory")
        ]
        journal_path: Annotated[
            Path,
            m.Field(
                description="Direct journal under the authenticated scope Git directory"
            ),
        ]
        transaction_id: Annotated[
            str | None,
            m.Field(
                pattern=r"^[0-9a-f]{32}$",
                description="Current unpredictable transaction identity, if mutating",
            ),
        ] = None
        projects: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegen.MiseToolchainProjectLayout],
            m.Field(min_length=1, description="Ordered complete workspace topology"),
        ]

    class MiseToolchainConfigState(m.ArbitraryTypesModel):
        """Current destination plus the exact planned Mise configuration."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        before: Annotated[
            m.Cli.AtomicFileState,
            m.Field(description="Exact preflight state of the live configuration"),
        ]
        replacement_content: Annotated[
            bytes,
            m.Field(
                min_length=1,
                strict=True,
                description="Exact rendered bytes to stage and publish",
            ),
        ]
        replacement_mode: Annotated[
            int,
            m.Field(
                ge=0,
                le=0o7777,
                strict=True,
                description="Exact permission mode to stage and publish",
            ),
        ]
        sources: Annotated[
            t.VariadicTuple[m.Cli.AtomicFileState],
            m.Field(description="Ordered YAML states that produced the replacement"),
        ] = ()

    class MiseToolchainProjectState(m.ArbitraryTypesModel):
        """Immutable source and destination snapshot for one project layout."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        layout: Annotated[
            FlextInfraModelsCodegen.MiseToolchainProjectLayout,
            m.Field(description="Stable project layout owning this snapshot"),
        ]
        config: Annotated[
            FlextInfraModelsCodegen.MiseToolchainConfigState,
            m.Field(description="Planned generated Mise configuration state"),
        ]
        artifacts: Annotated[
            FlextInfraModelsCodegen.MiseToolchainArtifactSet,
            m.Field(description="Named launcher states"),
        ]

        @u.model_validator(mode="after")
        def _validate_destination_paths(self) -> Self:
            """Bind every captured state to its declared live destination."""
            expected = (
                self.layout.artifacts.config,
                self.layout.artifacts.unix_launcher,
                self.layout.artifacts.windows_launcher,
            )
            observed = (
                self.config.before.path,
                self.artifacts.unix_launcher.path,
                self.artifacts.windows_launcher.path,
            )
            if observed != expected:
                msg = "Mise project states differ from declared destinations"
                raise ValueError(msg)
            return self

    class MiseToolchainArtifactSet(m.ArbitraryTypesModel):
        """Named file states that prevent artifact-order ambiguity."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        unix_launcher: Annotated[
            m.Cli.AtomicFileState, m.Field(description="Observed Unix launcher state")
        ]
        windows_launcher: Annotated[
            m.Cli.AtomicFileState,
            m.Field(description="Observed Windows launcher state"),
        ]

    class MiseToolchainWorkspacePlan(m.ArbitraryTypesModel):
        """One stable layout plus a coherent mutable-state snapshot."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        layout: Annotated[
            FlextInfraModelsCodegen.MiseToolchainWorkspaceLayout,
            m.Field(description="Stable workspace topology"),
        ]
        projects: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegen.MiseToolchainProjectState],
            m.Field(min_length=1, description="Ordered complete workspace topology"),
        ]

        @u.model_validator(mode="after")
        def _validate_project_layouts(self) -> Self:
            """Bind every mutable project snapshot to the exact stable layout."""
            if (
                tuple(project.layout for project in self.projects)
                != self.layout.projects
            ):
                msg = "Mise project snapshots differ from workspace layout"
                raise ValueError(msg)
            return self

    class CodegenStagedFile(m.ArbitraryTypesModel):
        """One destination state and its optional destination-local replacement."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        phase: Annotated[
            t.NonEmptyStr,
            m.Field(description="Generation phase that owns this publication"),
        ]
        project: Annotated[
            Path,
            m.Field(description="Absolute physical project owning the destination"),
        ]
        before: Annotated[
            m.Cli.AtomicFileState,
            m.Field(description="Exact destination state observed during preflight"),
        ]
        replacement: Annotated[
            m.Cli.AtomicFileState | None,
            m.Field(description="Exact staged state, or None for a planned deletion"),
        ] = None

        @u.model_validator(mode="after")
        def _validate_publication(self) -> Self:
            """Bind a complete staged state to one physical project destination."""
            if not self.project.is_absolute() or not self.before.path.is_relative_to(
                self.project
            ):
                msg = "codegen publication destination is outside its project"
                raise ValueError(msg)
            replacement = self.replacement
            if replacement is not None and (
                replacement.content is None or replacement.mode is None
            ):
                msg = "codegen staged replacement must be present"
                raise ValueError(msg)
            return self

    class CodegenJournalProject(m.ArbitraryTypesModel):
        """One journal participant bound to its physical directory identity."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        selector: Annotated[
            t.NonEmptyStr, m.Field(description="Workspace-relative project selector")
        ]
        device: Annotated[
            int, m.Field(ge=0, strict=True, description="Project directory device")
        ]
        inode: Annotated[
            int, m.Field(gt=0, strict=True, description="Project directory inode")
        ]

        @u.field_validator("selector")
        @classmethod
        def _validate_selector(cls, value: str) -> str:
            relative = Path(value)
            if (
                relative.is_absolute()
                or relative.as_posix() != value
                or ".." in relative.parts
            ):
                msg = f"unsafe codegen project selector: {value}"
                raise ValueError(msg)
            return value

    class CodegenJournalDirectory(m.ArbitraryTypesModel):
        """One journal-authorized directory creation and its physical identity."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        phase: Annotated[
            t.NonEmptyStr,
            m.Field(description="Generation phase that owns the directory"),
        ]
        project: Annotated[
            t.NonEmptyStr,
            m.Field(description="Journal project selector owning the directory"),
        ]
        path: Annotated[
            t.NonEmptyStr,
            m.Field(description="Workspace-relative directory proven absent"),
        ]
        disposition: Annotated[
            Literal["temporary", "generated"],
            m.Field(description="Commit-time retention policy for the directory"),
        ]
        before: Annotated[
            m.Cli.AtomicDirectoryState | None,
            m.Field(description="Exact absent leaf and existing-parent binding"),
        ] = None
        created: Annotated[
            m.Cli.AtomicDirectoryState | None,
            m.Field(description="Exact physical identity returned by guarded creation"),
        ] = None
        manifest: Annotated[
            m.Cli.AtomicPhysicalTreeManifest | None,
            m.Field(description="Last durable authorized temporary-tree manifest"),
        ] = None

        @u.field_validator("path")
        @classmethod
        def _validate_path(cls, value: str) -> str:
            """Keep the durable authority lexical and inside the workspace."""
            relative = Path(value)
            if (
                relative.is_absolute()
                or relative.as_posix() != value
                or value in {"", "."}
                or ".." in relative.parts
            ):
                msg = f"unsafe codegen journal directory: {value}"
                raise ValueError(msg)
            return value

        @u.model_validator(mode="after")
        def _validate_disposition(self) -> Self:
            """Bind lifecycle metadata to one physical leaf path."""
            if (self.phase == "transaction") != (self.disposition == "temporary"):
                msg = "transaction phase and temporary disposition must coincide"
                raise ValueError(msg)
            if self.before is not None and self.before.exists:
                msg = "codegen directory preflight state must be absent"
                raise ValueError(msg)
            if self.created is not None and not self.created.exists:
                msg = "codegen directory created state must be present"
                raise ValueError(msg)
            if (
                self.before is not None
                and self.created is not None
                and self.before.path != self.created.path
            ):
                msg = "codegen directory states belong to different paths"
                raise ValueError(msg)
            if self.manifest is not None:
                created = self.created
                root = self.manifest.root
                if created is None or self.disposition != "temporary":
                    msg = "only a created temporary directory may own a tree manifest"
                    raise ValueError(msg)
                manifest_identity = (
                    root.path,
                    root.parent_device,
                    root.parent_inode,
                    root.mode,
                    root.device,
                    root.inode,
                    root.file_attributes,
                    root.reparse_tag,
                )
                created_identity = (
                    created.path,
                    created.parent_device,
                    created.parent_inode,
                    created.mode,
                    created.device,
                    created.inode,
                    created.file_attributes,
                    created.reparse_tag,
                )
                if manifest_identity != created_identity:
                    msg = "temporary-tree manifest differs from created directory"
                    raise ValueError(msg)
            return self

    class CodegenJournalSource(m.ArbitraryTypesModel):
        """One immutable full source identity guarded by a generation journal."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        phase: Annotated[
            t.NonEmptyStr, m.Field(description="Generation phase that consumed source")
        ]
        path: Annotated[Path, m.Field(description="Absolute authenticated source path")]
        parent_device: Annotated[
            int, m.Field(ge=0, strict=True, description="Source parent device")
        ]
        parent_inode: Annotated[
            int, m.Field(gt=0, strict=True, description="Source parent inode")
        ]
        sha256: Annotated[
            str,
            m.Field(
                pattern=r"^[0-9a-f]{64}$",
                description="Exact source-byte SHA-256 identity",
            ),
        ]
        mode: Annotated[
            int,
            m.Field(
                ge=0, le=0o7777, strict=True, description="Exact source permission bits"
            ),
        ]
        device: Annotated[
            int, m.Field(ge=0, strict=True, description="Source device identity")
        ]
        inode: Annotated[
            int, m.Field(gt=0, strict=True, description="Source inode identity")
        ]
        link_count: Annotated[
            Literal[1], m.Field(description="Unique physical source link count")
        ]
        file_attributes: Annotated[
            int | None, m.Field(ge=0, strict=True, description="Host file attributes")
        ] = None
        reparse_tag: Annotated[
            int | None, m.Field(ge=0, strict=True, description="Host reparse tag")
        ] = None

        @u.field_validator("path")
        @classmethod
        def _validate_source_path(cls, value: Path) -> Path:
            """Reject relative or lexically escaping source identities."""
            if not value.is_absolute() or ".." in value.parts:
                msg = f"unsafe generation source path: {value}"
                raise ValueError(msg)
            return value

        @u.model_validator(mode="after")
        def _validate_source_physical_state(self) -> Self:
            """Reject a persisted source identity that represents a reparse point."""
            marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            if self.reparse_tag not in {None, 0} or (
                self.file_attributes is not None and bool(self.file_attributes & marker)
            ):
                msg = f"generation source is a reparse point: {self.path}"
                raise ValueError(msg)
            return self

    class CodegenJournalEntry(m.ArbitraryTypesModel):
        """Recoverable full before/after identity for one generated file."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        phase: Annotated[
            t.NonEmptyStr, m.Field(description="Generation phase owning this entry")
        ]
        project: Annotated[
            t.NonEmptyStr,
            m.Field(description="Journal project selector owning this entry"),
        ]
        path: Annotated[
            t.NonEmptyStr,
            m.Field(description="Workspace-relative live file destination"),
        ]
        desired_staging: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Workspace-relative staged replacement path"),
        ] = None
        original_exists: Annotated[
            bool,
            m.Field(
                strict=True, description="Whether the destination existed at preflight"
            ),
        ]
        original_parent_device: Annotated[
            int, m.Field(ge=0, strict=True, description="Original parent device")
        ]
        original_parent_inode: Annotated[
            int, m.Field(gt=0, strict=True, description="Original parent inode")
        ]
        original_backup: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Workspace-relative original-byte backup"),
        ] = None
        original_sha256: Annotated[
            str | None,
            m.Field(
                pattern=r"^[0-9a-f]{64}$",
                description="Exact original-byte SHA-256 identity when present",
            ),
        ] = None
        original_mode: Annotated[
            int | None,
            m.Field(
                ge=0,
                le=0o7777,
                strict=True,
                description="Exact original permission bits when present",
            ),
        ] = None
        original_device: Annotated[
            int | None,
            m.Field(ge=0, strict=True, description="Original device identity"),
        ] = None
        original_inode: Annotated[
            int | None,
            m.Field(gt=0, strict=True, description="Original inode identity"),
        ] = None
        original_link_count: Annotated[
            Literal[1] | None,
            m.Field(description="Original unique physical link count"),
        ] = None
        original_file_attributes: Annotated[
            int | None,
            m.Field(ge=0, strict=True, description="Original host attributes"),
        ] = None
        original_reparse_tag: Annotated[
            int | None, m.Field(ge=0, strict=True, description="Original reparse tag")
        ] = None
        desired_exists: Annotated[
            bool, m.Field(strict=True, description="Whether publication leaves a file")
        ]
        desired_parent_device: Annotated[
            int, m.Field(ge=0, strict=True, description="Desired live parent device")
        ]
        desired_parent_inode: Annotated[
            int, m.Field(gt=0, strict=True, description="Desired live parent inode")
        ]
        desired_sha256: Annotated[
            str | None,
            m.Field(
                pattern=r"^[0-9a-f]{64}$",
                description="Exact desired-byte SHA-256 identity",
            ),
        ] = None
        desired_mode: Annotated[
            int | None,
            m.Field(
                ge=0, le=0o7777, strict=True, description="Desired permission bits"
            ),
        ] = None
        desired_device: Annotated[
            int | None,
            m.Field(ge=0, strict=True, description="Staged replacement device"),
        ] = None
        desired_inode: Annotated[
            int | None,
            m.Field(gt=0, strict=True, description="Staged replacement inode"),
        ] = None
        desired_link_count: Annotated[
            Literal[1] | None,
            m.Field(description="Staged replacement unique link count"),
        ] = None
        desired_file_attributes: Annotated[
            int | None, m.Field(ge=0, strict=True, description="Staged host attributes")
        ] = None
        desired_reparse_tag: Annotated[
            int | None, m.Field(ge=0, strict=True, description="Staged reparse tag")
        ] = None
        rollback_exists: Annotated[
            bool | None,
            m.Field(
                strict=True,
                description="Recovery target presence once rollback is durable",
            ),
        ] = None
        rollback_parent_device: Annotated[
            int | None,
            m.Field(ge=0, strict=True, description="Rollback live parent device"),
        ] = None
        rollback_parent_inode: Annotated[
            int | None,
            m.Field(gt=0, strict=True, description="Rollback live parent inode"),
        ] = None
        rollback_sha256: Annotated[
            str | None,
            m.Field(pattern=r"^[0-9a-f]{64}$", description="Rollback bytes identity"),
        ] = None
        rollback_mode: Annotated[
            int | None,
            m.Field(ge=0, le=0o7777, strict=True, description="Rollback mode"),
        ] = None
        rollback_device: Annotated[
            int | None, m.Field(ge=0, strict=True, description="Rollback staged device")
        ] = None
        rollback_inode: Annotated[
            int | None, m.Field(gt=0, strict=True, description="Rollback staged inode")
        ] = None
        rollback_link_count: Annotated[
            Literal[1] | None, m.Field(description="Rollback staged unique link count")
        ] = None
        rollback_file_attributes: Annotated[
            int | None,
            m.Field(ge=0, strict=True, description="Rollback host attributes"),
        ] = None
        rollback_reparse_tag: Annotated[
            int | None, m.Field(ge=0, strict=True, description="Rollback reparse tag")
        ] = None
        rollback_staging: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Workspace-relative durable rollback candidate path"),
        ] = None

        @u.field_validator(
            "path", "original_backup", "desired_staging", "rollback_staging"
        )
        @classmethod
        def _validate_relative_file_path(cls, value: str | None) -> str | None:
            if value is None:
                return None
            relative = Path(value)
            if (
                relative.is_absolute()
                or relative.as_posix() != value
                or value in {"", "."}
                or ".." in relative.parts
            ):
                msg = f"unsafe codegen journal file path: {value}"
                raise ValueError(msg)
            return value

        @u.model_validator(mode="after")
        def _validate_original_tuple(self) -> Self:
            """Require complete recovery identity exactly when original existed."""
            original = (
                self.original_backup,
                self.original_sha256,
                self.original_mode,
                self.original_device,
                self.original_inode,
                self.original_link_count,
            )
            populated = tuple(value is not None for value in original)
            if (self.original_exists and not all(populated)) or (
                not self.original_exists and any(populated)
            ):
                msg = "Mise journal original recovery tuple is inconsistent"
                raise ValueError(msg)
            if not self.original_exists and (
                self.original_file_attributes is not None
                or self.original_reparse_tag is not None
            ):
                msg = "absent codegen original cannot contain host metadata"
                raise ValueError(msg)
            desired = (
                self.desired_sha256,
                self.desired_mode,
                self.desired_device,
                self.desired_inode,
                self.desired_link_count,
            )
            desired_populated = tuple(value is not None for value in desired)
            if (self.desired_exists and not all(desired_populated)) or (
                not self.desired_exists and any(desired_populated)
            ):
                msg = "codegen journal desired identity is inconsistent"
                raise ValueError(msg)
            if self.desired_exists != (self.desired_staging is not None):
                msg = "codegen journal desired staging path is inconsistent"
                raise ValueError(msg)
            if not self.desired_exists and (
                self.desired_file_attributes is not None
                or self.desired_reparse_tag is not None
            ):
                msg = "absent codegen desired state cannot contain host metadata"
                raise ValueError(msg)
            rollback = (
                self.rollback_sha256,
                self.rollback_mode,
                self.rollback_device,
                self.rollback_inode,
                self.rollback_link_count,
            )
            rollback_populated = tuple(value is not None for value in rollback)
            rollback_parent = (self.rollback_parent_device, self.rollback_parent_inode)
            parent_populated = tuple(value is not None for value in rollback_parent)
            if self.rollback_exists is None and (
                any(rollback_populated) or any(parent_populated)
            ):
                msg = "codegen journal rollback identity has no presence state"
                raise ValueError(msg)
            if self.rollback_exists is not None and not all(parent_populated):
                msg = "codegen journal rollback parent identity is incomplete"
                raise ValueError(msg)
            if self.rollback_exists is True and not all(rollback_populated):
                msg = "codegen journal rollback identity is incomplete"
                raise ValueError(msg)
            if (self.rollback_exists is True) != (self.rollback_staging is not None):
                msg = "codegen journal rollback staging path is inconsistent"
                raise ValueError(msg)
            if self.rollback_exists is False and any(rollback_populated):
                msg = "absent codegen rollback cannot contain file identity"
                raise ValueError(msg)
            if self.rollback_exists is False and (
                self.rollback_file_attributes is not None
                or self.rollback_reparse_tag is not None
            ):
                msg = "absent codegen rollback cannot contain host metadata"
                raise ValueError(msg)
            marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            physical = (
                (self.original_file_attributes, self.original_reparse_tag),
                (self.desired_file_attributes, self.desired_reparse_tag),
                (self.rollback_file_attributes, self.rollback_reparse_tag),
            )
            if any(
                reparse not in {None, 0}
                or (attributes is not None and bool(attributes & marker))
                for attributes, reparse in physical
            ):
                msg = f"codegen journal contains a reparse identity: {self.path}"
                raise ValueError(msg)
            return self

    class CodegenRecoveryAction(m.ArbitraryTypesModel):
        """One preclassified recovery decision with no live effect applied."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        entry: Annotated[
            FlextInfraModelsCodegen.CodegenJournalEntry,
            m.Field(description="Journal entry owning the recovery decision"),
        ]
        current: Annotated[
            m.Cli.AtomicFileState,
            m.Field(description="Exact live target state used for classification"),
        ]
        operation: Annotated[
            Literal["noop", "delete", "restore"],
            m.Field(description="Only authorized recovery effect for the target"),
        ]

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
            t.VariadicTuple[FlextInfraModelsCodegen.CodegenJournalProject],
            m.Field(
                min_length=1,
                description="Ordered project selectors owned by this transaction",
            ),
        ]
        sources: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegen.CodegenJournalSource],
            m.Field(description="Source identities used by staging"),
        ]
        directories: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegen.CodegenJournalDirectory],
            m.Field(description="Directories whose prior absence authorizes creation"),
        ]
        entries: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegen.CodegenJournalEntry],
            m.Field(description="Recoverable artifact transitions"),
        ]

        @u.model_validator(mode="after")
        def _validate_lifecycle(self) -> Self:
            """Bind staging and publication payloads to one safe project set."""
            selectors = tuple(project.selector for project in self.projects)
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

    class CodegenTransactionSession(m.ArbitraryTypesModel):
        """Immutable cursor for one live prepared generation transaction."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        plan: Annotated[
            FlextInfraModelsCodegen.MiseToolchainWorkspacePlan,
            m.Field(description="Locked Mise adapter plan and physical layout"),
        ]
        journal: Annotated[
            FlextInfraModelsCodegen.CodegenTransactionJournal,
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

    class CodegenPhaseAnalysis(m.ArbitraryTypesModel):
        """Immutable planner receipt reused for publication verification."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        phase: Annotated[
            Literal["docs", "lazy-init"],
            m.Field(description="Generation phase that produced this receipt"),
        ]
        files: Annotated[
            t.VariadicTuple[FlextInfraConfigModels.CodegenFilePlan],
            m.Field(description="Ordered desired publication states"),
        ]
        inputs: Annotated[
            t.VariadicTuple[m.Cli.AtomicFileState],
            m.Field(description="Ordered complete authenticated planner inputs"),
        ]

        @u.model_validator(mode="after")
        def _validate_unique_paths(self) -> Self:
            """Reject ambiguous receipts with competing path authorities."""
            file_paths = tuple(file.path for file in self.files)
            if len(set(file_paths)) != len(file_paths):
                msg = "codegen phase receipt destination paths must be unique"
                raise ValueError(msg)
            input_paths = tuple(state.path for state in self.inputs)
            if len(set(input_paths)) != len(input_paths):
                msg = "codegen phase receipt input paths must be unique"
                raise ValueError(msg)
            return self

    class CensusViolation(mm.RequiredNonNegativeLineMixin, m.ArbitraryTypesModel):
        """A single namespace violation detected by the census service."""

        module: t.NonEmptyStr = m.Field(description="Module file path")
        rule: t.NonEmptyStr = m.Field(
            description="Violated rule identifier (e.g. NS-001)"
        )
        message: t.NonEmptyStr = m.Field(description="Human-readable violation message")
        fixable: bool = m.Field(description="Whether this violation can be auto-fixed")

    class CensusReport(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Aggregated census report for a single project."""

        @staticmethod
        def _violations_default() -> list[FlextInfraModelsCodegen.CensusViolation]:
            """Violations default."""
            return []

        violations: Annotated[
            list[FlextInfraModelsCodegen.CensusViolation],
            m.Field(
                default_factory=_violations_default, description="Detected violations"
            ),
        ]
        total: Annotated[t.NonNegativeInt, m.Field(description="Total violation count")]
        fixable: Annotated[
            t.NonNegativeInt, m.Field(description="Count of auto-fixable violations")
        ]

    class ScaffoldResult(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Result of scaffolding base modules for a project.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        files_created: t.StrSequence = m.Field(
            default_factory=tuple, description="Newly created file paths"
        )
        files_skipped: t.StrSequence = m.Field(
            default_factory=tuple, description="Skipped (already existing) file paths"
        )

    class ScaffoldDirRequest(m.ArbitraryTypesModel):
        """Directory-level scaffold request and accumulation state."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            arbitrary_types_allowed=True, revalidate_instances="never"
        )

        target_dir: Annotated[Path, m.Field(description="Directory to scaffold")]
        prefix: Annotated[str, m.Field(description="Generated class name prefix")]
        modules: Annotated[
            t.VariadicTuple[t.Quad[str, str, str, str]],
            m.Field(description="Module skeleton definitions"),
        ]
        test_prefix: Annotated[str, m.Field(description="Generated test class prefix")]
        base_module: Annotated[
            t.NonEmptyStr,
            m.Field(description="Explicit module owning every generated base class"),
        ]
        dry_run: Annotated[
            bool, m.Field(description="Whether to report creations without writing")
        ]
        files_created: Annotated[
            t.MutableSequenceOf[str], m.Field(description="Created file accumulator")
        ]
        files_skipped: Annotated[
            t.MutableSequenceOf[str], m.Field(description="Skipped file accumulator")
        ]

    class AutoFixResult(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Result of auto-fixing namespace violations for a project."""

        @staticmethod
        def _violations_default() -> list[FlextInfraModelsCodegen.CensusViolation]:
            """Violations default."""
            return []

        violations_fixed: Annotated[
            list[FlextInfraModelsCodegen.CensusViolation],
            m.Field(
                default_factory=_violations_default, description="Fixed violations"
            ),
        ]
        violations_skipped: Annotated[
            list[FlextInfraModelsCodegen.CensusViolation],
            m.Field(
                default_factory=_violations_default,
                description="Skipped violations (not auto-fixable)",
            ),
        ]
        files_modified: t.StrSequence = m.Field(
            default_factory=tuple, description="Modified file paths"
        )

    class ConsolidatorFileResult(m.ContractModel):
        """Per-file result emitted by the constants consolidator."""

        file: Annotated[
            t.NonEmptyStr, m.Field(description="Workspace-relative file path")
        ]
        status: Annotated[
            Literal["applied", "reverted"],
            m.Field(description="File processing status"),
        ]
        changes: Annotated[
            t.StrSequence,
            m.Field(default_factory=tuple, description="Applied replacements"),
        ]

    class ConsolidatorReport(m.ContractModel):
        """JSON report emitted by the constants consolidator."""

        total_found: Annotated[
            t.NonNegativeInt, m.Field(description="Total replacements found")
        ] = 0
        total_applied: Annotated[
            t.NonNegativeInt, m.Field(description="Total replacements applied")
        ] = 0
        total_failed: Annotated[
            t.NonNegativeInt, m.Field(description="Total files reverted")
        ] = 0
        files: Annotated[
            t.SequenceOf[FlextInfraModelsCodegen.ConsolidatorFileResult],
            m.Field(default_factory=tuple, description="Per-file processing results"),
        ]

    class NamespaceModulePolicy(m.ArbitraryTypesModel):
        """Derived gen-init policy for one governed module."""

        enforce_contract: Annotated[
            bool, m.Field(description="Whether gen-init must enforce namespace shape.")
        ] = False
        export_symbols: Annotated[
            bool,
            m.Field(description="Whether gen-init should discover public symbols."),
        ] = False
        include_in_lazy_init: Annotated[
            bool,
            m.Field(description="Whether lazy-init should index this module at all."),
        ] = True
        project_prefix: Annotated[
            str, m.Field(description="Canonical class prefix expected for the module.")
        ] = ""
        expected_alias: Annotated[
            str | None,
            m.Field(description="Canonical module-level alias allowed for the file."),
        ] = None
        expected_family: Annotated[
            str | None,
            m.Field(description="Canonical namespace family suffix for the file."),
        ] = None
        family_tokens: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Accepted family markers for private namespace modules.",
        )
        accepted_suffixes: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Accepted class suffixes for governed facade classes.",
        )
        allow_main_export: Annotated[
            bool,
            m.Field(description="Whether the file may export a module-level main()."),
        ] = False
        allow_type_alias: Annotated[
            bool,
            m.Field(description="Whether the module may keep TypeAlias declarations."),
        ] = False
        is_fixture_module: Annotated[
            bool,
            m.Field(
                description="Whether the module belongs to a private fixtures package."
            ),
        ] = False
        type_checking_imports: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Canonical root names allowed inside TYPE_CHECKING imports.",
        )

    class LazyInitPackageContext(m.ArbitraryTypesModel):
        """Declarative package context for one lazy-init directory."""

        pkg_dir: Path = m.Field(description="Directory being processed.")
        init_path: Path = m.Field(description="Target __init__.py path.")
        current_pkg: str = m.Field(description="Importable package name.")
        surface: str = m.Field(description="Root surface for wrapper alias resolution.")
        generated_init: Annotated[
            bool,
            m.Field(
                description="Whether the current __init__.py is generated by lazy-init."
            ),
        ] = False
        importable: Annotated[
            bool,
            m.Field(
                description="Whether the directory resolves to an importable package."
            ),
        ] = False

    class LazyInitPlan(m.ArbitraryTypesModel):
        """Fully resolved lazy-init action and render payload.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        context: FlextInfraModelsCodegen.LazyInitPackageContext = m.Field(
            description="Discovered package context."
        )
        action: Annotated[
            c.Infra.LazyInitAction,
            m.Field(description="Action selected for this package."),
        ] = c.Infra.LazyInitAction.SKIP
        exports: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Public exports for generated __init__.py.",
        )
        lazy_map: t.LazyAliasMap = m.Field(
            default_factory=ImmutableEmptyMapping,
            description="Lazy import map: export name to module/attribute target.",
        )
        type_checking_map: t.LazyAliasMap = m.Field(
            default_factory=ImmutableEmptyMapping,
            description=(
                "Type-checking import map used to publish static package attributes "
                "without widening the runtime/public lazy export surface."
            ),
        )
        eager_dunders: t.LazyAliasMap = m.Field(
            default_factory=ImmutableEmptyMapping,
            description=(
                "Dunder exports that must be eagerly imported at __init__.py "
                "load time. Required for the ``__version__.py`` submodule case "
                "where the submodule name collides with the dunder string it "
                "exports — eager binding pins the canonical string in the "
                "package dict before any submodule re-import can shadow it."
            ),
        )
        inline_constants: t.StrMapping = m.Field(
            default_factory=ImmutableEmptyMapping,
            description="Inline constants emitted directly into __init__.py.",
        )
        wildcard_runtime_modules: t.StrSequence = m.Field(
            default_factory=tuple, description="Runtime wildcard import modules."
        )
        child_packages_for_lazy: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Direct child package imports merged at runtime.",
        )
        excluded_lazy_names: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Names excluded from runtime child lazy import merges.",
        )

    class QualityGateCheck(m.ArbitraryTypesModel):
        """A single quality gate check result entry."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Check identifier")]
        passed: Annotated[bool, m.Field(description="Whether check passed")]
        detail: Annotated[str, m.Field(description="Human-readable check detail")] = ""
        critical: Annotated[bool, m.Field(description="Whether failure is critical")]

    class QualityGateProjectFinding(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Per-project quality gate findings."""

        violations_total: Annotated[
            t.NonNegativeInt, m.Field(description="Total violations")
        ]
        fixable_violations: Annotated[
            t.NonNegativeInt, m.Field(description="Auto-fixable violations")
        ]
        validator_passed: Annotated[
            bool, m.Field(description="Whether validator passed")
        ]
        flext_failures: Annotated[
            t.NonNegativeInt, m.Field(description="FLEXT failure count")
        ]
        layer_violations: Annotated[
            t.NonNegativeInt, m.Field(description="Layer violation count")
        ]
        cross_project_reference_violations: Annotated[
            t.NonNegativeInt,
            m.Field(description="Cross-project reference violation count"),
        ]

    class BulkFixItem(
        mm.AbsoluteFilePathTextMixin, mm.PositiveLineMixin, m.ArbitraryTypesModel
    ):
        """Shared line-addressable item used by bulk codegen fixes."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Item identifier")]

    class ConstantDefinition(mm.ProjectNameMixin, mm.NestedClassPathMixin, BulkFixItem):
        """A single constant extracted from a constants.py file."""

        value_repr: Annotated[
            str, m.Field(description="Source repr (e.g., '30', '\"localhost\"')")
        ]
        type_annotation: Annotated[
            str, m.Field(description="Type annotation string")
        ] = ""

    class DuplicateConstantGroup(m.ArbitraryTypesModel):
        """Cross-project duplicate group with consolidation metadata."""

        constant_name: t.NonEmptyStr = m.Field(description="Constant identifier")
        definitions: list[FlextInfraModelsCodegen.ConstantDefinition] = m.Field(
            description="Definitions across projects"
        )
        is_value_identical: bool = m.Field(description="Whether all values match")
        canonical_ref: Annotated[
            str, m.Field(description="Canonical parent reference")
        ] = ""

    class DirectConstantRef(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Direct FlextXConstants.Y.Z reference that should use c.* alias."""

        full_ref: Annotated[
            t.NonEmptyStr,
            m.Field(description="e.g., FlextAuthConstants.Auth.DEFAULT_TIMEOUT"),
        ]
        alias_ref: Annotated[
            t.NonEmptyStr, m.Field(description="e.g., c.Auth.DEFAULT_TIMEOUT")
        ]
        file_path: Annotated[
            t.NonEmptyStr, m.Field(description="File containing the reference")
        ]
        line: Annotated[t.PositiveInt, m.Field(description="Line number")]

    class FixContext(m.ArbitraryTypesModel):
        """Mutable accumulation context for fix operations.

        Enforcement exemption: MutableSequence/MutableSet accumulators are
        appended/added to as fixes proceed; fresh per-instance — no shared
        state.
        """

        @staticmethod
        def _violations_default() -> list[FlextInfraModelsCodegen.CensusViolation]:
            """Violations default."""
            return []

        violations_fixed: Annotated[
            t.MutableSequenceOf[FlextInfraModelsCodegen.CensusViolation],
            m.Field(
                default_factory=_violations_default,
                description="List of violations that were fixed",
            ),
        ] = m.Field(
            default_factory=_violations_default,
            description="List of violations that were fixed",
        )
        violations_skipped: Annotated[
            t.MutableSequenceOf[FlextInfraModelsCodegen.CensusViolation],
            m.Field(
                default_factory=_violations_default,
                description="List of violations that were skipped",
            ),
        ] = m.Field(
            default_factory=_violations_default,
            description="List of violations that were skipped",
        )
        files_modified: Annotated[
            MutableSet[str],
            m.Field(
                default_factory=set, description="Set of unique modified file paths"
            ),
        ] = m.Field(
            default_factory=set, description="Set of unique modified file paths"
        )

        @property
        def has_changes(self) -> bool:
            """Whether at least one file was modified."""
            return bool(self.files_modified)

        def skip(self, *, module: str, rule: str, line: int, message: str) -> None:
            """Skip."""
            self.violations_skipped.append(
                FlextInfraModelsCodegen.CensusViolation(
                    module=module, rule=rule, line=line, message=message, fixable=False
                )
            )

        def fix(self, *, module: str, rule: str, line: int, message: str) -> None:
            """Fix."""
            self.violations_fixed.append(
                FlextInfraModelsCodegen.CensusViolation(
                    module=module, rule=rule, line=line, message=message, fixable=True
                )
            )

    class ViolationKey(m.ContractModel):
        """Content-stable violation identifier — resilient to line shifts."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        module: Annotated[str, m.Field(description="Module containing the violation")]
        rule: Annotated[str, m.Field(description="Rule that was violated")]
        content_hash: Annotated[
            str, m.Field(description="SHA256 of surrounding context lines")
        ]

        def __hash__(self) -> int:
            """Hash by stable business identity so keys work in sets and frozensets."""
            return hash((self.module, self.rule, self.content_hash))

        @staticmethod
        def from_violation(
            violation: FlextInfraModelsCodegen.CensusViolation,
            source_lines: t.StrSequence,
        ) -> FlextInfraModelsCodegen.ViolationKey:
            """Build key from violation and source context (+-2 lines)."""
            ctx_start = max(0, violation.line - 2)
            ctx_end = min(len(source_lines), violation.line + 3)
            context = "\n".join(source_lines[ctx_start:ctx_end])
            content_hash = u.Cli.sha256_content(context)
            return FlextInfraModelsCodegen.ViolationKey(
                module=violation.module, rule=violation.rule, content_hash=content_hash
            )

    class CodegenPipelineState(m.ArbitraryTypesModel):
        """Typed inter-stage state for the codegen pipeline — Pydantic v2 model."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", arbitrary_types_allowed=True
        )

        discovered_projects: Annotated[
            t.SequenceOf[p.Infra.ProjectInfo],
            m.Field(description="Projects discovered at pipeline start"),
        ] = ()
        census_service: Annotated[
            p.Infra.CodegenCensusService | None,
            m.Field(description="Cached census service for reuse across stages"),
        ] = None
        reports_before: Annotated[
            t.SequenceOf[FlextInfraModelsCodegen.CensusReport],
            m.Field(description="Census reports collected before fixes"),
        ] = ()
        reports_after: Annotated[
            t.SequenceOf[FlextInfraModelsCodegen.CensusReport],
            m.Field(description="Census reports collected after fixes"),
        ] = ()
        scaffold_results: Annotated[
            t.SequenceOf[FlextInfraModelsCodegen.ScaffoldResult],
            m.Field(description="Scaffolding stage results"),
        ] = ()
        fix_results: Annotated[
            t.SequenceOf[FlextInfraModelsCodegen.AutoFixResult],
            m.Field(description="Auto-fix stage results"),
        ] = ()


__all__: list[str] = ["FlextInfraModelsCodegen"]
