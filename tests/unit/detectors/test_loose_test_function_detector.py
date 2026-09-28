"""Tests for the loose test function detector."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import m, u
from flext_infra.detectors.loose_test_function_detector import (
    FlextInfraLooseTestFunctionDetector,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraLooseTestFunctionDetector:
    """Behavior contract for loose-test-function detection (config-driven engine)."""

    @staticmethod
    def _project(tmp_path: Path) -> Path:
        project = tmp_path / "demo-project"
        tests_dir = project / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        _ = (project / "pyproject.toml").write_text(
            "[project]\nname='demo-project'\n", encoding="utf-8"
        )
        return project

    @staticmethod
    def _violations(
        *, project: Path, file_path: Path
    ) -> t.VariadicTuple[m.Infra.LooseTestFunctionViolation]:
        with u.Infra.open_project(project) as rope_project:
            violations = FlextInfraLooseTestFunctionDetector.detect_file(
                m.Infra.DetectorContext(
                    file_path=file_path,
                    rope_project=rope_project,
                    project_root=project,
                    project_name="demo-project",
                )
            )
        return tuple(violations)

    def test_flags_module_level_test_function(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        test_file = project / "tests" / "unit" / "test_loose.py"
        _ = test_file.write_text(
            "from __future__ import annotations\n\n"
            "def test_ping() -> None:\n"
            "    assert True\n",
            encoding="utf-8",
        )

        violations = self._violations(project=project, file_path=test_file)

        tm.that(len(violations), eq=1)
        tm.that(violations[0].name, eq="test_ping")

    def test_allows_test_nested_in_tests_class(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        test_file = project / "tests" / "unit" / "test_nested.py"
        _ = test_file.write_text(
            "from __future__ import annotations\n\n"
            "class TestsDemoSmoke:\n"
            "    def test_ping(self) -> None:\n"
            "        assert True\n",
            encoding="utf-8",
        )

        violations = self._violations(project=project, file_path=test_file)

        tm.that(violations, eq=())

    def test_ignores_non_test_file_outside_globs(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        src_dir = project / "src" / "demo_project"
        src_dir.mkdir(parents=True)
        module_file = src_dir / "helpers.py"
        _ = module_file.write_text(
            "from __future__ import annotations\n\n"
            "def test_shaped_but_not_a_test() -> None:\n"
            "    return None\n",
            encoding="utf-8",
        )

        violations = self._violations(project=project, file_path=module_file)

        tm.that(violations, eq=())
