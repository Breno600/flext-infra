"""Repository-local development worktree lifecycle service.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, override

from flext_cli import r

from flext_infra import c, m, p, t, u
from flext_infra.base import s
from flext_infra.git_lanes import FlextInfraGitLanes


class FlextInfraWorktreeService(s[str]):
    """List, add, update, and remove development lanes under the repository."""

    operation: Annotated[
        c.Infra.WorktreeOperation,
        m.Field(description="Worktree lifecycle operation"),
    ]
    branch: Annotated[
        str | None,
        m.Field(description="Git branch identifying the development lane"),
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
        """Resolve the primary worktree from Git's canonical registry.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        primary = u.Infra.git_primary_worktree_root(
            m.Infra.GitRepoRequest(repo_root=self.repository_root),
        )
        if primary.failure:
            return r[Path].from_failure(primary)
        return r[Path].ok(primary.value.primary_root)

    def _validated_branch(self) -> p.Result[str]:
        """Validate and return the branch required by mutating operations.

        Returns:
            The resulting ``p.Result[str]``.

        """
        branch = (self.branch or "").strip()
        if not branch:
            return r[str].fail(f"worktree {self.operation} requires --branch")
        checked = u.Infra.git_check_branch_format(
            m.Infra.GitBranchRequest(repo_root=self.repository_root, branch=branch),
        )
        if checked.failure or not checked.value.value:
            return r[str].from_failure(checked)
        return r[str].ok(branch)

    @staticmethod
    def _lanes_root(
        primary_root: Path,
        epic_lane: Path | None = None,
    ) -> p.Result[Path]:
        """Place new lanes outside every ancestor project discovery boundary.

        A child lane is namespaced by its epic instead of by the repository:
        the epic owns the container, so Git's own registry proves the
        parent/child topology and no epic can be retired while one of its
        children is still registered.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        if epic_lane is not None:
            return r[Path].ok(
                (epic_lane.resolve() / c.Infra.WORKTREES_DIRNAME).resolve(),
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
            (
                outermost_project.parent / c.Infra.WORKTREES_DIRNAME / namespace
            ).resolve(),
        )

    @classmethod
    def _lane_path(
        cls,
        primary_root: Path,
        branch: str,
        epic_lane: Path | None = None,
    ) -> p.Result[Path]:
        """Derive an isolated lane path and reject branch traversal.

        Returns:
            The resulting ``p.Result[Path]``.

        """
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
        cls,
        primary_root: Path,
        branch: str,
        epic_lane: Path | None = None,
    ) -> p.Result[Path]:
        """Return the canonical path reserved by one branch topology.

        Returns:
            The canonical path reserved by one branch topology.

        """
        return cls._lane_path(primary_root, branch, epic_lane)

    @staticmethod
    def _registered_worktrees(
        primary_root: Path,
    ) -> p.Result[t.VariadicTuple[t.Pair[Path, str]]]:
        """Pair every registered worktree root with the branch it checks out.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[t.Pair[Path, str]]]``.

        """
        listed = u.Infra.git_list_worktrees(
            m.Infra.GitRepoRequest(repo_root=primary_root),
        )
        if listed.failure:
            return r[t.VariadicTuple[t.Pair[Path, str]]].from_failure(listed)
        entries = tuple(
            (entry.path, entry.branch or "") for entry in listed.value.entries
        )
        return r[t.VariadicTuple[t.Pair[Path, str]]].ok(entries)

    @classmethod
    def registered_lanes(
        cls,
        primary_root: Path,
        branch: str,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Return the lanes Git registers for a branch; empty means none exists.

        Returns:
            The lanes Git registers for a branch; empty means none exists.

        """
        entries = cls._registered_worktrees(primary_root)
        if entries.failure:
            return r[t.VariadicTuple[Path]].from_failure(entries)
        return r[t.VariadicTuple[Path]].ok(
            tuple(root for root, registered in entries.value if registered == branch),
        )

    @classmethod
    def registered_lane(cls, primary_root: Path, branch: str) -> p.Result[Path]:
        """Resolve an existing branch lane from Git's canonical registry.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        lanes = cls.registered_lanes(primary_root, branch)
        if lanes.failure:
            return r[Path].from_failure(lanes)
        if not lanes.value:
            return r[Path].fail(f"worktree branch is not registered: {branch}")
        return r[Path].ok(lanes.value[0])

    @classmethod
    def registered_children(
        cls,
        primary_root: Path,
        epic_lane: Path,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Return every registered lane nested under one epic lane container.

        Returns:
            Every registered lane nested under one epic lane container.

        """
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
                ),
            ),
        )

    def _ref_exists(self, reference: str) -> p.Result[bool]:
        """Return whether an exact Git ref exists, preserving command failures.

        Returns:
            Whether an exact Git ref exists, preserving command failures.

        """
        checked = u.Infra.git_ref_exists(
            m.Infra.GitRefRequest(repo_root=self.repository_root, reference=reference),
        )
        if checked.failure:
            return r[bool].from_failure(checked)
        return r[bool].ok(checked.value.value)

    @classmethod
    def setup_lane(cls, lane: Path) -> p.Result[bool]:
        """Provision one lane in its own physical environment inside the lane.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return u.Infra.setup_lane(lane)

    @staticmethod
    def _rollback_new_lane(
        primary_root: Path,
        lane: Path,
        branch: str,
        created_branch_oid: str | None,
        setup_error: str,
    ) -> p.Result[str]:
        """Roll back only a clean lane created by the current add operation.

        Returns:
            The resulting ``p.Result[str]``.

        """
        return u.Infra.rollback_new_lane(
            primary_root,
            lane,
            branch,
            created_branch_oid,
            setup_error,
        )

    def _add(self, primary_root: Path, branch: str, base: str) -> p.Result[str]:
        """Create one branch worktree without provisioning it.

        Returns:
            The resulting ``p.Result[str]``.

        """
        if not self.apply_changes:
            return r[str].fail("worktree add requires --apply")
        if base.startswith("-"):
            return r[str].fail(f"invalid base commitish: {base}")
        admitted = u.Infra.git_verify_lane(
            m.Infra.GitLaneVerificationRequest(
                repo_root=self.repository_root,
                operation="create",
                candidate=base,
            ),
        )
        if admitted.failure:
            return r[str].from_failure(admitted)
        base_oid = self._resolved_base(primary_root, base)
        if base_oid.failure:
            return r[str].from_failure(base_oid)
        admission = FlextInfraGitLanes.admit_lane(
            primary_root,
            branch,
            base_oid.value,
        )
        if admission.failure:
            return r[str].from_failure(admission)
        lane = self._new_lane_path(primary_root, branch)
        if lane.failure:
            return r[str].from_failure(lane)
        return self._create_lane(primary_root, lane.value, branch, base_oid.value)

    @staticmethod
    def _resolved_base(primary_root: Path, base: str) -> p.Result[str]:
        """Resolve the requested base to the commit the new lane starts from.

        Returns:
            The base commit oid, or the service's own refusal naming the base.

        """
        resolved = u.Infra.git_resolve_commit(
            m.Infra.GitCommitishRequest(repo_root=primary_root, commitish=base),
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
        return r[str].ok(resolved.value.oid)

    def _checked_epic_lane(self, primary_root: Path) -> p.Result[bool]:
        """Require a requested epic lane to be a registered, real container.

        Returns:
            Success when no epic lane is requested or the epic lane is valid.

        """
        epic_lane = self.epic_lane
        if epic_lane is None:
            return r[bool].ok(value=True)
        if epic_lane.is_symlink() or not epic_lane.is_dir():
            reason = "is a symlink" if epic_lane.is_symlink() else "does not exist"
            return r[bool].fail(f"epic lane worktree {reason}: {epic_lane}")
        registered = self._registered_worktrees(primary_root)
        if registered.failure:
            return r[bool].from_failure(registered)
        if epic_lane.resolve() not in {root for root, _ in registered.value}:
            return r[bool].fail(f"registered epic lane is required: {epic_lane}")
        container = epic_lane / c.Infra.WORKTREES_DIRNAME
        if container.is_symlink():
            return r[bool].fail(f"epic worktree container is a symlink: {container}")
        return r[bool].ok(value=True)

    def _new_lane_path(self, primary_root: Path, branch: str) -> p.Result[Path]:
        """Reserve the canonical path of a branch that has no lane yet.

        Returns:
            The unused canonical lane path for the branch.

        """
        epic = self._checked_epic_lane(primary_root)
        if epic.failure:
            return r[Path].from_failure(epic)
        existing = self.registered_lanes(primary_root, branch)
        if existing.failure:
            return r[Path].from_failure(existing)
        if existing.value:
            return r[Path].fail(f"worktree branch is already registered: {branch}")
        lane = self._lane_path(primary_root, branch, self.epic_lane)
        if lane.success and lane.value.exists():
            return r[Path].fail(f"worktree lane already exists: {lane.value}")
        return lane

    def _branch_refs(self, branch: str) -> p.Result[t.Pair[bool, bool]]:
        """Report whether the branch exists locally and on ``origin``.

        Returns:
            The local and remote existence of the branch, in that order.

        """
        local = self._ref_exists(f"refs/heads/{branch}")
        if local.failure:
            return r[t.Pair[bool, bool]].from_failure(local)
        remote = self._ref_exists(f"refs/remotes/origin/{branch}")
        if remote.failure:
            return r[t.Pair[bool, bool]].from_failure(remote)
        return r[t.Pair[bool, bool]].ok((local.value, remote.value))

    def _create_lane(
        self,
        primary_root: Path,
        lane: Path,
        branch: str,
        base_oid: str,
    ) -> p.Result[str]:
        """Register the lane worktree for a branch at the resolved base.

        Returns:
            The created lane path.

        """
        ensured = u.Cli.ensure_dir(lane.parent)
        if ensured.failure:
            return r[str].from_failure(ensured)
        refs = self._branch_refs(branch)
        if refs.failure:
            return r[str].from_failure(refs)
        local_exists, remote_exists = refs.value
        added = u.Infra.git_add_lane_worktree(
            m.Infra.GitWorktreeAddRequest(
                repo_root=self.repository_root,
                lane=lane,
                branch=branch,
                base=base_oid,
                local_branch_exists=local_exists,
                track_remote=not local_exists and remote_exists,
            ),
        )
        if added.failure:
            return r[str].from_failure(added)
        return self._verified_new_lane(
            primary_root,
            lane,
            branch,
            created_branch=not local_exists,
        )

    def _verified_new_lane(
        self,
        primary_root: Path,
        lane: Path,
        branch: str,
        *,
        created_branch: bool,
    ) -> p.Result[str]:
        """Keep a new lane only when its identity and metadata are valid.

        Returns:
            The lane path, or the rollback outcome of an invalid new lane.

        """
        created_branch_oid: str | None = None
        if created_branch:
            created_oid = u.Infra.git_repository_head(
                m.Infra.GitRepoRequest(repo_root=lane),
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
        if (lane / c.PYPROJECT_FILENAME).is_file():
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
        """Remove one clean canonical lane without deleting its branch.

        Returns:
            The resulting ``p.Result[str]``.

        """
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
                f"registered: {nested}",
            )
        integrated = FlextInfraGitLanes.verify_retirement(primary_root, branch)
        if integrated.failure:
            return r[str].from_failure(integrated)
        return u.Infra.git_remove_clean_worktree(primary_root, lane).map(
            lambda _: str(lane),
        )

    def _update(self, primary_root: Path, branch: str, base: str) -> p.Result[str]:
        """Merge-forward one clean canonical lane to the requested base.

        Returns:
            The resulting ``p.Result[str]``.

        """
        if not self.apply_changes:
            return r[str].fail("worktree update requires --apply")
        lane_result = self.registered_lane(primary_root, branch)
        if lane_result.failure:
            return r[str].from_failure(lane_result)
        lane = lane_result.value
        return u.Infra.update_lane(lane, branch, base)

    @override
    def execute(self) -> p.Result[str]:
        """Execute the selected worktree operation.

        Returns:
            The resulting ``p.Result[str]``.

        """
        primary = self._primary_root()
        if primary.failure:
            return r[str].from_failure(primary)
        if self.operation == c.Infra.WorktreeOperation.LIST:
            listed = u.Infra.git_list_worktrees(
                m.Infra.GitRepoRequest(repo_root=primary.value),
            )
            if listed.failure:
                return r[str].from_failure(listed)
            return r[str].ok(listed.value.porcelain)
        return self._mutate(primary.value)

    def _mutate(self, primary_root: Path) -> p.Result[str]:
        """Run the selected branch-scoped operation on one validated branch.

        Returns:
            The resulting ``p.Result[str]``.

        """
        branch = self._validated_branch()
        if branch.failure:
            return r[str].from_failure(branch)
        base = (self.base or "").strip()
        if self.operation == c.Infra.WorktreeOperation.REMOVE:
            return self._remove(primary_root, branch.value)
        if not base:
            return r[str].fail(f"worktree {self.operation} requires --base")
        if self.operation == c.Infra.WorktreeOperation.ADD:
            return self._add(primary_root, branch.value, base)
        return self._update(primary_root, branch.value, base)


__all__: list[str] = ["FlextInfraWorktreeService"]
