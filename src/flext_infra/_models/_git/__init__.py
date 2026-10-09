# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models. Git package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import build_lazy_import_map, install_lazy_exports
from flext_infra._models._git.identity import FlextInfraModelsGitIdentity
from flext_infra._models._git.worktree_facts import FlextInfraModelsGitWorktreeFacts
from flext_infra._models._git.worktree_state import FlextInfraModelsGitWorktreeState

__all__: tuple[str, ...] = (
    "FlextInfraModelsGitIdentity",
    "FlextInfraModelsGitWorktreeFacts",
    "FlextInfraModelsGitWorktreeState",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".identity": ("FlextInfraModelsGitIdentity",),
            ".worktree_facts": ("FlextInfraModelsGitWorktreeFacts",),
            ".worktree_state": ("FlextInfraModelsGitWorktreeState",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    ),
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
