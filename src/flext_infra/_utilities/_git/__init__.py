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
        "FlextInfraUtilitiesGitAttestationMixin": (
            ".attestation",
            "FlextInfraUtilitiesGitAttestationMixin",
        ),
        "FlextInfraUtilitiesGitMutationScopeMixin": (
            ".mutation_scope",
            "FlextInfraUtilitiesGitMutationScopeMixin",
        ),
        "FlextInfraUtilitiesGitRemote": (".remote", "FlextInfraUtilitiesGitRemote"),
        "FlextInfraUtilitiesGitRepo": (".repo", "FlextInfraUtilitiesGitRepo"),
        "FlextInfraUtilitiesGitScopeMixin": (
            ".scope",
            "FlextInfraUtilitiesGitScopeMixin",
        ),
        "FlextInfraUtilitiesGitSemanticIdentityMixin": (
            ".semantic_identity",
            "FlextInfraUtilitiesGitSemanticIdentityMixin",
        ),
        "FlextInfraUtilitiesGitSemanticIndexMixin": (
            ".semantic_index",
            "FlextInfraUtilitiesGitSemanticIndexMixin",
        ),
        "FlextInfraUtilitiesGitSemanticLaneMixin": (
            ".semantic_lane",
            "FlextInfraUtilitiesGitSemanticLaneMixin",
        ),
        "FlextInfraUtilitiesGitSemanticPathsMixin": (
            ".semantic_paths",
            "FlextInfraUtilitiesGitSemanticPathsMixin",
        ),
        "FlextInfraUtilitiesGitSemanticPublishMixin": (
            ".semantic_publish",
            "FlextInfraUtilitiesGitSemanticPublishMixin",
        ),
        "FlextInfraUtilitiesGitSemanticRefsMixin": (
            ".semantic_refs",
            "FlextInfraUtilitiesGitSemanticRefsMixin",
        ),
        "FlextInfraUtilitiesGitSemanticSubmoduleMixin": (
            ".semantic_submodule",
            "FlextInfraUtilitiesGitSemanticSubmoduleMixin",
        ),
        "FlextInfraUtilitiesGitSemanticWorktreeMixin": (
            ".semantic_worktree",
            "FlextInfraUtilitiesGitSemanticWorktreeMixin",
        ),
        "FlextInfraUtilitiesGitStateCaptureMixin": (
            ".state_capture",
            "FlextInfraUtilitiesGitStateCaptureMixin",
        ),
        "FlextInfraUtilitiesGitStateCheckpointMixin": (
            ".state_checkpoint",
            "FlextInfraUtilitiesGitStateCheckpointMixin",
        ),
        "FlextInfraUtilitiesGitStateFilesMixin": (
            ".state_files",
            "FlextInfraUtilitiesGitStateFilesMixin",
        ),
        "FlextInfraUtilitiesGitStatePublicationMixin": (
            ".state_publication",
            "FlextInfraUtilitiesGitStatePublicationMixin",
        ),
        "FlextInfraUtilitiesGitStateSnapshotMixin": (
            ".state_snapshot",
            "FlextInfraUtilitiesGitStateSnapshotMixin",
        ),
        "FlextInfraUtilitiesGitStateTransitionMixin": (
            ".state_transition",
            "FlextInfraUtilitiesGitStateTransitionMixin",
        ),
        "FlextInfraUtilitiesGitStateTreesMixin": (
            ".state_trees",
            "FlextInfraUtilitiesGitStateTreesMixin",
        ),
        "FlextInfraUtilitiesGitWorktreeCheckpointMixin": (
            ".worktree_checkpoint",
            "FlextInfraUtilitiesGitWorktreeCheckpointMixin",
        ),
        "FlextInfraUtilitiesGitWorktreeDiscoveryMixin": (
            ".worktree_discovery",
            "FlextInfraUtilitiesGitWorktreeDiscoveryMixin",
        ),
        "FlextInfraUtilitiesGitWorktreeFactsMixin": (
            ".worktree_facts",
            "FlextInfraUtilitiesGitWorktreeFactsMixin",
        ),
        "FlextInfraUtilitiesGitWorktreeIO": (
            ".worktree_io",
            "FlextInfraUtilitiesGitWorktreeIO",
        ),
        "FlextInfraUtilitiesGitWorktreeMaterializationMixin": (
            ".worktree_materialization",
            "FlextInfraUtilitiesGitWorktreeMaterializationMixin",
        ),
        "FlextInfraUtilitiesGitWorktreeMeasureMixin": (
            ".worktree_measure",
            "FlextInfraUtilitiesGitWorktreeMeasureMixin",
        ),
        "FlextInfraUtilitiesGitWorktreeMixin": (
            ".worktree",
            "FlextInfraUtilitiesGitWorktreeMixin",
        ),
        "FlextInfraUtilitiesGitWorktreePatchMixin": (
            ".worktree_patch",
            "FlextInfraUtilitiesGitWorktreePatchMixin",
        ),
        "FlextInfraUtilitiesGitWorktreeRemovalMixin": (
            ".worktree_removal",
            "FlextInfraUtilitiesGitWorktreeRemovalMixin",
        ),
        "FlextInfraUtilitiesGitWorktreeRootsMixin": (
            ".worktree_roots",
            "FlextInfraUtilitiesGitWorktreeRootsMixin",
        ),
        "FlextInfraUtilitiesGitWorktreeStatusMixin": (
            ".worktree_status",
            "FlextInfraUtilitiesGitWorktreeStatusMixin",
        ),
    }),
    public_exports=__all__,
)
