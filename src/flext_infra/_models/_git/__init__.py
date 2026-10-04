# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Models. Git package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._models._git.identity import FlextInfraModelsGitIdentity
    from flext_infra._models._git.worktree_facts import FlextInfraModelsGitWorktreeFacts
    from flext_infra._models._git.worktree_state import FlextInfraModelsGitWorktreeState


__all__: tuple[str, ...] = (
    "FlextInfraModelsGitIdentity",
    "FlextInfraModelsGitWorktreeFacts",
    "FlextInfraModelsGitWorktreeState",
)

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraModelsGitIdentity": (".identity", "FlextInfraModelsGitIdentity"),
        "FlextInfraModelsGitWorktreeFacts": (
            ".worktree_facts",
            "FlextInfraModelsGitWorktreeFacts",
        ),
        "FlextInfraModelsGitWorktreeState": (
            ".worktree_state",
            "FlextInfraModelsGitWorktreeState",
        ),
    }),
    public_exports=__all__,
)
