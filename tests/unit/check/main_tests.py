"""Tests for the centralized check CLI group.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


class TestsFlextInfraCheckMain:
    """Tests for ``FlextInfraCheckMain``."""

    @staticmethod
    def test_check_main_executes_real_cli(capsys: CaptureFixture[str]) -> None:
        """Test check main executes real cli."""
        exit_code = main(["check", "run", "--help"])
        captured = capsys.readouterr()
        tm.that(exit_code, eq=0)
        tm.that(captured.out.lower(), has="usage:")
