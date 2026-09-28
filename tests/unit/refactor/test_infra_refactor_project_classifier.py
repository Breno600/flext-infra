"""Tests for the refactor project classifier."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.refactor.project_classifier import FlextInfraProjectClassifier

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRefactorInfraRefactorProjectClassifier:
    """Behavior contract for test_infra_refactor_project_classifier."""

    @staticmethod
    def _write_pyproject(project_root: Path, content: str) -> None:
        pyproject_path = project_root / "pyproject.toml"
        pyproject_path.write_text(content.strip() + "\n", encoding="utf-8")

    def test_classify_reads_internal_dependencies_from_pep621(
        self, tmp_path: Path
    ) -> None:
        self._write_pyproject(
            tmp_path,
            """
            [project]
            name = "flext-example"
            dependencies = [
                "flext-core>=0.1.0",
                "flext-cli>=0.1.0",
                "requests>=2.0.0",
            ]
            """,
        )

        classification = FlextInfraProjectClassifier(tmp_path).classify()

        tm.that(classification.project_kind, eq="platform")

    def test_classify_reads_internal_dependencies_from_poetry(
        self, tmp_path: Path
    ) -> None:
        self._write_pyproject(
            tmp_path,
            """
            [tool.poetry]
            name = "flext-example"

            [tool.poetry.dependencies]
            python = "^3.13"
            flext-core = "^0.1.0"
            flext-cli = { version = "^0.1.0" }
            requests = "^2.0.0"

            [tool.poetry.group.test.dependencies]
            python = "^3.13"
            flext-ldap = "^0.1.0"
            pytest = "^8.0.0"
            """,
        )

        classification = FlextInfraProjectClassifier(tmp_path).classify()

        tm.that(classification.project_kind, eq="app")
