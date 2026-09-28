"""Tests for the centralized flext_infra CLI entrypoint.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main

if TYPE_CHECKING:
    import pytest


class TestsFlextInfraInfraMain:
    """Behavior contract for test_infra_main."""

    def test_main_returns_error_when_no_args(self) -> None:
        tm.that(main([]), eq=1)

    def test_main_help_flag_returns_zero(self) -> None:
        tm.that(main(["--help"]), eq=0)

    def test_main_unknown_group_returns_error(self) -> None:
        tm.that(main(["unknown"]), eq=1)

    def test_main_help_lists_core_groups(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        tm.that(main(["--help"]), eq=0)
        out = capsys.readouterr().out
        for group in ("check", "codegen", "docs", "refactor", "workspace"):
            tm.that(out, has=group)
