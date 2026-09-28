"""Tests for flext_infra.deps.fix_pyrefly_config module.

Tests the real CLI entry point.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main as infra_main

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture


class TestsFlextInfraFixPyreflyConfig:
    def test_fix_pyrefly_config_main_executes_real_cli_help(
        self, capsys: CaptureFixture[str]
    ) -> None:
        exit_code = infra_main(["check", "fix-pyrefly-settings", "--help"])
        captured = capsys.readouterr()
        tm.that(exit_code, eq=0)
        tm.that(captured.out.lower(), has="usage:")
