"""Toolchain layout and observed-state contracts for code generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Self

from flext_cli import m

from flext_infra import t


class FlextInfraModelsCodegenToolchain:
    """Describe toolchain destinations and their coherent state snapshots."""

    class CodegenParticipantPolicy(m.Value):
        """Caller-authorized physical roots, independent of recorded capabilities."""

        scope_root: Path = m.Field(description="Physical coordination root")
        roots: t.VariadicTuple[m.Cli.AtomicDirectoryChainPlan] = m.Field(
            min_length=1,
            description="Existing root identities authorized by the request topology",
        )

        @m.model_validator(mode="after")
        def _validate_roots(self) -> Self:
            """Require unique existing physical anchors including the scope.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If generation authorization requires unique existing
                    physical roots.
            """
            paths = tuple(root.target for root in self.roots)
            if (
                len(set(paths)) != len(paths)
                or self.scope_root not in paths
                or any(
                    root.directories or root.target != root.anchor_path
                    for root in self.roots
                )
            ):
                msg = "generation authorization requires unique existing physical roots"
                raise ValueError(msg)
            return self

    class MiseToolchainProjectLayout(m.ArbitraryTypesModel):
        """Stable paths needed to validate and recover one project."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        selector: Annotated[
            t.NonEmptyStr,
            m.Field(description="Workspace-relative project selector"),
        ]
        root: Annotated[Path, m.Field(description="Resolved project root")]
        transaction_root: Annotated[
            Path | None,
            m.Field(
                description="Persistent transaction root on this project filesystem",
            ),
        ] = None
        config: Annotated[
            Path,
            m.Field(description="Generated Mise configuration destination"),
        ]

    class CodegenFileParticipant(m.ArbitraryTypesModel):
        """Explicit physical publication capability without Git or Mise ownership."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        selector: Annotated[
            str,
            m.Field(
                pattern=r"^@[a-z][a-z0-9-]*$",
                description="File capability identity",
            ),
        ]
        root: Annotated[Path, m.Field(description="Exact authorized destination root")]
        device: Annotated[
            int,
            m.Field(ge=0, strict=True, description="Authenticated root device"),
        ]
        inode: Annotated[
            int,
            m.Field(gt=0, strict=True, description="Authenticated root inode"),
        ]
        transaction_root: Annotated[
            Path,
            m.Field(description="Destination-local staging for this transaction"),
        ]

        @m.model_validator(mode="after")
        def _validate_capability(self) -> Self:
            if (
                not self.root.is_absolute()
                or ".." in self.root.parts
                or self.root == Path(self.root.anchor)
                or not self.transaction_root.is_relative_to(self.root)
                or self.transaction_root == self.root
            ):
                msg = "file publication capability is not bound to its physical root"
                raise ValueError(msg)
            return self

    class MiseToolchainWorkspaceLayout(m.ArbitraryTypesModel):
        """Stable recovery topology independent of mutable source contents."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        scope_root: Annotated[Path, m.Field(description="Resolved transaction scope")]
        state_root: Annotated[
            Path,
            m.Field(description="Persistent scope transaction staging directory"),
        ]
        journal_path: Annotated[
            Path,
            m.Field(
                description=(
                    "Direct journal under the authenticated scope Git directory"
                ),
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
            t.VariadicTuple[
                FlextInfraModelsCodegenToolchain.MiseToolchainProjectLayout
            ],
            m.Field(description="Ordered Mise workspace participants"),
        ]
        file_participants: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegenToolchain.CodegenFileParticipant],
            m.Field(description="Explicit non-Mise publication capabilities"),
        ] = ()

        @m.model_validator(mode="after")
        def _validate_participants(self) -> Self:
            participants: t.VariadicTuple[
                FlextInfraModelsCodegenToolchain.MiseToolchainProjectLayout
                | FlextInfraModelsCodegenToolchain.CodegenFileParticipant
            ] = (*self.projects, *self.file_participants)
            if not participants:
                msg = "generation layout requires an explicit participant"
                raise ValueError(msg)
            selectors = tuple(item.selector for item in participants)
            roots = tuple(item.root for item in participants)
            if len(set(selectors)) != len(selectors) or len(set(roots)) != len(roots):
                msg = "generation participants must have unique selectors and roots"
                raise ValueError(msg)
            return self

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
            FlextInfraModelsCodegenToolchain.MiseToolchainProjectLayout,
            m.Field(description="Stable project layout owning this snapshot"),
        ]
        config: Annotated[
            FlextInfraModelsCodegenToolchain.MiseToolchainConfigState,
            m.Field(description="Planned generated Mise configuration state"),
        ]

        @m.model_validator(mode="after")
        def _validate_destination_paths(self) -> Self:
            """Bind every captured state to its declared live destination.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If Mise project states differ from declared destinations.

            """
            if self.config.before.path != self.layout.config:
                msg = "Mise project states differ from declared destinations"
                raise ValueError(msg)
            return self

    class MiseToolchainWorkspacePlan(m.ArbitraryTypesModel):
        """One stable layout plus a coherent mutable-state snapshot."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True, extra="forbid")

        layout: Annotated[
            FlextInfraModelsCodegenToolchain.MiseToolchainWorkspaceLayout,
            m.Field(description="Stable workspace topology"),
        ]
        projects: Annotated[
            t.VariadicTuple[FlextInfraModelsCodegenToolchain.MiseToolchainProjectState],
            m.Field(min_length=1, description="Ordered complete workspace topology"),
        ]

        @m.computed_field
        @property
        def sources(self) -> t.VariadicTuple[m.Cli.AtomicFileState]:
            """Every state the publication reads: the planned declarations.

            Returns:
                The resulting ``t.VariadicTuple[m.Cli.AtomicFileState]``.
            """
            return tuple(
                state for project in self.projects for state in project.config.sources
            )

        @m.model_validator(mode="after")
        def _validate_project_layouts(self) -> Self:
            """Bind every mutable project snapshot to the exact stable layout.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If Mise project snapshots differ from workspace layout.

            """
            if (
                tuple(project.layout for project in self.projects)
                != self.layout.projects
            ):
                msg = "Mise project snapshots differ from workspace layout"
                raise ValueError(msg)
            return self


__all__: list[str] = ["FlextInfraModelsCodegenToolchain"]
