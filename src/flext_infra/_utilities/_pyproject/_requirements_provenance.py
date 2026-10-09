"""Workspace provenance for canonicalizing internal requirement lines.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flext_infra import t


@dataclasses.dataclass(frozen=True, slots=True)
class _RequirementProvenance:
    """Workspace provenance consulted while canonicalizing requirement lines."""

    declared_sources: t.StrMapping
    candidate_sources: t.StrMapping
    family_line: str | None
    workspace_members: t.StrSequence = ()


__all__: list[str] = []
