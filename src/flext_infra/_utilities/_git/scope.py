"""Git-aware scope resolution mixin for the private git facet.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m
from flext_infra._utilities._git.semantic_identity import (
    FlextInfraUtilitiesGitSemanticIdentityMixin,
)
from flext_infra._utilities._git.semantic_index import (
    FlextInfraUtilitiesGitSemanticIndexMixin,
)

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesGitScopeMixin(FlextInfraUtilitiesGitSemanticIndexMixin):
    """Static helpers for resolving tracked files and directories within Git scopes."""

    @classmethod
    def _git_repo_root(cls, scope_root: str) -> str | None:
        """Return the enclosing Git worktree root, or ``None`` outside any worktree.

        Only the canonical three-way work-tree probe may classify a path as
        outside Git; a genuine probe or open failure raises instead of being
        reported as absence. Git is a required dependency of this scope probe;
        unavailable executables must fail rather than hide tracked-file scope.

        Returns:
            The enclosing Git worktree root, or ``None`` outside any worktree.

        Raises:
            OSError: If ``probed.failure``; or if ``opened.failure``.
            RuntimeError: If opened Git repository has no worktree.

        """
        resolved_scope = Path(scope_root).resolve()
        probe = FlextInfraUtilitiesGitSemanticIdentityMixin.git_is_inside_work_tree
        probed = probe(m.Infra.GitRepoRequest(repo_root=resolved_scope))
        if probed.failure:
            raise OSError(probed.error or "failed to probe Git work tree")
        if not probed.value.value:
            return None
        opened = cls._open_repo(resolved_scope)
        if opened.failure:
            raise OSError(opened.error or "failed to open git repository")
        working_tree_dir = opened.value.working_tree_dir
        if working_tree_dir is None:
            msg = f"opened Git repository has no worktree: {scope_root}"
            raise RuntimeError(msg)
        return str(Path(working_tree_dir).resolve())

    @classmethod
    def _git_tracked_repo_relative_paths(cls, repo_root: str) -> t.StrSequence:
        """Return literal index and dirty paths, preserving every filename byte.

        Porcelain v1 with NUL termination disables filename quoting. Disabling
        rename detection yields one path per record, including both sides of
        a rename as independent deletion/addition entries. Native Git errors
        escape instead of returning an incomplete inventory.

        Returns:
            Literal index and dirty paths, preserving every filename byte.

        """
        resolved_root = Path(repo_root).resolve()
        repo = cls._repo(resolved_root)
        tracked_output = repo.git.ls_files("-z", strip_newline_in_stdout=False)
        status_output = repo.git.status(
            "--porcelain=v1",
            "-z",
            "--no-renames",
            "--untracked-files=all",
            strip_newline_in_stdout=False,
        )
        scope_paths = {path for path in tracked_output.split("\0") if path}
        scope_paths.update(record[3:] for record in status_output.split("\0") if record)
        return tuple(sorted(scope_paths))

    @classmethod
    def _git_tracked_scope_relative_paths(cls, scope_root: str) -> t.StrSequence | None:
        """Return tracked paths relative to ``scope_root``; ``None`` outside Git.

        The Git index and porcelain status identify paths relative to the
        repository root. Callers join the result onto ``scope_root``, so this
        function strips the scope's path components. Returned paths remain
        literal and scope-relative. The index and status union is the sole
        tracked authority: a git-ignored scope
        directory may still carry force-staged tracked files, so check_ignore
        must never veto the result.

        Returns:
            Current tracked paths relative to ``scope_root`` or ``None`` outside Git.

        """
        resolved_root = Path(scope_root)
        repo_root_text = cls._git_repo_root(scope_root)
        if repo_root_text is None:
            return None
        repo_relative_paths = cls._git_tracked_repo_relative_paths(repo_root_text)
        repo_root = Path(repo_root_text).resolve()
        scope_prefix = resolved_root.resolve().relative_to(repo_root)
        prefix_parts = scope_prefix.parts
        scope_paths: set[str] = set()
        for repo_relative_text in repo_relative_paths:
            repo_relative = Path(repo_relative_text)
            if prefix_parts:
                if repo_relative.parts[: len(prefix_parts)] != prefix_parts:
                    continue
                scope_relative = Path(*repo_relative.parts[len(prefix_parts) :])
            else:
                scope_relative = repo_relative
            scope_paths.add(scope_relative.as_posix())
        return tuple(sorted(scope_paths))

    @classmethod
    def git_tracked_scope_paths(cls, scope_root: Path) -> t.SequenceOf[Path] | None:
        """Return tracked files under one scope as absolute paths when Git is active.

        Returns:
            Tracked files under one scope as absolute paths when Git is active.

        """
        resolved_root = scope_root.resolve()
        relative_paths = cls._git_tracked_scope_relative_paths(str(resolved_root))
        if relative_paths is None:
            return None
        return [
            resolved_root / Path(relative_path)
            for relative_path in relative_paths
            if (resolved_root / Path(relative_path)).is_file()
        ]

    @classmethod
    def git_tracked_top_level_dir_names(cls, scope_root: Path) -> frozenset[str] | None:
        """Return tracked top-level directory names under one scope when Git is active.

        Returns:
            Tracked top-level directory names under one scope when Git is active.

        """
        relative_paths = cls._git_tracked_scope_relative_paths(
            str(scope_root.resolve()),
        )
        if relative_paths is None:
            return None
        return frozenset(
            relative.parts[0]
            for relative_path in relative_paths
            if (relative := Path(relative_path)).parts
        )

    @classmethod
    def project_descriptor_is_tracked(
        cls,
        repository_root: Path,
        project_root: Path,
    ) -> bool:
        """Return whether one candidate project has a tracked descriptor file.

        Returns:
            Whether one candidate project has a tracked descriptor file.

        """
        relative_paths = cls._git_tracked_scope_relative_paths(
            str(repository_root.resolve()),
        )
        if relative_paths is None:
            return True
        tracked_paths = frozenset(relative_paths)
        resolved_workspace = repository_root.resolve()
        resolved_project = project_root.resolve()
        relative_prefix = ""
        if resolved_project != resolved_workspace:
            relative_prefix = (
                resolved_project.relative_to(resolved_workspace).as_posix() + "/"
            )
        tracked_gitlink = relative_prefix.removesuffix("/")
        if tracked_gitlink and tracked_gitlink in tracked_paths:
            return True
        return f"{relative_prefix}{c.PYPROJECT_FILENAME}" in tracked_paths


__all__: list[str] = ["FlextInfraUtilitiesGitScopeMixin"]
