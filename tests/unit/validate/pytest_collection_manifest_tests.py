"""The collection plugin imports its model facade only on a runner request."""

from __future__ import annotations

import sys
from pathlib import Path

from flext_tests import tm

from flext_infra import c, m, u


class TestsFlextInfraPytestCollectionManifest:
    """Exercise the installed collection plugin through a real nested pytest."""

    @staticmethod
    def _collect(project: Path, *options: str) -> str:
        """Collect the sample project with every installed pytest plugin."""
        tests = project / "tests"
        tests.mkdir(exist_ok=True)
        (project / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        (tests / "test_sample.py").write_text(
            "def test_sample() -> None:\n    assert 17 == 17\n", encoding="utf-8"
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
                    "no:randomly",
                    *options,
                ],
                cwd=project,
                remove_env_keys=("PYTEST_ADDOPTS",),
            )
        )
        return (project / "models-loaded.txt").read_text(encoding="utf-8")

    def test_unrequested_manifest_never_imports_the_model_facade(
        self, tmp_path: Path
    ) -> None:
        tm.that(self._collect(tmp_path), eq="False")
        tm.that(list(tmp_path.glob("*.json")), eq=[])

    def test_runner_requested_manifest_publishes_the_collected_items(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "collection.json"

        loaded = self._collect(
            tmp_path, f"{c.Infra.PYTEST_COLLECTION_MANIFEST_OPTION}={target}"
        )

        tm.that(loaded, eq="True")
        manifest = m.Infra.PytestCollectionManifest.model_validate_json(
            target.read_text(encoding="utf-8")
        )
        tm.that(manifest.node_ids, eq=("tests/test_sample.py::test_sample",))
