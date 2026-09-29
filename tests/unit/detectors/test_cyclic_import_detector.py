"""Behavior tests for prospective Rope import cycle detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import u
from flext_infra.detectors.cyclic_import_detector import FlextInfraCyclicImportDetector

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraCyclicImportDetector:
    """Prospective graph contracts for canonical alias migrations."""

    @staticmethod
    def _project(
        tmp_path: Path, files: t.StrMapping
    ) -> t.Pair[Path, t.MutableMappingKV[str, Path]]:
        project = tmp_path / "demo-project"
        package = project / "src" / "demo_pkg"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            '[project]\nname = "demo-project"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        paths: t.MutableMappingKV[str, Path] = {}
        for filename, source in files.items():
            path = package / filename
            path.write_text(source, encoding="utf-8")
            paths[filename] = path
        return project, paths

    def test_reports_every_independent_cycle(self, tmp_path: Path) -> None:
        project, paths = self._project(
            tmp_path,
            {
                "a.py": "from demo_pkg import b\n",
                "b.py": "from demo_pkg import a\n",
                "c.py": "VALUE = 1\n",
                "d.py": "from demo_pkg import c\n",
            },
        )
        with u.Infra.open_project(project) as rope_project:
            cycles = FlextInfraCyclicImportDetector.scan_project(
                project_root=project,
                rope_project=rope_project,
                proposed_sources={paths["c.py"]: "from demo_pkg import d\n"},
            )
        signatures = {frozenset(cycle.cycle) for cycle in cycles}
        tm.that(
            signatures,
            eq={
                frozenset({"demo_pkg.a", "demo_pkg.b"}),
                frozenset({"demo_pkg.c", "demo_pkg.d"}),
            },
        )

    def test_preserves_relative_import_module_identity(self, tmp_path: Path) -> None:
        project, paths = self._project(
            tmp_path, {"a.py": "from demo_pkg import b\n", "b.py": "VALUE = 1\n"}
        )
        with u.Infra.open_project(project) as rope_project:
            cycles = FlextInfraCyclicImportDetector.scan_project(
                project_root=project,
                rope_project=rope_project,
                proposed_sources={paths["b.py"]: "from . import a\n"},
            )
        tm.that(len(cycles), eq=1)
        tm.that(frozenset(cycles[0].cycle), eq=frozenset({"demo_pkg.a", "demo_pkg.b"}))

    def test_ignores_type_checking_reverse_edge(self, tmp_path: Path) -> None:
        project, paths = self._project(
            tmp_path,
            {
                "a.py": (
                    "from __future__ import annotations\n"
                    "from typing import TYPE_CHECKING\n\n"
                    "if TYPE_CHECKING:\n"
                    "    from demo_pkg import b\n"
                ),
                "b.py": "VALUE = 1\n",
            },
        )
        with u.Infra.open_project(project) as rope_project:
            cycles = FlextInfraCyclicImportDetector.scan_project(
                project_root=project,
                rope_project=rope_project,
                proposed_sources={paths["b.py"]: "from demo_pkg import a\n"},
            )
        tm.that(cycles, eq=[])
