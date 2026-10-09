"""Release orchestration service: one repository, one phase, one typed result.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, override

from flext_infra import c, m, p, r, t, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.release._release_plan import FlextInfraReleasePlanMixin


class FlextInfraReleaseOrchestrator(FlextInfraReleasePlanMixin):
    """Run one phase of the release protocol against the repository root.

    The version lives only in ``pyproject.toml``; the protocol derives every
    change from merged pull-request titles and is its sole writer.
    """

    phase: Annotated[
        c.Infra.ReleasePhase,
        m.Field(description="Release phase to execute"),
    ] = c.Infra.ReleasePhase.PLAN
    index: Annotated[
        bool,
        m.Field(description="Publish receipt-verified artifacts to the package index"),
    ] = False
    pr_title: Annotated[
        str,
        m.Field(description="Pull-request title to validate against the protocol"),
    ] = ""
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
        """Resolve the declared version once and dispatch the selected phase.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        current = u.Infra.current_workspace_version(self.root)
        if current.failure:
            return r[bool].from_failure(current)
        ctx = m.Infra.ReleasePhaseDispatchConfig(
            phase=self.phase,
            repository_root=self.root,
            version=current.value,
            tag=c.Infra.TAG_FORMAT.format(version=current.value),
            project_names=self.project_names or (),
            dry_run=self.effective_dry_run,
            index=self.index,
            pr_title=self.pr_title,
        )
        self.logger.info(
            "release_phase_started",
            phase=str(ctx.phase),
            current=ctx.version,
        )
        match ctx.phase:
            case c.Infra.ReleasePhase.PLAN:
                return self.phase_plan(ctx).map(lambda _plan: True)
            case c.Infra.ReleasePhase.VERSION:
                return self.phase_version(ctx)
            case c.Infra.ReleasePhase.TAG:
                return self.phase_tag(ctx)
            case c.Infra.ReleasePhase.BUILD:
                return self.phase_build(ctx)
            case c.Infra.ReleasePhase.PUBLISH:
                return self.phase_publish(ctx)

    def phase_version(self, ctx: m.Infra.ReleasePhaseDispatchConfig) -> p.Result[bool]:
        """Open or update the release pull request for the planned version.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        root = ctx.repository_root
        plan = self.phase_plan(ctx)
        if plan.failure:
            return r[bool].from_failure(plan)
        if not plan.value.releasable:
            self.logger.info("release_version_none", current=ctx.version)
        if not plan.value.releasable or ctx.dry_run:
            return r[bool].ok(value=True)
        exists = u.Cli.capture([c.Infra.GIT, "tag", "-l", plan.value.tag], cwd=root)
        if exists.failure:
            return r[bool].from_failure(exists)
        if exists.value.strip():
            return r[bool].fail(f"release tag already exists: {plan.value.tag}")
        integration = self._integration_branch(root)
        if integration.failure:
            return r[bool].from_failure(integration)
        published = u.Infra.git_publish_lane(
            m.Infra.GitLaneRequest(
                repo_root=root,
                branch=c.Infra.RELEASE_BRANCH,
                base=integration.value,
                subject=c.Infra.RELEASE_COMMIT_SUBJECT.format(version=plan.value.next),
                body_file=self._release_dir(root, plan.value.tag)
                / c.Infra.RELEASE_NOTES_FILENAME,
            ),
            lambda: self._stamp_release(ctx, plan.value),
        )
        if published.success:
            self.logger.info("release_version_pull_request", version=plan.value.next)
        return published

    def _stamp_release(
        self,
        ctx: m.Infra.ReleasePhaseDispatchConfig,
        plan: m.Infra.ReleasePlan,
    ) -> p.Result[bool]:
        """Write the version SSOT, settle its projections, then the release notes.

        Ordering version -> conform -> lock -> notes makes each step a pure
        function of the SSOT already on disk: conform settles pyproject.toml's
        dependencies and every rendered projection (docs render the version),
        the lock then matches them without upgrading anything, and the
        packaged-project list the notes name is the settled tree's. A rerun
        against an unchanged SSOT regenerates identical bytes.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        root = ctx.repository_root
        stamped = u.Infra.replace_project_version(root, plan.next)
        if stamped.failure:
            return stamped
        settled = FlextInfraCodegenConform.settle_repository(
            root,
            ports=self.conform_collaborators,
        )
        if settled.failure:
            return settled
        projects = u.Infra.resolve_projects(root, ctx.project_names)
        if projects.failure:
            return r[bool].from_failure(projects)
        notes = self._release_dir(root, plan.tag) / c.Infra.RELEASE_NOTES_FILENAME
        generated = u.Infra.generate_notes(
            plan.next,
            plan.tag,
            projects.value,
            "\n".join(plan.merges),
            notes,
        )
        if generated.failure:
            return generated
        return u.Infra.update_changelog(root, plan.next, plan.tag, notes)

    @classmethod
    def phase_tag(cls, ctx: m.Infra.ReleasePhaseDispatchConfig) -> p.Result[bool]:
        """Tag the merged release commit; idempotent when the tag already points here.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        root = ctx.repository_root
        head = u.Cli.capture(
            [c.Infra.GIT, "log", "-1", "--format=%s%n%H", c.Infra.GIT_HEAD],
            cwd=root,
        )
        if head.failure:
            return r[bool].from_failure(head)
        subject, _, head_oid = head.value.strip().partition("\n")
        located = cls._release_commit_oid(root, ctx.version, subject, head_oid)
        if located.failure:
            return r[bool].from_failure(located)
        subject, oid = located.value
        if ctx.dry_run:
            return r[bool].ok(value=True)
        existing = u.Cli.capture(
            [c.Infra.GIT, "rev-list", "-n", "1", ctx.tag],
            cwd=root,
        )
        if existing.success and existing.value.strip():
            if existing.value.strip() != oid:
                return r[bool].fail(f"release tag {ctx.tag} already points elsewhere")
        else:
            created = u.Cli.run_checked(
                # Tag the release commit's own oid: when HEAD moved past it
                # (hot lane), the tag must still mark the released state.
                [
                    c.Infra.GIT,
                    "tag",
                    "-a",
                    ctx.tag,
                    "-m",
                    f"release: {ctx.tag}",
                    oid,
                ],
                cwd=root,
            )
            if created.failure:
                return created
        return u.Cli.run_checked(
            [c.Infra.GIT, "push", c.Infra.GIT_ORIGIN, ctx.tag],
            cwd=root,
        )

    @staticmethod
    def _release_commit_oid(
        root: Path,
        version: str,
        subject: str,
        head_oid: str,
    ) -> p.Result[t.Pair[str, str]]:
        """Locate the merged release commit, or fail loud when it is absent.

        A hot integration lane keeps landing after the release commit: the
        contract is to tag the MERGED release commit wherever it now sits,
        not to demand the lane stop. Locate it in history and fail loud only
        when it truly is not there.

        Returns:
            The resulting ``(subject, oid)`` pair of the release commit.

        """
        result_type = r[t.Pair[str, str]]
        if u.Infra.release_subject(subject, version):
            return result_type.ok((subject, head_oid))
        expected = c.Infra.RELEASE_COMMIT_SUBJECT.format(version=version)
        located = u.Cli.capture(
            [
                c.Infra.GIT,
                "log",
                f"--grep={expected}",
                "-n",
                "1",
                "--format=%H",
                c.Infra.GIT_HEAD,
            ],
            cwd=root,
        )
        if located.failure:
            return result_type.from_failure(located)
        located_oid = located.value.strip()
        if not located_oid:
            return result_type.fail(
                f"release tag requires the release commit {expected!r} in "
                f"history, found head subject {subject!r}",
            )
        return result_type.ok((subject, located_oid))


__all__: list[str] = ["FlextInfraReleaseOrchestrator"]
