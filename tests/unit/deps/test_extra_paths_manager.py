"""Test extra paths manager behavior.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import u
from tests.unit.deps.extra_paths_support import TestsFlextInfraExtraPathsSupport

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraExtraPathsManager:
    """Test flext infra extra paths manager behavior."""

    @staticmethod
    def test_sync_one_missing_file(tmp_path: Path) -> None:
        """Verify sync one missing file."""
        tm.that(
            not TestsFlextInfraExtraPathsSupport
            .manager()
            .sync_one(tmp_path / "nonexistent.toml")
            .success,
            eq=True,
        )

    @staticmethod
    def test_sync_one_no_tool_section(tmp_path: Path) -> None:
        """Verify sync one no tool section."""
        pyproject = tmp_path / "pyproject.toml"
        doc = u.Cli.toml_document()
        doc["project"] = {"name": "test"}
        pyproject.write_text(doc.as_string(), encoding="utf-8")
        result = TestsFlextInfraExtraPathsSupport.manager().sync_one(pyproject)
        tm.that(result.success, eq=True)
        tm.that(result.value, eq=False)

    @staticmethod
    def test_sync_one_no_pyright_section(tmp_path: Path) -> None:
        """Verify sync one no pyright section."""
        pyproject = tmp_path / "pyproject.toml"
        doc = u.Cli.toml_document()
        tool = u.Cli.toml_table()
        tool["other"] = u.Cli.toml_table()
        doc["tool"] = tool
        pyproject.write_text(doc.as_string(), encoding="utf-8")
        result = TestsFlextInfraExtraPathsSupport.manager().sync_one(pyproject)
        tm.that(result.success, eq=True)
        tm.that(result.value, eq=False)

    @staticmethod
    @pytest.mark.parametrize(
        "tool_doc",
        [
            {"pyright": {"extraPaths": ["src"]}},
            {"pyright": {"extraPaths": []}, "mypy": {"mypy_path": ["src"]}},
            {"pyright": {"extraPaths": []}, "pyrefly": {"search-path": ["."]}},
        ],
    )
    def test_sync_one_success_cases(
        tmp_path: Path,
        tool_doc: t.MappingKV[str, t.JsonValue],
    ) -> None:
        """Verify sync one success cases."""
        pyproject = tmp_path / "pyproject.toml"
        doc = u.Cli.toml_document()
        doc["tool"] = tool_doc
        pyproject.write_text(doc.as_string(), encoding="utf-8")
        result = TestsFlextInfraExtraPathsSupport.manager().sync_one(
            pyproject,
            is_root="pyrefly" not in tool_doc,
        )
        tm.that(result.success, eq=True)

    @staticmethod
    def test_sync_one_dry_run(tmp_path: Path) -> None:
        """Verify sync one dry run."""
        pyproject = tmp_path / "pyproject.toml"
        doc = u.Cli.toml_document()
        doc["tool"] = {"pyright": {"extraPaths": ["old"]}}
        pyproject.write_text(doc.as_string(), encoding="utf-8")
        tm.ok(
            TestsFlextInfraExtraPathsSupport.manager().sync_one(
                pyproject,
                dry_run=True,
                is_root=True,
            ),
        )
        tm.that(pyproject.read_text(encoding="utf-8"), contains="old")

    @staticmethod
    def test_sync_one_write_failure(tmp_path: Path) -> None:
        """Verify sync one write failure."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.pyright]\nextraPaths = ["old"]\n', encoding="utf-8")
        pyproject.chmod(0o444)

        tm.fail(
            TestsFlextInfraExtraPathsSupport.manager().sync_one(
                pyproject,
                is_root=True,
            ),
            has="TOML write",
        )

    @staticmethod
    def test_pyrefly_includes_skip_empty_declared_directory(
        tmp_path: Path,
    ) -> None:
        """An existing empty env_dir is not reintroduced after conform removes it."""
        project = u.Tests.mk_project(tmp_path, "demo")
        (project / "src" / "demo").mkdir(parents=True)
        (project / "src" / "demo" / "__init__.py").write_text("", encoding="utf-8")
        (project / "tests").mkdir()
        (project / "tests" / "test_demo.py").write_text("", encoding="utf-8")
        (project / "examples").mkdir()

        includes = TestsFlextInfraExtraPathsSupport.manager(
            project,
        ).pyrefly_project_includes(
            project_dir=project,
            is_root=False,
        )

        tm.that(includes, eq=["src/**/*.py*", "tests/**/*.py*"])

    @staticmethod
    def test_base_constants() -> None:
        """Verify base constants."""
        manager = TestsFlextInfraExtraPathsSupport.manager()
        tm.that(manager.root.is_absolute(), eq=True)
