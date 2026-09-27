"""Public checker acceptance against real tools and native report schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, m
from flext_infra.gates.mypy import FlextInfraMypyGate
from flext_infra.gates.pyrefly import FlextInfraPyreflyGate
from flext_infra.gates.pyright import FlextInfraPyrightGate

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra.gates.base_gate import FlextInfraGate


class TestsFlextInfraTypeGates:
    """The selected project's actual findings determine acceptance."""

    @pytest.fixture
    def checker_context(self, real_python_package: Path) -> m.Infra.GateContext:
        """Configure the existing real package for native checker execution."""
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
            repository_root=real_python_package, reports_dir=reports
        )

    @pytest.mark.slow
    def test_mypy_preserves_protocol_member_diagnostics(
        self, checker_context: m.Infra.GateContext
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

    @pytest.mark.slow
    def test_mypy_preserves_malformed_native_output(
        self, checker_context: m.Infra.GateContext
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
                "[tool.mypy]\n", '[tool.mypy]\nplugins = ["plugin.py"]\n'
            ),
            encoding="utf-8",
        )

        result = FlextInfraMypyGate(project).check(project, checker_context)

        tm.that(result.result.passed, eq=False)
        tm.that(tuple(issue.code for issue in result.issues), has="TOOL_ERROR")
        tm.that(
            "\n".join(issue.message for issue in result.issues),
            has="native-plugin-output",
        )

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "gate_class", [FlextInfraMypyGate, FlextInfraPyrightGate, FlextInfraPyreflyGate]
    )
    def test_real_check_and_repair(
        self, checker_context: m.Infra.GateContext, gate_class: type[FlextInfraGate]
    ) -> None:
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

        if gate_class is FlextInfraMypyGate:
            native_reports = tuple(reports.rglob("coverage.json"))
            assert len(native_reports) == 1
            inventory = m.Infra.MypyCoverageReport.model_validate_json(
                native_reports[0].read_text(encoding="utf-8"), strict=True
            )
            assert set(inventory.lines) == {
                str(path.resolve()) for path in (project / "src").rglob("*.py")
            }

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
        self,
        real_python_package: Path,
        gate_class: type[FlextInfraGate],
        config_text: str,
    ) -> None:
        project = real_python_package
        pyproject = project / "pyproject.toml"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8") + "\n" + config_text, encoding="utf-8"
        )
        (project / "src" / "test_pkg" / "warning.py").write_text(
            'value: int = "incorrect"\n', encoding="utf-8"
        )
        reports = project / ".reports"
        reports.mkdir()
        result = gate_class(project).check(
            project, m.Infra.GateContext(repository_root=project, reports_dir=reports)
        )
        assert result.result.passed is False
        assert any(issue.severity in {"warn", "warning"} for issue in result.issues)

    @pytest.mark.slow
    def test_failed_pyrefly_cannot_reuse_previous_report(
        self, checker_context: m.Infra.GateContext
    ) -> None:
        project = checker_context.repository_root
        pyproject = project / "pyproject.toml"
        reports = checker_context.reports_dir
        gate = FlextInfraPyreflyGate(project)
        first = gate.check(project, checker_context)
        assert first.result.passed, first
        native_reports = tuple(reports.glob("*-pyrefly.json"))
        assert len(native_reports) == 1
        assert not m.Infra.PyreflyReport.model_validate_json(
            native_reports[0].read_text(encoding="utf-8"), strict=True
        ).errors
        pyproject.write_text("[tool.pyrefly\n", encoding="utf-8")
        failed = gate.check(project, checker_context)
        assert failed.result.passed is False
        assert failed.raw_output

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "gate_class", [FlextInfraMypyGate, FlextInfraPyrightGate, FlextInfraPyreflyGate]
    )
    def test_explicit_files_keep_selected_scope(
        self, checker_context: m.Infra.GateContext, gate_class: type[FlextInfraGate]
    ) -> None:
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

    @pytest.mark.parametrize(
        "gate_class", [FlextInfraMypyGate, FlextInfraPyrightGate, FlextInfraPyreflyGate]
    )
    def test_empty_source_is_not_passed(
        self, tmp_path: Path, gate_class: type[FlextInfraGate]
    ) -> None:
        result = gate_class(tmp_path).check(
            tmp_path,
            m.Infra.GateContext(repository_root=tmp_path, reports_dir=tmp_path),
        )
        assert result.result.passed is False
        # An empty source must never read as a clean pass: the skipped state
        # stays visible in the execution errors for every gate posture.
        assert result.result.errors

    @pytest.mark.parametrize("payload", ["", " ", "not JSON", "{}", "[]", "null"])
    @pytest.mark.parametrize(
        "report_model",
        [m.Infra.MypyDiagnostic, m.Infra.PyrightReport, m.Infra.PyreflyReport],
    )
    def test_invalid_native_report(
        self,
        report_model: type[
            m.Infra.MypyDiagnostic | m.Infra.PyrightReport | m.Infra.PyreflyReport
        ],
        payload: str,
    ) -> None:
        with pytest.raises(c.ValidationError):
            report_model.model_validate_json(payload, strict=True)

    def test_pyright_incomplete_counts(self) -> None:
        payload = (
            '{"version":"1.1.411","time":"1","generalDiagnostics":[], '
            '"summary":{"filesAnalyzed":1,"errorCount":0,"warningCount":1,'
            '"informationCount":0,"timeInSec":0.1}}'
        )
        with pytest.raises(c.ValidationError, match="warning count"):
            m.Infra.PyrightReport.model_validate_json(payload, strict=True)

    def test_pyrefly_empty_native_report(self) -> None:
        report = m.Infra.PyreflyReport.model_validate_json('{"errors":[]}', strict=True)
        assert not report.errors

    def test_pyright_information_without_location(self) -> None:
        report = m.Infra.PyrightReport.model_validate_json(
            '{"version":"1.1.411","time":"1","generalDiagnostics":['
            '{"file":"source.py","severity":"information","message":"type info"}],'
            '"summary":{"filesAnalyzed":1,"errorCount":0,"warningCount":0,'
            '"informationCount":1,"timeInSec":0.1}}',
            strict=True,
        )
        assert report.general_diagnostics[0].range is None
        assert report.summary.information_count == 1

    def test_pyright_zero_collection(self) -> None:
        with pytest.raises(c.ValidationError):
            m.Infra.PyrightReport.model_validate_json(
                '{"version":"1.1.411","time":"1","generalDiagnostics":[], '
                '"summary":{"filesAnalyzed":0,"errorCount":0,"warningCount":0,'
                '"informationCount":0,"timeInSec":0.1}}',
                strict=True,
            )

    @pytest.mark.parametrize(
        "payload", ['{"lines":{}}', '{"lines":{"relative.py":[1]}}', "{}"]
    )
    def test_mypy_requires_native_source_evidence(self, payload: str) -> None:
        with pytest.raises(c.ValidationError):
            m.Infra.MypyCoverageReport.model_validate_json(payload, strict=True)


__all__: list[str] = ["TestsFlextInfraTypeGates"]
