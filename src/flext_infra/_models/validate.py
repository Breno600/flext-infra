"""Domain models for the core subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self

from flext_cli import m

from flext_infra import c, t
from flext_infra._models import FlextInfraModelsMixins


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
            t.StrSequence,
            m.Field(description="Collected validation violations"),
        ] = m.Field(default_factory=tuple)
        summary: Annotated[
            str,
            m.Field(description="Human-readable validation summary"),
        ] = ""

    class FreshImportProbe(m.Value):
        """One complete child-process verification program and its subject."""

        subject: str = m.Field(description="Public contract verified by this process")
        code: str = m.Field(description="Python program rendered from typed contracts")

    class FreshImportEntryPoints(m.Value):
        """The standardized executable metadata consumed by importlib."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore")

        scripts: t.StrMapping | None = m.Field(
            default=None,
            description="Declared console entrypoints when present",
        )
        gui_scripts: t.StrMapping | None = m.Field(
            default=None,
            alias="gui-scripts",
            description="Declared graphical entrypoints when present",
        )
        entry_points: t.MappingKV[str, t.StrMapping] | None = m.Field(
            default=None,
            alias="entry-points",
            description="Declared plugin entrypoint groups when present",
        )

    class FreshImportMetadata(m.Value):
        """Typed entrypoint view of the published pyproject document."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore")

        project: FlextInfraModelsCore.FreshImportEntryPoints = m.Field(
            description="Executable metadata from the published project table",
        )

    class SkillRuleEvaluationContext(m.ArbitraryTypesModel):
        """Resolved inputs for one skill rule evaluation pass."""

        rules_list: Annotated[t.JsonList, m.Field(description="Rules to evaluate")]
        skill_dir: Annotated[Path, m.Field(description="Skill directory path")]
        root: Annotated[Path, m.Field(description="Repository root path")]
        mode: Annotated[
            c.Infra.OperationMode,
            m.Field(description="Skill validation mode"),
        ]
        include_globs: Annotated[t.StrSequence, m.Field(description="Include globs")]
        exclude_globs: Annotated[t.StrSequence, m.Field(description="Exclude globs")]

    class SkillReportContext(m.ArbitraryTypesModel):
        """Resolved inputs for one skill validation report."""

        rules: Annotated[
            t.MappingKV[str, t.JsonValue],
            m.Field(description="Rules payload"),
        ]
        root: Annotated[Path, m.Field(description="Repository root path")]
        skill_name: Annotated[str, m.Field(description="Skill folder name")]
        mode: Annotated[
            c.Infra.OperationMode,
            m.Field(description="Skill validation mode"),
        ]
        counts: Annotated[t.IntMapping, m.Field(description="Violation counts")]
        violations: Annotated[t.StrSequence, m.Field(description="Violations")]

    class StubAnalysisReport(
        FlextInfraModelsMixins.ProjectNameMixin,
        m.ArbitraryTypesModel,
    ):
        """Structured typed-dependency analysis result for a project."""

        mypy_hints: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Install-package hints extracted from mypy output"),
        ] = m.Field(default_factory=list)
        internal_missing: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Missing internal imports"),
        ] = m.Field(default_factory=list)
        unresolved_missing: Annotated[
            t.MutableSequenceOf[str],
            m.Field(
                description=(
                    "Missing external imports without an installed typed dependency"
                ),
            ),
        ] = m.Field(default_factory=list)
        total_missing: Annotated[
            t.NonNegativeInt,
            m.Field(description="Total missing imports"),
        ]

    class PytestMarkdownOrigin(m.Value):
        """Plugin-defined fence identity independent of rendered test names."""

        source_path: str = m.Field(description="Repository-relative source identity")
        start_line: int = m.Field(ge=0, description="Plugin first-code-line offset")
        source_sha256: str = m.Field(
            pattern=r"^[0-9a-f]{64}$",
            description="Digest of the exact plugin-defined executable source",
        )
        max_retries: int = m.Field(ge=0, description="Plugin-declared retry policy")

    class PytestMarkdownItem(m.Value):
        """Actual collected node bound to its definition, not its display name."""

        node_id: t.NonEmptyStr = m.Field(description="Actual collected pytest node ID")
        origin: FlextInfraModelsCore.PytestMarkdownOrigin = m.Field(
            description="Definition supplied by the installed Markdown collector",
        )

    class PytestMarkdownCollection(m.ArbitraryTypesModel):
        """Session-owned public collection-hook observations."""

        eligible: t.MutableSequenceOf[FlextInfraModelsCore.PytestMarkdownOrigin] = (
            m.Field(default_factory=list, description="Independently parsed origins")
        )
        collected: t.MutableSequenceOf[FlextInfraModelsCore.PytestMarkdownItem] = (
            m.Field(default_factory=list, description="Observed pre-selection items")
        )
        deselected: t.MutableSequenceOf[str] = m.Field(
            default_factory=list,
            description="Public pytest deselection notifications",
        )

    class PytestMarkdownAttempt(m.Value):
        """Native runner-entry count and the first escaping exception evidence."""

        node_id: t.NonEmptyStr = m.Field(description="Actual executed Markdown node")
        attempts: int = m.Field(ge=0, description="Observed native runner entries")
        first_exception_type: str | None = m.Field(
            default=None,
            description="First exception escaping the SDK runner",
        )
        first_exception_traceback: str | None = m.Field(
            default=None,
            description="Original first exception traceback",
        )

    class PytestCollectionManifest(m.Value):
        """The selected node IDs after every collection hook has completed."""

        node_ids: t.StrTuple = m.Field(description="Unique node IDs in execution order")
        markdown_eligible: t.VariadicTuple[
            FlextInfraModelsCore.PytestMarkdownOrigin
        ] = m.Field(default_factory=tuple, description="Independent plugin eligibility")
        markdown_collected: t.VariadicTuple[FlextInfraModelsCore.PytestMarkdownItem] = (
            m.Field(default_factory=tuple, description="Collection before deselection")
        )
        markdown_deselected: t.StrTuple = m.Field(
            default_factory=tuple,
            description="Explicit Markdown deselection node IDs",
        )

        @m.model_validator(mode="after")
        def require_unique_node_ids(self) -> Self:
            """Reject incomplete identifiers and ambiguous worker manifests.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If collection manifest requires nonempty unique node IDs.

            """
            if any(not node_id for node_id in self.node_ids) or len(
                self.node_ids,
            ) != len(set(self.node_ids)):
                msg = "collection manifest requires nonempty unique node IDs"
                raise ValueError(msg)
            origins = tuple(item.origin for item in self.markdown_collected)
            collected_ids = tuple(item.node_id for item in self.markdown_collected)
            if (
                len(set(self.markdown_eligible)) != len(self.markdown_eligible)
                or len(set(origins)) != len(origins)
                or len(set(collected_ids)) != len(collected_ids)
            ):
                msg = "duplicate Markdown eligible origin or collected identity"
                raise ValueError(msg)
            if set(origins) != set(self.markdown_eligible):
                msg = "Markdown eligible origins differ from collected definitions"
                raise ValueError(msg)
            if (
                len(set(self.markdown_deselected)) != len(self.markdown_deselected)
                or set(self.markdown_deselected) & set(self.node_ids)
                or set(collected_ids)
                != (set(collected_ids) & set(self.node_ids))
                | set(self.markdown_deselected)
            ):
                msg = "Markdown selection omitted or duplicated a deselection receipt"
                raise ValueError(msg)
            return self

    class PytestSelectionPlan(m.Value):
        """One validated selection and its canonical manifest artifact."""

        manifest_path: Path = m.Field(description="Canonical node-ID manifest")
        node_ids: t.StrTuple = m.Field(
            description="Selected node IDs in execution order",
        )
        whole_target: bool = m.Field(
            description="Whether the selection covers the complete test target",
        )
        inventory_collected: bool = m.Field(
            description="Whether this run executed the complete inventory phase",
        )
        owns_no_tests: bool = m.Field(
            default=False,
            description=(
                "The project declares no test files under the config-owned "
                "collection roots: an empty suite by design, not a broken run"
            ),
        )

    class PytestInvocation(m.Value):
        """How one suite invocation runs: manifest coupling and mode."""

        manifest_path: Path | None = m.Field(
            default=None,
            description="Collection manifest enforcing a nonempty selection",
        )
        serialize: bool = m.Field(
            default=False,
            description="Run serially without xdist workers",
        )
        whole_target: bool = m.Field(
            default=False,
            description="Selection covers the complete test target",
        )
        execution_mode: c.Infra.PytestExecutionMode = m.Field(
            default=c.Infra.PytestExecutionMode.INCREMENTAL,
            description="Canonical execution mode for this invocation",
        )

    class PytestRunContext(m.Value):
        """Immutable execution identity shared by a phase's native receipts."""

        execution_mode: c.Infra.PytestExecutionMode = m.Field(
            description="Canonical test operation for this report directory",
        )
        testmon_db: Path | None = m.Field(
            description="External pytest-testmon database; absent for coverage",
        )
        deadline_monotonic: float = m.Field(
            gt=0,
            description="Shared absolute deadline across all execution phases",
        )
        report_directory: Path | None = m.Field(
            default=None,
            description="Explicit directory binding profiled parent and children",
        )
        profile_sha256: str | None = m.Field(
            default=None,
            pattern=r"^[0-9a-f]{64}$",
            description="Digest binding a profile sidecar to its exact pstats artifact",
        )

    class PytestReportEvent(m.Value):
        """Common report-log envelope and the complete warning payload."""

        # Report-log event kinds carry different plugin-owned payload fields.
        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", strict=True)

        report_type: Annotated[
            str,
            m.Field(alias="$report_type", description="Pytest event kind"),
        ]
        category: Annotated[
            str | None,
            m.Field(description="Warning category name"),
        ] = None
        filename: Annotated[
            str | None,
            m.Field(description="Warning source filename"),
        ] = None
        lineno: Annotated[
            int | None,
            m.Field(ge=0, description="Warning source line"),
        ] = None
        message: Annotated[
            str | None,
            m.Field(description="Complete warning message"),
        ] = None
        nodeid: str | None = m.Field(default=None, description="TestReport node ID")
        when: str | None = m.Field(default=None, description="Pytest lifecycle phase")
        outcome: Literal["passed", "failed", "skipped"] | None = m.Field(
            default=None,
            description="TestReport outcome",
        )
        user_properties: t.VariadicTuple[t.Pair[str, t.JsonValue]] = m.Field(
            default_factory=tuple,
            description="Public pytest item properties transported by report-log",
        )

        @m.model_validator(mode="after")
        def require_event_payload(self) -> Self:
            """Reject incomplete runtime events instead of reporting zero findings.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If WarningMessage requires category, filename, lineno and
                    message; or if TestReport requires nodeid, a runtest phase and
                    outcome; or if CollectReport requires nodeid and outcome.

            """
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
        """Warning identity captured before report-log; every warning blocks."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(strict=True)

        category: str = m.Field(description="Runtime warning class name")
        category_module: str = m.Field(description="Declaring warning module")
        category_qualname: str = m.Field(description="Qualified runtime class name")
        filename: str = m.Field(description="Warning source filename")
        lineno: int = m.Field(ge=0, description="Warning source line")
        message: str = m.Field(description="Complete warning message")

    class PytestPhaseOutcome(m.Value):
        """One observed pytest lifecycle phase, never inferred from selection."""

        node_id: t.NonEmptyStr = m.Field(description="Actual TestReport node ID")
        phase: Literal["setup", "call", "teardown"] = m.Field(
            description="Observed public pytest runtest phase",
        )
        outcome: Literal["passed", "failed", "skipped"] = m.Field(
            description="Unmodified TestReport outcome",
        )

    class PytestDiagnostics(m.ArbitraryTypesModel):
        """Extracted diagnostics summary from JUnit XML and pytest report-log."""

        failed_count: Annotated[
            t.NonNegativeInt,
            m.Field(description="Failed test case count"),
        ]
        error_count: Annotated[
            t.NonNegativeInt,
            m.Field(description="Errored test case count"),
        ]
        warning_count: Annotated[
            t.NonNegativeInt,
            m.Field(description="Recorded warning event count"),
        ]
        skipped_count: Annotated[
            t.NonNegativeInt,
            m.Field(description="Skipped test case count"),
        ]
        collection_failed_count: t.NonNegativeInt = m.Field(
            description="Failed collection reports, separate from JUnit cases",
        )
        collection_skipped_count: t.NonNegativeInt = m.Field(
            description="Skipped collection reports, separate from JUnit cases",
        )
        collection_failed_cases: t.StrTuple = m.Field(
            default_factory=tuple,
            description="Node IDs with failed collection reports",
        )
        collection_skip_cases: t.StrTuple = m.Field(
            default_factory=tuple,
            description="Node IDs with skipped collection reports",
        )
        reported_node_ids: t.StrTuple = m.Field(
            default_factory=tuple,
            description="Unique node IDs with real TestReport events",
        )
        phase_outcomes: t.VariadicTuple[FlextInfraModelsCore.PytestPhaseOutcome] = (
            m.Field(
                default_factory=tuple,
                description="Complete observed runtest outcomes, including failures",
            )
        )
        markdown_attempts: t.VariadicTuple[
            FlextInfraModelsCore.PytestMarkdownAttempt
        ] = m.Field(
            default_factory=tuple, description="Observed SDK execution attempts",
        )
        markdown_items: t.VariadicTuple[FlextInfraModelsCore.PytestMarkdownItem] = (
            m.Field(default_factory=tuple, description="Executed call-phase origins")
        )
        failed_cases: Annotated[
            t.StrSequence,
            m.Field(description="Failed test labels"),
        ] = m.Field(default_factory=tuple)
        error_traces: Annotated[
            t.StrSequence,
            m.Field(description="Collected error traces"),
        ] = m.Field(default_factory=tuple)
        warning_lines: Annotated[
            t.StrSequence,
            m.Field(description="Captured warning lines"),
        ] = m.Field(default_factory=tuple)
        skip_cases: Annotated[
            t.StrSequence,
            m.Field(description="Skipped test labels"),
        ] = m.Field(default_factory=tuple)
        slow_entries: Annotated[
            t.StrSequence,
            m.Field(description="Slow test entries"),
        ] = m.Field(default_factory=tuple)

    class PytestMarkdownReconciliation(m.Value):
        """Origin and phase accounting; deselection is never execution."""

        eligible: t.VariadicTuple[FlextInfraModelsCore.PytestMarkdownOrigin] = m.Field(
            description="Independent parser eligibility",
        )
        selected: t.VariadicTuple[FlextInfraModelsCore.PytestMarkdownItem] = m.Field(
            description="Actual selected identities",
        )
        deselected: t.VariadicTuple[FlextInfraModelsCore.PytestMarkdownItem] = m.Field(
            description="Origins not executed in this phase",
        )
        diagnostics: FlextInfraModelsCore.PytestDiagnostics = m.Field(
            description="Unmodified observed phases, attempts and first causes",
        )
        cache_hit: bool = m.Field(
            description="Separate typed incremental cache receipt",
        )
        violations: t.StrTuple = m.Field(description="Reconciliation failures")

    class DiagResult(m.ArbitraryTypesModel):
        """Internal container for extracted diagnostics.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        reported_phases: t.MutableMappingKV[str, t.MutableStrMapping] = m.Field(
            default_factory=dict,
            description="Runtest phase outcomes keyed by TestReport node ID",
        )
        markdown_attempts: t.MutableSequenceOf[
            FlextInfraModelsCore.PytestMarkdownAttempt
        ] = m.Field(default_factory=list, description="Call-phase attempt observations")
        markdown_items: t.MutableSequenceOf[FlextInfraModelsCore.PytestMarkdownItem] = (
            m.Field(default_factory=list, description="Call-phase origin observations")
        )
        collection_failed_cases: t.MutableSequenceOf[str] = m.Field(
            default_factory=list,
            description="Node IDs with failed collection reports",
        )
        collection_skip_cases: t.MutableSequenceOf[str] = m.Field(
            default_factory=list,
            description="Node IDs with skipped collection reports",
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
            t.MutableSequenceOf[str],
            m.Field(description="Collected warning lines"),
        ] = m.Field(default_factory=list)
        slow_entries: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Collected slow-test entries"),
        ] = m.Field(default_factory=list)

    class InventoryReport(m.ArbitraryTypesModel):
        """Summary of written inventory report artifacts."""

        total_scripts: Annotated[
            t.NonNegativeInt,
            m.Field(description="Total discovered scripts"),
        ]
        reports_written: Annotated[
            t.MutableSequenceOf[str],
            m.Field(description="Written report file paths"),
        ] = m.Field(default_factory=list)

    class NamespaceValidateCommand(m.ContractModel):
        """CLI payload for ``flext-infra validate namespace``.

        Read-only rule-catalog scan of one repository root's namespace scope.
        """

        repository_root: Annotated[
            Path,
            m.Field(
                description="Repository root whose namespace contract is validated",
            ),
        ]


__all__: list[str] = ["FlextInfraModelsCore"]
