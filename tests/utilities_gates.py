"""Quality-gate and enforcement fixture test utilities for flext-infra."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.deps.fix_pyrefly_config import FlextInfraConfigFixer
from flext_infra.fixers.rope_fixer import FlextInfraRopeFixerAdapter
from flext_infra.refactor.census import FlextInfraRefactorCensus
from tests import m, t

if TYPE_CHECKING:
    from flext_infra.gates.base_gate import FlextInfraGate


class TestsFlextInfraUtilitiesGatesMixin:
    """Typed quality-gate execution and enforcement fixture helpers."""

    @staticmethod
    def run_rope_fixer(
        tmp_path: Path,
        project_dir: Path,
        rule: m.EnforcementRuleSpec,
        file_path: Path,
        *,
        apply: bool,
    ) -> m.Infra.ProjectFixResult:
        """Run one rope fixer adapter pass over a single reported file."""
        adapter = FlextInfraRopeFixerAdapter(tmp_path)
        ctx = m.Infra.FixEnforcementCommand(
            repository_root=tmp_path, projects=("demo",), apply=apply
        )
        return adapter.fix_project(
            project_dir, ((rule, SimpleNamespace(file_path=str(file_path))),), ctx
        )

    @staticmethod
    def detector_context(
        target: Path,
        source: str,
        rope_project: t.Infra.RopeProject,
        *,
        project_name: str = "",
    ) -> m.Infra.DetectorContext:
        """Write one fixture module and build the context detectors scan.

        Every detector declares its own violation type, so the shared owner
        stops at the context: the caller keeps its own ``detect_file`` call
        and therefore its precise return type.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        return m.Infra.DetectorContext(
            file_path=target, rope_project=rope_project, project_name=project_name
        )

    @staticmethod
    def reject_inaccessible_config_project(tmp_path: Path) -> None:
        """Run the config fixer on an inaccessible project, proving the failure."""
        fixer = FlextInfraConfigFixer(repository_root=tmp_path)
        result = fixer.run(["nonexistent"])

        tm.fail(result)
        tm.that(result.error, has="explicit project path is not accessible")

    @staticmethod
    def gate_context(root: Path) -> m.Infra.GateContext:
        """Build the standard check-mode gate context for one root."""
        return m.Infra.GateContext(repository_root=root, reports_dir=root)

    @staticmethod
    def check_gate_asserting(
        gate_class: type[FlextInfraGate],
        tmp_path: Path,
        project_dir: Path,
        *,
        passed: bool,
        issues_len: int,
    ) -> m.Infra.GateExecution:
        """Check one gate once, asserting its pass state and issue count."""
        gate = gate_class(tmp_path)
        result = gate.check(
            project_dir, TestsFlextInfraUtilitiesGatesMixin.gate_context(tmp_path)
        )
        tm.that(result.result.passed, eq=passed)
        tm.that(len(result.issues), eq=issues_len)
        return result

    @staticmethod
    def create_gate_execution(
        gate: str = "lint",
        project: str = "p",
        *,
        passed: bool = True,
        issues: t.SequenceOf[m.Infra.Issue] | None = None,
    ) -> m.Infra.GateExecution:
        """Create a typed quality-gate execution fixture."""
        return m.Infra.GateExecution(
            result=m.Infra.GateResult(
                gate=gate, project=project, passed=passed, errors=(), duration=0.0
            ),
            issues=tuple(issues or ()),
            raw_output="",
        )

    @staticmethod
    def make_issue(
        *,
        file: str = "a.py",
        line: int = 1,
        column: int = 1,
        code: str = "E1",
        message: str = "Error",
    ) -> m.Infra.Issue:
        """Create a typed quality issue fixture."""
        return m.Infra.Issue(
            file=file,
            line=line,
            column=column,
            code=code,
            message=message,
            severity="error",
        )

    @staticmethod
    def make_project(
        name: str = "p", gates: t.MappingKV[str, m.Infra.GateExecution] | None = None
    ) -> m.Infra.ProjectResult:
        """Create a typed project-result fixture."""
        resolved_gates: t.MappingKV[str, m.Infra.GateExecution] = (
            gates
            if gates is not None
            else {"lint": TestsFlextInfraUtilitiesGatesMixin.create_gate_execution()}
        )
        result: m.Infra.ProjectResult = m.Infra.ProjectResult.model_validate({
            "project": name,
            "gates": resolved_gates,
        })
        return result

    @staticmethod
    def create_gate_context(
        repository_root: Path, *, reports_dir: Path | None = None
    ) -> m.Infra.GateContext:
        """Provide the typed test helper `create_gate_context`."""
        return m.Infra.GateContext(
            repository_root=repository_root, reports_dir=reports_dir or repository_root
        )

    @staticmethod
    def run_gate_check(
        gate_class: type[FlextInfraGate],
        repository_root: Path,
        project_dir: Path,
        *,
        ctx: m.Infra.GateContext | None = None,
        reports_dir: Path | None = None,
    ) -> m.Infra.GateExecution:
        """Provide the typed test helper `run_gate_check`."""
        gate = gate_class(repository_root)
        return gate.check(
            project_dir,
            ctx
            or TestsFlextInfraUtilitiesGatesMixin.create_gate_context(
                repository_root, reports_dir=reports_dir
            ),
        )

    @staticmethod
    def census_report(
        workspace: Path,
        *,
        rules: t.StrSequence,
        kinds: t.StrSequence | None = None,
        include_local_scopes: bool = False,
        impact_map_output: str | None = None,
        apply_changes: bool = False,
        dry_run: bool = False,
    ) -> m.Infra.WorkspaceReport:
        """Execute one refactor census and unwrap its successful report."""
        result = FlextInfraRefactorCensus(
            repository_root=workspace,
            apply_changes=apply_changes,
            dry_run=dry_run,
            impact_map_output=impact_map_output,
            include_local_scopes=include_local_scopes,
            kinds=kinds,
            rules=rules,
        ).execute()
        tm.ok(result)
        report: m.Infra.WorkspaceReport = result.unwrap()
        return report

    @staticmethod
    def census_violations(report: m.Infra.WorkspaceReport) -> list[m.Infra.Violation]:
        """Flatten every per-project violation of one census report."""
        return [
            violation for project in report.projects for violation in project.violations
        ]


__all__: list[str] = ["TestsFlextInfraUtilitiesGatesMixin"]
