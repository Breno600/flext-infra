"""Work-lane models reject impossible persisted states."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from flext_infra import c, m


class TestsFlextInfraWorkLaneModels:
    """Validate persisted work-lane state through the public model facade."""

    @staticmethod
    def _plain_topology() -> m.Infra.PlainLaneTopology:
        return m.Infra.PlainLaneTopology(role=c.Infra.WorkLaneRole.PLAIN)

    @classmethod
    def _pending(cls) -> dict[str, object]:
        return {
            "branch": "feature/typed-lane",
            "namespace": c.Infra.WorkBranchNamespace.FEATURE,
            "worktree": Path("typed-lane"),
            "kind": c.Infra.WorkKind.FEATURE,
            "slug": "typed-lane",
            "integration_base": "HEAD",
            "topology": cls._plain_topology(),
            "provisioning": c.Infra.WorkProvisioningState.PENDING,
        }

    def test_pending_reservation_accepts_no_head(self) -> None:
        reservation = m.Infra.PendingLaneReservation.model_validate(self._pending())

        assert reservation.provisioning == c.Infra.WorkProvisioningState.PENDING

    def test_ready_metadata_requires_head(self) -> None:
        payload = self._pending() | {
            "provisioning": c.Infra.WorkProvisioningState.READY
        }

        with pytest.raises(ValidationError):
            m.Infra.ReadyLaneMetadata.model_validate(payload)

    def test_ready_metadata_with_supplied_matrix_requires_root_cas_identity(
        self,
    ) -> None:
        matrix = m.Infra.WorkLaneMatrix(
            entries=(
                m.Infra.WorkLaneEntry(
                    project=".",
                    branch="feature/typed-lane",
                    head_oid="abc",
                    state="started",
                ),
            )
        )
        ready = m.Infra.ReadyLaneMetadata.model_validate(
            self._pending()
            | {
                "provisioning": c.Infra.WorkProvisioningState.READY,
                "head_oid": "abc",
                "matrix": matrix,
            }
        )
        assert ready.matrix == matrix

        different_head = ready.model_dump() | {"head_oid": "different"}
        with pytest.raises(ValidationError):
            m.Infra.ReadyLaneMetadata.model_validate(different_head)

        partial_pr = ready.model_dump() | {"pr_number": "42", "pr_url": "https://pr/42"}
        with pytest.raises(ValidationError):
            m.Infra.ReadyLaneMetadata.model_validate(partial_pr)

    def test_ready_metadata_accepts_omitted_matrix(self) -> None:
        ready = m.Infra.ReadyLaneMetadata.model_validate(
            self._pending()
            | {"provisioning": c.Infra.WorkProvisioningState.READY, "head_oid": "abc"}
        )

        assert ready.matrix is None

    def test_failed_metadata_accepts_optional_head(self) -> None:
        failed = m.Infra.FailedLaneMetadata.model_validate(
            self._pending()
            | {
                "provisioning": c.Infra.WorkProvisioningState.FAILED,
                "recovery": c.Infra.WorkRecoveryCategory.RETRY_SETUP,
                "error_category": c.Infra.WorkProvisioningError.SETUP,
            }
        )

        assert failed.head_oid is None

    def test_lane_metadata_refuses_extra_fields(self) -> None:
        payload = self._pending() | {"unknown": "x"}
        with pytest.raises(ValidationError):
            m.Infra.PendingLaneReservation.model_validate(payload)

    @pytest.mark.parametrize(
        "payload",
        [
            {
                "branch": "feature/typed-lane",
                "namespace": "epic",
                "kind": "feature",
                "topology": {"role": "plain"},
            },
            {
                "branch": "epic/typed-lane",
                "namespace": "epic",
                "kind": "feature",
                "topology": {"role": "epic", "epic_bead": "mro-parent"},
            },
            {
                "branch": "feature/typed-lane",
                "namespace": "feature",
                "kind": None,
                "topology": {"role": "plain"},
            },
        ],
    )
    def test_lane_metadata_refuses_inconsistent_namespace_topology(
        self, payload: dict[str, object]
    ) -> None:
        candidate = self._pending() | payload
        with pytest.raises(ValidationError):
            m.Infra.PendingLaneReservation.model_validate(candidate)

    @pytest.mark.parametrize(
        "topology",
        [
            {"role": "epic", "epic_bead": "mro-parent", "child_slug": "child"},
            {"role": "child"},
            {"role": "plain", "epic_bead": "mro-parent"},
        ],
    )
    def test_lane_topology_refuses_illegal_variant_fields(
        self, topology: dict[str, str]
    ) -> None:
        payload = self._pending() | {"topology": topology}
        with pytest.raises(ValidationError):
            m.Infra.PendingLaneReservation.model_validate(payload)


__all__: tuple[str, ...] = ()
