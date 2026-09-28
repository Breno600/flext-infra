"""make work WHAT=start and WHAT=status saga steps."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import FlextInfraWorktreeService, c, m, u
from flext_infra._utilities.work_saga_common import FlextInfraWorkSagaCommon

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkSagaStart(FlextInfraWorkSagaCommon):
    """Start and status steps for the public work saga."""

    apply_changes: bool
    epic: str | None

    def _start(self, primary_root: Path) -> p.Result[str]:
        if not self.apply_changes:
            return r.fail("work start requires --apply")
        bead = (self.bead or "").strip()
        if not bead:
            return r.fail("work start requires --bead")
        shown = u.Infra.beads_show(
            bead, root=self.workspace_root, adopt_legacy_ready=True
        )
        if shown.failure:
            return r.fail(shown.error or f"unknown bead {bead}")
        epic_bead = (self.epic or "").strip()
        kind_slug = self._validated_kind_slug(
            shown.value.issue_type, child=bool(epic_bead)
        )
        if kind_slug.failure:
            return r.fail(kind_slug.error or "invalid kind/name")
        kind, namespace, slug = kind_slug.value
        branch = self._branch_name(namespace, slug)
        existing = shown.value.metadata
        existing_matrix: m.Infra.WorkLaneMatrix | None = None
        if existing is not None:
            bound = existing.worktree.exists()
            if bound and existing.branch != branch:
                return r.fail(
                    f"bead {bead} already bound to branch {existing.branch} "
                    f"at {existing.worktree}"
                )
            if isinstance(existing, m.Infra.ReadyLaneMetadata):
                if existing.matrix is None:
                    return r.fail("ready lane start requires matrix metadata")
                existing_matrix = existing.matrix
        epic_lane: Path | None = None
        base = ""
        if epic_bead:
            if epic_bead == bead:
                return r.fail("work start refuses a bead that is its own epic")
            if (self.base or "").strip():
                return r.fail(
                    "work start derives a child base from its epic lane; drop --base"
                )
            resolved_epic = self._registered_epic(primary_root, shown.value, epic_bead)
            if resolved_epic.failure:
                return r.fail(resolved_epic.error or "unresolved epic lane")
            # Why: the child base is the epic branch Git already has checked
            # out in the epic lane, never a literal the caller supplies.
            base, epic_lane = resolved_epic.value
        else:
            resolved_base = self._resolve_integration_base(primary_root)
            if resolved_base.failure:
                return r.fail(
                    resolved_base.error or "failed to resolve integration base"
                )
            base = resolved_base.value
        reserved_path = self._assert_start_reservation(
            primary_root, bead, branch, epic_lane
        )
        if reserved_path.failure:
            return r.fail(reserved_path.error or "lane reservation refused start")
        reused = self._reusable_lane(primary_root, branch)
        if reused is not None and reused.resolve() != reserved_path.value.resolve():
            return r.fail(
                f"registered lane path differs from canonical reservation: "
                f"registered={reused} canonical={reserved_path.value}"
            )
        if reused is None:
            fetched = u.Infra.git_fetch_origin(
                m.Infra.GitRepoRequest(repo_root=primary_root)
            )
            if fetched.failure:
                return r.fail(fetched.error or "work start failed to fetch origin")
            created = FlextInfraWorktreeService(
                workspace_root=primary_root,
                operation=c.Infra.WorktreeOperation.ADD,
                branch=branch,
                base=(
                    base
                    if epic_lane is not None
                    else self._git_integration_ref(primary_root, base)
                ),
                epic_lane=epic_lane,
                apply_changes=True,
            ).execute()
            if created.failure:
                return r.fail(created.error or f"failed to start lane {branch}")
            lane = Path(created.value)
        else:
            lane = reused
        if self._is_primary_path(primary_root, lane):
            return r.fail("work start refused to use the primary worktree as a lane")
        topology: (
            m.Infra.PlainLaneTopology
            | m.Infra.EpicLaneTopology
            | m.Infra.ChildLaneTopology
        )
        if epic_lane is None and shown.value.issue_type == "epic":
            topology = m.Infra.EpicLaneTopology(
                role=c.Infra.WorkLaneRole.EPIC, epic_bead=bead
            )
        elif epic_lane is None:
            topology = m.Infra.PlainLaneTopology(role=c.Infra.WorkLaneRole.PLAIN)
        else:
            topology = m.Infra.ChildLaneTopology(
                role=c.Infra.WorkLaneRole.CHILD,
                epic_bead=epic_bead,
                epic_branch=base,
                epic_worktree=epic_lane,
                child_slug=slug,
            )
        pending_metadata = self.pending(
            branch=branch,
            namespace=namespace,
            worktree=lane,
            kind=kind,
            slug=slug,
            integration_base=base,
            topology=topology,
        )
        pending = u.Infra.beads_update_lane(
            bead,
            metadata=pending_metadata,
            labels=(f"branch:{branch}",),
            notes=f"work start: decisive=lane-registered-before-provisioning path={lane}",
            root=self.workspace_root,
        )
        if pending.failure:
            return r.fail(
                self._rollback_started_lane(primary_root, branch, reused, pending.error)
            )
        ownership = self._owned_reservation(bead, branch, lane)
        if ownership.failure:
            return r.fail(ownership.error or "pending reservation ownership failed")
        # Why: mro-c6di — every maintained worktree runs `make setup`, so start
        # owns that guarantee for the lane it hands back. An adopted lane used to
        # skip provisioning entirely and was handed over with whatever
        # environment an interrupted start had left behind.
        prepared = FlextInfraWorktreeService.setup_lane(lane)
        if prepared.failure:
            known_head = self._git_head(lane)
            failed = self.failed(
                pending_metadata, known_head.value if known_head.success else None
            )
            recorded = u.Infra.beads_update_lane(
                bead,
                metadata=failed,
                notes=f"work start: decisive=provisioning-failed path={lane}",
                root=self.workspace_root,
            )
            if recorded.failure:
                return r.fail(recorded.error or "failed to record provisioning failure")
            # Why: provisioning is RESUMABLE, so a failed `make setup` must not
            # destroy the checkout it already produced. Rolling back here forced
            # a manual repair and re-clone after any transient setup failure (a
            # stale submodule checkout, a network blip). The lane and its branch
            # are kept exactly as they are and start stays idempotent: fix the
            # cause, run the same command again, and it resumes from the
            # existing checkout instead of starting over.
            return r.fail(
                f"{prepared.error or 'failed to provision lane'}; "
                f"lane {branch} preserved at {lane} - resolve the cause and "
                f"re-run the same work start to resume provisioning"
            )
        head = self._git_head(lane)
        if head.failure:
            return r.fail(head.error or "failed to read lane HEAD")
        decisive = "lane-reused" if reused is not None else "lane-ready"
        notes = (
            f"work start: cmd=make work WHAT=start cwd={lane} "
            f"branch={branch} base={base} exit=0 decisive={decisive} "
            f"head={head.value}"
        )
        # Why: mro-dipb.1 kind may arrive as str; coerce like _branch_name.
        projects = u.Infra.resolve_projects(primary_root, ())
        if projects.failure:
            return r.fail(projects.error or "failed to resolve workspace projects")
        entries: list[m.Infra.WorkLaneEntry] = []
        project_paths = (
            primary_root.resolve(),
            *(project.path.resolve() for project in projects.value),
        )
        for project_path in dict.fromkeys(project_paths):
            try:
                relative = project_path.relative_to(primary_root.resolve())
            except ValueError:
                return r.fail(f"workspace project is outside root: {project_path}")
            project_name = relative.as_posix() or "."
            lane_project = (lane / project_name).resolve()
            if (
                not lane_project.is_relative_to(lane.resolve())
                or not lane_project.is_dir()
            ):
                return r.fail(f"matrix project checkout is missing: {project_name}")
            if project_name != ".":
                current_branch = u.Infra.git_abbrev_ref_head(
                    m.Infra.GitRepoRequest(repo_root=lane_project)
                )
                if current_branch.failure:
                    return r.fail(
                        current_branch.error
                        or f"failed to resolve workspace project branch: {project_name}"
                    )
                if current_branch.value.text != branch:
                    attached = u.Infra.git_attach_branch_at_head(
                        m.Infra.GitBranchRequest(repo_root=lane_project, branch=branch)
                    )
                    if attached.failure:
                        return r.fail(
                            attached.error
                            or f"failed to attach workspace project branch: {project_name}"
                        )
            project_head = self._git_head(lane_project)
            if project_head.failure:
                return r.fail(
                    project_head.error
                    or f"failed to resolve matrix head: {project_name}"
                )
            entries.append(
                m.Infra.WorkLaneEntry(
                    project=project_name,
                    branch=branch,
                    head_oid=project_head.value,
                    state="started",
                )
            )
        matrix = existing_matrix or m.Infra.WorkLaneMatrix(entries=tuple(entries))
        lane_metadata = self.ready(pending_metadata, head.value, matrix)
        labels: tuple[str, ...] = (f"branch:{branch}",)
        if epic_lane is not None:
            labels = (*labels, f"epic:{epic_bead}")
        updated = u.Infra.beads_update_lane(
            bead,
            metadata=lane_metadata,
            labels=labels,
            notes=notes,
            root=self.workspace_root,
        )
        if updated.failure:
            return r.fail(
                self._rollback_started_lane(primary_root, branch, reused, updated.error)
            )
        ownership = self._owned_reservation(bead, branch, lane)
        if ownership.failure:
            return r.fail(ownership.error or "ready reservation ownership failed")
        receipt = self._format_receipt(
            bead=bead,
            operation=c.Infra.WorkOperation.START,
            primary=primary_root,
            worktree=str(lane),
            branch=branch,
            base=base,
            head_oid=head.value,
            pr="",
        )
        epic_selector = f" EPIC={epic_bead}" if epic_bead else ""
        return r.ok(
            f"LANE_ID={bead} BRANCH={branch} WORKTREE={lane} "
            f"BASE={base} HEAD={head.value}{epic_selector}\n{receipt}"
        )


__all__: list[str] = ["FlextInfraWorkSagaStart"]
