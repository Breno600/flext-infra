"""Repository-local development worktree lifecycle service."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, override

from flext_infra import c, m, p, r, s, t, u


class FlextInfraWorktreeService(s[str]):
    """List, add, update, and remove development lanes under the repository."""

    operation: Annotated[
        c.Infra.WorktreeOperation, m.Field(description="Worktree lifecycle operation")
    ]
    branch: Annotated[
        str | None, m.Field(description="Git branch identifying the development lane")
    ] = None
    base: Annotated[
        str | None,
        m.Field(description="Commit-ish used to create or fast-forward a branch"),
    ] = None
    epic_lane: Annotated[
        Path | None,
        m.Field(description="Registered epic lane owning this nested child lane"),
    ] = None

    def _primary_root(self) -> p.Result[Path]:
        """Resolve the primary worktree from Git's canonical registry."""
        primary = u.Infra.git_primary_worktree_root(
            m.Infra.GitRepoRequest(repo_root=self.repository_root)
        )
        if primary.failure:
            return r[Path].from_failure(primary)
        return r[Path].ok(primary.value.primary_root)

    def _validated_branch(self) -> p.Result[str]:
        """Validate and return the branch required by mutating operations."""
        branch = (self.branch or "").strip()
        if not branch:
            return r[str].fail(f"worktree {self.operation} requires --branch")
        checked = u.Infra.git_check_branch_format(
            m.Infra.GitBranchRequest(repo_root=self.repository_root, branch=branch)
        )
        if checked.failure or not checked.value.value:
            return r[str].from_failure(checked)
        return r[str].ok(branch)

    @staticmethod
    def _lanes_root(
        primary_root: Path, epic_lane: Path | None = None
    ) -> p.Result[Path]:
        """Place new lanes outside every ancestor project discovery boundary.

        A child lane is namespaced by its epic instead of by the repository:
        the epic owns the container, so Git's own registry proves the
        parent/child topology and no epic can be retired while one of its
        children is still registered.
        """
        if epic_lane is not None:
            return r[Path].ok(
                (epic_lane.resolve() / c.Infra.WORKTREES_DIRNAME).resolve()
            )
        resolved_primary = primary_root.resolve()
        outermost_project = resolved_primary
        for candidate in resolved_primary.parents:
            if (candidate / c.PYPROJECT_FILENAME).is_file():
                outermost_project = candidate
            if (candidate / ".git").exists():
                break
        namespace_digest = u.Cli.sha256_content(str(resolved_primary))[
            : c.Infra.WORKTREE_NAMESPACE_DIGEST_LENGTH
        ]
        namespace = f"{resolved_primary.name}-{namespace_digest}"
        return r[Path].ok(
            (outermost_project.parent / c.Infra.WORKTREES_DIRNAME / namespace).resolve()
        )

    @classmethod
    def _lane_path(
        cls, primary_root: Path, branch: str, epic_lane: Path | None = None
    ) -> p.Result[Path]:
        """Derive an isolated lane path and reject branch traversal."""
        root_result = cls._lanes_root(primary_root, epic_lane)
        if root_result.failure:
            return r[Path].from_failure(root_result)
        lanes_root = root_result.value
        lane_name = (
            branch.rsplit("/", maxsplit=1)[-1] if epic_lane is not None else branch
        )
        lane_path = (lanes_root / lane_name).resolve()
        if not lane_path.is_relative_to(lanes_root):
            return r[Path].fail(f"branch resolves outside {c.Infra.WORKTREES_DIRNAME}")
        return r[Path].ok(lane_path)

    @classmethod
    def canonical_lane_path(
        cls, primary_root: Path, branch: str, epic_lane: Path | None = None
    ) -> p.Result[Path]:
        """Return the canonical path reserved by one branch topology."""
        return cls._lane_path(primary_root, branch, epic_lane)

    @staticmethod
    def _registered_worktrees(
        primary_root: Path,
    ) -> p.Result[t.VariadicTuple[t.Pair[Path, str]]]:
        """Pair every registered worktree root with the branch it checks out."""
        listed = u.Infra.git_list_worktrees(
            m.Infra.GitRepoRequest(repo_root=primary_root)
        )
        if listed.failure:
            return r[t.VariadicTuple[t.Pair[Path, str]]].from_failure(listed)
        entries: list[t.Pair[Path, str]] = []
        current: Path | None = None
        branch = ""
        for line in (*listed.value.text.splitlines(), ""):
            if line.startswith("worktree "):
                current = Path(line.removeprefix("worktree ").strip()).resolve()
                branch = ""
            elif line.startswith("branch refs/heads/"):
                branch = line.removeprefix("branch refs/heads/").strip()
            elif not line and current is not None:
                entries.append((current, branch))
                current = None
                branch = ""
        return r[t.VariadicTuple[t.Pair[Path, str]]].ok(tuple(entries))

    @classmethod
    def registered_lane(cls, primary_root: Path, branch: str) -> p.Result[Path]:
        """Resolve an existing branch lane from Git's canonical registry."""
        entries = cls._registered_worktrees(primary_root)
        if entries.failure:
            return r[Path].from_failure(entries)
        for root, registered_branch in entries.value:
            if registered_branch == branch:
                return r[Path].ok(root)
        return r[Path].fail(f"worktree branch is not registered: {branch}")

    @classmethod
    def registered_children(
        cls, primary_root: Path, epic_lane: Path
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Return every registered lane nested under one epic lane container."""
        entries = cls._registered_worktrees(primary_root)
        if entries.failure:
            return r[t.VariadicTuple[Path]].from_failure(entries)
        container = (epic_lane.resolve() / c.Infra.WORKTREES_DIRNAME).resolve()
        return r[t.VariadicTuple[Path]].ok(
            tuple(
                sorted(
                    root
                    for root, _ in entries.value
                    if root != container and root.is_relative_to(container)
                )
            )
        )

    def _ref_exists(self, reference: str) -> p.Result[bool]:
        """Return whether an exact Git ref exists, preserving command failures."""
        checked = u.Infra.git_ref_exists(
            m.Infra.GitRefRequest(repo_root=self.repository_root, reference=reference)
        )
        if checked.failure:
            return r[bool].from_failure(checked)
        return r[bool].ok(checked.value.value)

    @classmethod
    def setup_lane(cls, lane: Path) -> p.Result[bool]:
        """Provision an isolated environment inside one lane."""
        return u.Infra.setup_lane(lane)

    @staticmethod
    def _rollback_new_lane(
        primary_root: Path,
        lane: Path,
        branch: str,
        created_branch_oid: str | None,
        setup_error: str,
    ) -> p.Result[str]:
        """Roll back only a clean lane created by the current add operation."""
        return u.Infra.rollback_new_lane(
            primary_root, lane, branch, created_branch_oid, setup_error
        )

    def _add(self, primary_root: Path, branch: str, base: str) -> p.Result[str]:
        """Create one branch worktree without provisioning it."""
        if not self.apply_changes:
            return r[str].fail("worktree add requires --apply")
        if base.startswith("-"):
            return r[str].fail(f"invalid base commitish: {base}")
        resolved = u.Infra.git_resolve_commit(
            m.Infra.GitCommitishRequest(repo_root=primary_root, commitish=base)
        )
        if resolved.failure:
            # `from_failure` handed the caller GitPython's own sentence about
            # refs, which names neither the worktree nor the base it refused.
            # The service states its own contract, the way the option-like
            # base above already does, and carries the cause with it.
            return r[str].fail(
                f"cannot resolve worktree base: {base} ({resolved.error})",
                exception=resolved.exception,
            )
        base_oid = resolved.value.oid
        if self.epic_lane is not None:
            if self.epic_lane.is_symlink():
                return r[str].fail(f"epic lane worktree is a symlink: {self.epic_lane}")
            if not self.epic_lane.is_dir():
                return r[str].fail(
                    f"epic lane worktree does not exist: {self.epic_lane}"
                )
            registered = self._registered_worktrees(primary_root)
            if registered.failure:
                return r[str].from_failure(registered)
            if self.epic_lane.resolve() not in {root for root, _ in registered.value}:
                return r[str].fail(
                    f"registered epic lane is required: {self.epic_lane}"
                )
            container = self.epic_lane / c.Infra.WORKTREES_DIRNAME
            if container.is_symlink():
                return r[str].fail(f"epic worktree container is a symlink: {container}")
        existing = self.registered_lane(primary_root, branch)
        if existing.success:
            return r[str].fail(f"worktree branch is already registered: {branch}")
        lane_result = self._lane_path(primary_root, branch, self.epic_lane)
        if lane_result.failure:
            return r[str].from_failure(lane_result)
        lane = lane_result.value
        if lane.exists():
            return r[str].fail(f"worktree lane already exists: {lane}")
        ensured = u.Cli.ensure_dir(lane.parent)
        if ensured.failure:
            return r[str].from_failure(ensured)
        local = self._ref_exists(f"refs/heads/{branch}")
        if local.failure:
            return r[str].from_failure(local)
        remote = self._ref_exists(f"refs/remotes/origin/{branch}")
        if remote.failure:
            return r[str].from_failure(remote)
        added = u.Infra.git_add_lane_worktree(
            m.Infra.GitWorktreeAddRequest(
                repo_root=self.repository_root,
                lane=lane,
                branch=branch,
                base=base_oid,
                local_branch_exists=local.value,
                track_remote=not local.value and remote.value,
            )
        )
        if added.failure:
            return r[str].from_failure(added)
        created_branch_oid: str | None = None
        if not local.value:
            created_oid = u.Infra.git_repository_head(
                m.Infra.GitRepoRequest(repo_root=lane)
            )
            if created_oid.failure:
                return self._rollback_new_lane(
                    primary_root,
                    lane,
                    branch,
                    None,
                    created_oid.error or "failed to retain created branch identity",
                )
            created_branch_oid = created_oid.value.oid
        pyproject = lane / c.PYPROJECT_FILENAME
        if pyproject.is_file():
            metadata = u.Infra.read_project_metadata_result(lane)
            if metadata.failure:
                return self._rollback_new_lane(
                    primary_root,
                    lane,
                    branch,
                    created_branch_oid,
                    metadata.error or "invalid lane project metadata",
                )
        return r[str].ok(str(lane))

    def _remove(self, primary_root: Path, branch: str) -> p.Result[str]:
        """Remove one clean canonical lane without deleting its branch."""
        if not self.apply_changes:
            return r[str].fail("worktree remove requires --apply")
        lane_result = self.registered_lane(primary_root, branch)
        if lane_result.failure:
            return r[str].from_failure(lane_result)
        lane = lane_result.value
        # Why: removing an epic lane deletes the directory that physically holds
        # its children, so Git would keep registering worktrees whose checkout
        # no longer exists. The registry is the authority on that topology.
        children = self.registered_children(primary_root, lane)
        if children.failure:
            return r[str].from_failure(children)
        if children.value:
            nested = ", ".join(str(child) for child in children.value)
            return r[str].fail(
                f"worktree remove refuses lane {branch} while children are "
                f"registered: {nested}"
            )
        removed = u.Infra.git_remove_clean_worktree(primary_root, lane)
        if removed.failure:
            return r[str].from_failure(removed)
        return r[str].ok(str(lane))

    def _update(self, primary_root: Path, branch: str, base: str) -> p.Result[str]:
        """Merge-forward one clean canonical lane to the requested base."""
        if not self.apply_changes:
            return r[str].fail("worktree update requires --apply")
        lane_result = self.registered_lane(primary_root, branch)
        if lane_result.failure:
            return r[str].from_failure(lane_result)
        lane = lane_result.value
        return u.Infra.update_lane(lane, branch, base)

    @override
    def execute(self) -> p.Result[str]:
        """Execute the selected worktree operation."""
        primary = self._primary_root()
        if primary.failure:
            return r[str].from_failure(primary)
        if self.operation == c.Infra.WorktreeOperation.LIST:
            listed = u.Infra.git_list_worktrees(
                m.Infra.GitRepoRequest(repo_root=primary.value)
            )
            if listed.failure:
                return r[str].from_failure(listed)
            return r[str].ok(listed.value.text)
        branch = self._validated_branch()
        if branch.failure:
            return r[str].from_failure(branch)
        base = (self.base or "").strip()
        if (
            self.operation
            in {c.Infra.WorktreeOperation.ADD, c.Infra.WorktreeOperation.UPDATE}
            and not base
        ):
            return r[str].fail(f"worktree {self.operation} requires --base")
        if self.operation == c.Infra.WorktreeOperation.ADD:
            return self._add(primary.value, branch.value, base)
        if self.operation == c.Infra.WorktreeOperation.UPDATE:
            return self._update(primary.value, branch.value, base)
        return self._remove(primary.value, branch.value)


__all__: list[str] = ["FlextInfraWorktreeService"]
