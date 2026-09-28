# AUTO-GENERATED FILE — Regenerate with: make gen
"""Tests.unit.workspace package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from flext_core.lazy import build_lazy_import_map, install_lazy_exports

if TYPE_CHECKING:
    from .test_work_finish_recovery import TestsWorkFinishRecovery
    from .work_public_adversarial_fixture import (
        MetadataSnapshot,
        WorkAdversarialFixture,
    )
    from .work_public_finish_fixture import (
        ChildFinishState,
        WorkInvocation,
        WorkPublicFinishFixture,
    )
    from .work_public_service_fixture import (
        PullRequestCreateReceipt,
        WorkPublicServiceFixture,
    )


__all__: tuple[str, ...] = (
    "ChildFinishState",
    "MetadataSnapshot",
    "PullRequestCreateReceipt",
    "TestsWorkFinishRecovery",
    "WorkAdversarialFixture",
    "WorkInvocation",
    "WorkPublicFinishFixture",
    "WorkPublicServiceFixture",
)

_LAZY_IMPORTS = MappingProxyType(
    build_lazy_import_map(
        MappingProxyType({
            ".test_work_finish_recovery": ("TestsWorkFinishRecovery",),
            ".work_public_adversarial_fixture": (
                "MetadataSnapshot",
                "WorkAdversarialFixture",
            ),
            ".work_public_finish_fixture": (
                "ChildFinishState",
                "WorkInvocation",
                "WorkPublicFinishFixture",
            ),
            ".work_public_service_fixture": (
                "PullRequestCreateReceipt",
                "WorkPublicServiceFixture",
            ),
        }),
        alias_groups=MappingProxyType({}),
        sort_keys=False,
    )
)

install_lazy_exports(__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)
