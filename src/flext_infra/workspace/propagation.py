"""Member propagation: this workspace's flext-infra, one pull request per member."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import c, config, m, p, s, u
from flext_infra.codegen.conform import FlextInfraCodegenConform

from .detector import FlextInfraWorkspaceDetector

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraWorkspacePropagation(s[bool]):
    """Carry this workspace's flext-infra projections and locks to every member.

    Each governed member is settled (conform, then lock) inside its own
    publication lane; a member whose projections and lock do not change
    publishes nothing. The first failure ends the run, nothing is merged, and
    every member checkout is left on its integration branch, so a rerun
    continues the same lanes and commits nothing new.
    """

    @override
    def execute(self) -> p.Result[bool]:
        """Propagate to every generated member in declared order."""
        root = self.root
        loaded = FlextInfraWorkspaceDetector.load_workspace_spec(root)
        if loaded.failure:
            return r[bool].from_failure(loaded)
        workspace = loaded.value
        if workspace.repository.role is not c.Infra.MakeProfile.WORKSPACE:
            return r[bool].fail(f"propagation requires a workspace root: {root}")
        revision = u.Cli.capture([c.Infra.GIT, "rev-parse", c.Infra.GIT_HEAD], cwd=root)
        if revision.failure:
            return r[bool].from_failure(revision)
        for member in workspace.subprojects:
            # Generation rewrites only mutable internal FLEXT repositories.
            if (
                member.kind is not c.Infra.ProjectKind.INTERNAL_FLEXT
                or member.codegen is c.Infra.CodegenKind.NONE
                or member.read_only
            ):
                continue
            propagated = self._propagate_member(
                workspace, member, revision.value.strip()
            )
            if propagated.failure:
                return propagated
        return r[bool].ok(True)

    def _propagate_member(
        self,
        workspace: m.Infra.WorkspaceSpec,
        member: m.Infra.RepositoryRef,
        revision: str,
    ) -> p.Result[bool]:
        """Publish one member's settled projections, then return it to its base."""
        member_root = self.root / member.path
        base = u.Infra.resolve_integration_branch(
            member_root,
            preference=config.Infra.codegen.branch_policy.integration_branch_preference,
            declared=(
                workspace.integration.branch
                if workspace.integration is not None
                else None
            ),
        )
        if base.failure:
            return r[bool].from_failure(base)
        body = self._write_body(workspace, member, revision)
        if body.failure:
            return r[bool].from_failure(body)
        published = u.Infra.git_publish_lane(
            m.Infra.GitLaneRequest(
                repo_root=member_root,
                branch=c.Infra.PROPAGATION_BRANCH,
                base=base.value,
                subject=c.Infra.PROPAGATION_COMMIT_SUBJECT,
                body_file=body.value,
            ),
            lambda: FlextInfraCodegenConform.settle_repository(member_root),
        )
        if published.failure:
            return published
        self.logger.info(
            "propagation_member", member=member.name, published=published.value
        )
        if not published.value:
            return published
        return u.Cli.run_checked([c.Infra.GIT, "switch", base.value], cwd=member_root)

    def _write_body(
        self,
        workspace: m.Infra.WorkspaceSpec,
        member: m.Infra.RepositoryRef,
        revision: str,
    ) -> p.Result[Path]:
        """Write the member's pull-request body under the workspace reports."""
        directory = u.Cli.ensure_dir(
            u.Cli.resolve_report_dir(
                self.root, c.Infra.PROJECT, c.Infra.PROPAGATION_REPORT_KEY
            )
        )
        if directory.failure:
            return directory
        body = directory.value / f"{member.name}.md"
        written = u.Cli.files_write_text(
            body,
            f"# Propagate the workspace flext-infra to {member.name}\n\n"
            f"`make propagate` at `{workspace.repository.name}` {revision} "
            "settled this member's managed projections (codegen conform) and "
            "its lock (`uv lock`, no upgrade). Nothing else changed.\n",
        )
        return written.map(lambda _written: body)


__all__: list[str] = ["FlextInfraWorkspacePropagation"]
