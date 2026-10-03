"""Wave 0 stub tests confirming rope is importable.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRefactorRopeStubs:
    """Behavior contract for test_rope_stubs."""

    @staticmethod
    def test_rope_project_wrapper(tmp_path: Path) -> None:
        """Confirm the Rope project wrapper creates a live project."""
        project = u.Infra.init_rope_project(tmp_path)
        project = tm.not_none(project)
        try:
            tm.that(project.root.real_path, empty=False)
        finally:
            project.close()

    @staticmethod
    def test_rope_find_occurrences_wrapper(tmp_path: Path) -> None:
        """Confirm occurrence search works through the utility wrapper."""
        package_dir = tmp_path / "demo"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        target = package_dir / "mod.py"
        target.write_text("class Demo:\n    pass\n\nvalue = Demo()\n", encoding="utf-8")
        project = u.Infra.init_rope_project(tmp_path)
        project = tm.not_none(project)
        try:
            resource = u.Infra.resolve_resource_from_path(project, target)
            resource = tm.not_none(resource)
            offset = u.Infra.find_definition_offset(project, resource, "Demo")
            offset = tm.not_none(offset)
            hits = u.Infra.find_occurrences(project, resource, offset)
            tm.that(len(hits) > 0, eq=True)
        finally:
            project.close()
