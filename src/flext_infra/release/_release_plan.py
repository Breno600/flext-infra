"""Release plan phase: the next version, derived only from Git and its titles."""

from __future__ import annotations

from pathlib import Path

from flext_core import r
from flext_infra import c, config, m, p, t, u

from ._release_publish import FlextInfraReleasePublishMixin


class FlextInfraReleasePlanMixin(FlextInfraReleasePublishMixin):
    """Decide the release and prove no version changed outside the protocol."""

    def phase_plan(
        self, ctx: m.Infra.ReleasePhaseDispatchConfig
    ) -> p.Result[m.Infra.ReleasePlan]:
        """Derive the next version and record it as the plan receipt."""
        root = ctx.repository_root
        if ctx.pr_title and not c.Infra.CONVENTIONAL_SUBJECT_RE.match(ctx.pr_title):
            return r[m.Infra.ReleasePlan].fail(
                "pull-request title must follow Conventional Commits "
                f"(type(scope)!: description): {ctx.pr_title!r}"
            )
        guard = self._guard_version_change(root, ctx.version)
        if guard.failure:
            return r[m.Infra.ReleasePlan].from_failure(guard)
        plan = self._derive_plan(root, ctx.version)
        if plan.failure:
            return plan
        written = u.Cli.json_write(
            self._release_dir(root) / c.Infra.RELEASE_PLAN_FILENAME,
            plan.value.model_dump(mode="json", exclude_computed_fields=True),
            m.Cli.JsonWriteOptions(sort_keys=True),
        )
        if written.failure:
            return r[m.Infra.ReleasePlan].from_failure(written)
        self.logger.info(
            "release_plan",
            current=plan.value.current,
            next=plan.value.next,
            bump=str(plan.value.bump),
            releasable=plan.value.releasable,
        )
        return plan

    @classmethod
    def _derive_plan(cls, root: Path, current: str) -> p.Result[m.Infra.ReleasePlan]:
        """Apply the protocol's decision rules to the repository state."""
        tags = u.Cli.capture(
            [
                c.Infra.GIT,
                "tag",
                "--list",
                c.Infra.TAG_FORMAT.format(version="*"),
                "--sort=-version:refname",
            ],
            cwd=root,
        )
        if tags.failure:
            return r[m.Infra.ReleasePlan].from_failure(tags)
        latest = next((line for line in tags.value.splitlines() if line), "")
        # Why: CI plans on the pull request's synthetic merge commit, so the
        # merged release commit is looked up in the whole history since the tag.
        history = cls._subjects(root, latest, merges_only=False)
        if history.failure:
            return r[m.Infra.ReleasePlan].from_failure(history)
        if latest != c.Infra.TAG_FORMAT.format(version=current) and any(
            u.Infra.is_release_subject(subject, current) for subject in history.value
        ):
            # The release commit is merged and awaits its tag: nothing to bump.
            return r[m.Infra.ReleasePlan].ok(
                m.Infra.ReleasePlan(
                    current=current,
                    next=current,
                    bump=c.Infra.VersionBump.NONE,
                    previous_tag=latest or None,
                )
            )
        final = u.Infra.finalize_version(current)
        if final.failure:
            return r[m.Infra.ReleasePlan].from_failure(final)
        # A pre-release segment is kept: ``0.12.0`` is ahead of ``v0.12.0rc2``.
        ahead = (
            u.Infra.version_is_newer(
                final.value, latest.removeprefix(c.Infra.TAG_FORMAT.format(version=""))
            )
            if latest
            else r[bool].ok(True)
        )
        if ahead.failure:
            return r[m.Infra.ReleasePlan].from_failure(ahead)
        if ahead.value or final.value != current:
            # A first release, a declared pre-release or a declared version
            # beyond the last tag was decided when the version was written:
            # the titles merged since the tag are not consulted.
            return r[m.Infra.ReleasePlan].ok(
                m.Infra.ReleasePlan(
                    current=current,
                    next=final.value,
                    bump=c.Infra.VersionBump.NONE,
                    previous_tag=latest or None,
                    declared=True,
                )
            )
        merges = cls._subjects(root, latest, merges_only=True)
        if merges.failure:
            return r[m.Infra.ReleasePlan].from_failure(merges)
        bump = u.Infra.plan_bump(merges.value, config.Infra.release.bump_types)
        if bump.failure:
            return r[m.Infra.ReleasePlan].from_failure(bump)
        return u.Infra.bump_version(current, bump.value).map(
            lambda next_version: m.Infra.ReleasePlan(
                current=current,
                next=next_version,
                bump=bump.value,
                previous_tag=latest,
                merges=tuple(merges.value),
            )
        )

    @classmethod
    def _guard_version_change(cls, root: Path, version: str) -> p.Result[bool]:
        """Reject a pyproject version that differs from the integration base.

        The only legitimate diff is the protocol's release commit, looked up in
        the whole base..HEAD range: CI checks out a synthetic merge commit and
        an open release lane may carry integration merges above it.
        """
        branch = cls._integration_branch(root)
        if branch.failure:
            return r[bool].from_failure(branch)
        base = u.Cli.capture(
            [
                c.Infra.GIT,
                "merge-base",
                f"{c.Infra.GIT_ORIGIN}/{branch.value}",
                c.Infra.GIT_HEAD,
            ],
            cwd=root,
        )
        head = u.Cli.capture([c.Infra.GIT, "rev-parse", c.Infra.GIT_HEAD], cwd=root)
        if base.failure or head.failure:
            return r[bool].from_failure(base if base.failure else head)
        base_oid, head_oid = base.value.strip(), head.value.strip()
        if base_oid == head_oid:
            return r[bool].ok(True)
        content = u.Cli.capture(
            [c.Infra.GIT, "show", f"{base_oid}:{c.PYPROJECT_FILENAME}"], cwd=root
        )
        if content.failure:
            return r[bool].from_failure(content)
        match = c.Infra.VERSION_RE.search(content.value)
        base_version = match.group(1) if match else ""
        subjects = cls._subjects(root, base_oid, merges_only=False)
        if subjects.failure:
            return r[bool].from_failure(subjects)
        if base_version == version or any(
            u.Infra.is_release_subject(subject, version) for subject in subjects.value
        ):
            return r[bool].ok(True)
        subject = c.Infra.RELEASE_COMMIT_SUBJECT.format(version=version)
        return r[bool].fail(
            f"{c.PYPROJECT_FILENAME} version changed outside the release "
            f"protocol: {base_version} -> {version} (HEAD {head_oid[:12]} "
            f"carries no {subject!r}); run `make release WHAT=version` instead"
        )

    @staticmethod
    def _integration_branch(root: Path) -> p.Result[str]:
        """Resolve the published integration branch this repository releases from."""
        return u.Infra.repository_baseline_branch(
            root,
            preference=tuple(
                config.Infra.codegen.branch_policy.integration_branch_preference
            ),
        )

    @staticmethod
    def _subjects(
        root: Path, since: str, *, merges_only: bool
    ) -> p.Result[t.VariadicTuple[str]]:
        """Return commit subjects reachable from HEAD since ``since``.

        Merge commits carry the pull-request titles the bump derives from.
        """
        log = u.Cli.capture(
            [
                c.Infra.GIT,
                "log",
                *(("--merges",) if merges_only else ()),
                "--format=%s",
                f"{since}..{c.Infra.GIT_HEAD}",
            ],
            cwd=root,
        )
        return log.map(
            lambda text: tuple(line for line in text.splitlines() if line.strip())
        )


__all__: list[str] = ["FlextInfraReleasePlanMixin"]
