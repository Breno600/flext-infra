"""Public-behavior tests for ``FlextInfraConfigFixer`` edge cases.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.deps.fix_pyrefly_config import FlextInfraConfigFixer
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraExtendedConfigFixerErrors:
    """Exercise ``FlextInfraConfigFixer`` only through its public surface."""

    @staticmethod
    @pytest.mark.parametrize(
        ("pyproject", "name"),
        [
            ('[tool]\npyrefly = "string"\n', "string-pyrefly"),
            ("[build-system]\n", "no-tool-pyrefly"),
        ],
    )
    @staticmethod
    def test_process_file_returns_empty_for_non_fixable_documents(
        tmp_path: Path,
        pyproject: str,
        name: str,
    ) -> None:
        """Test process file returns empty for non fixable documents."""
        file_path = tmp_path / f"{name}.toml"
        file_path.write_text(pyproject, encoding="utf-8")

        result = FlextInfraConfigFixer(repository_root=tmp_path).process_file(file_path)

        tm.ok(result)
        tm.that(result.value, eq=[])

    @staticmethod
    def test_run_returns_verbose_messages_for_selected_project(
        tmp_path: Path,
    ) -> None:
        """Test run returns verbose messages for selected project."""
        u.Tests.mk_project(
            tmp_path,
            "project1",
            pyproject="[tool.pyrefly]\nsearch-path = []\n",
        )

        result = FlextInfraConfigFixer(repository_root=tmp_path).run(
            ["project1"],
            verbose=True,
        )

        tm.ok(result)
        tm.that(result.value, empty=False)
        tm.that(
            any("project1/pyproject.toml" in line for line in result.value),
            eq=True,
        )

    @staticmethod
    def test_run_dry_run_preserves_file_while_reporting_fixes(
        tmp_path: Path,
    ) -> None:
        """Test run dry run preserves file while reporting fixes."""
        project_dir = u.Tests.mk_project(
            tmp_path,
            "project1",
            pyproject="[tool.pyrefly]\nsearch-path = []\n",
        )
        pyproject = project_dir / "pyproject.toml"
        original = pyproject.read_text(encoding="utf-8")

        result = FlextInfraConfigFixer(repository_root=tmp_path).run(
            ["project1"],
            dry_run=True,
            verbose=True,
        )

        tm.ok(result)
        tm.that(result.value, empty=False)
        tm.that(pyproject.read_text(encoding="utf-8"), eq=original)
