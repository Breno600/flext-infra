# AUTO-GENERATED FILE — Regenerate with: make gen
"""Flext Infra. Utilities. Git package.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core import install_lazy_exports

if TYPE_CHECKING:
    from flext_infra._utilities import FlextInfraUtilitiesGitAttestationMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitMutationScopeMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitRemote
    from flext_infra._utilities import FlextInfraUtilitiesGitRepo
    from flext_infra._utilities import FlextInfraUtilitiesGitScopeMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticIdentityMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticIndexMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticLaneMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticPathsMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticPublishMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticRefsMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticSubmoduleMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitSemanticWorktreeMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateCaptureMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateCheckpointMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateFilesMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStatePublicationMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateSnapshotMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateTransitionMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitStateTreesMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeCheckpointMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeDiscoveryMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeFactsMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeIO
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeMaterializationMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeMeasureMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreePatchMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeRemovalMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeRootsMixin
    from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeStatusMixin


__all__: tuple[str, ...] = (
    "FlextInfraUtilitiesGitAttestationMixin",
    "FlextInfraUtilitiesGitMutationScopeMixin",
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
    "FlextInfraUtilitiesGitStateCaptureMixin",
    "FlextInfraUtilitiesGitStateCheckpointMixin",
    "FlextInfraUtilitiesGitStateFilesMixin",
    "FlextInfraUtilitiesGitStatePublicationMixin",
    "FlextInfraUtilitiesGitStateSnapshotMixin",
    "FlextInfraUtilitiesGitStateTransitionMixin",
    "FlextInfraUtilitiesGitStateTreesMixin",
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

install_lazy_exports(
    __name__,
    globals(),
    MappingProxyType({
        "FlextInfraUtilitiesGitAttestationMixin": ".attestation",
        "FlextInfraUtilitiesGitMutationScopeMixin": ".mutation_scope",
        "FlextInfraUtilitiesGitRemote": ".remote",
        "FlextInfraUtilitiesGitRepo": ".repo",
        "FlextInfraUtilitiesGitScopeMixin": ".scope",
        "FlextInfraUtilitiesGitSemanticIdentityMixin": ".semantic_identity",
        "FlextInfraUtilitiesGitSemanticIndexMixin": ".semantic_index",
        "FlextInfraUtilitiesGitSemanticLaneMixin": ".semantic_lane",
        "FlextInfraUtilitiesGitSemanticPathsMixin": ".semantic_paths",
        "FlextInfraUtilitiesGitSemanticPublishMixin": ".semantic_publish",
        "FlextInfraUtilitiesGitSemanticRefsMixin": ".semantic_refs",
        "FlextInfraUtilitiesGitSemanticSubmoduleMixin": ".semantic_submodule",
        "FlextInfraUtilitiesGitSemanticWorktreeMixin": ".semantic_worktree",
        "FlextInfraUtilitiesGitStateCaptureMixin": ".state_capture",
        "FlextInfraUtilitiesGitStateCheckpointMixin": ".state_checkpoint",
        "FlextInfraUtilitiesGitStateFilesMixin": ".state_files",
        "FlextInfraUtilitiesGitStatePublicationMixin": ".state_publication",
        "FlextInfraUtilitiesGitStateSnapshotMixin": ".state_snapshot",
        "FlextInfraUtilitiesGitStateTransitionMixin": ".state_transition",
        "FlextInfraUtilitiesGitStateTreesMixin": ".state_trees",
        "FlextInfraUtilitiesGitWorktreeCheckpointMixin": ".worktree_checkpoint",
        "FlextInfraUtilitiesGitWorktreeDiscoveryMixin": ".worktree_discovery",
        "FlextInfraUtilitiesGitWorktreeFactsMixin": ".worktree_facts",
        "FlextInfraUtilitiesGitWorktreeIO": ".worktree_io",
        "FlextInfraUtilitiesGitWorktreeMaterializationMixin": (
            ".worktree_materialization"
        ),
        "FlextInfraUtilitiesGitWorktreeMeasureMixin": ".worktree_measure",
        "FlextInfraUtilitiesGitWorktreeMixin": ".worktree",
        "FlextInfraUtilitiesGitWorktreePatchMixin": ".worktree_patch",
        "FlextInfraUtilitiesGitWorktreeRemovalMixin": ".worktree_removal",
        "FlextInfraUtilitiesGitWorktreeRootsMixin": ".worktree_roots",
        "FlextInfraUtilitiesGitWorktreeStatusMixin": ".worktree_status",
    }),
    public_exports=__all__,
)
