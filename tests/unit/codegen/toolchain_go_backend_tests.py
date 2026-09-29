"""Contract tests for the Go runtime required by go: backend selectors."""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config


class TestsFlextInfraToolchainGoBackend:
    """The independent Go runtime follows the moving fleet selector."""

    def test_go_version_tracks_latest_without_coupling_to_beads(self) -> None:
        """Keep Go policy explicit while mise resolves its newest release."""
        toolchain = config.Infra.codegen.toolchain

        tm.that(toolchain.go_version, eq="latest")
