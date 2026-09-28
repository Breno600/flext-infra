"""Tests for p facade.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from tests import p


class TestsFlextInfraInfraProtocols:
    """Test p class import and structure."""

    def test_flext_infra_protocols_is_importable(self) -> None:
        """Test that p can be imported."""
        tm.that(p, none=False)
