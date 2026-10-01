"""Detection of modules written in the canonical facade-rebind form.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import u


class TestsFlextInfraFacadeRebindModules:
    """Only a letter rebound to the facade class that subclasses it qualifies."""

    @staticmethod
    def test_detects_exactly_the_rebind_form(tmp_path: Path) -> None:
        package = tmp_path / "src" / "demo"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "utilities.py").write_text(
            "from flext_core import u\n\n\n"
            "class DemoUtilities(u):\n    pass\n\n\n"
            "u = DemoUtilities\n",
            encoding="utf-8",
        )
        (package / "models.py").write_text(
            "from flext_core import FlextModels\n\n\n"
            "class DemoModels(FlextModels):\n    pass\n\n\n"
            "m = DemoModels\n",
            encoding="utf-8",
        )
        (package / "paths.py").write_text(
            "from os import sep\n\nsep = sep.upper()\n",
            encoding="utf-8",
        )

        tm.that(u.Infra.facade_rebind_modules(tmp_path), eq=("demo.utilities",))

    @staticmethod
    def test_a_project_not_on_disk_has_none(tmp_path: Path) -> None:
        tm.that(u.Infra.facade_rebind_modules(tmp_path / "absent"), eq=())
