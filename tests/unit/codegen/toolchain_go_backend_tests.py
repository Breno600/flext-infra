"""Contract tests for the Go runtime required by go: backend selectors.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config


class TestsFlextInfraToolchainGoBackend:
    """The independent Go runtime follows the moving fleet selector."""

    @staticmethod
    def test_go_version_tracks_latest_without_coupling_to_beads() -> None:
        """Keep Go policy explicit while mise resolves its newest release."""
        toolchain = config.Infra.codegen.toolchain

        tm.that(toolchain.go_version, eq="latest")
