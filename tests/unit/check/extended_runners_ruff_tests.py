"""Real gate behavior tests for Ruff and Pyright."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import m
from flext_infra.gates.pyright import FlextInfraPyrightGate
from flext_infra.gates.ruff_format import FlextInfraRuffFormatGate
from flext_infra.gates.ruff_lint import FlextInfraRuffLintGate
from flext_tests import tm
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestRealGateRunners:
    """Exercise real gate behavior through public gate APIs."""

    @staticmethod
    def make_ctx(root: Path) -> m.Infra.GateContext:
        return m.Infra.GateContext(workspace=root, reports_dir=root)

    def test_ruff_lint_reports_real_issue(self, tmp_path: Path) -> None:
        project_dir = u.Tests.mk_project(tmp_path, "lint-project", with_src=True)
        (project_dir / "src" / "demo.py").write_text("import os\n", encoding="utf-8")

        result = FlextInfraRuffLintGate(tmp_path).check(
            project_dir, self.make_ctx(tmp_path)
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), gte=1)

    def test_ruff_lint_honors_public_ruff_args(self, tmp_path: Path) -> None:
        project_dir = u.Tests.mk_project(tmp_path, "lint-args", with_src=True)
        (project_dir / "src" / "demo.py").write_text(
            'value = "' + ("x" * 120) + '"\n', encoding="utf-8"
        )

        result = FlextInfraRuffLintGate(tmp_path).check(
            project_dir,
            m.Infra.GateContext(
                workspace=tmp_path, reports_dir=tmp_path, ruff_args=("--select", "E501")
            ),
        )

        tm.that(not result.result.passed, eq=True)
        tm.that([issue.code for issue in result.issues], has=["E501"])

    def test_ruff_lint_scopes_nested_project_to_owned_source_dirs(
        self, tmp_path: Path
    ) -> None:
        """Do not recurse into nested consumer repositories or worktrees."""
        project_dir = u.Tests.mk_project(tmp_path, "scoped-project", with_src=True)
        (project_dir / "tests").mkdir()
        nested = project_dir / ".claude" / "worktrees" / "nested"
        nested.mkdir(parents=True)
        (nested / "pyproject.toml").write_text(
            "[project]\nname='nested'\n", encoding="utf-8"
        )
        (nested / "bad.py").write_text("import os\n", encoding="utf-8")

        gate = FlextInfraRuffLintGate(tmp_path)
        check_dirs = gate.check(project_dir, self.make_ctx(tmp_path))

        tm.that(check_dirs.result.passed, eq=True)
        tm.that(check_dirs.issues, empty=True)

    def test_ruff_format_reports_real_reformat(self, tmp_path: Path) -> None:
        project_dir = u.Tests.mk_project(tmp_path, "format-project", with_src=True)
        (project_dir / "src" / "demo.py").write_text(
            "value=[1,2,3]\n", encoding="utf-8"
        )

        result = FlextInfraRuffFormatGate(tmp_path).check(
            project_dir, self.make_ctx(tmp_path)
        )

        tm.that(not result.result.passed, eq=True)

    def test_ruff_format_fix_stays_within_owned_source_dirs(
        self, tmp_path: Path
    ) -> None:
        project_dir = u.Tests.mk_project(tmp_path, "format-scope", with_src=True)
        source = project_dir / "src" / "demo.py"
        source.write_text("value=[1,2,3]\n", encoding="utf-8")
        agents = project_dir / ".agents"
        agents.mkdir()
        (agents / "INSTRUCTION_SURFACE.md").symlink_to(
            tmp_path / "external-owner" / "INSTRUCTION_SURFACE.md"
        )

        result = FlextInfraRuffFormatGate(tmp_path).fix(
            project_dir,
            m.Infra.GateContext(
                workspace=tmp_path, reports_dir=tmp_path, apply_fixes=True
            ),
        )

        tm.that(result.result.passed, eq=True)
        tm.that(source.read_text(encoding="utf-8"), eq="value = [1, 2, 3]\n")

    def test_pyright_reports_real_type_error(self, tmp_path: Path) -> None:
        project_dir = u.Tests.mk_project(tmp_path, "pyright-project", with_src=True)
        (project_dir / "src" / "demo.py").write_text(
            "value: str = 1\n", encoding="utf-8"
        )

        result = FlextInfraPyrightGate(tmp_path).check(
            project_dir, self.make_ctx(tmp_path)
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), gte=1)


__all__: t.StrSequence = []
