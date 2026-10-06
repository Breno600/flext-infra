"""Canonical Git worktree composition for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra._utilities import FlextInfraUtilitiesGitWorktreeRemovalMixin


class FlextInfraUtilitiesGitWorktreeMixin(FlextInfraUtilitiesGitWorktreeRemovalMixin):
    """Compose worktree discovery, materialization, checkpoint, patch, and removal."""


__all__: list[str] = ["FlextInfraUtilitiesGitWorktreeMixin"]
