"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from git import BadName, GitCommandError

from flext_infra import c, m, p, r
from flext_infra._utilities import FlextInfraUtilitiesGitWorktreePatchMixin


class FlextInfraUtilitiesGitSemanticRefsMixin(FlextInfraUtilitiesGitWorktreePatchMixin):
    """Own semantic refs operations."""

    @classmethod
    def git_verify_lane(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Verify stash absence and live-tip ancestry without changing Git state.

        Creation and retirement remain closed until the canonical ownership and
        preservation contracts reach those mutation requests. Correlation rows
        and caller assertions are not authority to admit either effect.

        Returns:
            The unchanged, twice-advertised integration tip, or a precise refusal.

        """
        stash_absent = cls._git_lane_no_stash(request.repo_root)
        if stash_absent.failure:
            return r[m.Infra.GitOidReport].from_failure(stash_absent)
        tip = cls._git_lane_tip(request)
        if tip.failure:
            return tip
        if request.operation == "create":
            return r[m.Infra.GitOidReport].fail(
                "new lane refused: authoritative Beads ownership and previous owned "
                "lane integration are not available in the native admission contract; "
                "continue the existing candidate, not another lane",
            )
        if request.operation == "retire":
            return r[m.Infra.GitOidReport].fail(
                "retirement refused: the native removal contract carries no verified "
                "published preservation or active-session ownership proof; ancestry "
                "alone does not authorize removal",
            )
        return tip

    @classmethod
    def _git_lane_no_stash(cls, root: Path) -> p.Result[bool]:
        """Require both the stash log and its incident reference to be absent.

        Returns:
            Stash absence or the original query failure.

        """
        stashes = cls.git_stash_oids(m.Infra.GitRepoRequest(repo_root=root))
        if stashes.failure:
            return r[bool].from_failure(stashes)
        retained = cls.git_ref_exists(
            m.Infra.GitRefRequest(repo_root=root, reference="refs/stash"),
        )
        if retained.failure:
            return r[bool].from_failure(retained)
        if stashes.value.oids or retained.value.value:
            return r[bool].fail(
                "lane admission refuses existing stash state; preserve and integrate "
                "the incident without creating, applying, or popping a stash",
            )
        return r[bool].ok(value=True)

    @classmethod
    def _git_lane_tip(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Bind the declared integration branch to a live, unchanged remote OID.

        Returns:
            Verified integration tip without fetching or writing refs.

        """
        remote = cls._git_lane_declared_remote(request)
        if remote.failure:
            return r[m.Infra.GitOidReport].from_failure(remote)
        tip = cls._git_lane_cached_tip(remote.value, request.expected_tip)
        if tip.failure:
            return tip
        ancestry = cls._git_lane_ancestry(request, tip.value.oid)
        if ancestry.failure:
            return ancestry
        confirmed = cls.git_remote_branch_oid(remote.value)
        if confirmed.failure:
            return r[m.Infra.GitOidReport].from_failure(confirmed)
        if confirmed.value.text != tip.value.oid:
            return r[m.Infra.GitOidReport].fail(
                "integration tip changed during preflight",
            )
        return ancestry

    @classmethod
    def _git_lane_declared_remote(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
    ) -> p.Result[m.Infra.GitRemoteBranchRequest]:
        """Resolve the integration branch the lane's repository declares.

        A member composed by a superproject declares its line in that
        superproject's ``.gitmodules`` ``branch`` key; an undeclared member or a
        member that follows the superproject (``.``) fails closed. A standalone
        checkout declares its line through its forge default branch, read live
        from the remote's ``HEAD``. No branch is inferred from names or cached
        refs.

        Returns:
            Declared integration query or a missing-authority diagnostic.

        """
        result = r[m.Infra.GitRemoteBranchRequest]
        primary = cls._git_primary_worktree_root_path(request.repo_root)
        if primary.failure:
            return result.from_failure(primary)
        superproject = cls._git_repository_root_path(primary.value)
        if superproject.failure:
            return result.from_failure(superproject)
        if superproject.value == primary.value:
            default = cls.git_remote_default_branch(
                m.Infra.GitRemoteRequest(
                    repo_root=request.repo_root,
                    remote=request.remote,
                ),
            )
            if default.failure:
                return result.from_failure(default)
            return result.ok(
                m.Infra.GitRemoteBranchRequest(
                    repo_root=request.repo_root,
                    remote=request.remote,
                    branch=default.value.text,
                ),
            )
        declaration = cls.git_submodule_declaration(
            m.Infra.GitSubmoduleContractRequest(
                repo_root=superproject.value,
                member_path=primary.value.relative_to(superproject.value).as_posix(),
            ),
        )
        if declaration.failure:
            return result.from_failure(declaration)
        branch = declaration.value.branch
        if branch == c.Infra.FOLLOW_SUPERPROJECT_BRANCH:
            return result.fail(
                "lane admission requires a named .gitmodules branch; "
                f"{declaration.value.path} follows its superproject",
            )
        return result.ok(
            m.Infra.GitRemoteBranchRequest(
                repo_root=request.repo_root,
                remote=request.remote,
                branch=branch,
            ),
        )

    @classmethod
    def _git_lane_cached_tip(
        cls,
        request: m.Infra.GitRemoteBranchRequest,
        expected_tip: str | None,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Compare the advertised integration OID with its local cached commit.

        Returns:
            Current cached identity or a precise freshness refusal.

        """
        tip = cls.git_remote_branch_oid(request)
        if tip.failure:
            return r[m.Infra.GitOidReport].from_failure(tip)
        if not tip.value.text:
            return r[m.Infra.GitOidReport].fail(
                f"declared integration branch is absent on {request.remote}: "
                f"{request.branch}",
            )
        if expected_tip is not None and expected_tip != tip.value.text:
            return r[m.Infra.GitOidReport].fail("integration tip changed before effect")
        cached = cls.git_resolve_commit(
            m.Infra.GitCommitishRequest(
                repo_root=request.repo_root,
                commitish=f"refs/remotes/{request.remote}/{request.branch}",
            ),
        )
        if cached.failure:
            return r[m.Infra.GitOidReport].from_failure(cached)
        if cached.value.oid != tip.value.text:
            return r[m.Infra.GitOidReport].fail(
                "stale integration cache; refresh through the canonical fetch owner "
                "before lane admission",
            )
        return cached

    @classmethod
    def _git_lane_ancestry(
        cls,
        request: m.Infra.GitLaneVerificationRequest,
        tip: str,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Check the appropriate ancestry direction and retirement cleanliness.

        Returns:
            Integration OID when the measured Git boundary is valid.

        """
        if request.operation == "retire":
            clean = cls._git_lane_retirement_clean(request.repo_root)
            if clean.failure:
                return r[m.Infra.GitOidReport].from_failure(clean)
        ancestry = cls.git_is_ancestor(
            m.Infra.GitAncestryRequest(
                repo_root=request.repo_root,
                ancestor=(request.candidate if request.operation == "retire" else tip),
                descendant=(
                    tip if request.operation == "retire" else request.candidate
                ),
            ),
        )
        if ancestry.failure:
            return r[m.Infra.GitOidReport].from_failure(ancestry)
        if not ancestry.value.value:
            return r[m.Infra.GitOidReport].fail(
                "retirement refuses an unintegrated candidate"
                if request.operation == "retire"
                else "lane has not absorbed the latest integration tip; merge forward",
            )
        return r[m.Infra.GitOidReport].ok(m.Infra.GitOidReport(oid=tip))

    @classmethod
    def _git_lane_retirement_clean(cls, root: Path) -> p.Result[bool]:
        """Require a clean, unlocked retirement subject without index writes.

        Returns:
            Cleanliness or the original inspection failure.

        """
        status = cls.git_status(m.Infra.GitStatusRequest(repo_root=root))
        if status.failure:
            return r[bool].from_failure(status)
        if status.value.dirty:
            return r[bool].fail("retirement refuses a dirty worktree")
        entries = cls.git_list_worktrees(m.Infra.GitRepoRequest(repo_root=root))
        if entries.failure:
            return r[bool].from_failure(entries)
        if any(
            entry.locked and entry.path == root.resolve()
            for entry in entries.value.entries
        ):
            return r[bool].fail("retirement refuses a locked worktree")
        return r[bool].ok(value=True)

    @classmethod
    def git_list_worktrees(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitWorktreeListReport]:
        """Read Git's canonical worktree registry, parsed once for every consumer.

        Returns:
            The resulting ``p.Result[m.Infra.GitWorktreeListReport]``.

        """
        repo_root = request.repo_root.expanduser().resolve()
        try:
            repo = cls._repo(repo_root)
            porcelain = repo.git.worktree("list", "--porcelain")
            entries = cls._worktree_registry(repo, porcelain)
        except GitCommandError as exc:
            return r[m.Infra.GitWorktreeListReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitWorktreeListReport].fail(
                f"failed to list Git worktrees: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitWorktreeListReport].ok(
            m.Infra.GitWorktreeListReport(
                root=repo_root,
                entries=entries,
                porcelain=porcelain,
            ),
        )

    @classmethod
    def git_check_branch_format(
        cls,
        request: m.Infra.GitBranchRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Validate a branch name with ``git check-ref-format --branch``.

        Returns:
            The resulting ``p.Result[m.Infra.GitBoolReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            repo.git.check_ref_format("--branch", request.branch)
        except GitCommandError as exc:
            # check-ref-format documents exit 1 for an invalid name; any other
            # status is a real failure.
            if exc.status == c.Infra.GIT_EXIT_NEGATIVE:
                return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
            return r[m.Infra.GitBoolReport].fail(
                f"failed to validate branch name: {exc}",
                exception=exc,
            )
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to validate branch name: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_ref_exists(
        cls,
        request: m.Infra.GitRefRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Return whether an exact Git ref exists (exit 0/1 only).

        Returns:
            Whether an exact Git ref exists (exit 0/1 only).

        """
        try:
            repo = cls._repo(request.repo_root)
            repo.git.show_ref("--verify", "--quiet", request.reference)
        except GitCommandError as exc:
            # show-ref documents exit 1 for a missing ref; any other status is
            # a real failure.
            if exc.status == c.Infra.GIT_EXIT_NEGATIVE:
                return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
            return r[m.Infra.GitBoolReport].fail(
                f"failed to inspect Git ref: {exc}",
                exception=exc,
            )
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to inspect Git ref: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=True))

    @classmethod
    def git_superproject_working_tree(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitTextReport]:
        """Capture ``rev-parse --show-superproject-working-tree`` stdout.

        Returns:
            The resulting ``p.Result[m.Infra.GitTextReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            text = repo.git.rev_parse("--show-superproject-working-tree")
        except GitCommandError as exc:
            return r[m.Infra.GitTextReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitTextReport].fail(
                f"failed to resolve superproject working tree: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitTextReport].ok(m.Infra.GitTextReport(text=text))

    @classmethod
    def git_show_toplevel(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitRootReport]:
        """Report the resolved top-level directory of the request's worktree.

        Returns:
            The resulting ``p.Result[m.Infra.GitRootReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            root = (
                Path(repo.working_tree_dir).resolve() if repo.working_tree_dir else None
            )
            if root is None:
                return r[m.Infra.GitRootReport].fail(
                    "failed to resolve Git top level: working tree is None",
                )
        except GitCommandError as exc:
            return r[m.Infra.GitRootReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitRootReport].fail(
                f"failed to resolve Git top level: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitRootReport].ok(m.Infra.GitRootReport(repository_root=root))

    @classmethod
    def git_current_branch(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitTextReport]:
        """Resolve the current non-detached branch name.

        Returns:
            The resulting ``p.Result[m.Infra.GitTextReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            branch = repo.active_branch.name
        except GitCommandError as exc:
            return r[m.Infra.GitTextReport].fail(str(exc), exception=exc)
        except (TypeError, OSError, ValueError) as exc:
            # active_branch raises TypeError on detached HEAD.
            return r[m.Infra.GitTextReport].fail(
                f"head branch is required from a detached HEAD: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitTextReport].ok(m.Infra.GitTextReport(text=branch))

    @classmethod
    def git_resolve_commit(
        cls,
        request: m.Infra.GitCommitishRequest,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Resolve a commit-ish to its commit oid, failing on a non-commit name.

        Returns:
            The resulting ``p.Result[m.Infra.GitOidReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            oid = repo.commit(request.commitish).hexsha
        except (BadName, GitCommandError) as exc:
            return r[m.Infra.GitOidReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitOidReport].fail(
                f"cannot resolve commitish: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitOidReport].ok(m.Infra.GitOidReport(oid=oid))

    @classmethod
    def git_is_ancestor(
        cls,
        request: m.Infra.GitAncestryRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Return whether ``ancestor`` is an ancestor of ``descendant``.

        One owner proves ancestry for any pair. ``descendant`` defaults to
        ``HEAD``, so the HEAD-bound proof existing consumers relied on is a
        use of this verb, not a separate one.

        Returns:
            Whether ``ancestor`` is an ancestor of ``descendant``.

        """
        try:
            repo = cls._repo(request.repo_root)
            result = repo.is_ancestor(
                repo.commit(request.ancestor),
                repo.commit(request.descendant),
            )
        except (BadName, GitCommandError) as exc:
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"failed to inspect ancestry: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=result))

    @classmethod
    def git_rev_parse(
        cls,
        request: m.Infra.GitCommitishRequest,
    ) -> p.Result[m.Infra.GitOidReport]:
        """Resolve an arbitrary rev-parse argument to stripped text oid.

        Returns:
            The resulting ``p.Result[m.Infra.GitOidReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            oid = repo.git.rev_parse(request.commitish).strip()
        except GitCommandError as exc:
            return r[m.Infra.GitOidReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitOidReport].fail(
                f"rev-parse failed for {request.commitish}: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitOidReport].ok(m.Infra.GitOidReport(oid=oid))

    @classmethod
    def git_ref_heads(
        cls,
        request: m.Infra.GitRefHeadsRequest,
    ) -> p.Result[m.Infra.GitRefHeadsReport]:
        """Map every ref below ``namespace`` to its tip oid.

        Names are relative to the namespace; the symbolic remote ``HEAD`` is
        an alias of another listed ref and is left out.

        Returns:
            The resulting ``p.Result[m.Infra.GitRefHeadsReport]``.

        """
        prefix = f"{request.namespace.rstrip('/')}/"
        try:
            repo = cls._repo(request.repo_root)
            text = repo.git.for_each_ref("--format=%(refname)%00%(objectname)", prefix)
        except GitCommandError as exc:
            return r[m.Infra.GitRefHeadsReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitRefHeadsReport].fail(
                f"failed to list refs below {request.namespace}: {exc}",
                exception=exc,
            )
        heads = {
            name.removeprefix(prefix): oid
            for name, _, oid in (line.partition("\0") for line in text.splitlines())
            if name.removeprefix(prefix) != c.Infra.GIT_HEAD
        }
        return r[m.Infra.GitRefHeadsReport].ok(m.Infra.GitRefHeadsReport(heads=heads))

    @classmethod
    def git_stash_oids(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitOidListReport]:
        """List the stash commits, newest (``stash@{0}``) first.

        Returns:
            The resulting ``p.Result[m.Infra.GitOidListReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            text = repo.git.stash("list", "--format=%H")
        except GitCommandError as exc:
            return r[m.Infra.GitOidListReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitOidListReport].fail(
                f"failed to list stash entries: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitOidListReport].ok(
            m.Infra.GitOidListReport(oids=tuple(text.split())),
        )

    @classmethod
    def git_remote_branch_oid(
        cls,
        request: m.Infra.GitRemoteBranchRequest,
    ) -> p.Result[m.Infra.GitTextReport]:
        """Ask the remote itself for one branch tip; empty text means absent.

        Unlike a remote-tracking ref this is the live remote state, so it
        proves a publication rather than remembering one.

        Returns:
            The resulting ``p.Result[m.Infra.GitTextReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            text = repo.git.ls_remote(
                "--heads",
                request.remote,
                f"refs/heads/{request.branch}",
            )
        except GitCommandError as exc:
            return r[m.Infra.GitTextReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitTextReport].fail(
                f"failed to query {request.remote} for {request.branch}: {exc}",
                exception=exc,
            )
        output = text if isinstance(text, str) else str(text)
        return r[m.Infra.GitTextReport].ok(
            m.Infra.GitTextReport(text=output.partition("\t")[0].strip()),
        )

    @classmethod
    def git_remote_default_branch(
        cls,
        request: m.Infra.GitRemoteRequest,
    ) -> p.Result[m.Infra.GitTextReport]:
        """Ask the remote itself which branch its ``HEAD`` declares.

        The forge default branch is the integration declaration of a
        standalone repository; it is read live, never from a cached
        ``refs/remotes/<remote>/HEAD``.

        Returns:
            The declared branch name, or a failure when the remote declares none.

        """
        try:
            text = cls._repo(request.repo_root).git.ls_remote(
                "--symref",
                request.remote,
                c.Infra.GIT_HEAD,
            )
        except GitCommandError as exc:
            return r[m.Infra.GitTextReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitTextReport].fail(
                f"failed to query {request.remote} for its default branch: {exc}",
                exception=exc,
            )
        output = text if isinstance(text, str) else str(text)
        symref_prefix = f"ref: {c.Infra.GIT_REFS_HEADS}"
        for line in output.splitlines():
            target, _, name = line.partition("\t")
            if name == c.Infra.GIT_HEAD and target.startswith(symref_prefix):
                return r[m.Infra.GitTextReport].ok(
                    m.Infra.GitTextReport(text=target.removeprefix(symref_prefix)),
                )
        return r[m.Infra.GitTextReport].fail(
            f"{request.remote} declares no default branch through its HEAD",
        )

    @classmethod
    def git_unique_patch_oids(
        cls,
        request: m.Infra.GitMergeProbeRequest,
    ) -> p.Result[m.Infra.GitOidListReport]:
        """List commits whose patch identity is not represented in the baseline.

        Returns:
            Real unique patch OIDs from read-only git cherry, without merge-tree writes.

        """
        try:
            text = cls._repo(request.repo_root).git.cherry(
                request.base,
                request.commitish,
            )
        except GitCommandError as exc:
            return r[m.Infra.GitOidListReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitOidListReport].fail(
                f"failed to inspect unique patches: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitOidListReport].ok(
            m.Infra.GitOidListReport(
                oids=tuple(
                    line.removeprefix("+ ")
                    for line in text.splitlines()
                    if line.startswith("+ ")
                ),
            ),
        )

    @classmethod
    def git_merge_is_noop(
        cls,
        request: m.Infra.GitMergeProbeRequest,
    ) -> p.Result[m.Infra.GitBoolReport]:
        """Whether merging ``commitish`` into ``base`` leaves its tree unchanged.

        This proves a squash- or rebase-merged branch is already contained in
        ``base`` without touching the index or worktree; a conflicting merge
        is not a no-op.

        Returns:
            The resulting ``p.Result[m.Infra.GitBoolReport]``.

        """
        try:
            repo = cls._repo(request.repo_root)
            merged = repo.git.merge_tree(
                "--write-tree",
                request.base,
                request.commitish,
            ).splitlines()[0]
            base_tree = repo.git.rev_parse(f"{request.base}^{{tree}}").strip()
        except GitCommandError as exc:
            if exc.status == c.Infra.GIT_EXIT_NEGATIVE:
                return r[m.Infra.GitBoolReport].ok(m.Infra.GitBoolReport(value=False))
            return r[m.Infra.GitBoolReport].fail(str(exc), exception=exc)
        except (OSError, ValueError, IndexError) as exc:
            return r[m.Infra.GitBoolReport].fail(
                f"merge probe failed for {request.commitish}: {exc}",
                exception=exc,
            )
        return r[m.Infra.GitBoolReport].ok(
            m.Infra.GitBoolReport(value=merged.strip() == base_tree),
        )

    @classmethod
    def git_last_activity(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitTimestampReport]:
        """Newest of the HEAD commit time and this worktree's last HEAD move.

        The HEAD reflog is per worktree, so checkouts, commits, resets and
        rebases in one linked worktree never age or refresh another.

        Returns:
            The resulting ``p.Result[m.Infra.GitTimestampReport]``.

        """
        return cls.git_ref_last_activity(
            m.Infra.GitCommitishRequest(repo_root=request.repo_root, commitish="HEAD"),
        )

    @classmethod
    def git_ref_last_activity(
        cls,
        request: m.Infra.GitCommitishRequest,
    ) -> p.Result[m.Infra.GitTimestampReport]:
        """Read the newest commit/ref movement for one explicit reference.

        Returns:
            Activity evidence, never an ownership or abandonment decision.

        """
        try:
            repo = cls._repo(request.repo_root)
            committed = int(
                repo.git.log("-1", "--format=%ct", request.commitish).strip(),
            )
            moved = repo.git.log(
                "--walk-reflogs",
                "-1",
                "--date=unix",
                "--format=%gd",
                request.commitish,
            ).strip()
        except GitCommandError as exc:
            return r[m.Infra.GitTimestampReport].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[m.Infra.GitTimestampReport].fail(
                f"failed to read last activity: {exc}",
                exception=exc,
            )
        stamp = moved.partition("@{")[2].rstrip("}")
        latest = max(committed, int(stamp)) if stamp.isdigit() else committed
        return r[m.Infra.GitTimestampReport].ok(
            m.Infra.GitTimestampReport(epoch_seconds=latest),
        )


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticRefsMixin"]
