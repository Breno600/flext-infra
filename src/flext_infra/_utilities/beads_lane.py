"""Beads lane registry adapter for the make work saga."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from flext_cli import u
from flext_core import r

from flext_infra import c, m

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesBeadsLane:
    """Shell `bd` for lane metadata, labels, and evidence notes."""

    _UPDATE_BASE_ARGV_LENGTH = 2
    _BEADS_ROOT_CACHE: ClassVar[dict[Path, Path]] = {}

    @classmethod
    def beads_resolve_root(cls, hint: Path | None = None) -> p.Result[Path]:
        """Resolve the Beads project root that owns the workspace ledger.

        A Git submodule routes to its governing superproject ledger. A
        standalone repository keeps its own declared tracker. Uses typed Git
        root reports — never raw argv helpers.
        """
        start = (hint or Path.cwd()).expanduser().resolve()
        cached = cls._BEADS_ROOT_CACHE.get(start)
        if cached is not None:
            return r.ok(cached)
        from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

        governing = FlextInfraWorkspaceDetector.resolve_workspace_root(start)
        if governing.failure:
            return r.fail(governing.error or "unable to resolve governing workspace")
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(governing.value)
        if workspace.failure:
            return r.fail(workspace.error or "unable to load governing workspace")
        if workspace.value.ledger_id is None:
            return r.fail(
                f"governing workspace declares no Beads ledger: {governing.value}"
            )
        cls._BEADS_ROOT_CACHE[start] = governing.value
        return r.ok(governing.value)

    @classmethod
    def _bd_command(
        cls, *parts: str, root: Path | None = None
    ) -> p.Result[tuple[str, ...]]:
        resolved = cls.beads_resolve_root(root)
        if resolved.failure:
            return r.fail(resolved.error or "failed to resolve Beads root")
        return r.ok(("bd", "-C", str(resolved.value), *parts))

    @classmethod
    def beads_show(
        cls, bead_id: str, *, root: Path | None = None, adopt_legacy_ready: bool = False
    ) -> p.Result[m.Infra.BeadIssue]:
        """Return one issue parsed through the strict lane boundary."""
        cleaned = bead_id.strip()
        if not cleaned:
            return r.fail("beads show requires a non-empty bead id")
        command = cls._bd_command("show", cleaned, "--json", root=root)
        if command.failure:
            return r.fail(command.error or "failed to build bd show command")
        captured = u.Cli.capture(command.value)
        if captured.failure:
            return r.fail(captured.error or f"bd show failed for {cleaned}")
        try:
            payload = json.loads(captured.value)
        except json.JSONDecodeError as exc:
            return r.fail(f"bd show returned invalid JSON: {exc}")
        if isinstance(payload, list):
            if not payload or not isinstance(payload[0], dict):
                return r.fail(f"bd show returned empty list for {cleaned}")
            payload = payload[0]
        if not isinstance(payload, dict):
            return r.fail(f"bd show returned unexpected JSON for {cleaned}")
        return cls._parse_issue(payload, adopt_legacy_ready=adopt_legacy_ready)

    @classmethod
    def beads_list_reservations(
        cls, *, root: Path | None = None
    ) -> p.Result[tuple[m.Infra.BeadIssue, ...]]:
        """List issues that currently carry a typed lane reservation."""
        command = cls._bd_command("list", "--json", root=root)
        if command.failure:
            return r.fail(command.error or "failed to build bd list command")
        captured = u.Cli.capture(command.value)
        if captured.failure:
            return r.fail(captured.error or "bd list failed")
        try:
            payload = json.loads(captured.value)
        except json.JSONDecodeError as exc:
            return r.fail(f"bd list returned invalid JSON: {exc}")
        if not isinstance(payload, list):
            return r.fail("bd list returned unexpected JSON")
        issues: list[m.Infra.BeadIssue] = []
        for row in payload:
            if not isinstance(row, dict):
                return r.fail("bd list returned a non-object issue")
            parsed = cls._parse_issue(row)
            if parsed.failure:
                return r.fail(parsed.error or "bd list issue validation failed")
            if parsed.value.metadata is not None:
                issues.append(parsed.value)
        return r.ok(tuple(issues))

    @staticmethod
    def _project_lane_metadata(
        metadata: object,
        *,
        bead_id: str,
        issue_type: str | None,
        adopt_legacy_ready: bool = False,
    ) -> dict[str, object] | None:
        if not isinstance(metadata, dict):
            return None
        if "provisioning" not in metadata:
            if not adopt_legacy_ready:
                return None
            legacy_epic = (
                issue_type == "epic"
                and metadata.get("kind") == "epic"
                and all(
                    metadata.get(key)
                    for key in ("slug", "worktree", "integration_base")
                )
            )
            if not legacy_epic:
                return None
            if "matrix" not in metadata:
                msg = "legacy ready lane adoption requires matrix metadata"
                raise ValueError(msg)
            slug = str(metadata.get("slug") or "")
            branch = (
                f"epic/{slug}"
                if issue_type == "epic"
                else str(metadata.get("branch") or "")
            )
            matrix = metadata["matrix"]
            parsed_matrix = (
                m.Infra.WorkLaneMatrix.model_validate_json(matrix)
                if isinstance(matrix, str)
                else m.Infra.WorkLaneMatrix.model_validate_json(json.dumps(matrix))
            )
            root_entry = next(
                (entry for entry in parsed_matrix.entries if entry.project == "."),
                parsed_matrix.entries[0],
            )
            namespace = branch.partition("/")[0]
            adopted_metadata: dict[str, object] = {
                **metadata,
                "branch": branch,
                "namespace": namespace,
                "kind": None if issue_type == "epic" else namespace,
                "head_oid": root_entry.head_oid,
                "provisioning": c.Infra.WorkProvisioningState.READY.value,
                "role": (
                    c.Infra.WorkLaneRole.EPIC.value
                    if issue_type == "epic"
                    else c.Infra.WorkLaneRole.PLAIN.value
                ),
            }
            if issue_type == "epic":
                adopted_metadata["epic_bead"] = bead_id
            metadata = adopted_metadata
        role = metadata.get("role") or c.Infra.WorkLaneRole.PLAIN.value
        topology = {"role": role}
        for key in ("epic_bead", "epic_branch", "epic_worktree", "child_slug"):
            if key in metadata:
                topology[key] = metadata[key]
        provisioning = metadata.get("provisioning")
        state_fields: tuple[str, ...] = ()
        if provisioning == c.Infra.WorkProvisioningState.READY:
            state_fields = ("pr_number", "pr_url")
        elif provisioning == c.Infra.WorkProvisioningState.FAILED:
            state_fields = ("recovery", "error_category")
        projected = {
            key: metadata[key]
            for key in (
                "branch",
                "namespace",
                "worktree",
                "kind",
                "slug",
                "integration_base",
                "provisioning",
                "head_oid",
                *state_fields,
            )
            if key in metadata
        }
        if "worktree" in projected:
            projected["worktree"] = Path(str(projected["worktree"]))
        if projected.get("kind") is not None:
            projected["kind"] = c.Infra.WorkKind(str(projected["kind"]))
        else:
            projected.pop("kind", None)
        if "namespace" in projected:
            projected["namespace"] = c.Infra.WorkBranchNamespace(
                str(projected["namespace"])
            )
        if "recovery" in projected:
            projected["recovery"] = c.Infra.WorkRecoveryCategory(
                str(projected["recovery"])
            )
        if "error_category" in projected:
            projected["error_category"] = c.Infra.WorkProvisioningError(
                str(projected["error_category"])
            )
        if projected.get("provisioning") == c.Infra.WorkProvisioningState.READY:
            matrix = metadata.get("matrix")
            if isinstance(matrix, str):
                projected["matrix"] = m.Infra.WorkLaneMatrix.model_validate_json(matrix)
            elif isinstance(matrix, Mapping):
                projected["matrix"] = m.Infra.WorkLaneMatrix.model_validate_json(
                    json.dumps(dict(matrix))
                )
        if "epic_worktree" in topology:
            topology["epic_worktree"] = Path(str(topology["epic_worktree"]))
        projected["topology"] = topology
        return projected

    @classmethod
    def _parse_issue(
        cls, payload: dict[str, object], *, adopt_legacy_ready: bool = False
    ) -> p.Result[m.Infra.BeadIssue]:
        try:
            projected_metadata = cls._project_lane_metadata(
                payload.get("metadata"),
                bead_id=str(payload.get("id") or ""),
                issue_type=(
                    str(payload["issue_type"])
                    if payload.get("issue_type") is not None
                    else None
                ),
                adopt_legacy_ready=adopt_legacy_ready,
            )
            projected = {
                "id": payload.get("id"),
                "status": c.Infra.BeadIssueStatus(str(payload.get("status"))),
                "issue_type": payload.get("issue_type"),
                "parent": payload.get("parent"),
                "metadata": projected_metadata,
            }
            return r.ok(m.Infra.BeadIssue.model_validate(projected))
        except (ValueError, m.ValidationError) as exc:
            return r.fail(f"Beads issue validation failed: {exc}")

    @classmethod
    def beads_update_lane(
        cls,
        bead_id: str,
        *,
        metadata: (
            m.Infra.PendingLaneReservation
            | m.Infra.ReadyLaneMetadata
            | m.Infra.FailedLaneMetadata
            | None
        ) = None,
        labels: tuple[str, ...] = (),
        notes: str | None = None,
        claim: bool = False,
        root: Path | None = None,
    ) -> p.Result[str]:
        """Update lane registry fields on one bead."""
        cleaned = bead_id.strip()
        if not cleaned:
            return r.fail("beads update requires a non-empty bead id")
        parts: list[str] = ["update", cleaned]
        if claim:
            parts.append("--claim")
        if metadata is not None:
            values = metadata.model_dump(
                mode="json", exclude_none=True, exclude={"topology", "matrix"}
            )
            topology = metadata.topology.model_dump(mode="json", exclude_none=True)
            assignments = tuple(
                f"{key}={value}" for key, value in values.items()
            ) + tuple(f"{key}={value}" for key, value in topology.items())
            if (
                isinstance(metadata, m.Infra.ReadyLaneMetadata)
                and metadata.matrix is not None
            ):
                assignments = (
                    *assignments,
                    f"matrix={metadata.matrix.model_dump_json()}",
                )
            for assignment in assignments:
                parts.extend(("--set-metadata", assignment))
            if metadata.kind is None:
                parts.extend(("--unset-metadata", "kind"))
            stale_fields: tuple[str, ...]
            if isinstance(metadata, m.Infra.PendingLaneReservation):
                stale_fields = (
                    "recovery",
                    "error_category",
                    "pr_number",
                    "pr_url",
                    "matrix",
                )
            elif isinstance(metadata, m.Infra.ReadyLaneMetadata):
                stale_fields = ("recovery", "error_category")
            else:
                stale_fields = ("pr_number", "pr_url", "matrix")
            for stale_field in stale_fields:
                parts.extend(("--unset-metadata", stale_field))
        for label in labels:
            parts.extend(("--add-label", label))
        if notes:
            parts.extend(("--append-notes", notes))
        if len(parts) == cls._UPDATE_BASE_ARGV_LENGTH:
            return r.fail("beads update requires metadata, labels, notes, or claim")
        command = cls._bd_command(*parts, root=root)
        if command.failure:
            return r.fail(command.error or "failed to build bd update command")
        ran = u.Cli.run(command.value)
        if ran.failure:
            return r.fail(ran.error or f"bd update failed for {cleaned}")
        if ran.value.exit_code != 0:
            detail = (ran.value.stderr or ran.value.stdout).strip()
            return r.fail(detail or f"bd update failed for {cleaned}")
        return r.ok(cleaned)


__all__: list[str] = ["FlextInfraUtilitiesBeadsLane"]
