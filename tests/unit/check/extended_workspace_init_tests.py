"""Public behavior tests for FlextInfraWorkspaceChecker."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.check import FlextInfraWorkspaceChecker
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraWorkspaceInit:
    """Declarative public-contract tests for workspace checker setup."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("--fix --unsafe-fixes", ["--fix", "--unsafe-fixes"]), (None, []), ("", [])],
    )
    def test_parse_tool_args(self, raw: str | None, expected: t.StrSequence) -> None:
        tm.that(FlextInfraWorkspaceChecker.parse_tool_args(raw), eq=list(expected))

    def test_init_creates_default_reports_dir(self, tmp_path: Path) -> None:
        FlextInfraWorkspaceChecker(repository_root=tmp_path)
        reports_dir = tmp_path / c.Infra.REPORTS_DIR_NAME / c.Infra.VERB_CHECK
        tm.that(reports_dir.exists(), eq=True)

    def test_execute_returns_failure(self, tmp_path: Path) -> None:
        result = FlextInfraWorkspaceChecker(repository_root=tmp_path).execute()
        tm.fail(result, has="Use execute_command() directly")

    def test_resolve_gates_rejects_duplicate_explicit_gates(self) -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates([
            c.Infra.PYREFLY,
            c.Infra.PYREFLY,
        ])
        tm.fail(result, has=f"duplicate gate '{c.Infra.PYREFLY}'")

    def test_resolve_gates_rejects_unknown_gate(self) -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates(["unknown"])
        tm.fail(result, has="unknown gate")

    def test_resolve_repository_root_or_cwd_returns_absolute_path(self) -> None:
        tm.that(u.Infra.resolve_repository_root_or_cwd(None).is_absolute(), eq=True)

    def test_run_projects_fails_when_reports_dir_is_not_a_directory(
        self, tmp_path: Path
    ) -> None:
        reports_file = tmp_path / "reports.txt"
        reports_file.write_text("", encoding="utf-8")

        result = FlextInfraWorkspaceChecker(repository_root=tmp_path).run_projects(
            ["project-a"], [c.Infra.LINT], reports_dir=reports_file
        )

        tm.fail(result)
