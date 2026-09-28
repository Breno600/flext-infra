"""Contract tests for the portable Make toolchain provider.

Root cause (R1): ``make`` was not declared in generated ``.mise.toml``, so
``direnv exec .`` resolved ``make`` from a stale host shim (a conda-carried
installation) instead of a Mise-managed binary, causing ``make setup`` to
exit 1. The fleet toolchain now owns ``make`` as a moving ``latest``
selector rendered through the canonical ``.mise.toml`` projection.
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config


class TestsFlextInfraToolchainMake:
    """The Make provider is a managed Mise tool, never a host shim."""

    def test_make_version_tracks_latest(self) -> None:
        """Keep Make policy explicit while Mise resolves its newest release."""
        toolchain = config.Infra.codegen.toolchain

        tm.that(toolchain.make_version, eq="latest")
