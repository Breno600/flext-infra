"""make work WHAT=land saga step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import FlextInfraWorktreeService, c, m, u
from flext_infra._utilities.work_saga_common import FlextInfraWorkSagaCommon

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkSagaPublish(FlextInfraWorkSagaCommon):
    """Land step for the public work saga."""

    apply_changes: bool

    def _observe_open_pr(
        self, primary_root: Path, branch: str
    ) -> p.Result[tuple[str, str]]:
        listed = u.Cli.capture(
            (
                "gh",
                "pr",
                "list",
                "--head",
                branch,
                "--state",
                "open",
                "--json",
                "number,url",
            ),
            cwd=primary_root,
        )
        if listed.failure:
            return r.fail(listed.error or "failed to list open PRs")
        rows = json.loads(listed.value or "[]")
        if not rows:
            return r.fail(f"no open PR for head {branch}")
        return r.ok((str(rows[0].get("number", "")), str(rows[0].get("url", ""))))

    def _land(self, primary_root: Path) -> p.Result[str]:
        if not self.apply_changes:
            return r.fail("work land requires --apply")
        bead = (self.bead or "").strip()
        if not bead:
            return r.fail("work land requires --bead")
        shown = u.Infra.beads_show(bead, root=self.workspace_root)
        if shown.failure:
            return r.fail(shown.error or f"unknown bead {bead}")
        metadata = shown.value.metadata
        if metadata is None:
            return r.fail(f"bead {bead} has no lane metadata; run work start first")
        if not isinstance(metadata, m.Infra.ReadyLaneMetadata):
            return r.fail(f"bead {bead} lane is not ready for land")
        branch = metadata.branch
        worktree = str(metadata.worktree)
        recorded_integration = metadata.integration_base
        ownership = self._owned_reservation(bead, branch, metadata.worktree)
        if ownership.failure:
            return r.fail(ownership.error or "work land reservation ownership failed")
        base = self._resolve_integration_base(primary_root)
        if base.failure:
            return r.fail(base.error or "missing integration base")
        integration = base.value
        if isinstance(metadata.topology, m.Infra.ChildLaneTopology):
            live = self._live_child_topology(
                primary_root, shown.value, metadata.topology
            )
            if live.failure:
                return r.fail(live.error or "work land child binding failed")
            integration = metadata.topology.epic_branch
        if (
            recorded_integration
            and recorded_integration not in {"HEAD", integration}
            and recorded_integration != integration
        ):
            return r.fail(
                "work land refuses metadata.integration_base drift: "
                f"metadata={recorded_integration} ssot={integration}"
            )
        permanent = self._refuse_permanent_branch(branch, integration)
        if permanent.failure:
            return r.fail(
                permanent.error or f"work land refuses permanent branch {branch}"
            )
        bound = self._bound_registered_lane(primary_root, branch, worktree)
        if bound.failure:
            return r.fail(bound.error or "work land lane binding failed")
        lane = bound.value
        topology = self._validated_lane_topology(primary_root, metadata, lane)
        if topology.failure:
            return r.fail(topology.error or "work land topology validation failed")
        if isinstance(metadata.topology, m.Infra.EpicLaneTopology):
            children = FlextInfraWorktreeService.registered_children(primary_root, lane)
            if children.failure:
                return r.fail(children.error or "failed to inspect epic child lanes")
            if children.value:
                registered = ", ".join(str(child) for child in children.value)
                return r.fail(
                    f"work land refuses epic while children are registered: {registered}"
                )
        ownership = self._owned_reservation(bead, branch, lane)
        if ownership.failure:
            return r.fail(ownership.error or "work land reservation changed")
        if self._is_primary_path(primary_root, lane):
            return r.fail("work land refuses the primary worktree")
        if not lane.is_dir():
            return r.fail(f"lane worktree missing: {lane}")
        matrix = metadata.matrix
        if matrix is None:
            return r.fail("work land requires matrix metadata")
        matrix_cas = self._validate_matrix_cas(lane, matrix)
        if matrix_cas.failure:
            return r.fail(matrix_cas.error or "work land matrix CAS failed")
        synced = FlextInfraWorktreeService(
            workspace_root=primary_root,
            operation=c.Infra.WorktreeOperation.UPDATE,
            branch=branch,
            base=self._git_integration_ref(primary_root, integration),
            apply_changes=True,
        ).execute()
        if synced.failure:
            return r.fail(synced.error or "work land sync failed")
        if isinstance(metadata.topology, m.Infra.ChildLaneTopology):
            live = self._live_child_topology(
                primary_root, shown.value, metadata.topology
            )
            if live.failure:
                return r.fail(live.error or "work land child binding changed")
        pr_base = integration
        if pr_base == "HEAD":
            resolved_base = u.Infra.git_abbrev_ref_head(
                m.Infra.GitRepoRequest(repo_root=primary_root)
            )
            if resolved_base.failure:
                return r.fail(
                    resolved_base.error or "failed to resolve HEAD for PR base"
                )
            pr_base = resolved_base.value.text
            if not pr_base or pr_base == "HEAD":
                return r.fail(
                    "work land cannot open a PR with unresolved integration base HEAD"
                )
        landed_entries: list[m.Infra.WorkLaneEntry] = []
        for entry in sorted(matrix.entries, key=lambda item: item.project == "."):
            project_root = self._matrix_project_root(lane, entry.project)
            if project_root.failure:
                return r.fail(project_root.error or "matrix project is invalid")
            pushed = u.Infra.git_push_upstream(
                m.Infra.GitPushRequest(
                    repo_root=project_root.value, branch=entry.branch
                )
            )
            if pushed.failure:
                return r.fail(
                    self._push_rejection(
                        project_root.value,
                        entry.branch,
                        pushed.error or f"failed to push {entry.project}",
                    )
                )
            entry_head = self._git_head(project_root.value)
            if entry_head.failure:
                return r.fail(
                    entry_head.error
                    or f"failed to resolve matrix HEAD: {entry.project}"
                )
            pr = u.Infra.run_github_pull_request(
                m.Infra.GithubPullRequestRequest(
                    repo_root=str(project_root.value),
                    action=c.Infra.PullRequestAction.CREATE,
                    base=pr_base,
                    head=entry.branch,
                    title=f"{entry.branch}: lane land",
                    body=f"Automated land for bead {bead} ({entry.branch}).",
                    draft=False,
                )
            )
            observed = self._observe_open_pr(project_root.value, entry.branch)
            if pr.failure and observed.failure:
                return r.fail(pr.error or observed.error or "work land PR failed")
            entry_pr, entry_url = observed.value if observed.success else ("", "")
            landed_entries.append(
                entry.model_copy(
                    update={
                        "head_oid": entry_head.value,
                        "pr_number": entry_pr,
                        "pr_url": entry_url,
                        "state": "landed",
                    }
                )
            )
            if entry.project != ".":
                progress = m.Infra.WorkLaneMatrix(
                    entries=tuple(
                        next(
                            (
                                landed
                                for landed in landed_entries
                                if landed.project == current.project
                            ),
                            current,
                        )
                        for current in matrix.entries
                    )
                )
                checkpoint = u.Infra.beads_update_lane(
                    bead,
                    metadata=metadata.model_copy(update={"matrix": progress}),
                    notes=(
                        "work land progress: "
                        f"project={entry.project} pr={entry_pr or 'pending'} "
                        f"sha={entry_head.value}"
                    ),
                    root=self.workspace_root,
                )
                if checkpoint.failure:
                    return r.fail(
                        checkpoint.error
                        or f"failed to persist land progress for {entry.project}"
                    )
        landed_matrix = m.Infra.WorkLaneMatrix(entries=tuple(landed_entries))
        root_entry = next(
            entry for entry in landed_matrix.entries if entry.project == "."
        )
        head = root_entry.head_oid
        pr_number = root_entry.pr_number
        pr_url = root_entry.pr_url
        updated_metadata = metadata.model_copy(
            update={
                "head_oid": head,
                "integration_base": pr_base,
                "matrix": landed_matrix,
                "pr_number": pr_number or None,
                "pr_url": pr_url or None,
            }
        )
        labels: tuple[str, ...] = ()
        if pr_number:
            labels = (f"pr:{pr_number}",)
        notes = (
            f"work land: cmd=make work WHAT=land cwd={lane} exit=0 "
            f"decisive=PR {pr_url or pr_number or 'pending'} sha={head}"
        )
        updated = u.Infra.beads_update_lane(
            bead,
            metadata=updated_metadata,
            labels=labels,
            notes=notes,
            root=self.workspace_root,
        )
        if updated.failure:
            return r.fail(updated.error or "failed to record land on bead")
        receipt = self._format_receipt(
            bead=bead,
            operation=c.Infra.WorkOperation.LAND,
            primary=primary_root,
            worktree=str(lane),
            branch=branch,
            base=pr_base,
            head_oid=head,
            pr=pr_number,
        )
        return r.ok(
            f"BRANCH={branch} HEAD={head} PR_NUMBER={pr_number} "
            f"PR_URL={pr_url}\n{receipt}"
        )


__all__: list[str] = ["FlextInfraWorkSagaPublish"]
