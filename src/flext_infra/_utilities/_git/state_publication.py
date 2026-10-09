"""Credential-safe remote retention receipts for worktree checkpoints.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from git import GitCommandError

from flext_infra import c, m, p, r
from flext_infra._utilities import FlextInfraUtilitiesGitRemote
from flext_infra._utilities._git.state_checkpoint import (
    FlextInfraUtilitiesGitStateCheckpointMixin,
)


class FlextInfraUtilitiesGitStatePublicationMixin(
    FlextInfraUtilitiesGitStateCheckpointMixin,
):
    """Bind retained history to one configured credential-free Git endpoint."""

    @classmethod
    def _state_remote_url(cls, root: Path, remote: str) -> str:

        repo = cls._repo(root)
        fetch = repo.git.remote("get-url", "--all", remote).splitlines()
        push = repo.git.remote("get-url", "--push", "--all", remote).splitlines()
        match fetch, push:
            case [str() as url], [str() as push_url] if url == push_url:
                if FlextInfraUtilitiesGitRemote.redact_origin_remote(url) != url:
                    msg = "checkpoint remote must not embed credentials"
                    raise ValueError(msg)
                return url
            case _:
                msg = (
                    "checkpoint publication requires one identical "
                    "fetch and push endpoint"
                )
                raise ValueError(msg)

    @classmethod
    def _state_advertised(cls, root: Path, remote: str, reference: str) -> str:
        return cls._repo(root).git.execute(
            [c.Infra.GIT, "ls-remote", "--refs", remote, reference],
            with_extended_output=False,
            as_process=False,
            stdout_as_string=True,
        )

    @classmethod
    def _state_verify_publication(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        publication: m.Infra.GitWorktreeCheckpointPublication,
    ) -> None:
        cls._state_validate_checkpoint(checkpoint)
        if (publication.checkpoint_ref, publication.checkpoint_oid) != (
            checkpoint.checkpoint_ref,
            checkpoint.worktree_commit,
        ):
            msg = "publication receipt belongs to a different checkpoint"
            raise ValueError(msg)
        root = checkpoint.snapshot.repo_root
        if (
            cls._state_remote_url(root, publication.remote_name)
            != publication.remote_url
        ):
            msg = "checkpoint remote endpoint changed since publication"
            raise ValueError(msg)
        if cls._state_advertised(
            root,
            publication.remote_name,
            checkpoint.checkpoint_ref,
        ).splitlines() != [
            f"{checkpoint.worktree_commit}\t{checkpoint.checkpoint_ref}",
        ]:
            msg = "remote no longer advertises the retained checkpoint"
            raise ValueError(msg)

    @classmethod
    def _state_publish(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        remote: str,
    ) -> m.Infra.GitWorktreeCheckpointPublication:
        cls._state_validate_checkpoint(checkpoint)
        root = checkpoint.snapshot.repo_root
        publication = m.Infra.GitWorktreeCheckpointPublication(
            remote_name=remote,
            remote_url=cls._state_remote_url(root, remote),
            checkpoint_ref=checkpoint.checkpoint_ref,
            checkpoint_oid=checkpoint.worktree_commit,
        )
        advertised = cls._state_advertised(
            root,
            remote,
            checkpoint.checkpoint_ref,
        ).splitlines()
        if advertised and advertised != [
            f"{checkpoint.worktree_commit}\t{checkpoint.checkpoint_ref}",
        ]:
            msg = "remote checkpoint reference belongs to a different capture"
            raise ValueError(msg)
        if not advertised:
            cls._repo(root).git.push(
                "--atomic",
                remote,
                f"{checkpoint.worktree_commit}:{checkpoint.checkpoint_ref}",
            )
        cls._state_verify_publication(checkpoint, publication)
        return publication

    @classmethod
    def git_publish_worktree_checkpoint(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        remote: str,
    ) -> p.Result[m.Infra.GitWorktreeCheckpointPublication]:
        """Publish once by ordinary atomic push and return its exact remote proof.

        Returns:
            The resulting ``p.Result[m.Infra.GitWorktreeCheckpointPublication]``.

        """
        try:
            publication = cls._state_publish(checkpoint, remote)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[m.Infra.GitWorktreeCheckpointPublication].fail(
                str(exc),
                exception=exc,
            )
        return r[m.Infra.GitWorktreeCheckpointPublication].ok(publication)

    @classmethod
    def git_verify_worktree_checkpoint_publication(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        publication: m.Infra.GitWorktreeCheckpointPublication,
    ) -> p.Result[bool]:
        """Revalidate endpoint identity and retained remote reference without writes.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            cls._state_verify_publication(checkpoint, publication)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[bool].fail(str(exc), exception=exc)
        return r[bool].ok(value=True)

    @classmethod
    def _state_checkpoint_branch_ref(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        publication: m.Infra.GitWorktreeCheckpointPublication,
        branch: str,
    ) -> str:
        cls._state_verify_publication(checkpoint, publication)
        reference = f"{c.Infra.GIT_REFS_HEADS}{branch}"
        cls._repo(checkpoint.snapshot.repo_root).git.check_ref_format(reference)
        return reference

    @classmethod
    def git_create_checkpoint_branch(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        publication: m.Infra.GitWorktreeCheckpointPublication,
        branch: str,
    ) -> p.Result[bool]:
        """Create an immutable recovery alias, never switch or carry unknown WIP.

        The live published checkpoint authenticates the captured index and raw
        working scope. The branch points to that retained commit, not HEAD or a
        caller-selected start. This is preservation, not managed lane admission.

        Returns:
            Successful CAS creation or an unchanged-source refusal.
        """
        root = checkpoint.snapshot.repo_root
        try:
            with cls._state_leases((root,)):
                reference = cls._state_checkpoint_branch_ref(
                    checkpoint,
                    publication,
                    branch,
                )
                cls._state_require_original(checkpoint.snapshot)
                cls._repo(root).git.update_ref(
                    "--no-deref",
                    reference,
                    checkpoint.worktree_commit,
                    "",
                )
        except (GitCommandError, OSError, ValueError) as exc:
            return r[bool].fail(str(exc), exception=exc)
        return r[bool].ok(value=True)

    @classmethod
    def _state_push_checkpoint_branch(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        publication: m.Infra.GitWorktreeCheckpointPublication,
        branch: str,
    ) -> None:
        root = checkpoint.snapshot.repo_root
        reference = cls._state_checkpoint_branch_ref(checkpoint, publication, branch)
        repo = cls._repo(root)
        if repo.commit(reference).hexsha != checkpoint.worktree_commit:
            msg = "recovery branch no longer names the retained checkpoint"
            raise ValueError(msg)
        prior = cls._state_advertised(
            root, publication.remote_name, reference
        ).splitlines()
        if prior and prior != [f"{checkpoint.worktree_commit}\t{reference}"]:
            msg = "remote recovery reference belongs to different history"
            raise ValueError(msg)
        if not prior:
            # The empty lease permits creation only, never rewriting a live ref.
            repo.git.push(
                "--atomic",
                f"--force-with-lease={reference}:",
                publication.remote_name,
                f"{checkpoint.worktree_commit}:{reference}",
            )
        advertised = cls._state_advertised(
            root,
            publication.remote_name,
            reference,
        ).splitlines()
        if advertised != [f"{checkpoint.worktree_commit}\t{reference}"]:
            msg = "remote does not advertise the published recovery branch"
            raise ValueError(msg)

    @classmethod
    def git_publish_checkpoint_branch(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        publication: m.Infra.GitWorktreeCheckpointPublication,
        branch: str,
    ) -> p.Result[bool]:
        """Publish only an alias of the independently retained checkpoint.

        Returns:
            A live remote identity proof, without changing source bytes or index.

        """
        root = checkpoint.snapshot.repo_root
        try:
            with cls._state_leases((root,)):
                cls._state_push_checkpoint_branch(checkpoint, publication, branch)
        except (GitCommandError, OSError, ValueError) as exc:
            return r[bool].fail(str(exc), exception=exc)
        return r[bool].ok(value=True)

    @classmethod
    def _state_delete_checkpoint_branch(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        publication: m.Infra.GitWorktreeCheckpointPublication,
        branch: str,
        expected_oid: str,
    ) -> None:
        root = checkpoint.snapshot.repo_root
        reference = cls._state_checkpoint_branch_ref(checkpoint, publication, branch)
        if expected_oid != checkpoint.worktree_commit:
            msg = "recovery deletion lease is not the retained checkpoint"
            raise ValueError(msg)
        cls._repo(root).git.push(
            f"--force-with-lease={reference}:{expected_oid}",
            publication.remote_name,
            f":{reference}",
        )
        cls._state_verify_publication(checkpoint, publication)
        if cls._state_advertised(root, publication.remote_name, reference):
            msg = "remote still advertises the recovery alias"
            raise ValueError(msg)

    @classmethod
    def git_delete_checkpoint_branch(
        cls,
        checkpoint: m.Infra.GitWorktreeStateCheckpoint,
        publication: m.Infra.GitWorktreeCheckpointPublication,
        branch: str,
        expected_oid: str,
    ) -> p.Result[bool]:
        """CAS-delete a remote alias while its independent checkpoint stays live.

        This does not retire the checkpoint or authorize managed lane retirement.

        Returns:
            Successful alias deletion or a stale-object/retention refusal.

        """
        root = checkpoint.snapshot.repo_root
        try:
            with cls._state_leases((root,)):
                cls._state_delete_checkpoint_branch(
                    checkpoint,
                    publication,
                    branch,
                    expected_oid,
                )
        except (GitCommandError, OSError, ValueError) as exc:
            return r[bool].fail(str(exc), exception=exc)
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraUtilitiesGitStatePublicationMixin"]
