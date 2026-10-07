"""Public staged pin CLI preserves native lock inputs and selector quoting."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from flext_tests import tm

from tests import u


class TestsMiseLockPin:
    """Exercise the shipped CLI without provisioning any tools."""

    @staticmethod
    def test_pin_preserves_present_tools_and_restores_only_missing_tools(
        tmp_path: Path,
    ) -> None:
        """Pin CLI keeps current resolutions and never duplicates committed blocks."""
        stage = tmp_path / "stage"
        stage.mkdir()
        present = '[[tools."github:alpha/release"]]\nversion = "2.0"\n'
        missing = '[[tools."npm:beta"]]\nversion = "1.0"\n'
        (stage / "mise.lock").write_text(present, encoding="utf-8")
        (stage / ".mise.toml").write_text(
            '[tools]\n"github:alpha/release" = "latest"\n"npm:beta" = "latest"\n',
            encoding="utf-8",
        )
        committed = tmp_path / "committed.lock"
        committed_content = present.replace('"2.0"', '"1.0"') + missing
        committed.write_text(committed_content, encoding="utf-8")
        script = Path(__file__).resolve().parents[3] / "bin/mise-lock-converge.py"
        for _ in range(2):
            outcome = tm.ok(
                u.Cli.run_raw(
                    [sys.executable, str(script), "pin", str(stage), str(committed)],
                    cwd=tmp_path,
                ),
            )
            tm.that(u.Cli.process_succeeded(outcome.outcome), eq=True)
            tm.that((stage / "mise.lock").read_text(), eq=present + "\n" + missing)
            manifest = tomllib.loads((stage / ".mise.toml").read_text())
            tm.that(
                manifest["tools"],
                eq={"github:alpha/release": "2.0", "npm:beta": "1.0"},
            )
        tm.that(committed.read_text(), eq=committed_content)
