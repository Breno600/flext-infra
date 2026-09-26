"""Unified, fail-closed conformance for new and existing repositories.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, p, u

from ._conform import FlextInfraCodegenConformBase

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraCodegenConform(FlextInfraCodegenConformBase):
    """Plan every selected output, then atomically write only a clean plan."""

    @classmethod
    def settle_repository(cls, root: Path) -> p.Result[bool]:
        """Conform every projection of ``root``, then lock it without upgrading.

        Conform settles ``pyproject.toml`` and every rendered projection first,
        so the lock resolves against them; it upgrades nothing (only ``upg``
        resolves the newest releases). Identical inputs regenerate identical
        bytes, so a rerun changes nothing.
        """
        conformed = cls.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                scope=c.Infra.CodegenConformScope.ALL,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )
        if conformed.failure:
            return r[bool].from_failure(conformed)
        return u.Cli.run_checked([c.Infra.UV, "lock", "--project", str(root)], cwd=root)


__all__: list[str] = ["FlextInfraCodegenConform"]
