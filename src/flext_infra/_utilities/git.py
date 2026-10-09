"""Public Git utilities facet for ``u.Infra`` (composed into utilities FLEXT).

Private GitPython parts live under ``_utilities/_git/``. Consumers use
``from flext_infra import u`` only — never import this module or ``_git``.

The composing owner imports its bases from their defining modules. Resolving
them through the aggregate lazy utilities export makes the Git inheritance
chain depend on that same export during static semantic analysis.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities._git.attestation import (
    FlextInfraUtilitiesGitAttestationMixin,
)
from flext_infra._utilities._git.lane_hygiene import (
    FlextInfraUtilitiesGitLaneHygieneMixin,
)
from flext_infra._utilities._git.mutation_scope import (
    FlextInfraUtilitiesGitMutationScopeMixin,
)
from flext_infra._utilities._git.scope import FlextInfraUtilitiesGitScopeMixin
from flext_infra._utilities._git.semantic_submodule import (
    FlextInfraUtilitiesGitSemanticSubmoduleMixin,
)
from flext_infra._utilities._git.state_capture import (
    FlextInfraUtilitiesGitStateCaptureMixin,
)
from flext_infra._utilities._git.worktree import FlextInfraUtilitiesGitWorktreeMixin


class FlextInfraUtilitiesGit(
    FlextInfraUtilitiesGitMutationScopeMixin,
    FlextInfraUtilitiesGitWorktreeMixin,
    FlextInfraUtilitiesGitAttestationMixin,
    FlextInfraUtilitiesGitScopeMixin,
    FlextInfraUtilitiesGitSemanticSubmoduleMixin,
    FlextInfraUtilitiesGitLaneHygieneMixin,
    FlextInfraUtilitiesGitStateCaptureMixin,
):
    """Canonical Git owner for flext-infra: scope + worktree + checkpoint/patch.

    Removal and semantic publication share the refs/preflight owner below both
    effect boundaries. Compose removal here, not below refs: otherwise the
    removal owner cannot call the shared guard without an import cycle.
    """

    @staticmethod
    def git_attribute_pattern(path: str) -> str:
        """Encode one literal path with Git's glob escaping and C quoting.

        Returns:
            The resulting ``str``.

        """
        literal = (
            path
            .replace("\\", "\\\\")
            .replace("*", "\\*")
            .replace("?", "\\?")
            .replace("[", "\\[")
        )
        quoted = "".join(
            chr(byte)
            if chr(byte).isascii()
            and chr(byte).isprintable()
            and chr(byte) not in {'"', "\\"}
            else f"\\{byte:03o}"
            for byte in literal.encode("utf-8")
        )
        return f'"{quoted}"'


__all__: list[str] = ["FlextInfraUtilitiesGit"]
