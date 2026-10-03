"""Contract tests for generated toolchain requirement expressions.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config


class TestsFlextInfraToolchainRequirement:
    """Toolchain requirements tolerate compatible Python patch drift."""

    @staticmethod
    def test_python_requirement_uses_declared_minor_as_floor() -> None:
        """The declared Python minor remains the lower compatibility bound."""
        toolchain = config.Infra.codegen.toolchain

        tm.that(
            toolchain.python_required_version,
            has=f">={toolchain.python_version},<",
        )

    @staticmethod
    def test_python_requirement_rejects_the_next_minor() -> None:
        """Python minor upgrades remain an explicit SSOT migration."""
        toolchain = config.Infra.codegen.toolchain
        major, _, minor = toolchain.python_version.partition(".")

        tm.that(toolchain.python_required_version, has=f",<{major}.{int(minor) + 1}")
