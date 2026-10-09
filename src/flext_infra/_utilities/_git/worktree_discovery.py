"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from git import GitCommandError

from flext_infra import p, r, t
from flext_infra._utilities import FlextInfraUtilitiesBase
from flext_infra._utilities._git.worktree_roots import (
    FlextInfraUtilitiesGitWorktreeRootsMixin,
)


class FlextInfraUtilitiesGitWorktreeDiscoveryMixin(
    FlextInfraUtilitiesGitWorktreeRootsMixin,
):
    """Own worktree discovery operations."""

    @staticmethod
    def git_remote_identity(url: str) -> str:
        """Normalize remotes to owner/repo identity across HTTPS, SSH, and aliases.

        CI deploy-key init rewrites private member ``origin`` to an SSH URL that
        may use a Host alias (for example ``git@charts-github:org/repo.git``)
        while the workspace manifest and ``.gitmodules`` keep HTTPS on
        ``github.com``. Compare the repository path only so gen does not
        false-fail after a successful private checkout.

        Returns:
            The resulting ``str``.

        """
        value = url.strip()
        remote_path = ""
        if value.startswith("git@"):
            host_path = value.removeprefix("git@")
            if ":" in host_path:
                _host, remote_path = host_path.split(":", 1)
        else:
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https", "ssh"} and parsed.netloc:
                remote_path = parsed.path.lstrip("/")
            else:
                remote_path = value
        remote_path = remote_path.rstrip("/").removesuffix(".git")
        parts = [part for part in remote_path.split("/") if part]
        match parts:
            case [*_, owner, repo]:
                return f"{owner}/{repo}".lower()
            case _:
                return remote_path.lower()

    @classmethod
    def git_submodule_paths(cls, repository_root: Path) -> p.Result[t.SequenceOf[Path]]:
        """Resolve every initialized recursive submodule path.

        Returns:
            The resulting ``p.Result[t.SequenceOf[Path]]``.

        Raises:
            ValueError: If malformed git submodule status line.

        """
        try:
            repo = cls._repo(repository_root)
            status = repo.git.submodule("status", "--recursive")
        except GitCommandError as exc:
            return r[t.SequenceOf[Path]].fail(str(exc), exception=exc)
        except (OSError, ValueError) as exc:
            return r[t.SequenceOf[Path]].fail(
                f"failed to discover Git submodules: {exc}",
                exception=exc,
            )
        paths: t.MutableSequenceOf[Path] = []
        for raw_line in status.splitlines():
            normalized = raw_line.strip()
            if not normalized:
                continue
            _status_and_sha, separator, remainder = normalized.partition(" ")
            path_fields = remainder.split(maxsplit=1)
            if not separator or not path_fields:
                msg = f"malformed git submodule status line: {raw_line!r}"
                raise ValueError(msg)
            relative_path_text = path_fields[0]
            relative_path = Path(relative_path_text)
            if (repository_root / relative_path / ".git").exists():
                paths.append(relative_path)
        return r[t.SequenceOf[Path]].ok(
            tuple(sorted(paths, key=FlextInfraUtilitiesBase.path_depth_then_text)),
        )


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeDiscoveryMixin"]
