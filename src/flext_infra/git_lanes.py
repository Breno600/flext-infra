"""Read-only lane admission and hygiene over the canonical Git primitives.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import FlextInfraWorkspaceDetector, c, config, m, p, r, t, u

if TYPE_CHECKING:
    from collections.abc import Iterator


class FlextInfraGitLanes:
    """One evaluator; never fetch, repair, delete, or infer ownership from age."""

    @staticmethod
    def _no_stashes(repo_root: Path) -> p.Result[bool]:
        """Reject stash objects before any lane effects.

        Returns:
            Success only when the canonical stash inventory is empty.

        """
        listed = u.Infra.git_stash_oids(m.Infra.GitRepoRequest(repo_root=repo_root))
        if listed.failure:
            return r[bool].from_failure(listed)
        if listed.value.oids:
            return r[bool].fail("forbidden stashes: " + ", ".join(listed.value.oids))
        return r[bool].ok(value=True)

    @classmethod
    def admit_lane(
        cls,
        repo_root: Path,
        branch: str,
        base_oid: str,
    ) -> p.Result[bool]:
        """Reject stashes/stale bases, including existing branch resumptions.

        Returns:
            Admission proof before directory, ref, index, or WIP mutation.

        """
        stashes = cls._no_stashes(repo_root)
        if stashes.failure:
            return stashes
        fresh = cls.fresh_integration(
            m.Infra.GitLaneVerificationRequest(
                repo_root=repo_root,
            ),
        )
        if fresh.failure:
            return r[bool].from_failure(fresh)
        if base_oid != fresh.value:
            return r[bool].fail(
                f"stale lane base: requested={base_oid} fresh={fresh.value}",
            )
        return cls._existing_lane(repo_root, branch, fresh.value)

    @staticmethod
    def _existing_lane(repo_root: Path, branch: str, fresh: str) -> p.Result[bool]:
        """Prove the effective tip used when resuming an existing branch.

        Returns:
            Whether the actual lane tip contains the fresh integration object.

        """
        remote = config.Infra.codegen.branch_policy.lane_remote
        for namespace in ("refs/heads", f"refs/remotes/{remote}"):
            heads = u.Infra.git_ref_heads(
                m.Infra.GitRefHeadsRequest(
                    repo_root=repo_root,
                    namespace=namespace,
                ),
            )
            if heads.failure:
                return r[bool].from_failure(heads)
            if branch in heads.value.heads:
                consumes = u.Infra.git_is_ancestor(
                    m.Infra.GitAncestryRequest(
                        repo_root=repo_root,
                        ancestor=fresh,
                        descendant=heads.value.heads[branch],
                    ),
                )
                if consumes.failure:
                    return r[bool].from_failure(consumes)
                if not consumes.value.value:
                    return r[bool].fail(
                        f"existing lane has stale base: {namespace}/{branch}",
                    )
                break
        return r[bool].ok(value=True)

    @classmethod
    def verify_retirement(cls, repo_root: Path, branch: str) -> p.Result[bool]:
        """Require published integration ancestry before the removal boundary.

        Returns:
            Proof the lane tip is contained in the live integration commit.

        """
        fresh = cls.fresh_integration(
            m.Infra.GitLaneVerificationRequest(
                repo_root=repo_root,
            ),
        )
        if fresh.failure:
            return r[bool].from_failure(fresh)
        integrated = u.Infra.git_is_ancestor(
            m.Infra.GitAncestryRequest(
                repo_root=repo_root,
                ancestor=f"{c.Infra.GIT_REFS_HEADS}{branch}",
                descendant=fresh.value,
            ),
        )
        if integrated.failure:
            return r[bool].from_failure(integrated)
        if not integrated.value.value:
            return r[bool].fail(
                "retirement refuses unintegrated lane: "
                f"{c.Infra.GIT_REFS_HEADS}{branch}",
            )
        return r[bool].ok(value=True)

    @staticmethod
    def fresh_integration(request: m.Infra.GitLaneVerificationRequest) -> p.Result[str]:
        """Prove the locally available integration object is the live remote tip.

        Returns:
            The fresh integration commit OID, or the original read failure.

        """
        policy = config.Infra.codegen.branch_policy
        base = u.Infra.resolve_integration_branch(
            request.repo_root,
            preference=policy.integration_branch_preference,
            declared=request.declared,
        )
        if base.failure:
            return r[str].from_failure(base)
        remote = u.Infra.git_remote_branch_oid(
            m.Infra.GitRemoteBranchRequest(
                repo_root=request.repo_root,
                remote=policy.lane_remote,
                branch=base.value,
            ),
        )
        if remote.failure:
            return r[str].from_failure(remote)
        if not remote.value.text:
            return r[str].fail(f"integration branch is absent remotely: {base.value}")
        local = u.Infra.git_resolve_commit(
            m.Infra.GitCommitishRequest(
                repo_root=request.repo_root,
                commitish=(
                    f"{c.Infra.GIT_REFS_REMOTES}{policy.lane_remote}/{base.value}"
                ),
            ),
        )
        if local.failure:
            return r[str].from_failure(local)
        if local.value.oid != remote.value.text:
            return r[str].fail(
                f"stale integration: refs/remotes/{policy.lane_remote}/{base.value} "
                f"local={local.value.oid} remote={remote.value.text}; "
                "coordinator synchronization required (no fetch in this guard)",
            )
        return r[str].ok(remote.value.text)

    @classmethod
    def _evidence(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
    ) -> p.Result[m.Infra.GitLaneEvidence]:
        """Parse coordinator evidence or query the selected public tracker/provider.

        Returns:
            Repository-bound typed evidence; read/provider failures never become empty.

        """
        if request.evidence_file is not None:
            return cls._receipt_evidence(request)
        pull_requests: tuple[m.Infra.GitLanePullRequest, ...] | None = None
        beads: tuple[m.Infra.GitLaneBead, ...] | None = None
        if request.read_pull_requests:
            wire = cls._read_ownership(
                (
                    c.Infra.GH,
                    "pr",
                    "list",
                    "--state",
                    "open",
                    "--limit",
                    str(config.Infra.codegen.branch_policy.lane_pr_limit),
                    "--json",
                    "number,headRefName,updatedAt",
                ),
                request.repo_root,
            )
            if wire.failure:
                return r[m.Infra.GitLaneEvidence].from_failure(wire)
            pull_requests = u.TypeAdapter(
                tuple[m.Infra.GitLanePullRequest, ...],
            ).validate_json(wire.value)
        if request.read_beads:
            wire = cls._selected_beads(request.repo_root)
            if wire.failure:
                return r[m.Infra.GitLaneEvidence].from_failure(wire)
            beads = u.TypeAdapter(tuple[m.Infra.GitLaneBead, ...]).validate_json(
                wire.value,
            )
        evidence = m.Infra.GitLaneEvidence(
            repo_root=request.repo_root,
            captured_at=datetime.now(UTC),
            pull_requests=pull_requests,
            beads=beads,
        )
        if pull_requests is not None and len(pull_requests) >= (
            config.Infra.codegen.branch_policy.lane_pr_limit
        ):
            return r[m.Infra.GitLaneEvidence].fail("PR inventory limit reached")
        return r[m.Infra.GitLaneEvidence].ok(evidence)

    @staticmethod
    def _read_ownership(command: t.StrSequence, cwd: Path) -> p.Result[str]:
        """Execute one explicitly selected public read, without retries or startup.

        Returns:
            Public JSON wire output for typed ingress or its first causal failure.

        """
        run = u.Cli.run_raw(command, cwd=cwd, timeout=c.Infra.TIMEOUT_SHORT)
        if run.failure:
            return r[str].from_failure(run)
        if run.value.outcome.raw_return_code != 0:
            return r[str].fail(
                f"selected ownership read failed: cwd={cwd} command={tuple(command)} "
                f"exit={run.value.outcome.raw_return_code}: {run.value.stderr}",
            )
        return r[str].ok(run.value.stdout)

    @classmethod
    def _selected_beads(cls, repo_root: Path) -> p.Result[str]:
        """Resolve the selected tracker through its existing typed config owner.

        Returns:
            Bead ownership output from the declared city/rig command only.

        """
        loaded = FlextInfraWorkspaceDetector.load_beads_spec(repo_root)
        if loaded.failure:
            return r[str].from_failure(loaded)
        spec = loaded.value
        if not spec.ownership_command_prefix or spec.ownership_command_cwd is None:
            return r[str].fail(
                "selected Beads ownership backend requires ownership_command_prefix "
                f"and ownership_command_cwd in {repo_root}/config/beads.yaml",
            )
        declared_cwd = spec.ownership_command_cwd.expanduser()
        cwd = declared_cwd if declared_cwd.is_absolute() else repo_root / declared_cwd
        return cls._read_ownership(
            (
                *spec.ownership_command_prefix,
                "--readonly",
                "list",
                "--all",
                "--flat",
                "--limit",
                "0",
                "--json",
            ),
            cwd.resolve(),
        )

    @staticmethod
    def _receipt_evidence(
        request: m.Infra.GitLaneVerificationRequest,
    ) -> p.Result[m.Infra.GitLaneEvidence]:
        """Validate the identity and freshness of explicitly selected evidence.

        Returns:
            The typed receipt or a precise refusal, never live-looking stale data.

        """
        if request.evidence_file is None:
            return r[m.Infra.GitLaneEvidence].fail(
                "coordinator evidence file is required",
            )
        evidence = m.Infra.GitLaneEvidence.model_validate_json(
            request.evidence_file.read_text(encoding=c.Cli.ENCODING_DEFAULT),
        )
        if evidence.repo_root.resolve() != request.repo_root.resolve():
            return r[m.Infra.GitLaneEvidence].fail("lane evidence repository mismatch")
        policy = FlextInfraGitLanes._activity_policy(request)
        age = (datetime.now(UTC) - evidence.captured_at).total_seconds()
        if not 0 <= age <= policy.abandonment_threshold_minutes * 60:
            return r[m.Infra.GitLaneEvidence].fail("stale/future ownership receipt")
        return r[m.Infra.GitLaneEvidence].ok(evidence)

    @staticmethod
    def _activity_policy(
        request: m.Infra.GitLaneVerificationRequest,
    ) -> m.Infra.GitLaneCoordinationPolicy:
        """Read the selected/configured global policy without a local threshold.

        Returns:
            The actual global coordination SSOT; read/validation failures escape.

        """
        source = (
            request.governance_file
            if request.governance_file is not None
            else config.Infra.codegen.branch_policy.lane_governance_file
        )
        return m.Infra.GitLaneGovernance.model_validate_json(
            source.expanduser().read_text(encoding=c.Cli.ENCODING_DEFAULT),
        ).coordination

    @staticmethod
    def _ownership(
        evidence: m.Infra.GitLaneEvidence,
        branch: str,
        path: Path | None,
    ) -> tuple[m.Infra.GitLaneBead, ...]:
        """Correlate all matching tracker rows rather than guessing one owner.

        Returns:
            Beads explicitly declaring the branch or registered worktree path.

        """
        if evidence.beads is None:
            return ()
        return tuple(
            bead
            for bead in evidence.beads
            if bead.metadata is not None
            and (
                (
                    branch in {bead.metadata.branch, bead.metadata.work_branch}
                    and bool(branch)
                    and str(evidence.repo_root)
                    in {bead.metadata.work_dir, bead.metadata.gc_work_dir}
                )
                or (
                    path is not None
                    and str(path)
                    in {
                        bead.metadata.work_dir,
                        bead.metadata.gc_work_dir,
                    }
                    and (
                        not branch
                        or not (bead.metadata.branch or bead.metadata.work_branch)
                        or branch in {bead.metadata.branch, bead.metadata.work_branch}
                    )
                )
            )
        )

    @staticmethod
    def _lane_branch(reference: str) -> str:
        """Strip the local or lane-remote namespace from one lane reference.

        Returns:
            The bare branch name the reference designates.

        """
        remote = config.Infra.codegen.branch_policy.lane_remote
        return reference.removeprefix(c.Infra.GIT_REFS_HEADS).removeprefix(
            f"{c.Infra.GIT_REFS_REMOTES}{remote}/",
        )

    @classmethod
    def _unique_ref(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        evidence: m.Infra.GitLaneEvidence,
        reference: str,
        oid: str,
    ) -> str | None:
        """Classify unique work only with correlated owner and activity evidence.

        Returns:
            An exact refusal, or None for a legitimate declared lane/open PR.

        """
        branch = cls._lane_branch(reference)
        if evidence.pull_requests is None:
            return (
                f"inconclusive unique ref: {reference} oid={oid}; "
                "PR ownership evidence NOT EXECUTED (not selected)"
            )
        pull_requests = tuple(
            pr for pr in evidence.pull_requests if pr.head_ref_name == branch
        )
        if pull_requests:
            return cls._pr_ref(request, evidence, reference, pull_requests)
        return cls._bead_ref(request, evidence, reference, oid)

    @classmethod
    def _bead_ref(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        evidence: m.Infra.GitLaneEvidence,
        reference: str,
        oid: str,
    ) -> str | None:
        """Classify no-PR work only with observed, repository-scoped Bead data.

        Returns:
            A known-owner classification or an explicit inconclusive source state.

        """
        if evidence.beads is None:
            return (
                f"inconclusive unique ref: {reference} oid={oid}; "
                "Beads ownership evidence NOT EXECUTED (not selected)"
            )
        branch = cls._lane_branch(reference)
        owners = cls._ownership(evidence, branch, None)
        worktrees = u.Infra.git_list_worktrees(
            m.Infra.GitRepoRequest(repo_root=request.repo_root),
        )
        if worktrees.failure:
            return f"worktree read error: {reference}: {worktrees.error}"
        owners += tuple(
            bead
            for entry in worktrees.value.entries
            if entry.branch == branch
            for bead in cls._ownership(evidence, branch, entry.path)
            if bead not in owners
        )
        if not owners:
            return (
                f"inconclusive unique ref: {reference} oid={oid}; "
                "owner/activity policy unproven"
            )
        policy = cls._activity_policy(request)
        now = datetime.now(UTC)
        threshold = policy.abandonment_threshold_minutes * 60
        if (now - evidence.captured_at).total_seconds() > threshold:
            return (
                f"inconclusive unique ref: {reference} oid={oid}; "
                "stale ownership receipt"
            )
        if any(
            bead.assignee
            and bead.status == "in_progress"
            and 0 <= (now - bead.updated_at).total_seconds() <= threshold
            for bead in owners
        ):
            return None
        return cls._inactive_ref(request, owners, reference, threshold)

    @classmethod
    def _pr_ref(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        evidence: m.Infra.GitLaneEvidence,
        reference: str,
        pull_requests: tuple[m.Infra.GitLanePullRequest, ...],
    ) -> str | None:
        """Open PRs corroborate ownership; activity still comes from live facts.

        Returns:
            None for an active PR lane, otherwise inconclusive rather than abandoned.

        """
        policy = cls._activity_policy(request)
        activity = u.Infra.git_ref_last_activity(
            m.Infra.GitCommitishRequest(
                repo_root=request.repo_root,
                commitish=reference,
            ),
        )
        if activity.failure:
            return f"PR activity read error: {reference}: {activity.error}"
        branch = pull_requests[0].head_ref_name
        latest = max(
            activity.value.epoch_seconds,
            *(pr.updated_at.timestamp() for pr in pull_requests),
            *(
                bead.updated_at.timestamp()
                for bead in cls._ownership(evidence, branch, None)
            ),
        )
        now = datetime.now(UTC)
        threshold = policy.abandonment_threshold_minutes * 60
        if (
            0 <= now.timestamp() - latest <= threshold
            and 0 <= (now - evidence.captured_at).total_seconds() <= threshold
        ):
            return None
        return f"inconclusive inactive PR lane: {reference}; latest_activity={latest}"

    @staticmethod
    def _inactive_ref(
        request: m.Infra.GitLaneVerificationRequest,
        owners: tuple[m.Infra.GitLaneBead, ...],
        reference: str,
        threshold: float,
    ) -> str:
        """Corroborate inactive ownership with ref and worktree activity.

        Returns:
            The exact inactive/inconclusive ref, never a deletion authorization.

        """
        timestamp = u.Infra.git_ref_last_activity(
            m.Infra.GitCommitishRequest(
                repo_root=request.repo_root,
                commitish=reference,
            ),
        )
        if timestamp.failure:
            return f"read error: {reference}: {timestamp.error}"
        latest = max(
            timestamp.value.epoch_seconds,
            *(bead.updated_at.timestamp() for bead in owners),
        )
        worktrees = u.Infra.git_list_worktrees(
            m.Infra.GitRepoRequest(repo_root=request.repo_root),
        )
        if worktrees.failure:
            return f"read error: {reference}: {worktrees.error}"
        branch = FlextInfraGitLanes._lane_branch(reference)
        for entry in worktrees.value.entries:
            if entry.branch == branch:
                status = u.Infra.git_status(
                    m.Infra.GitStatusRequest(repo_root=entry.path),
                )
                if status.failure or status.value.dirty or entry.locked:
                    return (
                        f"inconclusive unique ref: {reference}; "
                        "live/locked WIP must be adjudicated"
                    )
                activity = u.Infra.git_last_activity(
                    m.Infra.GitRepoRequest(repo_root=entry.path),
                )
                if activity.failure:
                    return f"read error: {reference}: {activity.error}"
                latest = max(latest, activity.value.epoch_seconds)
        state = (
            "abandoned"
            if datetime.now(UTC).timestamp() - latest > threshold
            else "inconclusive"
        )
        return (
            f"{state} unique ref without PR: {reference} "
            f"beads={','.join(bead.id for bead in owners)} "
            f"latest_activity={latest}"
        )

    @classmethod
    def verify_lanes(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
    ) -> p.Result[m.Infra.GitLaneReport]:
        """Return a complete inventory; fail loud without repairing any artifact.

        Returns:
            A green inventory or a failure containing the full structured report.

        """
        request = request.model_copy(
            update={
                "repo_root": request.repo_root.expanduser().resolve(),
            },
        )
        manifest = u.Infra.load_workspace_manifest(request.repo_root)
        requests = [request]
        if manifest.failure:
            return r[m.Infra.GitLaneReport].from_failure(manifest)
        if manifest.value:
            workspace = manifest.value[0]
            declared = (
                workspace.integration.branch
                if workspace.integration
                else request.declared
            )
            requests.extend(
                m.Infra.GitLaneVerificationRequest(
                    repo_root=request.repo_root / member.path,
                    declared=declared,
                    governance_file=request.governance_file,
                    read_pull_requests=request.read_pull_requests,
                    read_beads=request.read_beads,
                )
                for member in workspace.members
            )
        reports = tuple(cls._inspect_repository(item) for item in requests)
        report = m.Infra.GitLaneReport(
            repo_root=request.repo_root,
            integration_branch=reports[0].integration_branch,
            integration_oid=reports[0].integration_oid,
            inventory=tuple(
                f"{item.repo_root}: {entry}"
                for item in reports
                for entry in item.inventory
            ),
            findings=tuple(
                f"{item.repo_root}: {finding}"
                for item in reports
                for finding in item.findings
            ),
            violations=tuple(
                violation for item in reports for violation in item.violations
            ),
        )
        if report.findings:
            return r[m.Infra.GitLaneReport].fail(report.model_dump_json(indent=2))
        return r[m.Infra.GitLaneReport].ok(report)

    @classmethod
    def _inspect_repository(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
    ) -> m.Infra.GitLaneReport:
        """Collect all successful observations as well as every read failure.

        Returns:
            A complete report for one repository, without changing Git state.

        """
        findings: list[str] = []
        inventory: list[str] = []
        violations: list[m.Infra.GitLaneViolation] = []
        refs = cls._collect_lane_facts(request, inventory, findings, violations)
        base = u.Infra.resolve_integration_branch(
            request.repo_root,
            preference=config.Infra.codegen.branch_policy.integration_branch_preference,
            declared=request.declared,
        )
        fresh = cls.fresh_integration(request)
        if fresh.failure:
            findings.append(f"integration read error: {fresh.error}")
        inventory.extend(f"{ref}: {oid}" for ref, oid in refs)
        evidence = cls._collect_evidence(request, inventory, findings)
        integration = (
            (base.value, fresh.value) if base.success and fresh.success else None
        )
        violations.extend(
            cls._verify_worktrees(
                request,
                evidence,
                inventory,
                findings,
                integration,
            )
        )
        cls._verify_current_lane(request, fresh, inventory, findings)
        if base.success and fresh.success:
            violations.extend(
                cls._verify_refs(
                    request,
                    refs,
                    (base.value, fresh.value),
                    evidence,
                    findings,
                )
            )
        return m.Infra.GitLaneReport(
            repo_root=request.repo_root,
            integration_branch=base.value if base.success else "",
            integration_oid=fresh.value if fresh.success else "",
            inventory=tuple(inventory),
            findings=tuple(findings),
            violations=tuple(violations),
        )

    @classmethod
    def _collect_lane_facts(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        inventory: list[str],
        findings: list[str],
        violations: list[m.Infra.GitLaneViolation],
    ) -> list[tuple[str, str]]:
        """Read native refs and stashes, recording every stash as a violation.

        Returns:
            The observed ``(ref, oid)`` pairs; a read failure stays in findings.

        """
        facts = u.Infra.git_lane_facts(
            m.Infra.GitRepoRequest(repo_root=request.repo_root),
        )
        if facts.failure:
            findings.append(f"native lane facts read error: {facts.error}")
            return []
        findings.extend(facts.value.read_errors)
        for oid in facts.value.stash_oids:
            findings.append(f"forbidden stash: {oid}")
            inventory.append(f"refs/stash: {oid}")
            violations.append(cls._violation(c.Infra.LaneViolationKind.STASH, oid))
        return [(ref.name, ref.oid) for ref in facts.value.refs]

    @classmethod
    def _collect_evidence(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        inventory: list[str],
        findings: list[str],
    ) -> p.Result[m.Infra.GitLaneEvidence]:
        """Read ownership evidence and inventory which sources were observed.

        Returns:
            The ownership evidence result; a read failure stays in findings.

        """
        try:
            evidence = cls._evidence(request)
        except (OSError, ValueError) as exc:
            evidence = r[m.Infra.GitLaneEvidence].fail(str(exc), exception=exc)
        if evidence.failure:
            findings.append(f"ownership read error: {evidence.error}")
            return evidence
        for name, observed in (
            ("PR", evidence.value.pull_requests is not None),
            ("Beads", evidence.value.beads is not None),
        ):
            inventory.append(
                f"{name} ownership evidence: "
                + ("observed" if observed else "NOT EXECUTED (not selected/unknown)"),
            )
        return evidence

    @classmethod
    def _verify_worktrees(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        evidence: p.Result[m.Infra.GitLaneEvidence],
        inventory: list[str],
        findings: list[str],
        integration: tuple[str, str] | None,
    ) -> tuple[m.Infra.GitLaneViolation, ...]:
        """Report registry orphans and unowned temporary/detached worktrees.

        Returns:
            Structured registry violations; all read failures stay in findings.

        """
        worktrees = u.Infra.git_list_worktrees(
            m.Infra.GitRepoRequest(repo_root=request.repo_root),
        )
        if worktrees.failure:
            findings.append(f"worktree read error: {worktrees.error}")
            return ()
        violations: list[m.Infra.GitLaneViolation] = []
        for entry in worktrees.value.entries:
            inventory.append(
                f"worktree: {entry.path} head={entry.head} "
                f"branch={entry.branch} locked={entry.locked}",
            )
            violations.extend(
                cls._worktree_violations(evidence, entry, findings),
            )
            if entry.path.is_dir() and integration is not None:
                violations.extend(
                    cls._merged_worktree_violations(
                        request,
                        entry,
                        integration,
                        findings,
                    ),
                )
        return tuple(violations)

    @classmethod
    def _worktree_violations(
        cls,
        evidence: p.Result[m.Infra.GitLaneEvidence],
        entry: m.Infra.GitWorktreeEntry,
        findings: list[str],
    ) -> Iterator[m.Infra.GitLaneViolation]:
        """Classify one registered worktree as orphaned or unowned temporary.

        Yields:
            The registration violation for the entry, if any.

        """
        kind = c.Infra.LaneViolationKind
        temporary = any(
            entry.path.is_relative_to(root)
            for root in config.Infra.codegen.branch_policy.lane_temporary_roots
        )
        if not entry.path.is_dir():
            findings.append(
                f"orphan worktree registration: {entry.path} head={entry.head}",
            )
            yield cls._violation(kind.MISSING_WORKTREE, str(entry.path))
        elif (temporary or entry.detached) and not cls._worktree_owned(
            evidence,
            entry,
        ):
            findings.append(
                "inconclusive unowned temporary/detached worktree: "
                f"{entry.path} head={entry.head}",
            )
            violation_kind = kind.TEMP_WORKTREE if temporary else kind.DETACHED_WORKTREE
            yield cls._violation(violation_kind, str(entry.path))

    @classmethod
    def _merged_worktree_violations(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        entry: m.Infra.GitWorktreeEntry,
        integration: tuple[str, str],
        findings: list[str],
    ) -> Iterator[m.Infra.GitLaneViolation]:
        """Classify one existing worktree as fully integrated and clean.

        Yields:
            The merged-worktree violation for the entry, if any.

        """
        merged = cls._merged_worktree(request, entry, integration)
        if merged.failure:
            findings.append(
                f"merged worktree read error: {entry.path}: {merged.error}",
            )
        elif merged.value:
            findings.append(
                "merged clean worktree still registered: "
                f"{entry.path} head={entry.head}",
            )
            yield cls._violation(
                c.Infra.LaneViolationKind.MERGED_WORKTREE,
                str(entry.path),
            )

    @classmethod
    def _worktree_owned(
        cls,
        evidence: p.Result[m.Infra.GitLaneEvidence],
        entry: m.Infra.GitWorktreeEntry,
    ) -> bool:
        """Return positive ownership proof only; absence remains inconclusive.

        Returns:
            Whether selected evidence proves the registered worktree's ownership.

        """
        return evidence.success and (
            bool(cls._ownership(evidence.value, entry.branch or "", entry.path))
            or (
                evidence.value.pull_requests is not None
                and any(
                    pr.head_ref_name == entry.branch
                    for pr in evidence.value.pull_requests
                )
            )
        )

    @staticmethod
    def _violation(
        kind: c.Infra.LaneViolationKind, ref: str
    ) -> m.Infra.GitLaneViolation:
        """Preserve incoming structured classes at the sole verdict owner.

        Returns:
            A typed violation with its canonical preservation-first instruction.

        """
        return m.Infra.GitLaneViolation(
            kind=kind,
            ref=ref,
            detail=c.Infra.GIT_LANE_VIOLATION_REMEDY[kind].format(ref=ref),
        )

    @staticmethod
    def _merged_worktree(
        request: m.Infra.GitLaneVerificationRequest,
        entry: m.Infra.GitWorktreeEntry,
        integration: tuple[str, str],
    ) -> p.Result[bool]:
        """Classify clean linked content against the same live integration proof.

        Returns:
            Whether a linked lane is fully integrated and clean, never permission
            to remove it or disregard locked/active ownership.

        """
        if (
            entry.path == request.repo_root
            or entry.bare
            or entry.head is None
            or entry.branch in {None, integration[0]}
        ):
            return r[bool].ok(value=False)
        contained = u.Infra.git_is_ancestor(
            m.Infra.GitAncestryRequest(
                repo_root=request.repo_root,
                ancestor=entry.head,
                descendant=integration[1],
            )
        )
        if contained.failure:
            return r[bool].from_failure(contained)
        if not contained.value.value:
            return r[bool].ok(value=False)
        status = u.Infra.git_status(m.Infra.GitStatusRequest(repo_root=entry.path))
        if status.failure:
            return r[bool].from_failure(status)
        return r[bool].ok(value=not status.value.dirty)

    @classmethod
    def _verify_refs(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        refs: list[tuple[str, str]],
        integration: tuple[str, str],
        evidence: p.Result[m.Infra.GitLaneEvidence],
        findings: list[str],
    ) -> tuple[m.Infra.GitLaneViolation, ...]:
        """Check every non-protected ref against the fresh integration object.

        Returns:
            Structured merged-ref violations, without retirement authorization.

        """
        base, fresh = integration
        violations: list[m.Infra.GitLaneViolation] = []
        remote = config.Infra.codegen.branch_policy.lane_remote
        for reference, oid in refs:
            if reference in {
                f"{c.Infra.GIT_REFS_HEADS}{base}",
                f"{c.Infra.GIT_REFS_REMOTES}{remote}/{base}",
            }:
                continue
            remote_failure = cls._remote_ref_failure(request.repo_root, reference, oid)
            if remote_failure is not None:
                findings.append(remote_failure)
                continue
            contained = u.Infra.git_is_ancestor(
                m.Infra.GitAncestryRequest(
                    repo_root=request.repo_root,
                    ancestor=oid,
                    descendant=fresh,
                ),
            )
            if contained.failure:
                findings.append(f"ancestry read error: {reference}: {contained.error}")
            elif contained.value.value:
                findings.append(f"merged but alive ref: {reference} oid={oid}")
                violations.append(
                    cls._violation(
                        c.Infra.LaneViolationKind.MERGED_BRANCH,
                        reference,
                    )
                )
            elif evidence.success:
                try:
                    refusal = cls._unmerged_ref(
                        request,
                        (reference, oid),
                        fresh,
                        evidence.value,
                    )
                except (OSError, ValueError) as exc:
                    refusal = f"ownership read error: {reference}: {exc}"
                if refusal is not None:
                    findings.append(refusal)
        return tuple(violations)

    @staticmethod
    def _verify_current_lane(
        request: m.Infra.GitLaneVerificationRequest,
        fresh: p.Result[str],
        inventory: list[str],
        findings: list[str],
    ) -> None:
        """Bind ancestry to the native current branch/OID, including stale reports."""
        identity = u.Infra.git_identity(
            m.Infra.GitRepoRequest(
                repo_root=request.repo_root,
            ),
        )
        if identity.failure:
            findings.append(f"current lane identity read error: {identity.error}")
            return
        current = identity.value
        inventory.append(
            f"current lane: {current.repo_root} head={current.head_oid} "
            f"branch={current.branch} git_dir={current.git_dir} "
            f"common_dir={current.common_dir}",
        )
        if fresh.failure:
            return
        consumes = u.Infra.git_is_ancestor(
            m.Infra.GitAncestryRequest(
                repo_root=request.repo_root,
                ancestor=fresh.value,
                descendant=current.head_oid,
            ),
        )
        if consumes.failure:
            findings.append(f"current lane ancestry read error: {consumes.error}")
        elif not consumes.value.value:
            findings.append(
                "current lane does not consume fresh integration: "
                f"fresh={fresh.value} head={current.head_oid} branch={current.branch}",
            )

    @classmethod
    def _unmerged_ref(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        ref: tuple[str, str],
        fresh: str,
        evidence: m.Infra.GitLaneEvidence,
    ) -> str | None:
        """Separate unique patches from non-ancestor history without object writes.

        Returns:
            An exact ref classification based on patch identity and ownership.

        """
        reference, oid = ref
        patches = u.Infra.git_unique_patch_oids(
            m.Infra.GitMergeProbeRequest(
                repo_root=request.repo_root,
                base=fresh,
                commitish=oid,
            ),
        )
        if patches.failure:
            return f"unique-patch read error: {reference}: {patches.error}"
        if not patches.value.oids:
            return (
                f"inconclusive non-ancestor ref without unique patches: {reference} "
                f"oid={oid}; integration/supersession proof required"
            )
        return cls._unique_ref(request, evidence, reference, oid)

    @staticmethod
    def _remote_ref_failure(repo_root: Path, reference: str, oid: str) -> str | None:
        """Never label cached remote refs as living remote branches without proof.

        Returns:
            The exact read/divergence refusal, or None when the tip matches.

        """
        remote = config.Infra.codegen.branch_policy.lane_remote
        prefix = f"{c.Infra.GIT_REFS_REMOTES}{remote}/"
        if not reference.startswith(prefix):
            return None
        live = u.Infra.git_remote_branch_oid(
            m.Infra.GitRemoteBranchRequest(
                repo_root=repo_root,
                remote=remote,
                branch=reference.removeprefix(prefix),
            ),
        )
        if live.failure or live.value.text != oid:
            return (
                f"inconclusive stale remote ref: {reference} cached={oid}; "
                f"live={live.value.text if live.success else live.error}"
            )
        return None


__all__: list[str] = ["FlextInfraGitLanes"]
