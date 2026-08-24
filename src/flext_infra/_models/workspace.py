"""Domain models for the workspace subpackage."""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Annotated, ClassVar

from flext_cli import m
from flext_infra import c, t
from flext_infra._models.mixins import FlextInfraModelsMixins as mm


class FlextInfraModelsWorkspace:
    """Models for workspace discovery and orchestration.

    Canonical base policy:
    - ``ArbitraryTypesModel`` for mutable discovery payloads.
    - ``ContractModel`` reserved for immutable workspace settings contracts.
    """

    class WorkspaceEnvironmentRequest(m.ContractModel):
        """Read-only request for validating the active workspace environment."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(populate_by_name=True)

        workspace_root: Annotated[
            Path, m.Field(alias="workspace", description="Workspace root path")
        ]

    class FlextBindingRequest(m.ContractModel):
        """Session request binding one consumer onto a flext worktree."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(populate_by_name=True)

        workspace_root: Annotated[
            Path, m.Field(alias="workspace", description="Consumer project root")
        ]
        flext_root: Annotated[
            Path, m.Field(description="Flext worktree supplying the packages")
        ]
        python: Annotated[
            Path, m.Field(description="Interpreter of the environment to rebind")
        ]

    class DirectUrlDirectoryInfo(m.ContractModel):
        """PEP 610 directory metadata for one installed distribution."""

        editable: Annotated[
            bool, m.Field(description="Distribution is installed as editable")
        ]

    class EditableDirectUrl(m.ContractModel):
        """Validated PEP 610 editable provenance payload."""

        url: Annotated[t.NonEmptyStr, m.Field(description="Editable source URL")]
        dir_info: Annotated[
            FlextInfraModelsWorkspace.DirectUrlDirectoryInfo,
            m.Field(description="Editable directory metadata"),
        ]

    class ProjectInfo(mm.ProjectEntryNameMixin, m.ArbitraryTypesModel):
        """Discovered project metadata for workspace operations."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            frozen=True, validate_default=False
        )

        path: Annotated[Path, m.Field(description="Absolute or relative project path")]
        stack: Annotated[t.NonEmptyStr, m.Field(description="Primary technology stack")]
        has_tests: Annotated[bool, m.Field(description="Project has test suite")] = (
            False
        )
        has_src: Annotated[
            bool, m.Field(description="Project has source directory")
        ] = True
        project_class: Annotated[
            t.NonEmptyStr, m.Field(description="Docs/governance project classification")
        ] = "platform"
        package_name: Annotated[
            str, m.Field(description="Primary Python package name")
        ] = ""
        workspace_role: Annotated[
            c.Infra.WorkspaceProjectRole,
            m.Field(description="Operational role relative to the uv workspace root"),
        ] = c.Infra.WorkspaceProjectRole.ATTACHED

    class WorkLaneParentContext(m.ContractModel):
        """Resolved anchor a lane is nested under and based on."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        parent_lane: Annotated[
            Path, m.Field(description="Workspace root or parent epic lane path")
        ]
        parent_bead: Annotated[
            str, m.Field(description="Parent epic bead id; empty at the workspace root")
        ] = ""
        parent_branch: Annotated[
            str, m.Field(description="Parent epic branch; empty at the workspace root")
        ] = ""
        base_branch: Annotated[
            t.NonEmptyStr, m.Field(description="Branch the lane is created from")
        ]

    class WorkLaneIdentity(m.ContractModel):
        """Canonical recursive identity of one workspace lane.

        A lane always lives at ``<parent_lane>/.worktrees/<lane_dir>`` and is
        always a worktree of the workspace-root repository. ``parent_lane`` is
        the workspace root for a top-level epic and the immediate parent epic
        lane for every other lane.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        bead: Annotated[t.NonEmptyStr, m.Field(description="Bead owning the lane")]
        slug: Annotated[t.NonEmptyStr, m.Field(description="Kebab-case lane slug")]
        kind: Annotated[
            c.Infra.WorkKind, m.Field(description="GitFlow kind of this lane")
        ]
        branch: Annotated[t.NonEmptyStr, m.Field(description="Lane branch name")]
        lane_dir: Annotated[
            t.NonEmptyStr, m.Field(description="Directory name under .worktrees")
        ]
        lane_path: Annotated[Path, m.Field(description="Canonical lane worktree path")]
        parent_lane: Annotated[
            Path, m.Field(description="Workspace root or parent epic lane path")
        ]
        parent_bead: Annotated[
            str, m.Field(description="Parent epic bead id; empty for top-level epics")
        ] = ""
        parent_branch: Annotated[
            str, m.Field(description="Parent epic branch; empty for top-level epics")
        ] = ""
        base_branch: Annotated[
            t.NonEmptyStr, m.Field(description="Branch this lane is based on")
        ]

        @property
        def is_epic(self) -> bool:
            """Whether this lane may own child lanes.

            WorkKind is a StrEnum and the contract model stores enum values, so
            the field arrives as its string form; normalizing before comparing
            keeps this true for both storage shapes.
            """
            return c.Infra.WorkKind(self.kind) is c.Infra.WorkKind.EPIC

    class WorkLaneReuse(m.ContractModel):
        """Whether Git already owns the canonical lane, and where it sits.

        Modelled instead of an optional payload because a success result never
        carries ``None``: "no lane to reuse" is a state, not an absent value.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        reused: Annotated[
            bool, m.Field(description="Git already owns the canonical lane")
        ]
        lane_path: Annotated[Path, m.Field(description="Canonical lane worktree path")]

    class ProjectPyprojectState(m.ArbitraryTypesModel):
        """Centralized parsed pyproject state reused across discovery services.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            frozen=True, validate_default=False
        )

        project_root: Annotated[Path, m.Field(description="Project root path")]
        pyproject_path: Annotated[Path, m.Field(description="Resolved pyproject path")]
        payload: Annotated[
            t.JsonMapping, m.Field(description="Parsed pyproject payload")
        ] = m.Field(default_factory=lambda: MappingProxyType({}))
        docs_meta: Annotated[
            t.JsonMapping, m.Field(description="Parsed tool.flext.docs payload")
        ] = m.Field(default_factory=lambda: MappingProxyType({}))
        project_name: Annotated[str, m.Field(description="Declared project name")] = ""
        package_name: Annotated[str, m.Field(description="Primary package name")] = ""
        dependency_names: Annotated[
            t.StrSequence, m.Field(description="Declared dependency names")
        ] = m.Field(default_factory=tuple)


__all__: list[str] = ["FlextInfraModelsWorkspace"]
