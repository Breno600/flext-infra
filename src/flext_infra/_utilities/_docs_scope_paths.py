"""Authenticated lexical path and workspace-topology helpers for docs scope."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_cli import u

from flext_core.result import FlextResult as r
from flext_infra import c, t

from .git import FlextInfraUtilitiesGit

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesDocsScopePathsMixin:
    """Authenticate docs paths without dereferencing their lexical ownership."""

    @staticmethod
    def absolute_lexical(path: Path) -> Path:
        """Return an absolute lexical path without dereferencing aliases."""
        if ".." in path.parts:
            msg = f"docs path cannot contain parent traversal: {path}"
            raise ValueError(msg)
        return path if path.is_absolute() else path.absolute()

    @staticmethod
    def physical_directory_exists(path: Path) -> bool:
        """Return presence only after descriptor-authenticated traversal."""
        planned = u.Cli.atomic_plan_directory_chain(path)
        if planned.failure:
            raise ValueError(planned.error or f"docs directory is unsafe: {path}")
        return not planned.value.directories

    @staticmethod
    def _physical_file_exists(path: Path) -> bool:
        """Return file presence only after descriptor-authenticated inspection."""
        state = u.Cli.atomic_read_binary_file_state(path, required=False)
        if state.failure:
            raise ValueError(state.error or f"docs file is unsafe: {path}")
        return state.value.content is not None

    @staticmethod
    def docs_repository_roots(
        repository_root: Path, extra_roots: t.SequenceOf[Path] = ()
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Return existing physical roots from one stable workspace topology."""
        try:
            return FlextInfraUtilitiesDocsScopePathsMixin._docs_repository_roots(
                repository_root, extra_roots
            )
        except (OSError, TypeError, ValueError) as exc:
            return r[t.VariadicTuple[Path]].fail(
                f"docs workspace discovery failed: {exc}", exception=exc
            )

    @staticmethod
    def _docs_repository_roots(
        repository_root: Path, extra_roots: t.SequenceOf[Path]
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Discover roots while the public boundary owns exception conversion."""
        root = FlextInfraUtilitiesDocsScopePathsMixin.absolute_lexical(repository_root)
        if not FlextInfraUtilitiesDocsScopePathsMixin.physical_directory_exists(root):
            return r[t.VariadicTuple[Path]].fail(
                f"docs repository root is missing: {root}"
            )
        manifest_path = root / c.Infra.GITMODULES
        manifest_before = u.Cli.atomic_read_binary_file_state(
            manifest_path, required=False
        )
        if manifest_before.failure:
            return r[t.VariadicTuple[Path]].from_failure(manifest_before)
        declared = FlextInfraUtilitiesGit.git_declared_submodule_paths(root)
        if declared.failure:
            return r[t.VariadicTuple[Path]].from_failure(declared)
        manifest_after = u.Cli.atomic_read_binary_file_state(
            manifest_path, required=False
        )
        if manifest_after.failure:
            return r[t.VariadicTuple[Path]].from_failure(manifest_after)
        if manifest_after.value != manifest_before.value:
            return r[t.VariadicTuple[Path]].fail(
                f"docs repository topology changed during discovery: {manifest_path}"
            )
        candidates = [root]
        for declared_path in declared.value:
            selector = Path(declared_path)
            if selector.is_absolute() or ".." in selector.parts:
                return r[t.VariadicTuple[Path]].fail(
                    f"invalid docs composed project path: {selector}"
                )
            candidates.append(root / selector)
        for candidate in extra_roots:
            lexical = FlextInfraUtilitiesDocsScopePathsMixin.absolute_lexical(candidate)
            if not lexical.is_relative_to(root):
                return r[t.VariadicTuple[Path]].fail(
                    f"docs source root escapes repository {root}: {lexical}"
                )
            candidates.append(lexical)
        roots = [
            candidate
            for candidate in dict.fromkeys(candidates)
            if FlextInfraUtilitiesDocsScopePathsMixin.physical_directory_exists(
                candidate
            )
        ]
        return r[t.VariadicTuple[Path]].ok(tuple(roots))


__all__: list[str] = ["FlextInfraUtilitiesDocsScopePathsMixin"]
