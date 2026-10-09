"""Member propagation: this workspace's flext-infra, one pull request per member.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, override

from flext_infra import c, config, m, p, r, u
from flext_infra.base import s
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraWorkspacePropagation(s[bool]):
    """Carry this workspace's flext-infra projections and locks to every member.

    Each governed member is settled (conform, then lock) inside its own
    publication lane; a member whose projections and lock do not change
    publishes nothing. The first failure ends the run, nothing is merged, and
    every member checkout is left on its integration branch, so a rerun
    continues the same lanes and commits nothing new.
    """

    conform_collaborators: Annotated[
        m.Infra.CodegenConformPorts | None,
        m.Field(
            exclude=True,
            description=(
                "Docs port bound by the FlextInfra facade; the settling "
                "conform fails before any effect without it"
            ),
        ),
    ] = None

    @override
    def execute(self) -> p.Result[bool]:
        """Propagate to every generated member in declared order.

        Returns:
            The resulting ``p.Result[bool]``.

        """
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
        propagated = self._propagate_members(workspace, revision.value.strip())
        if propagated.failure:
            return propagated
        for consumer in workspace.external_consumers:
            propagated = self._propagate_external_consumer(
                workspace,
                consumer,
                revision.value.strip(),
            )
            if propagated.failure:
                return propagated
        return r[bool].ok(value=True)

    def _propagate_members(
        self,
        workspace: m.Infra.WorkspaceSpec,
        revision: str,
    ) -> p.Result[bool]:
        """Preflight every generated member's lock owner, then propagate each.

        Generation rewrites only mutable internal FLEXT repositories. Before
        the first lane opens, every one of them must own its lock: a member uv
        resolves inside an enclosing uv workspace would settle by rewriting the
        workspace lock instead of its own, so the run stops before any effect.

        Returns:
            True when every member propagated, else the first failure.

        """
        members = tuple(
            member
            for member in workspace.subprojects
            if member.kind is c.Infra.ProjectKind.INTERNAL_FLEXT
            and member.codegen is not c.Infra.CodegenKind.NONE
            and not member.read_only
        )
        for member in members:
            owned = FlextInfraCodegenConform.require_own_lock(self.root / member.path)
            if owned.failure:
                return r[bool].from_failure(owned)
        for member in members:
            propagated = self._propagate_member(workspace, member, revision)
            if propagated.failure:
                return propagated
        return r[bool].ok(value=True)

    def _propagate_external_consumer(
        self,
        workspace: m.Infra.WorkspaceSpec,
        consumer: m.Infra.ExternalConsumerSpec,
        revision: str,
    ) -> p.Result[bool]:
        """Advance one external consumer's lane through its own make verbs.

        The consumer's checkout keeps its governance: propagation only runs
        the consumer's declared canonical verbs inside its own lane branch and
        publishes nothing when the run changes nothing.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        consumer_root = consumer.root
        if not consumer_root.is_dir():
            return r[bool].fail(
                f"external consumer root does not exist: {consumer_root}",
            )
        base = u.Infra.resolve_integration_branch(
            consumer_root,
            preference=config.Infra.codegen.branch_policy.integration_branch_preference,
            declared=consumer.integration_branch,
        )
        if base.failure:
            return r[bool].from_failure(base)
        body = self._write_external_body(workspace, consumer, revision)
        if body.failure:
            return r[bool].from_failure(body)
        published = u.Infra.git_publish_lane(
            m.Infra.GitLaneRequest(
                repo_root=consumer_root,
                branch=c.Infra.PROPAGATION_BRANCH,
                base=base.value,
                subject=c.Infra.PROPAGATION_COMMIT_SUBJECT,
                body_file=body.value,
            ),
            lambda: self._settle_external_consumer(consumer),
        )
        if published.failure:
            return published
        self.logger.info(
            "propagation_external_consumer",
            consumer=consumer.name,
            published=published.value,
        )
        if not published.value:
            return published
        return u.Cli.run_checked([c.Infra.GIT, "switch", base.value], cwd=consumer_root)

    @staticmethod
    def _settle_external_consumer(
        consumer: m.Infra.ExternalConsumerSpec,
    ) -> p.Result[bool]:
        """Run the consumer's declared canonical verbs once, in order.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        verbs: list[str] = []
        if consumer.advance_locks:
            verbs.append("upg")
        verbs.append("gen")
        if consumer.fix_namespace:
            verbs.append("fix-namespace")
        if consumer.fix_accessors:
            verbs.append("fix-accessors")
        verbs.extend(("fix", "fmt"))
        for verb in verbs:
            settled = u.Cli.run_checked(
                [c.Infra.MAKE, verb],
                cwd=consumer.root,
            )
            if settled.failure:
                return r[bool].from_failure(settled)
        return r[bool].ok(value=True)

    def _write_external_body(
        self,
        workspace: m.Infra.WorkspaceSpec,
        consumer: m.Infra.ExternalConsumerSpec,
        revision: str,
    ) -> p.Result[Path]:
        """Write the external consumer's pull-request body under the reports.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        directory = u.Cli.ensure_dir(
            u.Cli.resolve_report_dir(
                self.root,
                c.Infra.PROJECT,
                c.Infra.PROPAGATION_REPORT_KEY,
            ),
        )
        if directory.failure:
            return r[Path].from_failure(directory)
        body = directory.value / f"external-{consumer.name}.md"
        written = u.Cli.files_write_text(
            body,
            f"# Propagate the workspace flext-infra to {consumer.name}\n\n"
            f"`make propagate` at `{workspace.repository.name}` {revision} "
            "advanced this consumer's lane through its own canonical verbs "
            "(upg, gen, fix-namespace, fix-accessors, fix, fmt). Nothing else"
            " changed.\n",
        )
        return written.map(lambda _written: body)

    def _propagate_member(
        self,
        workspace: m.Infra.WorkspaceSpec,
        member: m.Infra.RepositoryRef,
        revision: str,
    ) -> p.Result[bool]:
        """Publish one member's settled projections, then return it to its base.

        Returns:
            The resulting ``p.Result[bool]``.

        """
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
            lambda: FlextInfraCodegenConform.settle_repository(
                member_root,
                ports=self.conform_collaborators,
                refresh_git_peers=True,
            ),
        )
        if published.failure:
            return published
        self.logger.info(
            "propagation_member",
            member=member.name,
            published=published.value,
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
        """Write the member's pull-request body under the workspace reports.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        directory = u.Cli.ensure_dir(
            u.Cli.resolve_report_dir(
                self.root,
                c.Infra.PROJECT,
                c.Infra.PROPAGATION_REPORT_KEY,
            ),
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
