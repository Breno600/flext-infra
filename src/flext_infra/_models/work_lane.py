"""Strict Beads issue and work-lane metadata contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal

from flext_infra import c, m, t


class FlextInfraModelsWorkLane:
    """Public MRO composition for typed lane contracts."""

    class LaneContract(m.ContractModel):
        """Immutable strict base for externally persisted lane data."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

    class PlainLaneTopology(LaneContract):
        """Standalone lane with no epic relationship."""

        role: Annotated[
            Literal[c.Infra.WorkLaneRole.PLAIN],
            m.Field(description="Standalone lane topology discriminator"),
        ]

    class EpicLaneTopology(LaneContract):
        """Epic lane that may own nested child lanes."""

        role: Annotated[
            Literal[c.Infra.WorkLaneRole.EPIC],
            m.Field(description="Epic lane topology discriminator"),
        ]
        epic_bead: Annotated[
            t.NonEmptyStr, m.Field(description="Beads issue that owns the epic lane")
        ]

    class ChildLaneTopology(LaneContract):
        """Child lane bound to one registered epic lane."""

        role: Annotated[
            Literal[c.Infra.WorkLaneRole.CHILD],
            m.Field(description="Child lane topology discriminator"),
        ]
        epic_bead: Annotated[
            t.NonEmptyStr, m.Field(description="Beads issue that owns the epic lane")
        ]
        epic_branch: Annotated[
            t.NonEmptyStr, m.Field(description="Registered epic lane branch")
        ]
        epic_worktree: Annotated[
            Path, m.Field(description="Registered epic lane worktree root")
        ]
        child_slug: Annotated[
            t.NonEmptyStr, m.Field(description="Child slug within the epic lane")
        ]

    type LaneTopology = Annotated[
        PlainLaneTopology | EpicLaneTopology | ChildLaneTopology,
        m.Field(discriminator="role", description="Discriminated lane topology"),
    ]

    class WorkLaneEntry(LaneContract):
        """Lifecycle state for one project in a workspace-root lane."""

        project: Annotated[
            t.NonEmptyStr, m.Field(description="Workspace-relative project")
        ]
        branch: Annotated[t.NonEmptyStr, m.Field(description="Project lane branch")]
        head_oid: Annotated[t.NonEmptyStr, m.Field(description="CAS-protected HEAD")]
        pr_number: Annotated[str, m.Field(description="Pull request number")] = ""
        pr_url: Annotated[str, m.Field(description="Pull request URL")] = ""
        state: Annotated[t.NonEmptyStr, m.Field(description="Lifecycle state")]

    class WorkLaneMatrix(LaneContract):
        """Project lifecycle matrix owned by one workspace-root lane."""

        entries: Annotated[
            tuple[FlextInfraModelsWorkLane.WorkLaneEntry, ...],
            m.Field(min_length=1, description="Projects owned by the root lane"),
        ]

    class _LaneReservation(LaneContract):
        branch: Annotated[t.NonEmptyStr, m.Field(description="Canonical lane branch")]
        namespace: Annotated[
            c.Infra.WorkBranchNamespace,
            m.Field(description="Topology-derived canonical branch namespace"),
        ]
        worktree: Annotated[Path, m.Field(description="Canonical lane worktree path")]
        kind: Annotated[
            c.Infra.WorkKind | None,
            m.Field(description="GitFlow lane kind; absent for epic lanes"),
        ] = None
        slug: Annotated[t.NonEmptyStr, m.Field(description="Canonical lane slug")]
        integration_base: Annotated[
            t.NonEmptyStr, m.Field(description="Logical lane integration base")
        ]
        topology: Annotated[
            FlextInfraModelsWorkLane.LaneTopology,
            m.Field(description="Validated lane topology binding"),
        ]

        @m.field_validator("topology", mode="after")
        @classmethod
        def validate_branch_identity(
            cls, topology: FlextInfraModelsWorkLane.LaneTopology, info: m.ValidationInfo
        ) -> FlextInfraModelsWorkLane.LaneTopology:
            required = ("branch", "namespace", "kind", "slug")
            if not all(field in info.data for field in required):
                return topology
            branch = info.data["branch"]
            namespace = info.data["namespace"]
            kind = info.data["kind"]
            slug = info.data["slug"]
            expected_branch = f"{namespace}/{slug}"
            if branch != expected_branch:
                msg = f"lane branch must equal namespace/slug: {expected_branch}"
                raise ValueError(msg)
            match topology:
                case FlextInfraModelsWorkLane.EpicLaneTopology():
                    valid = (
                        namespace == c.Infra.WorkBranchNamespace.EPIC and kind is None
                    )
                case (
                    FlextInfraModelsWorkLane.PlainLaneTopology()
                    | FlextInfraModelsWorkLane.ChildLaneTopology()
                ):
                    match kind:
                        case None:
                            valid = False
                        case work_kind:
                            valid = (
                                c.Infra.WorkBranchNamespace(namespace).value
                                == c.Infra.WorkKind(work_kind).value
                            )
            if not valid:
                msg = "lane namespace, kind, and topology are inconsistent"
                raise ValueError(msg)
            return topology

    class PendingLaneReservation(_LaneReservation):
        """Reserved branch and path before provisioning produces a HEAD."""

        provisioning: Annotated[
            Literal[c.Infra.WorkProvisioningState.PENDING],
            m.Field(description="Pending provisioning discriminator"),
        ]
        head_oid: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional last-known HEAD during an identical retry"),
        ] = None

    class ReadyLaneMetadata(_LaneReservation):
        """Fully provisioned lane with a CAS-protected HEAD."""

        provisioning: Annotated[
            Literal[c.Infra.WorkProvisioningState.READY],
            m.Field(description="Ready provisioning discriminator"),
        ]
        head_oid: Annotated[
            t.NonEmptyStr, m.Field(description="CAS-protected ready lane HEAD")
        ]
        matrix: Annotated[
            FlextInfraModelsWorkLane.WorkLaneMatrix | None,
            m.Field(description="Workspace project lifecycle matrix when recorded"),
        ] = None
        pr_number: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Pull request number recorded after land"),
        ] = None
        pr_url: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Pull request URL recorded after land"),
        ] = None

    class FailedLaneMetadata(_LaneReservation):
        """Recoverable reservation retained after provisioning failure."""

        provisioning: Annotated[
            Literal[c.Infra.WorkProvisioningState.FAILED],
            m.Field(description="Failed provisioning discriminator"),
        ]
        head_oid: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Last known lane HEAD when one was observed"),
        ] = None
        recovery: Annotated[
            c.Infra.WorkRecoveryCategory,
            m.Field(description="Typed recovery action for the failed reservation"),
        ]
        error_category: Annotated[
            c.Infra.WorkProvisioningError,
            m.Field(description="Provisioning stage that failed"),
        ]

    type LaneMetadata = Annotated[
        PendingLaneReservation | ReadyLaneMetadata | FailedLaneMetadata,
        m.Field(discriminator="provisioning", description="Discriminated lane state"),
    ]

    class BeadIssue(LaneContract):
        """Trusted subset of one Beads issue consumed by the work saga."""

        id: Annotated[t.NonEmptyStr, m.Field(description="Canonical Beads issue id")]
        status: Annotated[
            c.Infra.BeadIssueStatus, m.Field(description="Current Beads issue status")
        ]
        issue_type: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Beads issue type used for lane kind derivation"),
        ] = None
        parent: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Parent Beads issue id when this is a child"),
        ] = None
        metadata: Annotated[
            FlextInfraModelsWorkLane.LaneMetadata | None,
            m.Field(description="Validated lane reservation or lifecycle state"),
        ] = None


__all__: list[str] = ["FlextInfraModelsWorkLane"]
