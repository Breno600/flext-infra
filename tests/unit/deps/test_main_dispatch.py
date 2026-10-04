"""Behavior tests for the canonical ``flext-infra deps`` CLI group.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import main


class TestsFlextInfraDepsMainDispatch:
    """Test flext infra deps main dispatch behavior."""

    @staticmethod
    def test_subcommand_help_is_available() -> None:
        # NOTE (multi-agent, flext-wkii.17.9): deps exposes no conformance alias;
        # pyproject normalization is consumed only by the codegen owner.
        """Verify subcommand help is available."""
        for subcommand in ("detect", "extra-paths", "modernize", "verify-locks"):
            tm.that(main(["deps", subcommand, "--help"]), eq=0)
