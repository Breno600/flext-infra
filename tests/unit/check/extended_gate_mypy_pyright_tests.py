"""Public checker acceptance against real tools and native report schemas.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, config, m, main
from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from flext_infra.gates.mypy import FlextInfraMypyGate
from flext_infra.gates.pyrefly import FlextInfraPyreflyGate
from flext_infra.gates.pyright import FlextInfraPyrightGate
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra.gates.base_gate import FlextInfraGate


class TestsFlextInfraTypeGates:
    """The selected project's actual findings determine acceptance."""

    @staticmethod
    @pytest.mark.slow
    def test_mypy_cache_is_project_keyed_across_checkouts_and_relocks(
        tmp_path: Path,
    ) -> None:
        """Real gate runs populate one external cache per declared project name."""
        spec = config.Infra.codegen.make.mypy_cache
        cache_home = tmp_path / "cache"
        shared_root = cache_home / spec.external_storage_directory
        with tm.scope(env={str(spec.data_home_environment_variable): str(cache_home)}):
            for checkout, project in (
                ("lane", "fixture-alpha"),
                ("primary", "fixture-alpha"),
                ("other", "fixture-beta"),
            ):
                root = tmp_path / checkout
                root.mkdir()
                (root / c.PYPROJECT_FILENAME).write_text(
                    f"[project]\nname = '{project}'\nversion = '0.0.0'\n[tool.mypy]\n",
                    encoding="utf-8",
                )
                (root / "sample.py").write_text("value: int = 1\n", encoding="utf-8")
                lock = root / c.Infra.UV_LOCK_FILENAME
                context = m.Infra.GateContext(
                    repository_root=root,
                    reports_dir=root / ".reports",
                )
                gate = FlextInfraMypyGate(root)
                cache = shared_root / project
                for revision in (1, 2):
                    lock.write_text(
                        f"version = 1\nrevision = {revision}\n",
                        encoding="utf-8",
                    )
                    execution = gate.check(root, context)
                    tm.that(execution.result.passed, eq=True)
                    tm.that(
                        [
                            line.partition("Cache Dir:")[2].strip()
                            for line in execution.raw_output.splitlines()
                            if line.startswith("LOG:") and "Cache Dir:" in line
                        ],
                        eq=[str(cache)],
                    )
                    tm.that(cache.is_dir(), eq=True)
                    tm.that(any(path.is_file() for path in cache.rglob("*")), eq=True)
                tm.that((root / ".mypy_cache").exists(), eq=False)
            tm.that(
                {path.name for path in shared_root.iterdir()},
                eq={"fixture-alpha", "fixture-beta"},
            )

    @staticmethod
    @pytest.fixture
    def checker_context(real_python_package: Path) -> m.Infra.GateContext:
        """Configure the existing real package for native checker execution.

        Returns:
            The resulting ``m.Infra.GateContext``.

        """
        pyproject = real_python_package / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8")
            + '\n[tool.mypy]\n[tool.pyright]\ninclude = ["src"]\n'
            + '[tool.pyrefly]\nproject-includes = ["src"]\n',
            encoding="utf-8",
        )
        reports = real_python_package / ".reports"
        reports.mkdir()
        return m.Infra.GateContext(
            repository_root=real_python_package,
            reports_dir=reports,
        )

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize(
        "gate",
        sorted(c.Infra.TYPE_CHECKER_GATES),
    )
    def test_public_literal_file_checker_preserves_native_findings_policy(
        checker_context: m.Infra.GateContext,
        gate: str,
    ) -> None:
        """Native findings survive while acceptance follows the typed SSOT policy."""
        project = checker_context.repository_root
        source_root = project / config.Infra.source_scan.roots[0]
        source_root.mkdir(exist_ok=True)
        selected = source_root / "literal_file.py"
        selected.write_text("value: int = 'incorrect'\n", encoding="utf-8")
        sibling = source_root / "unselected_file.py"
        sibling.write_text("def :\n", encoding="utf-8")
        reports = checker_context.reports_dir / "literal-file"
        code = main([
            "check",
            "run",
            "--repository-root",
            str(project),
            "--file",
            str(selected.relative_to(project)),
            "--gates",
            gate,
            "--reports-dir",
            str(reports),
        ])
        tm.that(code, eq=1)
        (report_path,) = reports.glob(f"*/{c.Infra.CHECK_REPORT_SARIF_FILENAME}")
        findings = tm.ok(
            u.Infra.check_report_findings(project, reports_dir=report_path.parent),
        )
        tm.that(findings, empty=False)
        tm.that(
            any(
                location.uri.endswith(str(selected.relative_to(project)))
                for finding in findings
                for location in finding.locations
            ),
            eq=True,
        )

    @staticmethod
    @pytest.mark.slow
    def test_mypy_preserves_protocol_member_diagnostics(
        checker_context: m.Infra.GateContext,
    ) -> None:
        """Native protocol conflict details remain visible in reported issues."""
        project = checker_context.repository_root
        source = project / "src" / "test_pkg" / "contract.py"
        source.write_text(
            "from typing import Protocol\n"
            "class Expected(Protocol):\n"
            "    def size(self) -> int: ...\n"
            "class Actual:\n"
            "    def size(self) -> str:\n"
            "        return 'incorrect'\n"
            "value: Expected = Actual()\n",
            encoding="utf-8",
        )

        result = FlextInfraMypyGate(project).check(project, checker_context)

        tm.that(result.result.passed, eq=False)
        messages = "\n".join(issue.message for issue in result.issues)
        tm.that(messages, has=["Expected", "Actual", "def size", "int", "str"])

    @staticmethod
    @pytest.mark.slow
    def test_mypy_preserves_malformed_native_output(
        checker_context: m.Infra.GateContext,
    ) -> None:
        """Unexpected plugin output remains a causal, visible tool failure."""
        project = checker_context.repository_root
        plugin = project / "plugin.py"
        plugin.write_text(
            "from mypy.plugin import Plugin\n"
            "def plugin(version: str) -> type[Plugin]:\n"
            "    print('native-plugin-output')\n"
            "    return Plugin\n",
            encoding="utf-8",
        )
        pyproject = project / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8").replace(
                "[tool.mypy]\n",
                '[tool.mypy]\nplugins = ["plugin.py"]\n',
            ),
            encoding="utf-8",
        )

        result = FlextInfraMypyGate(project).check(project, checker_context)

        tm.that(result.result.passed, eq=False)
        tm.that(
            tuple(issue.code for issue in result.issues),
            has=c.Infra.ToolOutcome.ERROR,
        )
        tm.that(
            "\n".join(issue.message for issue in result.issues),
            has="native-plugin-output",
        )

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize(
        "gate_class",
        [FlextInfraMypyGate, FlextInfraPyrightGate, FlextInfraPyreflyGate],
    )
    def test_real_check_and_repair(
        checker_context: m.Infra.GateContext,
        gate_class: type[FlextInfraGate],
    ) -> None:
        """Test real check and repair."""
        project = checker_context.repository_root
        reports = checker_context.reports_dir
        ctx = m.Infra.GateContext(repository_root=project, reports_dir=reports)
        gate = gate_class(project)
        source = project / "src" / "test_pkg" / "contract.py"
        source.write_text('value: int = "incorrect"\n', encoding="utf-8")
        failed = gate.check(project, ctx)
        assert failed.result.passed is False
        assert failed.issues
        assert failed.result.errors
        assert any(issue.severity.lower() == "error" for issue in failed.issues)

        source.write_text("value: int = 1\n", encoding="utf-8")
        repaired = gate.check(project, ctx)
        assert repaired.result.passed, repaired
        assert not repaired.issues

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize(
        ("gate_class", "config_text"),
        [
            (
                FlextInfraPyrightGate,
                '[tool.pyright]\ninclude = ["src"]\nreportAssignmentType = "warning"\n',
            ),
            (
                FlextInfraPyreflyGate,
                (
                    '[tool.pyrefly]\nproject-includes = ["src"]\n'
                    '[tool.pyrefly.errors]\nbad-assignment = "warn"\n'
                ),
            ),
        ],
    )
    def test_real_warning_is_red(
        real_python_package: Path,
        gate_class: type[FlextInfraGate],
        config_text: str,
    ) -> None:
        """Test real warning is red."""
        project = real_python_package
        pyproject = project / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8") + "\n" + config_text,
            encoding="utf-8",
        )
        (project / "src" / "test_pkg" / "warning.py").write_text(
            'value: int = "incorrect"\n',
            encoding="utf-8",
        )
        reports = project / ".reports"
        reports.mkdir()
        result = gate_class(project).check(
            project,
            m.Infra.GateContext(repository_root=project, reports_dir=reports),
        )
        assert result.result.passed is False
        assert any(issue.severity in {"warn", "warning"} for issue in result.issues)

    @staticmethod
    @pytest.mark.slow
    def test_failed_pyrefly_cannot_reuse_previous_report(
        checker_context: m.Infra.GateContext,
    ) -> None:
        """Test failed pyrefly cannot reuse previous report."""
        project = checker_context.repository_root
        pyproject = project / "pyproject.toml"
        reports = checker_context.reports_dir
        gate = FlextInfraPyreflyGate(project)
        first = gate.check(project, checker_context)
        assert first.result.passed, first
        native_reports = tuple(reports.glob("*-pyrefly.json"))
        assert len(native_reports) == 1
        assert not m.Infra.PyreflyReport.model_validate_json(
            native_reports[0].read_text(encoding="utf-8"),
            strict=True,
        ).errors
        pyproject.write_text("[tool.pyrefly\n", encoding="utf-8")
        failed = gate.check(project, checker_context)
        assert failed.result.passed is False
        assert failed.raw_output
        # The gate's declared report path is replaced per run: the passing
        # run's report is removed before the failing run, never reused.
        assert not native_reports[0].exists()

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize(
        "gate_class",
        [FlextInfraMypyGate, FlextInfraPyrightGate, FlextInfraPyreflyGate],
    )
    def test_explicit_files_keep_selected_scope(
        checker_context: m.Infra.GateContext,
        gate_class: type[FlextInfraGate],
    ) -> None:
        """Test explicit files keep selected scope."""
        project = checker_context.repository_root
        package = project / "src" / "test_pkg"
        unselected = package / "unselected.py"
        unselected.write_text('value: int = "incorrect"\n', encoding="utf-8")
        gate = gate_class(project)
        result = gate.check_files([package / "identity.py"], project, checker_context)
        assert result.result.passed, result
        assert not result.issues

        selected_error = gate.check_files([unselected], project, checker_context)
        assert selected_error.result.passed is False, selected_error
        assert any(
            issue.file.endswith(unselected.name) for issue in selected_error.issues
        )

        full_project = gate.check(project, checker_context)
        assert full_project.result.passed is False, full_project
        assert any(
            issue.file.endswith(unselected.name) for issue in full_project.issues
        )

    @staticmethod
    @pytest.mark.parametrize(
        "gate_class",
        [FlextInfraMypyGate, FlextInfraPyrightGate, FlextInfraPyreflyGate],
    )
    def test_empty_source_is_not_passed(
        tmp_path: Path,
        gate_class: type[FlextInfraGate],
    ) -> None:
        """A checker invoked without inputs never reads as a clean pass."""
        result = gate_class(tmp_path).check(
            tmp_path,
            m.Infra.GateContext(repository_root=tmp_path, reports_dir=tmp_path),
        )
        assert result.result.passed is False
        # An empty source must never read as a clean pass: the skipped state
        # stays visible in the execution errors for every gate posture.
        assert result.result.errors

    @staticmethod
    @pytest.mark.parametrize(
        "gate_class",
        [FlextInfraPyrightGate, FlextInfraPyreflyGate],
    )
    def test_python_analysis_gates_follow_detected_content(
        tmp_path: Path,
        real_python_package: Path,
        gate_class: type[FlextInfraGate],
    ) -> None:
        """Detected Python content, not a pass receipt, selects the type gates."""
        tm.that(gate_class(tmp_path).selected_for(tmp_path), eq=False)
        tm.that(
            gate_class(real_python_package).selected_for(real_python_package),
            eq=True,
        )

    @staticmethod
    @pytest.mark.parametrize("payload", ["", " ", "not JSON", "{}", "[]", "null"])
    @pytest.mark.parametrize(
        "report_model",
        [m.Infra.MypyDiagnostic, m.Infra.PyrightReport, m.Infra.PyreflyReport],
    )
    def test_invalid_native_report(
        report_model: type[
            m.Infra.MypyDiagnostic | m.Infra.PyrightReport | m.Infra.PyreflyReport
        ],
        payload: str,
    ) -> None:
        """Test invalid native report."""
        with pytest.raises(c.ValidationError):
            report_model.model_validate_json(payload, strict=True)

    @staticmethod
    def test_pyright_incomplete_counts() -> None:
        """Test pyright incomplete counts."""
        payload = (
            '{"version":"1.1.411","time":"1","generalDiagnostics":[], '
            '"summary":{"filesAnalyzed":1,"errorCount":0,"warningCount":1,'
            '"informationCount":0,"timeInSec":0.1}}'
        )
        with pytest.raises(c.ValidationError, match="warning count"):
            m.Infra.PyrightReport.model_validate_json(payload, strict=True)

    @staticmethod
    def test_pyrefly_empty_native_report() -> None:
        """Test pyrefly empty native report."""
        report = m.Infra.PyreflyReport.model_validate_json('{"errors":[]}', strict=True)
        assert not report.errors

    @staticmethod
    def test_pyright_information_without_location() -> None:
        """Test pyright information without location."""
        report = m.Infra.PyrightReport.model_validate_json(
            '{"version":"1.1.411","time":"1","generalDiagnostics":['
            '{"file":"source.py","severity":"information","message":"type info"}],'
            '"summary":{"filesAnalyzed":1,"errorCount":0,"warningCount":0,'
            '"informationCount":1,"timeInSec":0.1}}',
            strict=True,
        )
        assert report.general_diagnostics[0].range is None
        assert report.summary.information_count == 1

    @staticmethod
    def test_pyright_zero_collection() -> None:
        """filesAnalyzed=0 parses; the gate, not the model, judges it."""
        report = m.Infra.PyrightReport.model_validate_json(
            '{"version":"1.1.411","time":"1","generalDiagnostics":[], '
            '"summary":{"filesAnalyzed":0,"errorCount":0,"warningCount":0,'
            '"informationCount":0,"timeInSec":0.1}}',
            strict=True,
        )
        assert report.summary.files_analyzed == 0
        assert not report.general_diagnostics

    @staticmethod
    def test_checker_does_not_run_type_gates_on_content_only_project(
        real_python_package: Path,
    ) -> None:
        """A project without Python targets gets no type-gate row at all."""
        for module in (real_python_package / "src").rglob("*.py"):
            module.unlink()
        reports = real_python_package / ".reports"

        results = tm.ok(
            FlextInfraWorkspaceChecker(
                repository_root=real_python_package.parent,
            ).run_projects(
                [real_python_package.name],
                [FlextInfraPyrightGate.gate_id, FlextInfraPyreflyGate.gate_id],
                reports_dir=reports,
            ),
        )

        tm.that(results[0].gates, empty=True)
        (report_path,) = reports.glob(f"*/{c.Infra.CHECK_REPORT_MARKDOWN_FILENAME}")
        markdown = report_path.read_text(
            encoding="utf-8",
        )
        tm.that(markdown, lacks=f"- {FlextInfraPyrightGate.gate_id}:")
        tm.that(markdown, lacks=f"- {FlextInfraPyreflyGate.gate_id}:")
