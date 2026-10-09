"""Real gate behavior tests for Ruff and Pyright.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, m
from flext_infra.gates.pyright import FlextInfraPyrightGate
from flext_infra.gates.ruff_format import FlextInfraRuffFormatGate
from flext_infra.gates.ruff_lint import FlextInfraRuffLintGate
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRealGateRunners:
    """Exercise real gate behavior through public gate APIs."""

    @staticmethod
    def make_ctx(root: Path) -> m.Infra.GateContext:
        """Provide ``make_ctx``.

        Returns:
            The resulting ``m.Infra.GateContext``.

        """
        return m.Infra.GateContext(repository_root=root, reports_dir=root)

    def test_ruff_lint_reports_real_issue(self, tmp_path: Path) -> None:
        """Test ruff lint reports real issue."""
        project_dir = u.Tests.mk_project(tmp_path, "lint-project", with_src=True)
        (project_dir / "src" / "demo.py").write_text("import os\n", encoding="utf-8")

        result = FlextInfraRuffLintGate(tmp_path).check(
            project_dir,
            self.make_ctx(tmp_path),
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), gte=1)

    @staticmethod
    def test_ruff_lint_honors_public_ruff_args(tmp_path: Path) -> None:
        """Test ruff lint honors public ruff args."""
        project_dir = u.Tests.mk_project(tmp_path, "lint-args", with_src=True)
        (project_dir / "src" / "demo.py").write_text(
            'value = "' + ("x" * 120) + '"\n',
            encoding="utf-8",
        )

        result = FlextInfraRuffLintGate(tmp_path).check(
            project_dir,
            m.Infra.GateContext(
                repository_root=tmp_path,
                reports_dir=tmp_path,
                ruff_args=("--select", "line-too-long"),
            ),
        )

        tm.that(not result.result.passed, eq=True)
        tm.that([issue.code for issue in result.issues], has=["line-too-long"])

    @pytest.mark.slow
    def test_ruff_lint_fix_reports_stderr_diagnostics_instead_of_deleting_them(
        self,
        tmp_path: Path,
    ) -> None:
        """Make fix applies safe fixes and keeps a stderr diagnostic reachable.

        Ruff's unsafe T201 fix deleted ``print(..., file=sys.stderr)`` from a
        consumer script and turned its failures silent. Under the rendered
        fleet policy the lint repair still sorts the imports, while the
        diagnostic survives and stays reported.
        """
        project_dir = u.Tests.mk_project(
            tmp_path,
            "fix-safety",
            pyproject=u.Tests.scaffold_text(
                tmp_path / "fixture-project",
                c.PYPROJECT_FILENAME,
            ),
        )
        script = project_dir / "scripts" / "report_failure.py"
        script.parent.mkdir()
        script.write_text(
            '"""Report one failure on stderr."""\n\n'
            "from __future__ import annotations\n\n"
            "import sys\n"
            "import json\n\n"
            'print(json.dumps({"failed": True}), file=sys.stderr)\n',
            encoding="utf-8",
        )
        gate = FlextInfraRuffLintGate(tmp_path)

        before = gate.check(project_dir, self.make_ctx(tmp_path))
        _ = gate.fix(
            project_dir,
            m.Infra.GateContext(
                repository_root=tmp_path,
                reports_dir=tmp_path,
                apply_fixes=True,
            ),
        )
        after = gate.check(project_dir, self.make_ctx(tmp_path))
        emitted = tm.ok(u.Cli.run_raw([sys.executable, str(script)], cwd=project_dir))

        tm.that(len(after.issues), lt=len(before.issues))
        tm.that(not after.result.passed, eq=True)
        tm.that(emitted.stderr, has='{"failed": true}')

    @pytest.mark.slow
    def test_ruff_lint_fix_hoists_inline_imports_and_wraps_long_literals(
        self,
        tmp_path: Path,
    ) -> None:
        """Make fix repairs import-outside-top-level and line-too-long itself.

        Ruff has no fix for either rule: the normalize-imports recipe hoists the
        inline import through the import-law engine and the wrap-long-line
        recipe splits the long literal; the module keeps running.
        """
        project_dir = u.Tests.mk_project(
            tmp_path,
            "fix-imports",
            pyproject=u.Tests.scaffold_text(
                tmp_path / "fixture-project",
                c.PYPROJECT_FILENAME,
            ),
            with_src=True,
        )
        module = project_dir / "src" / "fix_imports" / "report.py"
        long_words = " ".join(["payload"] * 14)
        module.write_text(
            '"""Render one report."""\n\n'
            "from __future__ import annotations\n\n\n"
            "def render() -> str:\n"
            '    """Render the report payload."""\n'
            "    import json\n\n"
            f'    return json.dumps({{"message": "{long_words}"}})\n',
            encoding="utf-8",
        )
        gate = FlextInfraRuffLintGate(tmp_path)

        _ = gate.fix(
            project_dir,
            m.Infra.GateContext(
                repository_root=tmp_path,
                reports_dir=tmp_path,
                apply_fixes=True,
            ),
        )
        after = gate.check(project_dir, self.make_ctx(tmp_path))
        repaired = module.read_text(encoding="utf-8")
        emitted = tm.ok(
            u.Cli.run_raw(
                [
                    sys.executable,
                    "-c",
                    (
                        "import sys; sys.path.insert(0, 'src'); "
                        "from fix_imports.report import render; print(render())"
                    ),
                ],
                cwd=project_dir,
            ),
        )

        tm.that(
            [issue.code for issue in after.issues],
            lacks=["import-outside-top-level", "line-too-long"],
        )
        tm.that(repaired, has="\nimport json\n")
        tm.that(repaired, lacks="    import json")
        tm.that(emitted.stdout, has=long_words)

    def test_ruff_lint_scopes_nested_project_to_owned_source_dirs(
        self,
        tmp_path: Path,
    ) -> None:
        """Do not recurse into nested consumer repositories or worktrees."""
        project_dir = u.Tests.mk_project(tmp_path, "scoped-project", with_src=True)
        (project_dir / "src/scoped_project/__init__.py").write_text(
            '"""Scoped test package."""\n',
            encoding="utf-8",
        )
        (project_dir / "tests").mkdir()
        nested = project_dir / ".claude" / "worktrees" / "nested"
        nested.mkdir(parents=True)
        (nested / "pyproject.toml").write_text(
            "[project]\nname='nested'\n",
            encoding="utf-8",
        )
        (nested / "bad.py").write_text("import os\n", encoding="utf-8")

        gate = FlextInfraRuffLintGate(tmp_path)
        check_dirs = gate.check(project_dir, self.make_ctx(tmp_path))

        tm.that(check_dirs.result.passed, eq=True)
        tm.that(check_dirs.issues, empty=True)

    def test_ruff_format_reports_real_reformat(self, tmp_path: Path) -> None:
        """Test ruff format reports real reformat."""
        project_dir = u.Tests.mk_project(tmp_path, "format-project", with_src=True)
        (project_dir / "src" / "demo.py").write_text(
            "value=[1,2,3]\n",
            encoding="utf-8",
        )

        result = FlextInfraRuffFormatGate(tmp_path).check(
            project_dir,
            self.make_ctx(tmp_path),
        )

        tm.that(not result.result.passed, eq=True)

    @staticmethod
    def test_ruff_format_fix_stays_within_owned_source_dirs(
        tmp_path: Path,
    ) -> None:
        """Test ruff format fix stays within owned source dirs."""
        project_dir = u.Tests.mk_project(tmp_path, "format-scope", with_src=True)
        source = project_dir / "src" / "demo.py"
        source.write_text("value=[1,2,3]\n", encoding="utf-8")
        agents = project_dir / ".agents"
        agents.mkdir()
        (agents / "INSTRUCTION_SURFACE.md").symlink_to(
            tmp_path / "external-owner" / "INSTRUCTION_SURFACE.md",
        )

        result = FlextInfraRuffFormatGate(tmp_path).fix(
            project_dir,
            m.Infra.GateContext(
                repository_root=tmp_path,
                reports_dir=tmp_path,
                apply_fixes=True,
            ),
        )

        tm.that(result.result.passed, eq=True)
        tm.that(source.read_text(encoding="utf-8"), eq="value = [1, 2, 3]\n")

    @pytest.mark.requires_engine("pyright")
    def test_pyright_reports_real_type_error(self, tmp_path: Path) -> None:
        """Test pyright reports real type error."""
        project_dir = u.Tests.mk_project(
            tmp_path,
            "pyright-project",
            pyproject=(
                '[tool.pyright]\ninclude = ["src"]\ntypeCheckingMode = "strict"\n'
            ),
            with_src=True,
        )
        (project_dir / "src" / "demo.py").write_text(
            "value: str = 1\n",
            encoding="utf-8",
        )

        result = FlextInfraPyrightGate(tmp_path).check(
            project_dir,
            self.make_ctx(tmp_path),
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(len(result.issues), gte=1)
