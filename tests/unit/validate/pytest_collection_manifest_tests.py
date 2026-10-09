"""The collection plugin never imports the model facade to honor a runner request.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m, u
from tests.unit.validate.pytest_runner_support import runner_for


class TestsFlextInfraPytestCollectionManifest:
    """Exercise the installed collection plugin through a real nested pytest."""

    @staticmethod
    def _collect(project: Path, *options: str) -> str:
        """Collect with the real collection plugin as the only external plugin.

        Returns:
            The resulting ``str``.

        """
        tests = project / "tests"
        tests.mkdir(exist_ok=True)
        (project / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        (tests / "test_sample.py").write_text(
            "def test_sample() -> None:\n    assert 17 == 17\n",
            encoding="utf-8",
        )
        (project / "conftest.py").write_text(
            "import sys\nfrom pathlib import Path\n\n"
            "def pytest_sessionfinish(session):\n"
            "    Path(session.config.rootpath, 'models-loaded.txt').write_text(\n"
            "        str('flext_infra.models' in sys.modules))\n",
            encoding="utf-8",
        )
        tm.ok(
            u.Cli.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests",
                    "--collect-only",
                    "-q",
                    "-p",
                    "pytest_reportlog.plugin",
                    "-p",
                    "flext_tests.enforcement_plugin",
                    "-p",
                    "flext_infra._pytest_collection",
                    *options,
                ],
                cwd=project,
                env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
                remove_env_keys=("PYTEST_ADDOPTS",),
            ),
        )
        return (project / "models-loaded.txt").read_text(encoding="utf-8")

    def test_unrequested_manifest_never_imports_the_model_facade(
        self,
        tmp_path: Path,
    ) -> None:
        """Test unrequested manifest never imports the model facade."""
        tm.that(self._collect(tmp_path), eq="False")
        tm.that(list(tmp_path.glob("*.json")), eq=[])

    def test_runner_requested_manifest_publishes_the_collected_items(
        self,
        tmp_path: Path,
    ) -> None:
        """Test runner requested manifest publishes the collected items."""
        target = tmp_path / "collection.json"

        loaded = self._collect(
            tmp_path,
            f"{c.Infra.PYTEST_COLLECTION_MANIFEST_OPTION}={target}",
        )

        tm.that(loaded, eq="False")
        manifest = m.Infra.PytestCollectionManifest.model_validate_json(
            target.read_text(encoding="utf-8"),
        )
        tm.that(manifest.node_ids, eq=("tests/test_sample.py::test_sample",))

    @staticmethod
    @pytest.mark.slow
    def test_missing_collection_manifest_preserves_file_failure(
        cached_runner_project: Path,
    ) -> None:
        """Test missing collection manifest preserves file failure."""
        (cached_runner_project / "conftest.py").write_text(
            "from pathlib import Path\n\n"
            "def pytest_sessionfinish(session):\n"
            "    target = session.config.getoption(\n"
            f"        {c.Infra.PYTEST_COLLECTION_MANIFEST_OPTION!r})\n"
            "    if target:\n        Path(target).unlink()\n",
            encoding="utf-8",
        )
        runner = runner_for(cached_runner_project)

        with pytest.raises(FileNotFoundError, match=r"testmon-selection\.json"):
            runner.execute()
