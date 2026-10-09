"""Read-only lane gate and automatic admission against real local Git remotes.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraGitService, FlextInfraWorktreeService, config, main
from tests import c, m, u


class TestsVerifyLanes:
    """Exercise the real public CLI and shared lifecycle boundaries without mocks."""

    @staticmethod
    def _repository(
        root: Path,
        integration: str,
        minutes: float,
    ) -> m.Infra.GitLaneVerificationRequest:
        """Build an independent remote and a typed, fresh ownership receipt.

        Returns:
            The public request with arbitrary integration/activity policy inputs.

        """
        repo = u.Tests.git_repository(root)
        manifest = u.Tests.write_workspace_manifest(repo, repo.name)
        workspace = tm.ok(u.Infra.load_workspace_manifest(repo))[0]
        declared = workspace.model_copy(
            update={
                "integration": m.Infra.WorkspaceIntegrationSpec(
                    provider=workspace.repository.provider,
                    branch=integration,
                ),
            },
        )
        tm.ok(u.Cli.yaml_dump(manifest, declared.model_dump(mode="json")))
        u.Tests.git_run(repo, "add", "config")
        u.Tests.git_run(repo, "commit", "-m", "declare integration fixture")
        u.Tests.git_run(repo, "branch", "-m", integration)
        remote = root / "remote.git"
        u.Tests.git_bootstrap(root, ("init", "--bare", str(remote)))
        policy = config.Infra.codegen.branch_policy
        remote_action = "set-url" if policy.lane_remote == c.Infra.GIT_ORIGIN else "add"
        u.Tests.git_run(repo, "remote", remote_action, policy.lane_remote, str(remote))
        u.Tests.git_run(
            repo,
            "update-ref",
            "-d",
            f"refs/remotes/{c.Infra.GIT_ORIGIN}/{u.Tests.provider_branch()}",
        )
        u.Tests.git_run(repo, "push", "-u", policy.lane_remote, integration)
        u.Tests.git_run(
            repo,
            "symbolic-ref",
            f"refs/remotes/{policy.lane_remote}/HEAD",
            f"refs/remotes/{policy.lane_remote}/{integration}",
        )
        now = datetime.now(UTC)
        bead = m.Infra.GitLaneBead(
            id="fixture-owned",
            status="in_progress",
            assignee="fixture-owner",
            updated_at=now,
            metadata=m.Infra.GitLaneBeadMetadata(
                branch=integration,
                work_dir=str(repo),
            ),
        )
        evidence = m.Infra.GitLaneEvidence(
            repo_root=repo,
            captured_at=now,
            beads=(bead,),
            pull_requests=(),
        )
        evidence_file = root / "ownership.json"
        evidence_file.write_text(
            evidence.model_dump_json(by_alias=True),
            encoding="utf-8",
        )
        governance = m.Infra.GitLaneGovernance(
            coordination=m.Infra.GitLaneCoordinationPolicy(
                abandonment_threshold_minutes=minutes,
            ),
        )
        governance_file = root / "governance.json"
        governance_file.write_text(governance.model_dump_json(), encoding="utf-8")
        return m.Infra.GitLaneVerificationRequest(
            repo_root=repo,
            evidence_file=evidence_file,
            governance_file=governance_file,
        )

    @staticmethod
    def _argv(request: m.Infra.GitLaneVerificationRequest) -> list[str]:
        """Translate the typed public request to the real registered CLI.

        Returns:
            Public CLI arguments, never a private service execution substitute.

        """
        return [
            "workspace",
            "verify-lanes",
            "--repo-root",
            str(request.repo_root),
            "--evidence-file",
            str(request.evidence_file),
            "--governance-file",
            str(request.governance_file),
        ]

    @classmethod
    @pytest.mark.parametrize("integration", ["release/alpha", "delivery/beta"])
    @pytest.mark.parametrize("minutes", [2.5, 17.0])
    def test_cli_clean_and_merged_ref_inventory(
        cls,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        integration: str,
        minutes: float,
    ) -> None:
        """Protect arbitrary integration lines and report both living merged refs."""
        request = cls._repository(tmp_path, integration, minutes)
        storage = tmp_path / "separate-storage.git"
        u.Tests.git_bootstrap(
            request.repo_root,
            ("init", "--separate-git-dir", str(storage)),
        )
        registry = tm.ok(
            u.Infra.git_list_worktrees(
                m.Infra.GitRepoRequest(
                    repo_root=request.repo_root,
                ),
            ),
        )
        tm.that(registry.entries[0].path, eq=request.repo_root)
        tm.that(registry.entries[0].branch, eq=integration)
        tm.that(
            registry.entries[0].head,
            eq=u.Tests.git_capture(request.repo_root, "rev-parse", "HEAD"),
        )
        tm.that(main(cls._argv(request)), eq=0)
        _ = capsys.readouterr()
        branch = "completed-slice"
        u.Tests.git_run(request.repo_root, "branch", branch)
        policy = config.Infra.codegen.branch_policy
        u.Tests.git_run(request.repo_root, "push", policy.lane_remote, branch)
        refs = u.Tests.git_capture(request.repo_root, "show-ref")
        tm.that(main(cls._argv(request)), eq=1)
        output = capsys.readouterr()
        text = output.out + output.err
        tm.that(text, has=f"refs/heads/{branch}")
        tm.that(text, has=f"refs/remotes/{policy.lane_remote}/{branch}")
        tm.that(text, has="merged but alive")
        tm.that(u.Tests.git_capture(request.repo_root, "show-ref"), eq=refs)
        tm.that(
            main([
                "workspace",
                "verify-lanes",
                "--repo-root",
                str(request.repo_root),
            ]),
            eq=1,
        )
        dormant = capsys.readouterr()
        tm.that(dormant.out + dormant.err, has="NOT EXECUTED (not selected/unknown)")
        tm.that(u.Tests.git_capture(request.repo_root, "show-ref"), eq=refs)

    @classmethod
    def test_cli_stash_preserves_index_refs_and_wip(
        cls,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A real recovery ref blocks CLI/admission without altering any WIP."""
        request = cls._repository(tmp_path, "integration/incident", 11.0)
        repo = request.repo_root
        head = u.Tests.git_capture(repo, "rev-parse", "HEAD")
        u.Tests.git_run(
            repo,
            "update-ref",
            "--create-reflog",
            "-m",
            "recovery incident",
            "refs/stash",
            head,
        )
        staged = repo / "staged.txt"
        staged.write_bytes(b"staged WIP\x00\n")
        u.Tests.git_run(repo, "add", staged.name)
        untracked = repo / "untracked.txt"
        untracked.write_bytes(b"untracked WIP\xff\n")
        index = (repo / ".git" / "index").read_bytes()
        refs = u.Tests.git_capture(repo, "show-ref")
        tm.that(main(cls._argv(request)), eq=1)
        output = capsys.readouterr()
        tm.that(output.out + output.err, has=f"forbidden stash: {head}")
        tm.that((repo / ".git" / "index").read_bytes(), eq=index)
        tm.that(u.Tests.git_capture(repo, "show-ref"), eq=refs)
        tm.that(staged.read_bytes(), eq=b"staged WIP\x00\n")
        tm.that(untracked.read_bytes(), eq=b"untracked WIP\xff\n")
        rejected = FlextInfraWorktreeService(
            repository_root=repo,
            operation=c.Infra.WorktreeOperation.ADD,
            branch="new-slice",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(rejected, has="forbidden stashes")
        tm.that(u.Tests.git_capture(repo, "show-ref"), eq=refs)

    @classmethod
    def test_unknown_unique_ref_is_inconclusive_not_abandoned(
        cls,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Unknown branch ownership never becomes an age-based abandonment claim."""
        request = cls._repository(tmp_path, "integration/unknown", 7.0)
        repo = request.repo_root
        branch = "unidentified-slice"
        u.Tests.git_run(repo, "switch", "-c", branch)
        (repo / "work.txt").write_text("unique work\n", encoding="utf-8")
        u.Tests.git_run(repo, "add", "work.txt")
        u.Tests.git_run(repo, "commit", "-m", "unidentified work")
        tm.that(main(cls._argv(request)), eq=1)
        output = capsys.readouterr()
        tm.that(
            output.out + output.err,
            has=f"inconclusive unique ref: refs/heads/{branch}",
        )
        tm.that("abandoned unique ref" in output.out + output.err, eq=False)

    @classmethod
    def test_open_pr_allows_unique_lane_and_unintegrated_retirement_refuses(
        cls,
        tmp_path: Path,
    ) -> None:
        """Owned open-PR work is legitimate but is never safe to retire unmerged."""
        request = cls._repository(tmp_path, "integration/active", 13.0)
        repo = request.repo_root
        branch = "active-slice"
        lane = u.Tests.git_linked_lane(tmp_path, repo, branch)
        (lane / "unique.txt").write_text("active work\n", encoding="utf-8")
        u.Tests.git_run(lane, "add", "unique.txt")
        u.Tests.git_run(lane, "commit", "-m", "active work")
        evidence = m.Infra.GitLaneEvidence.model_validate_json(
            tm.not_none(request.evidence_file).read_text(encoding="utf-8"),
        )
        now = datetime.now(UTC)
        active = m.Infra.GitLaneBead(
            id="active-bead",
            status="in_progress",
            assignee="active-owner",
            updated_at=now,
            metadata=m.Infra.GitLaneBeadMetadata(branch=branch, work_dir=str(lane)),
        )
        updated = evidence.model_copy(
            update={
                "beads": (*tm.not_none(evidence.beads), active),
                "pull_requests": (
                    m.Infra.GitLanePullRequest.model_validate({
                        "number": 1,
                        "headRefName": branch,
                        "updatedAt": now,
                    }),
                ),
            },
        )
        tm.not_none(request.evidence_file).write_text(
            updated.model_dump_json(by_alias=True),
            encoding="utf-8",
        )
        tm.ok(FlextInfraGitService.verify_lanes(request))
        rejected = FlextInfraWorktreeService(
            repository_root=repo,
            operation=c.Infra.WorktreeOperation.REMOVE,
            branch=branch,
            apply_changes=True,
        ).execute()
        tm.fail(rejected, has="unintegrated lane")
        tm.that(lane.is_dir(), eq=True)

    @classmethod
    def test_stale_base_and_expired_receipt_fail_without_mutation(
        cls,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Policy changes drive receipt expiry; stale bases cannot create lanes."""
        request = cls._repository(tmp_path, "integration/stale", 5.5)
        repo = request.repo_root
        original = u.Tests.git_capture(repo, "rev-parse", "HEAD")
        (repo / "new.txt").write_text("new integration\n", encoding="utf-8")
        u.Tests.git_run(repo, "add", "new.txt")
        u.Tests.git_run(repo, "commit", "-m", "advance integration")
        u.Tests.git_run(repo, "push", config.Infra.codegen.branch_policy.lane_remote)
        rejected = FlextInfraWorktreeService(
            repository_root=repo,
            operation=c.Infra.WorktreeOperation.ADD,
            branch="stale-slice",
            base=original,
            apply_changes=True,
        ).execute()
        tm.fail(rejected, has="stale lane base")
        evidence_file = tm.not_none(request.evidence_file)
        evidence = m.Infra.GitLaneEvidence.model_validate_json(
            evidence_file.read_text(encoding="utf-8"),
        )
        governance = m.Infra.GitLaneGovernance.model_validate_json(
            tm.not_none(request.governance_file).read_text(encoding="utf-8"),
        )
        stale = evidence.model_copy(
            update={
                "captured_at": datetime.now(UTC)
                - timedelta(
                    minutes=governance.coordination.abandonment_threshold_minutes * 2,
                ),
            },
        )
        evidence_file.write_text(
            stale.model_dump_json(by_alias=True),
            encoding="utf-8",
        )
        refs = u.Tests.git_capture(repo, "show-ref")
        tm.that(main(cls._argv(request)), eq=1)
        output = capsys.readouterr()
        tm.that(output.out + output.err, has="stale/future ownership receipt")
        tm.that(u.Tests.git_capture(repo, "show-ref"), eq=refs)

    @classmethod
    def test_remote_divergence_and_read_errors_never_pass(
        cls,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A stale tracking object or failed evidence read cannot be empty/green."""
        request = cls._repository(tmp_path, "integration/divergent", 9.0)
        repo = request.repo_root
        previous = u.Tests.git_capture(repo, "rev-parse", "HEAD")
        (repo / "advanced.txt").write_text("advance remote\n", encoding="utf-8")
        u.Tests.git_run(repo, "add", "advanced.txt")
        u.Tests.git_run(repo, "commit", "-m", "advance remote integration")
        policy = config.Infra.codegen.branch_policy
        u.Tests.git_run(repo, "push", policy.lane_remote)
        tracking = f"refs/remotes/{policy.lane_remote}/integration/divergent"
        u.Tests.git_run(repo, "update-ref", tracking, previous)
        refs = u.Tests.git_capture(repo, "show-ref")
        tm.that(main(cls._argv(request)), eq=1)
        output = capsys.readouterr()
        tm.that(output.out + output.err, has="stale integration")
        tm.that(u.Tests.git_capture(repo, "show-ref"), eq=refs)
        missing = request.model_copy(
            update={
                "evidence_file": tmp_path / "missing-evidence.json",
            },
        )
        tm.that(main(cls._argv(missing)), eq=1)
        output = capsys.readouterr()
        tm.that(output.out + output.err, has="ownership read error")
        tm.that(output.out + output.err, has=tracking)
        tm.that(u.Tests.git_capture(repo, "show-ref"), eq=refs)
        tm.that(
            main([
                "workspace",
                "verify-lanes",
                "--repo-root",
                str(repo),
                "--read-beads",
            ]),
            eq=1,
        )
        selected = capsys.readouterr()
        tm.that(
            selected.out + selected.err,
            has="missing required repository-local Beads configuration",
        )
        tm.that(selected.out + selected.err, has=tracking)
        tm.that(u.Tests.git_capture(repo, "show-ref"), eq=refs)

    @classmethod
    def test_existing_branch_cannot_bypass_fresh_base_admission(
        cls,
        tmp_path: Path,
    ) -> None:
        """An existing stale branch cannot substitute its tip after base validation."""
        request = cls._repository(tmp_path, "integration/resumption", 12.0)
        repo = request.repo_root
        branch = "stale-existing-slice"
        u.Tests.git_run(repo, "branch", branch)
        (repo / "advanced.txt").write_text("fresh baseline\n", encoding="utf-8")
        u.Tests.git_run(repo, "add", "advanced.txt")
        u.Tests.git_run(repo, "commit", "-m", "advance resumption baseline")
        u.Tests.git_run(repo, "push", config.Infra.codegen.branch_policy.lane_remote)
        lane = tm.ok(FlextInfraWorktreeService.canonical_lane_path(repo, branch))
        refs = u.Tests.git_capture(repo, "show-ref")
        rejected = FlextInfraWorktreeService(
            repository_root=repo,
            operation=c.Infra.WorktreeOperation.ADD,
            branch=branch,
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(rejected, has="existing lane has stale base")
        tm.that(lane.exists(), eq=False)
        tm.that(u.Tests.git_capture(repo, "show-ref"), eq=refs)

    @classmethod
    @pytest.mark.parametrize("artifact", ["detached", "orphan"])
    def test_unowned_detached_and_orphan_registry_entries_are_preserved(
        cls,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        artifact: str,
    ) -> None:
        """Registry evidence is reported without removal, relocation, or pruning."""
        request = cls._repository(tmp_path, "integration/registry", 8.0)
        repo = request.repo_root
        lane = tmp_path / "unowned-worktree"
        u.Tests.git_run(repo, "worktree", "add", "--detach", str(lane), "HEAD")
        if artifact == "orphan":
            lane.rename(tmp_path / "preserved-worktree")
        registry = u.Tests.git_capture(repo, "worktree", "list", "--porcelain")
        tm.that(main(cls._argv(request)), eq=1)
        output = capsys.readouterr()
        expected = (
            "orphan worktree registration"
            if artifact == "orphan"
            else "inconclusive unowned temporary/detached worktree"
        )
        tm.that(output.out + output.err, has=expected)
        tm.that(output.out + output.err, has=str(lane))
        tm.that(
            u.Tests.git_capture(repo, "worktree", "list", "--porcelain"),
            eq=registry,
        )

    @classmethod
    @pytest.mark.parametrize("minutes", [3.25, 19.0])
    def test_abandonment_requires_correlated_owner_patch_and_activity_policy(
        cls,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        minutes: float,
    ) -> None:
        """Only real unique patches with stale declared ownership are abandoned."""
        request = cls._repository(tmp_path, "integration/abandonment", minutes)
        repo = request.repo_root
        policy = m.Infra.GitLaneGovernance.model_validate_json(
            tm.not_none(request.governance_file).read_text(encoding="utf-8"),
        ).coordination
        old = datetime.now(UTC) - timedelta(
            minutes=policy.abandonment_threshold_minutes * 3,
        )
        dates = m.Cli.ProcessOptions(
            env={
                "GIT_AUTHOR_DATE": old.isoformat(),
                "GIT_COMMITTER_DATE": old.isoformat(),
            },
        )
        branch = "abandoned-owned-slice"
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "switch", "-c", branch],
                cwd=repo,
                options=dates,
            ),
        )
        (repo / "unique.txt").write_text("real unique patch\n", encoding="utf-8")
        u.Tests.git_run(repo, "add", "unique.txt")
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "commit", "-m", "old unique work"],
                cwd=repo,
                options=dates,
            ),
        )
        u.Tests.git_run(repo, "switch", "integration/abandonment")
        evidence_file = tm.not_none(request.evidence_file)
        evidence = m.Infra.GitLaneEvidence.model_validate_json(
            evidence_file.read_text(encoding="utf-8"),
        )
        owner = m.Infra.GitLaneBead(
            id="abandoned-bead",
            status="closed",
            assignee="former-owner",
            updated_at=old,
            metadata=m.Infra.GitLaneBeadMetadata(branch=branch, work_dir=str(repo)),
        )
        measured = evidence.model_copy(
            update={"beads": (*tm.not_none(evidence.beads), owner)},
        )
        evidence_file.write_text(
            measured.model_dump_json(by_alias=True),
            encoding="utf-8",
        )
        refs = u.Tests.git_capture(repo, "show-ref")
        tm.that(main(cls._argv(request)), eq=1)
        output = capsys.readouterr()
        tm.that(output.out + output.err, has="abandoned unique ref without PR")
        tm.that(output.out + output.err, has=f"refs/heads/{branch}")
        tm.that(u.Tests.git_capture(repo, "show-ref"), eq=refs)
