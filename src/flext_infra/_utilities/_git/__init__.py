# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Git package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .attestation import FlextInfraUtilitiesGitAttestationMixin
    from .remote import FlextInfraUtilitiesGitRemote
    from .repo import FlextInfraUtilitiesGitRepo
    from .scope import FlextInfraUtilitiesGitScopeMixin
    from .semantic_identity import FlextInfraUtilitiesGitSemanticIdentityMixin
    from .semantic_index import FlextInfraUtilitiesGitSemanticIndexMixin
    from .semantic_lane import FlextInfraUtilitiesGitSemanticLaneMixin
    from .semantic_paths import FlextInfraUtilitiesGitSemanticPathsMixin
    from .semantic_publish import FlextInfraUtilitiesGitSemanticPublishMixin
    from .semantic_refs import FlextInfraUtilitiesGitSemanticRefsMixin
    from .semantic_submodule import FlextInfraUtilitiesGitSemanticSubmoduleMixin
    from .semantic_worktree import FlextInfraUtilitiesGitSemanticWorktreeMixin
    from .worktree import FlextInfraUtilitiesGitWorktreeMixin
    from .worktree_checkpoint import FlextInfraUtilitiesGitWorktreeCheckpointMixin
    from .worktree_discovery import FlextInfraUtilitiesGitWorktreeDiscoveryMixin
    from .worktree_facts import FlextInfraUtilitiesGitWorktreeFactsMixin
    from .worktree_io import FlextInfraUtilitiesGitWorktreeIO
    from .worktree_materialization import (
        FlextInfraUtilitiesGitWorktreeMaterializationMixin,
    )
    from .worktree_measure import FlextInfraUtilitiesGitWorktreeMeasureMixin
    from .worktree_patch import FlextInfraUtilitiesGitWorktreePatchMixin
    from .worktree_removal import FlextInfraUtilitiesGitWorktreeRemovalMixin
    from .worktree_roots import FlextInfraUtilitiesGitWorktreeRootsMixin
    from .worktree_status import FlextInfraUtilitiesGitWorktreeStatusMixin


__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesGitAttestationMixin",
    "FlextInfraUtilitiesGitRemote",
    "FlextInfraUtilitiesGitRepo",
    "FlextInfraUtilitiesGitScopeMixin",
    "FlextInfraUtilitiesGitSemanticIdentityMixin",
    "FlextInfraUtilitiesGitSemanticIndexMixin",
    "FlextInfraUtilitiesGitSemanticLaneMixin",
    "FlextInfraUtilitiesGitSemanticPathsMixin",
    "FlextInfraUtilitiesGitSemanticPublishMixin",
    "FlextInfraUtilitiesGitSemanticRefsMixin",
    "FlextInfraUtilitiesGitSemanticSubmoduleMixin",
    "FlextInfraUtilitiesGitSemanticWorktreeMixin",
    "FlextInfraUtilitiesGitWorktreeCheckpointMixin",
    "FlextInfraUtilitiesGitWorktreeDiscoveryMixin",
    "FlextInfraUtilitiesGitWorktreeFactsMixin",
    "FlextInfraUtilitiesGitWorktreeIO",
    "FlextInfraUtilitiesGitWorktreeMaterializationMixin",
    "FlextInfraUtilitiesGitWorktreeMeasureMixin",
    "FlextInfraUtilitiesGitWorktreeMixin",
    "FlextInfraUtilitiesGitWorktreePatchMixin",
    "FlextInfraUtilitiesGitWorktreeRemovalMixin",
    "FlextInfraUtilitiesGitWorktreeRootsMixin",
    "FlextInfraUtilitiesGitWorktreeStatusMixin",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".attestation": ("FlextInfraUtilitiesGitAttestationMixin",),
            ".remote": ("FlextInfraUtilitiesGitRemote",),
            ".repo": ("FlextInfraUtilitiesGitRepo",),
            ".scope": ("FlextInfraUtilitiesGitScopeMixin",),
            ".semantic_identity": ("FlextInfraUtilitiesGitSemanticIdentityMixin",),
            ".semantic_index": ("FlextInfraUtilitiesGitSemanticIndexMixin",),
            ".semantic_lane": ("FlextInfraUtilitiesGitSemanticLaneMixin",),
            ".semantic_paths": ("FlextInfraUtilitiesGitSemanticPathsMixin",),
            ".semantic_publish": ("FlextInfraUtilitiesGitSemanticPublishMixin",),
            ".semantic_refs": ("FlextInfraUtilitiesGitSemanticRefsMixin",),
            ".semantic_submodule": ("FlextInfraUtilitiesGitSemanticSubmoduleMixin",),
            ".semantic_worktree": ("FlextInfraUtilitiesGitSemanticWorktreeMixin",),
            ".worktree": ("FlextInfraUtilitiesGitWorktreeMixin",),
            ".worktree_checkpoint": ("FlextInfraUtilitiesGitWorktreeCheckpointMixin",),
            ".worktree_discovery": ("FlextInfraUtilitiesGitWorktreeDiscoveryMixin",),
            ".worktree_facts": ("FlextInfraUtilitiesGitWorktreeFactsMixin",),
            ".worktree_io": ("FlextInfraUtilitiesGitWorktreeIO",),
            ".worktree_materialization": (
                "FlextInfraUtilitiesGitWorktreeMaterializationMixin",
            ),
            ".worktree_measure": ("FlextInfraUtilitiesGitWorktreeMeasureMixin",),
            ".worktree_patch": ("FlextInfraUtilitiesGitWorktreePatchMixin",),
            ".worktree_removal": ("FlextInfraUtilitiesGitWorktreeRemovalMixin",),
            ".worktree_roots": ("FlextInfraUtilitiesGitWorktreeRootsMixin",),
            ".worktree_status": ("FlextInfraUtilitiesGitWorktreeStatusMixin",),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
