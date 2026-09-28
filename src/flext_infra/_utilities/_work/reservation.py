"""Typed reservation construction and provisioning transitions."""

from __future__ import annotations

from flext_infra import c, m


class FlextInfraWorkReservation:
    """Construct immutable lane states for Beads persistence."""

    @staticmethod
    def ready(
        reservation: m.Infra.PendingLaneReservation | m.Infra.FailedLaneMetadata,
        head_oid: str,
        matrix: m.Infra.WorkLaneMatrix,
    ) -> m.Infra.ReadyLaneMetadata:
        return m.Infra.ReadyLaneMetadata(
            branch=reservation.branch,
            namespace=c.Infra.WorkBranchNamespace(reservation.namespace),
            worktree=reservation.worktree,
            kind=(
                c.Infra.WorkKind(reservation.kind)
                if reservation.kind is not None
                else None
            ),
            slug=reservation.slug,
            integration_base=reservation.integration_base,
            topology=reservation.topology,
            provisioning=c.Infra.WorkProvisioningState.READY,
            head_oid=head_oid,
            matrix=matrix,
        )

    @staticmethod
    def failed(
        reservation: m.Infra.PendingLaneReservation, head_oid: str | None
    ) -> m.Infra.FailedLaneMetadata:
        return m.Infra.FailedLaneMetadata(
            branch=reservation.branch,
            namespace=c.Infra.WorkBranchNamespace(reservation.namespace),
            worktree=reservation.worktree,
            kind=(
                c.Infra.WorkKind(reservation.kind)
                if reservation.kind is not None
                else None
            ),
            slug=reservation.slug,
            integration_base=reservation.integration_base,
            topology=reservation.topology,
            provisioning=c.Infra.WorkProvisioningState.FAILED,
            head_oid=head_oid,
            recovery=c.Infra.WorkRecoveryCategory.RETRY_SETUP,
            error_category=c.Infra.WorkProvisioningError.SETUP,
        )


__all__: list[str] = ["FlextInfraWorkReservation"]
