"""Release orchestration service: one repository, one phase, one typed result."""

from __future__ import annotations

from typing import Annotated, override

from flext_core import r
from flext_infra import c, m, p, u
from flext_infra.codegen.conform import FlextInfraCodegenConform

from ._release_plan import FlextInfraReleasePlanMixin


class FlextInfraReleaseOrchestrator(FlextInfraReleasePlanMixin):
    """Run one phase of the release protocol against the repository root.

    The version lives only in ``pyproject.toml``; the protocol derives every
    change from merged pull-request titles and is its sole writer.
    """

    phase: Annotated[
        c.Infra.ReleasePhase, m.Field(description="Release phase to execute")
    ] = c.Infra.ReleasePhase.PLAN
    index: Annotated[
        bool,
        m.Field(description="Publish receipt-verified artifacts to the package index"),
    ] = False
    pr_title: Annotated[
        str, m.Field(description="Pull-request title to validate against the protocol")
    ] = ""

    @override
    def execute(self) -> p.Result[bool]:
        """Resolve the declared version once and dispatch the selected phase."""
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
            "release_phase_started", phase=str(ctx.phase), current=ctx.version
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
        """Open or update the release pull request for the planned version."""
        root = ctx.repository_root
        plan = self.phase_plan(ctx)
        if plan.failure:
            return r[bool].from_failure(plan)
        if not plan.value.releasable:
            self.logger.info("release_version_none", current=ctx.version)
            return r[bool].ok(True)
        if ctx.dry_run:
            return r[bool].ok(True)
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
        self, ctx: m.Infra.ReleasePhaseDispatchConfig, plan: m.Infra.ReleasePlan
    ) -> p.Result[bool]:
        """Write the version SSOT, settle its projections, then the release notes.

        Ordering version -> conform -> lock -> notes makes each step a pure
        function of the SSOT already on disk: conform settles pyproject.toml's
        dependencies and every rendered projection (docs render the version),
        the lock then matches them without upgrading anything, and the
        packaged-project list the notes name is the settled tree's. A rerun
        against an unchanged SSOT regenerates identical bytes.
        """
        root = ctx.repository_root
        stamped = u.Infra.replace_project_version(root, plan.next)
        if stamped.failure:
            return stamped
        settled = FlextInfraCodegenConform.settle_repository(root)
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
            "\n".join(f"- {subject}" for subject in plan.merges),
            notes,
        )
        if generated.failure:
            return generated
        return u.Infra.update_changelog(root, plan.next, plan.tag, notes)

    def phase_tag(self, ctx: m.Infra.ReleasePhaseDispatchConfig) -> p.Result[bool]:
        """Tag the merged release commit; idempotent when the tag already points here."""
        root = ctx.repository_root
        head = u.Cli.capture(
            [c.Infra.GIT, "log", "-1", "--format=%s%n%H", c.Infra.GIT_HEAD], cwd=root
        )
        if head.failure:
            return r[bool].from_failure(head)
        subject, _, oid = head.value.strip().partition("\n")
        if not u.Infra.is_release_subject(subject, ctx.version):
            expected = c.Infra.RELEASE_COMMIT_SUBJECT.format(version=ctx.version)
            return r[bool].fail(
                f"release tag requires HEAD to be the release commit {expected!r}, "
                f"found {subject!r}"
            )
        if ctx.dry_run:
            return r[bool].ok(True)
        existing = u.Cli.capture(
            [c.Infra.GIT, "rev-list", "-n", "1", ctx.tag], cwd=root
        )
        if existing.success and existing.value.strip():
            if existing.value.strip() != oid:
                return r[bool].fail(f"release tag {ctx.tag} already points elsewhere")
        else:
            created = u.Cli.run_checked(
                [c.Infra.GIT, "tag", "-a", ctx.tag, "-m", f"release: {ctx.tag}"],
                cwd=root,
            )
            if created.failure:
                return created
        return u.Cli.run_checked(
            [c.Infra.GIT, "push", c.Infra.GIT_ORIGIN, ctx.tag], cwd=root
        )


__all__: list[str] = ["FlextInfraReleaseOrchestrator"]
