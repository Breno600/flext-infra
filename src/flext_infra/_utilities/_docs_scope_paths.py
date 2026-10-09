"""Authenticated lexical path and workspace-topology helpers for docs scope.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_cli import u

from flext_core.result import FlextResult as r
from flext_infra import c, p, t
from flext_infra._utilities import FlextInfraUtilitiesGit


class FlextInfraUtilitiesDocsScopePathsMixin:
    """Authenticate docs paths without dereferencing their lexical ownership."""

    @staticmethod
    def absolute_lexical(path: Path) -> Path:
        """Return an absolute lexical path without dereferencing aliases.

        Returns:
            An absolute lexical path without dereferencing aliases.

        Raises:
            ValueError: If docs path cannot contain parent traversal.

        """
        if ".." in path.parts:
            msg = f"docs path cannot contain parent traversal: {path}"
            raise ValueError(msg)
        return path if path.is_absolute() else path.absolute()

    @staticmethod
    def physical_directory_exists(path: Path) -> bool:
        """Return presence only after descriptor-authenticated traversal.

        Returns:
            Presence only after descriptor-authenticated traversal.

        Raises:
            ValueError: If ``planned.failure``.

        """
        planned = u.Cli.atomic_plan_directory_chain(path)
        if planned.failure:
            raise ValueError(planned.error or f"docs directory is unsafe: {path}")
        return not planned.value.directories

    @staticmethod
    def _physical_file_exists(path: Path) -> bool:
        """Return file presence only after descriptor-authenticated inspection.

        Returns:
            File presence only after descriptor-authenticated inspection.

        Raises:
            ValueError: If ``state.failure``.

        """
        state = u.Cli.atomic_read_binary_file_state(path, required=False)
        if state.failure:
            raise ValueError(state.error or f"docs file is unsafe: {path}")
        return state.value.content is not None

    @staticmethod
    def docs_repository_roots(
        repository_root: Path,
        extra_roots: t.SequenceOf[Path] = (),
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Return existing physical roots from one stable workspace topology.

        Returns:
            Existing physical roots from one stable workspace topology.

        """
        try:
            return FlextInfraUtilitiesDocsScopePathsMixin._docs_repository_roots(
                repository_root,
                extra_roots,
            )
        except (OSError, TypeError, ValueError) as exc:
            return r[t.VariadicTuple[Path]].fail(
                f"docs workspace discovery failed: {exc}",
                exception=exc,
            )

    @staticmethod
    def _docs_repository_roots(
        repository_root: Path,
        extra_roots: t.SequenceOf[Path],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Discover roots while the public boundary owns exception conversion.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        from flext_core.result import FlextResult as r
        """
        root = FlextInfraUtilitiesDocsScopePathsMixin.absolute_lexical(repository_root)
        if not FlextInfraUtilitiesDocsScopePathsMixin.physical_directory_exists(root):
            return r[t.VariadicTuple[Path]].fail(
                f"docs repository root is missing: {root}",
            )
        declared = (
            FlextInfraUtilitiesDocsScopePathsMixin._attested_declared_submodule_paths(
                root,
            )
        )
        if declared.failure:
            return r[t.VariadicTuple[Path]].from_failure(declared)
        candidates_result = (
            FlextInfraUtilitiesDocsScopePathsMixin._declared_root_candidates(
                root,
                declared.value,
            )
        )
        if candidates_result.failure:
            return r[t.VariadicTuple[Path]].from_failure(candidates_result)
        candidates = list(candidates_result.value)
        for candidate in extra_roots:
            lexical = FlextInfraUtilitiesDocsScopePathsMixin.absolute_lexical(candidate)
            if not lexical.is_relative_to(root):
                return r[t.VariadicTuple[Path]].fail(
                    f"docs source root escapes repository {root}: {lexical}",
                )
            candidates.append(lexical)
        roots = [
            candidate
            for candidate in dict.fromkeys(candidates)
            if FlextInfraUtilitiesDocsScopePathsMixin.physical_directory_exists(
                candidate,
            )
        ]
        return r[t.VariadicTuple[Path]].ok(tuple(roots))

    @staticmethod
    def _attested_declared_submodule_paths(
        root: Path,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Read declared submodule paths under a stable manifest topology.

        The ``.gitmodules`` bytes are read before and after the declaration
        walk; a changed manifest fails the discovery instead of composing
        candidates from a tree that moved underneath it.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        manifest_path = root / c.Infra.GITMODULES
        manifest_before = u.Cli.atomic_read_binary_file_state(
            manifest_path,
            required=False,
        )
        if manifest_before.failure:
            return r[t.VariadicTuple[Path]].from_failure(manifest_before)
        declared = FlextInfraUtilitiesGit.git_submodule_declarations(root)
        if declared.failure:
            return r[t.VariadicTuple[Path]].from_failure(declared)
        manifest_after = u.Cli.atomic_read_binary_file_state(
            manifest_path,
            required=False,
        )
        if manifest_after.failure:
            return r[t.VariadicTuple[Path]].from_failure(manifest_after)
        if manifest_after.value != manifest_before.value:
            return r[t.VariadicTuple[Path]].fail(
                f"docs repository topology changed during discovery: {manifest_path}",
            )
        return r[t.VariadicTuple[Path]].ok(tuple(item.path for item in declared.value))

    @staticmethod
    def _declared_root_candidates(
        root: Path,
        declared_paths: t.SequenceOf[Path],
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Compose repository-root candidates from declared submodule paths.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        candidates: list[Path] = [root]
        for declared_path in declared_paths:
            selector = declared_path
            if selector.is_absolute() or ".." in selector.parts:
                return r[t.VariadicTuple[Path]].fail(
                    f"invalid docs composed project path: {selector}",
                )
            candidates.append(root / selector)
        return r[t.VariadicTuple[Path]].ok(tuple(candidates))


__all__: list[str] = ["FlextInfraUtilitiesDocsScopePathsMixin"]
