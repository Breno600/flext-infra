"""Credential-safe remote retention receipts for worktree checkpoints.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from git import GitCommandError

from flext_infra import c, m, r
from flext_infra._utilities._git.remote import FlextInfraUtilitiesGitRemote
from flext_infra._utilities._git.state_checkpoint import (
    FlextInfraUtilitiesGitStateCheckpointMixin,
)

if TYPE_CHECKING:
    from flext_infra import p


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
            case [url], [push_url] if url == push_url:
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


__all__: list[str] = ["FlextInfraUtilitiesGitStatePublicationMixin"]
