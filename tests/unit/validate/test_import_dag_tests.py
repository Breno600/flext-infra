"""Behavior tests for the strict test import DAG guard."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.validate.test_import_dag import FlextInfraValidateTestImportDag
from tests import m

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraImportDag:
    """Verify allowed and forbidden package-test import edges."""

    @staticmethod
    def _project(tmp_path: Path, files: t.MappingKV[str, str]) -> Path:
        project = tmp_path / "sample"
        (project / "pyproject.toml").parent.mkdir(parents=True, exist_ok=True)
        (project / "pyproject.toml").write_text(
            '[project]\nname = "sample"\nversion = "0.0.1"\n', encoding="utf-8"
        )
        for relative, source in files.items():
            target = project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source, encoding="utf-8")
        return project

    @pytest.mark.parametrize(
        ("source", "imported"),
        [
            ("tests/typings.py", "from tests.constants import C\n"),
            ("tests/protocols.py", "from tests.typings import T\n"),
            ("tests/models.py", "from tests.protocols import P\n"),
            ("tests/utilities.py", "from tests.models import M\n"),
            ("tests/constants.py", "from tests import c\n"),
            ("tests/models.py", "from tests.fixtures.users import user\n"),
            ("tests/__init__.py", "from tests.conftest import fixture\n"),
            ("src/sample/api.py", "from tests import u\n"),
        ],
    )
    def test_forbidden_edges_fail(
        self, tmp_path: Path, source: str, imported: str
    ) -> None:
        project = self._project(tmp_path, {source: imported})
        report: m.Infra.ValidationReport = tm.ok(
            FlextInfraValidateTestImportDag().build_report(project)
        )
        tm.that(report.passed, eq=False)

    def test_forward_facets_and_type_checking_reverse_edges_pass(
        self, tmp_path: Path
    ) -> None:
        project = self._project(
            tmp_path,
            {
                "tests/constants.py": "from tests.typings import t\n",
                "tests/typings.py": "from tests.protocols import p\n",
                "tests/protocols.py": "from tests.models import m\n",
                "tests/models.py": "from tests.utilities import u\n",
                "tests/utilities.py": (
                    "from __future__ import annotations\n"
                    "from typing import TYPE_CHECKING\n"
                    "if TYPE_CHECKING:\n"
                    "    from tests.constants import c\n"
                ),
            },
        )
        report: m.Infra.ValidationReport = tm.ok(
            FlextInfraValidateTestImportDag().build_report(project)
        )
        tm.that(report.passed, eq=True)
