"""Behavior tests for the Rope snapshot inventory boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.workspace.rope import FlextInfraRopeWorkspace
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRopeSnapshot:
    """Validate the closed snapshot inventory against governed entry files."""

    def test_snapshot_serves_project_root_entry_module(self, tmp_path: Path) -> None:
        """A governed root conftest.py joins the closed inventory from disk."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        conftest = repository_root / "conftest.py"
        conftest.write_text(
            '"""Root entry module outside every source folder."""\n', encoding="utf-8"
        )
        package_init = package_root / "__init__.py"
        sources = {
            package_init.resolve(): package_init.read_text(encoding="utf-8"),
            conftest.resolve(): conftest.read_text(encoding="utf-8"),
        }
        with FlextInfraRopeWorkspace.open_workspace(repository_root) as rope:
            snapshot = u.Infra.snapshot_project(rope.rope_project, sources)
            try:
                resource = snapshot.get_resource("conftest.py")
                tm.that(resource.read(), eq=sources[conftest.resolve()])
            finally:
                snapshot.close()

    def test_snapshot_rejects_sources_outside_the_project(self, tmp_path: Path) -> None:
        """A path outside the workspace root never enters the closed inventory."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        outsider = tmp_path / "outside.py"
        outsider.write_text("value = 1\n", encoding="utf-8")
        package_init = package_root / "__init__.py"
        sources = {
            package_init.resolve(): package_init.read_text(encoding="utf-8"),
            outsider.resolve(): "value = 1\n",
        }
        with (
            FlextInfraRopeWorkspace.open_workspace(repository_root) as rope,
            pytest.raises(
                ValueError, match=r"outside its input inventory"
            ) as guard_error,
        ):
            u.Infra.snapshot_project(rope.rope_project, sources)

        tm.that(str(outsider.resolve()) in str(guard_error.value), eq=True)
