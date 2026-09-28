"""Guard 5 — tier / abstraction-boundary enforcer.

Enforces AGENTS.md §2.7 abstraction-boundary rules: each external library
listed in ``c.ENFORCEMENT_LIBRARY_OWNERS`` (flext-core SSOT) has exactly
one owning FLEXT project. Bare runtime imports of those libs outside the
canonical wrapper sites are violations.

Uses rope's semantic import resolution so ``if TYPE_CHECKING:`` imports
are automatically exempt (they live in conditional blocks that rope
skips when collecting runtime imports).

Mandate: 100% ROPE-based per the flext-infra detector mandate — no raw
``ast``/``libcst`` source analysis. Uses
``u.Infra`` Rope boundary helpers.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, u

from ._rope_import_boundary import FlextInfraRopeImportBoundaryBase

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraValidateTierWhitelist(FlextInfraRopeImportBoundaryBase):
    """Enforce the §2.7 abstraction boundary at runtime-import level.

    Banned-lib set + per-library ownership are both derived from
    ``c.ENFORCEMENT_LIBRARY_OWNERS`` (flext-core SSOT): each banned library's
    owning project tree is the only place that library may be imported.
    Declared member repositories are excluded by the shared boundary base.
    """

    _BANNED: ClassVar[frozenset[str]] = frozenset(c.ENFORCEMENT_LIBRARY_OWNERS)
    _OK_SUMMARY: ClassVar[str] = (
        "abstraction boundary respected (flext-core-only libs not imported elsewhere)"
    )
    _VIOLATION_KIND: ClassVar[str] = "abstraction-boundary"
    _SCAN_KIND: ClassVar[str] = "tier-whitelist"

    @override
    def _is_in_scope(self, _file_path: Path, *, repository_root: Path) -> bool:
        """Skip files inside git submodule directories and cache/temp directories.

        Submodule directories are independent projects with their own
        tier-whitelist runs; scanning them from the workspace level is
        redundant and produces cross-boundary false positives.

        Cache/temp/state directories (virtual envs, tool caches, test temp dirs,
        IDE/editor dirs, etc.) are not project source and must not be scanned.
        """
        # The checkout's ancestors do not belong to this scan. A linked lane
        # under .claude/worktrees is still a complete project source root.
        relative = _file_path.relative_to(repository_root)
        excluded_dirs = {
            ".test-tmp",
            ".venv",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".cache",
            ".github",
            ".kilo",
            ".vscode",
            ".worktrees",
            "worktrees",
            "flext-infra-worktrees",
            "dist",
            ".agents-sync-home",
            ".beads",
            ".benchmarks",
            ".claude",
            ".codex",
            ".mimosa",
            ".poolside",
            ".qlty",
            ".reports",
            ".ropeproject",
            ".rumdl_cache",
            ".snapshots",
            ".state",
            ".gc",
            ".agents",
        }
        for part in relative.parts:
            if part in excluded_dirs:
                return False

        # Skip files owned by governed member repositories (submodules).
        member_roots = frozenset(u.Infra.governed_project_roots(repository_root)) - {
            repository_root.resolve()
        }
        return not any(parent in member_roots for parent in _file_path.parents)

    @override
    def _is_allowlisted(
        self, _file_path: Path, _module_name: str, *, repository_root: Path
    ) -> bool:
        """Return True iff ``file_path`` owns ``module_name`` per OWNERS SSOT.

        Ownership comes directly from ``c.ENFORCEMENT_LIBRARY_OWNERS``
        (flext-core SSOT): each banned library has exactly one owning project,
        and the entire ``<owner>/src/<package>/`` tree is allowed to import
        that library. ``tests/``, ``examples/``, ``scripts/`` are runtime-
        exempt globally.

        Settings modules (``*/settings.py``) are additionally allowed to
        import ``pydantic_settings`` — the canonical pattern for project
        configuration is ``class Foo(FlextSettings, BaseSettings)`` per
        ``flext_core._settings.base`` docstring, and that base name only
        lives in ``pydantic_settings``.

        Leaf config modules (``_config.py``) are exempt for ALL banned
        libraries: they sit at the bottom of the c/t/p/m/u chain and own
        their external-library imports directly as the canonical ingress
        seam.
        """
        rooted = self._rooted_posix(_file_path, repository_root)
        if any(
            part in c.Infra.TIER_WHITELIST_NON_RUNTIME_DIR_PARTS
            for part in rooted.split("/")[:-1]
        ):
            return True
        if _file_path.name in c.Infra.TIER_WHITELIST_LEAF_CONFIG_FILES:
            return True
        top = self._top_module(_module_name)
        if (
            top in c.Infra.TIER_WHITELIST_SETTINGS_MODULE_LIBRARIES
            and _file_path.name.endswith("settings.py")
        ):
            return True
        owner = c.ENFORCEMENT_LIBRARY_OWNERS.get(top)
        if owner is None:
            return False
        # Ownership is the owner's PACKAGE tree, never the checkout directory
        # name: a lane worktree named ``flext-infra-<lane>`` is still the
        # ``flext-infra`` source tree, so dirname matching would be blind to
        # every governed worktree.
        package_root = f"/{c.Infra.DEFAULT_SRC_DIR}/{owner.replace('-', '_')}/"
        return package_root in rooted

    @override
    def _format_violation(self, file_path: Path, module_name: str) -> str:
        """Format the abstraction-boundary violation message."""
        return (
            f"{file_path}: bare import of {module_name!r} "
            "— use flext_core facades (c/m/p/t/u)"
        )


__all__: t.StrSequence = ("FlextInfraValidateTierWhitelist",)
