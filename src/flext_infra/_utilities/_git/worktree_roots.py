"""Canonical Git responsibility mixin for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from git import Git, GitCommandError

from flext_infra import c, m, p, r, t
from flext_infra._utilities._git.worktree_facts import (
    FlextInfraUtilitiesGitWorktreeFactsMixin,
)


class FlextInfraUtilitiesGitWorktreeRootsMixin(
    FlextInfraUtilitiesGitWorktreeFactsMixin,
):
    """Own worktree roots and the superproject's ``.gitmodules`` declarations."""

    @classmethod
    def git_repository_root(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitRootReport]:
        """Resolve the superproject root or the repository's own top level.

        Returns:
            The resulting ``p.Result[m.Infra.GitRootReport]``.

        """
        root = cls._git_repository_root_path(request.repo_root)
        if root.failure:
            return r[m.Infra.GitRootReport].from_failure(root)
        return r[m.Infra.GitRootReport].ok(
            m.Infra.GitRootReport(repository_root=root.value),
        )

    @classmethod
    def git_primary_worktree_root(
        cls,
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitPrimaryRootReport]:
        """Resolve the primary worktree from Git's canonical storage topology.

        Returns:
            The resulting ``p.Result[m.Infra.GitPrimaryRootReport]``.

        """
        primary = cls._git_primary_worktree_root_path(request.repo_root)
        if primary.failure:
            return r[m.Infra.GitPrimaryRootReport].from_failure(primary)
        return r[m.Infra.GitPrimaryRootReport].ok(
            m.Infra.GitPrimaryRootReport(primary_root=primary.value),
        )

    @classmethod
    def _git_repository_root_path(cls, repository_path: Path) -> p.Result[Path]:
        """Private Path-based workspace/superproject resolver.

        ``rev-parse --show-superproject-working-tree`` exits 0 and prints
        nothing when the checkout is not a submodule; that empty answer selects
        the checkout's own top level. Every Git failure is a failure.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        try:
            repo = cls._repo(repository_path)
            superproject = repo.git.rev_parse(
                "--show-superproject-working-tree",
            ).strip()
            root = superproject or repo.git.rev_parse("--show-toplevel").strip()
        except (GitCommandError, OSError, ValueError) as exc:
            return r[Path].fail(
                f"failed to resolve repository root: {exc}",
                exception=exc,
            )
        return r[Path].ok(Path(root).resolve())

    @classmethod
    def git_submodule_declarations(
        cls,
        repository_root: Path,
    ) -> p.Result[t.VariadicTuple[m.Infra.GitSubmoduleDeclaration]]:
        """Parse the repository's ``.gitmodules`` through ``git config -f``.

        Git itself reads the file, so its syntax is Git's. A missing file is
        a standalone repository (no members). A non-regular file, a malformed
        file, a repeated key, a section without a path, and an absolute,
        empty, escaping or duplicated path fail closed.

        Returns:
            Every declared submodule in declaration order.

        """
        result = r[t.VariadicTuple[m.Infra.GitSubmoduleDeclaration]]
        sections = cls._gitmodules_sections(repository_root)
        if sections.failure:
            return result.from_failure(sections)
        declarations: list[m.Infra.GitSubmoduleDeclaration] = []
        for section, values in sections.value.items():
            raw_path = values.get(c.Infra.GITMODULE_PATH_KEY, "")
            relative = Path(raw_path)
            if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                return result.fail(
                    f"invalid Git submodule path in {section}: {raw_path!r}",
                )
            if any(item.path == relative for item in declarations):
                return result.fail(f"duplicate Git submodule path: {raw_path}")
            flag = values.get(c.Infra.GITMODULE_MANAGED_KEY)
            declarations.append(
                m.Infra.GitSubmoduleDeclaration(
                    path=relative,
                    url=values.get(c.Infra.GITMODULE_URL_KEY, ""),
                    branch=values.get(c.Infra.GITMODULE_BRANCH_KEY, ""),
                    managed=None if flag is None else flag.lower() == "true",
                ),
            )
        return result.ok(tuple(declarations))

    @staticmethod
    def _gitmodules_sections(
        repository_root: Path,
    ) -> p.Result[t.MappingKV[str, t.StrMapping]]:
        """Group every ``submodule.*`` key Git reads from ``.gitmodules``.

        Returns:
            Section name to its keys; empty when the file is absent.

        """
        result = r[t.MappingKV[str, t.StrMapping]]
        gitmodules = repository_root / c.Infra.GITMODULES
        if not gitmodules.exists():
            return result.ok({})
        if not gitmodules.is_file():
            return result.fail(
                f"Git submodule manifest is not a regular file: {gitmodules}",
            )
        try:
            listing = Git(repository_root).config(
                "--file",
                str(gitmodules),
                "--null",
                "--list",
            )
        except (GitCommandError, OSError) as exc:
            return result.fail(
                f"failed to read Git submodule declarations: {exc}",
                exception=exc,
            )
        sections: MutableMapping[str, MutableMapping[str, str]] = {}
        for entry in filter(None, listing.split("\0")):
            key, _, value = entry.partition("\n")
            section, _, variable = key.rpartition(".")
            if not section.startswith(c.Infra.GITMODULE_SECTION_PREFIX):
                continue
            values = sections.setdefault(section, {})
            if variable in values:
                return result.fail(f"Git submodule key is declared twice: {key}")
            values[variable] = value.strip()
        return result.ok(sections)

    @classmethod
    def git_submodule_declaration(
        cls,
        request: m.Infra.GitSubmoduleContractRequest,
    ) -> p.Result[m.Infra.GitSubmoduleDeclaration]:
        """Return the one declaration of a path that carries URL and branch.

        Returns:
            The declaration; a missing path, URL or branch fails closed.

        """
        result = r[m.Infra.GitSubmoduleDeclaration]
        declared = cls.git_submodule_declarations(request.repo_root)
        if declared.failure:
            return result.from_failure(declared)
        declaration = next(
            (
                item
                for item in declared.value
                if item.path.as_posix() == request.member_path
            ),
            None,
        )
        if declaration is None:
            return result.fail(
                f"Git submodule path must be declared exactly once: "
                f"{request.member_path}",
            )
        if not declaration.url:
            return result.fail(f"Git submodule URL is missing: {request.member_path}")
        if not declaration.branch:
            return result.fail(
                f"Git submodule branch is missing: {request.member_path}",
            )
        return result.ok(declaration)


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeRootsMixin"]
