r"""Validate the generated Python selector through its real artifact contract.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, u
from flext_tests import tm


class TestsFlextInfraPythonSelectorRender:
    def test_render_is_the_selector_and_nothing_else(self) -> None:
        """The generated consumer artifact equals its typed configuration owner."""
        expected = f"{config.Infra.codegen.toolchain.python_selector}\n"
        rendered = tm.ok(u.Cli.files_read_text(Path(c.Infra.PYTHON_VERSION_FILENAME)))

        tm.that(rendered, eq=expected)
