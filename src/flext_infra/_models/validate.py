"""Domain models for the core subpackage."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m, u

from .. import c, t
from . import FlextInfraModelsMixins as mm
from ._defaults import FlextInfraModelsDefaults


def _default_fresh_import_entry_points() -> FlextInfraModelsCore.FreshImportEntryPoints:
    """Default factory for the fresh-import entry-points payload.

    Module-level on purpose: neither a qualified nor a bare reference to the
    nested model resolves inside the class body at definition time (class
    scopes do not nest, and the outer class is still being defined), so the
    deferred lookup must live outside it.
    """
    return FlextInfraModelsCore.FreshImportEntryPoints()


class FlextInfraModelsCore:
    """Models for core infrastructure services (subprocess, validation).

    Canonical base policy:
    - ``ArbitraryTypesModel`` for mutable report/result payloads.
    - ``ContractModel`` reserved for immutable settings/settings contracts.
    """

    class ValidationReport(m.ArbitraryTypesModel):
        """Validation report model with violations and summary."""

        passed: Annotated[bool, m.Field(description="Validation status")]
        violations: Annotated[
            t.StrSequence, m.Field(description="Collected validation violations")
        ] = m.Field(default_factory=tuple)
        summary: Annotated[
            str, m.Field(description="Human-readable validation summary")
        ] = ""

    class FreshImportProbe(m.Value):
        """One complete child-process verification program and its subject."""

        subject: str = m.Field(description="Public contract verified by this process")
        code: str = m.Field(description="Python program rendered from typed contracts")

    class FreshImportEntryPoints(m.Value):
        """The standardized executable metadata consumed by importlib."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore")

        scripts: t.StrMapping = m.Field(
            default_factory=FlextInfraModelsDefaults.ImmutableEmptyMapping,
            description="Declared console entrypoints",
        )
        gui_scripts: t.StrMapping = m.Field(
            default_factory=FlextInfraModelsDefaults.ImmutableEmptyMapping,
            alias="gui-scripts",
            description="Declared graphical entrypoints",
        )
        entry_points: t.MappingKV[str, t.StrMapping] = m.Field(
            default_factory=FlextInfraModelsDefaults.ImmutableEmptyMapping,
            alias="entry-points",
            description="Declared plugin entrypoint groups",
        )

    class FreshImportMetadata(m.Value):
        """Typed entrypoint view of the published pyproject document."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore")

        project: FlextInfraModelsCore.FreshImportEntryPoints = m.Field(
            default_factory=_default_fresh_import_entry_points,
            description="Executable metadata from the published project table",
        )

    class SkillRuleEvaluationContext(m.ArbitraryTypesModel):
        """Resolved inputs for one skill rule evaluation pass."""

        rules_list: Annotated[t.JsonList, m.Field(description="Rules to evaluate")]
        skill_dir: Annotated[Path, m.Field(description="Skill directory path")]
        root: Annotated[Path, m.Field(description="Repository root path")]
        mode: Annotated[
            c.Infra.OperationMode, m.Field(description="Skill validation mode")
        ]
        include_globs: Annotated[t.StrSequence, m.Field(description="Include globs")]
        exclude_globs: Annotated[t.StrSequence, m.Field(description="Exclude globs")]

    class SkillReportContext(m.ArbitraryTypesModel):
        """Resolved inputs for one skill validation report."""

        rules: Annotated[
            t.MappingKV[str, t.JsonValue], m.Field(description="Rules payload")
        ]
        root: Annotated[Path, m.Field(description="Repository root path")]
        skill_name: Annotated[str, m.Field(description="Skill folder name")]
        mode: Annotated[
            c.Infra.OperationMode, m.Field(description="Skill validation mode")
        ]
        counts: Annotated[t.IntMapping, m.Field(description="Violation counts")]
        violations: Annotated[t.StrSequence, m.Field(description="Violations")]

    class StubAnalysisReport(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Structured typed-dependency analysis result for a project."""

        mypy_hints: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Install-package hints extracted from mypy output"),
        ] = m.Field(default_factory=list)
        internal_missing: Annotated[
            t.MutableSequenceOf[str], m.Field(description="Missing internal imports")
        ] = m.Field(default_factory=list)
        unresolved_missing: Annotated[
            t.MutableSequenceOf[str],
            m.Field(
                description="Missing external imports without an installed typed dependency"
            ),
        ] = m.Field(default_factory=list)
        total_missing: Annotated[
            t.NonNegativeInt, m.Field(description="Total missing imports")
        ]

    class PytestCollectionManifest(m.Value):
        """The selected node IDs after every collection hook has completed."""

        node_ids: t.StrTuple = m.Field(description="Unique node IDs in execution order")

        @u.model_validator(mode="after")
        def require_unique_node_ids(self) -> Self:
            """Reject incomplete identifiers and ambiguous worker manifests."""
            if any(not node_id for node_id in self.node_ids) or len(
                self.node_ids
            ) != len(set(self.node_ids)):
                msg = "collection manifest requires nonempty unique node IDs"
                raise ValueError(msg)
            return self

    class PytestRunContext(m.Value):
        """Immutable execution identity shared by a phase's native receipts."""

        execution_mode: c.Infra.PytestExecutionMode = m.Field(
            description="Canonical test operation for this report directory"
        )
        testmon_db: Path | None = m.Field(
            description="Persistent external testmon database; absent for coverage"
        )
        deadline_monotonic: float = m.Field(
            gt=0, description="Shared absolute deadline across all execution phases"
        )

    class PytestReportEvent(m.Value):
        """Common report-log envelope and the complete warning payload."""

        # Report-log event kinds carry different plugin-owned payload fields.
        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", strict=True)

        report_type: Annotated[
            str, m.Field(alias="$report_type", description="Pytest event kind")
        ]
        category: Annotated[
            str | None, m.Field(description="Warning category name")
        ] = None
        filename: Annotated[
            str | None, m.Field(description="Warning source filename")
        ] = None
        lineno: Annotated[
            int | None, m.Field(ge=0, description="Warning source line")
        ] = None
        message: Annotated[
            str | None, m.Field(description="Complete warning message")
        ] = None
        nodeid: str | None = m.Field(default=None, description="TestReport node ID")
        when: str | None = m.Field(default=None, description="Pytest lifecycle phase")
        outcome: Literal["passed", "failed", "skipped"] | None = m.Field(
            default=None, description="TestReport outcome"
        )

        @u.model_validator(mode="after")
        def require_event_payload(self) -> Self:
            """Reject incomplete runtime events instead of reporting zero findings."""
            if self.report_type == "WarningMessage" and any(
                value is None
                for value in (self.category, self.filename, self.lineno, self.message)
            ):
                msg = "WarningMessage requires category, filename, lineno and message"
                raise ValueError(msg)
            if self.report_type == "TestReport" and (
                not self.nodeid
                or self.when not in {"setup", "call", "teardown"}
                or self.outcome is None
            ):
                msg = "TestReport requires nodeid, a runtest phase and outcome"
                raise ValueError(msg)
            if self.report_type == "CollectReport" and (
                self.nodeid is None or self.outcome is None
            ):
                msg = "CollectReport requires nodeid and outcome"
                raise ValueError(msg)
            return self

    class PytestWarningEvent(m.Value):
        """Warning identity and enforcement decision captured before report-log."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(strict=True)

        category: str = m.Field(description="Runtime warning class name")
        category_module: str = m.Field(description="Declaring warning module")
        category_qualname: str = m.Field(description="Qualified runtime class name")
        filename: str = m.Field(description="Warning source filename")
        lineno: int = m.Field(ge=0, description="Warning source line")
        message: str = m.Field(description="Complete warning message")
        enforcement_strict: bool = m.Field(description="Resolved enforcement mode")
        suspended: bool = m.Field(description="Runtime enforcement policy decision")

    class PytestDiagnostics(m.ArbitraryTypesModel):
        """Extracted diagnostics summary from JUnit XML and pytest report-log."""

        failed_count: Annotated[
            t.NonNegativeInt, m.Field(description="Failed test case count")
        ]
        error_count: Annotated[
            t.NonNegativeInt, m.Field(description="Errored test case count")
        ]
        warning_count: Annotated[
            t.NonNegativeInt, m.Field(description="Recorded warning event count")
        ]
        blocking_warning_count: Annotated[
            t.NonNegativeInt, m.Field(description="Warnings outside suspended policy")
        ]
        suspended_warning_count: Annotated[
            t.NonNegativeInt, m.Field(description="Warnings retained under suspension")
        ]
        skipped_count: Annotated[
            t.NonNegativeInt, m.Field(description="Skipped test case count")
        ]
        collection_failed_count: t.NonNegativeInt = m.Field(
            description="Failed collection reports, separate from JUnit cases"
        )
        collection_skipped_count: t.NonNegativeInt = m.Field(
            description="Skipped collection reports, separate from JUnit cases"
        )
        collection_failed_cases: t.StrTuple = m.Field(
            default_factory=tuple, description="Node IDs with failed collection reports"
        )
        collection_skip_cases: t.StrTuple = m.Field(
            default_factory=tuple,
            description="Node IDs with skipped collection reports",
        )
        reported_node_ids: t.StrTuple = m.Field(
            default_factory=tuple,
            description="Unique node IDs with real TestReport events",
        )
        failed_cases: Annotated[
            t.StrSequence, m.Field(description="Failed test labels")
        ] = m.Field(default_factory=tuple)
        error_traces: Annotated[
            t.StrSequence, m.Field(description="Collected error traces")
        ] = m.Field(default_factory=tuple)
        warning_lines: Annotated[
            t.StrSequence, m.Field(description="Captured warning lines")
        ] = m.Field(default_factory=tuple)
        suspended_warning_lines: Annotated[
            t.StrSequence, m.Field(description="Visible suspended warning occurrences")
        ] = m.Field(default_factory=tuple)
        skip_cases: Annotated[
            t.StrSequence, m.Field(description="Skipped test labels")
        ] = m.Field(default_factory=tuple)
        slow_entries: Annotated[
            t.StrSequence, m.Field(description="Slow test entries")
        ] = m.Field(default_factory=tuple)

    class DiagResult(m.ArbitraryTypesModel):
        """Internal container for extracted diagnostics.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        reported_node_ids: t.MutableSequenceOf[str] = m.Field(
            default_factory=list, description="Node IDs from each real TestReport"
        )
        collection_failed_cases: t.MutableSequenceOf[str] = m.Field(
            default_factory=list, description="Node IDs with failed collection reports"
        )
        collection_skip_cases: t.MutableSequenceOf[str] = m.Field(
            default_factory=list, description="Node IDs with skipped collection reports"
        )

        failed_cases: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Collected failed test-case labels"),
        ] = m.Field(default_factory=list)
        error_cases: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Collected error test-case labels"),
        ] = m.Field(default_factory=list)
        error_traces: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Collected error trace chunks"),
        ] = m.Field(default_factory=list)
        skip_cases: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Collected skipped test-case labels"),
        ] = m.Field(default_factory=list)
        warning_lines: Annotated[
            t.MutableSequenceOf[str], m.Field(description="Collected warning lines")
        ] = m.Field(default_factory=list)
        suspended_warning_lines: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Collected suspended warning occurrences"),
        ] = m.Field(default_factory=list)
        slow_entries: Annotated[
            t.MutableSequenceOf[str], m.Field(description="Collected slow-test entries")
        ] = m.Field(default_factory=list)

    class InventoryReport(m.ArbitraryTypesModel):
        """Summary of written inventory report artifacts."""

        total_scripts: Annotated[
            t.NonNegativeInt, m.Field(description="Total discovered scripts")
        ]
        reports_written: Annotated[
            t.MutableSequenceOf[str], m.Field(description="Written report file paths")
        ] = m.Field(default_factory=list)

    class GateContractViolation(m.Value):
        """One gate-script contract violation."""

        # Why: leaf validate contract owned by m.Infra (collision-safe vs census Violation).
        script: Annotated[str, m.Field(description="Script path")]
        check: Annotated[str, m.Field(description="Failed check")]
        message: Annotated[str, m.Field(description="Violation message")]
        severity: Annotated[str, m.Field(description="Severity")] = (
            c.Infra.GateSeverity.ERROR.value
        )

    class GateContractScriptInfo(m.Value):
        """Validation result for one gate script."""

        path: Annotated[str, m.Field(description="Script path")]
        extension: Annotated[str, m.Field(description="File extension")]
        role: Annotated[str, m.Field(description="Script role")]
        violations: Annotated[
            t.VariadicTuple[FlextInfraModelsCore.GateContractViolation],
            m.Field(description="Violations"),
        ] = ()

    class GateContractSummary(m.Value):
        """Aggregate gate-contract counts."""

        errors: Annotated[int, m.Field(description="Error count")] = 0
        gate_scripts: Annotated[int, m.Field(description="Gate script count")] = 0
        ok: Annotated[int, m.Field(description="Passing gate script count")] = 0
        warnings: Annotated[int, m.Field(description="Warning count")] = 0

    class GateContractRunResult(m.Value):
        """CLI outcome for one gate-contract validation run."""

        exit_code: Annotated[int, m.Field(description="Process exit code")]
        violation_count: Annotated[int, m.Field(description="Error count")]

    class NamespaceValidateCommand(mm.ReadMixin, m.ContractModel):
        """CLI payload for ``flext-infra validate namespace``.

        Read-only namespace rule scan (NS-000..003) across selected projects.
        """

        scan_tests: Annotated[
            bool,
            m.Field(
                alias="scan-tests",
                description="Include test packages in the namespace scan",
            ),
        ] = False


__all__: list[str] = ["FlextInfraModelsCore"]
