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
    from flext_infra._utilities._git.attestation import (
        FlextInfraUtilitiesGitAttestationMixin,
    )
    from flext_infra._utilities._git.mutation_scope import (
        FlextInfraUtilitiesGitMutationScopeMixin,
    )
    from flext_infra._utilities._git.remote import FlextInfraUtilitiesGitRemote
    from flext_infra._utilities._git.repo import FlextInfraUtilitiesGitRepo
    from flext_infra._utilities._git.scope import FlextInfraUtilitiesGitScopeMixin
    from flext_infra._utilities._git.semantic_identity import (
        FlextInfraUtilitiesGitSemanticIdentityMixin,
    )
    from flext_infra._utilities._git.semantic_index import (
        FlextInfraUtilitiesGitSemanticIndexMixin,
    )
    from flext_infra._utilities._git.semantic_lane import (
        FlextInfraUtilitiesGitSemanticLaneMixin,
    )
    from flext_infra._utilities._git.semantic_paths import (
        FlextInfraUtilitiesGitSemanticPathsMixin,
    )
    from flext_infra._utilities._git.semantic_publish import (
        FlextInfraUtilitiesGitSemanticPublishMixin,
    )
    from flext_infra._utilities._git.semantic_refs import (
        FlextInfraUtilitiesGitSemanticRefsMixin,
    )
    from flext_infra._utilities._git.semantic_submodule import (
        FlextInfraUtilitiesGitSemanticSubmoduleMixin,
    )
    from flext_infra._utilities._git.semantic_worktree import (
        FlextInfraUtilitiesGitSemanticWorktreeMixin,
    )
    from flext_infra._utilities._git.state_capture import (
        FlextInfraUtilitiesGitStateCaptureMixin,
    )
    from flext_infra._utilities._git.state_checkpoint import (
        FlextInfraUtilitiesGitStateCheckpointMixin,
    )
    from flext_infra._utilities._git.state_files import (
        FlextInfraUtilitiesGitStateFilesMixin,
    )
    from flext_infra._utilities._git.state_publication import (
        FlextInfraUtilitiesGitStatePublicationMixin,
    )
    from flext_infra._utilities._git.state_snapshot import (
        FlextInfraUtilitiesGitStateSnapshotMixin,
    )
    from flext_infra._utilities._git.state_transition import (
        FlextInfraUtilitiesGitStateTransitionMixin,
    )
    from flext_infra._utilities._git.state_trees import (
        FlextInfraUtilitiesGitStateTreesMixin,
    )
    from flext_infra._utilities._git.worktree import FlextInfraUtilitiesGitWorktreeMixin
    from flext_infra._utilities._git.worktree_checkpoint import (
        FlextInfraUtilitiesGitWorktreeCheckpointMixin,
    )
    from flext_infra._utilities._git.worktree_discovery import (
        FlextInfraUtilitiesGitWorktreeDiscoveryMixin,
    )
    from flext_infra._utilities._git.worktree_facts import (
        FlextInfraUtilitiesGitWorktreeFactsMixin,
    )
    from flext_infra._utilities._git.worktree_io import FlextInfraUtilitiesGitWorktreeIO
    from flext_infra._utilities._git.worktree_materialization import (
        FlextInfraUtilitiesGitWorktreeMaterializationMixin,
    )
    from flext_infra._utilities._git.worktree_measure import (
        FlextInfraUtilitiesGitWorktreeMeasureMixin,
    )
    from flext_infra._utilities._git.worktree_patch import (
        FlextInfraUtilitiesGitWorktreePatchMixin,
    )
    from flext_infra._utilities._git.worktree_removal import (
        FlextInfraUtilitiesGitWorktreeRemovalMixin,
    )
    from flext_infra._utilities._git.worktree_roots import (
        FlextInfraUtilitiesGitWorktreeRootsMixin,
    )
    from flext_infra._utilities._git.worktree_status import (
        FlextInfraUtilitiesGitWorktreeStatusMixin,
    )


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
