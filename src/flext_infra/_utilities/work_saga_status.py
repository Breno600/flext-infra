"""make work WHAT=status saga step."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import FlextInfraWorktreeService, c, m, u
from flext_infra._utilities.work_saga_common import FlextInfraWorkSagaCommon

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkSagaStatus(FlextInfraWorkSagaCommon):
    """Read-only status step for the public work saga."""

    @classmethod
    def _reported_topology(
        cls,
        primary_root: Path,
        metadata: (
            m.Infra.PendingLaneReservation
            | m.Infra.ReadyLaneMetadata
            | m.Infra.FailedLaneMetadata
        ),
    ) -> list[str]:
        lane = metadata.worktree
        match metadata.topology:
            case m.Infra.PlainLaneTopology():
                return []
            case m.Infra.ChildLaneTopology() as child:
                checked = cls._bound_child_topology(primary_root, child, lane)
                if checked.failure:
                    return [f"epic_topology: error={checked.error}"]
                return [f"epic_topology: child of {checked.value}"]
            case m.Infra.EpicLaneTopology():
                children = FlextInfraWorktreeService.registered_children(
                    primary_root, lane
                )
                if children.failure:
                    return [f"epic_topology: error={children.error}"]
                rendered = " ".join(str(child) for child in children.value)
                return [
                    f"epic_topology: epic children={len(children.value)} {rendered}".rstrip()
                ]

    def _status(self, primary_root: Path) -> p.Result[str]:
        bead = (self.bead or "").strip()
        branch_result = self._resolve_lane_branch()
        branch = branch_result.value if branch_result.success else (self.branch or "")
        lines: list[str] = ["work status"]
        if bead:
            shown = u.Infra.beads_show(bead, root=self.workspace_root)
            if shown.failure:
                return r.fail(shown.error or f"invalid Beads issue {bead}")
            lines.extend((f"bead: {bead}", f"bead_status: {shown.value.status}"))
            metadata = shown.value.metadata
            if metadata is not None:
                ownership = self._owned_reservation(
                    bead, metadata.branch, metadata.worktree
                )
                if ownership.failure:
                    return r.fail(
                        ownership.error or "work status reservation ownership failed"
                    )
                if isinstance(metadata.topology, m.Infra.ChildLaneTopology):
                    live = self._live_child_topology(
                        primary_root, shown.value, metadata.topology
                    )
                    if live.failure:
                        return r.fail(live.error or "work status child binding failed")
                values = metadata.model_dump(
                    mode="json", exclude_none=True, exclude={"topology", "matrix"}
                )
                topology = metadata.topology.model_dump(mode="json", exclude_none=True)
                for key, value in values.items():
                    lines.append(f"metadata.{key}: {value}")
                for key, value in topology.items():
                    if key != "role" or value != c.Infra.WorkLaneRole.PLAIN:
                        lines.append(f"metadata.{key}: {value}")
                lines.extend(self._reported_topology(primary_root, metadata))
                if (
                    isinstance(metadata, m.Infra.ReadyLaneMetadata)
                    and metadata.matrix is not None
                ):
                    lines.extend(
                        "matrix: "
                        f"project={entry.project} branch={entry.branch} "
                        f"head_oid={entry.head_oid} pr_number={entry.pr_number} "
                        f"pr_url={entry.pr_url} state={entry.state}"
                        for entry in metadata.matrix.entries
                    )
                if not branch:
                    branch = metadata.branch
        listed = FlextInfraWorktreeService(
            workspace_root=primary_root, operation=c.Infra.WorktreeOperation.LIST
        ).execute()
        lines.extend(
            (f"worktrees: error={listed.error}",)
            if listed.failure
            else ("worktrees:", listed.value.rstrip())
        )
        if branch:
            lines.append(f"branch: {branch}")
            pr_list = u.Cli.capture(
                (
                    "gh",
                    "pr",
                    "list",
                    "--head",
                    branch,
                    "--state",
                    "open",
                    "--json",
                    "number,url,state,baseRefName",
                ),
                cwd=primary_root,
            )
            lines.append(
                f"pr: error={pr_list.error}"
                if pr_list.failure
                else f"pr_open: {pr_list.value or '[]'}"
            )
        lines.append(
            f"primary_checkout: {self.workspace_root.resolve() == primary_root.resolve()}"
        )
        return r.ok("\n".join(lines))


__all__: list[str] = ["FlextInfraWorkSagaStatus"]
