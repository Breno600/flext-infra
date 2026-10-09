"""Domain models for the shared utilities subpackage.

Scan violation and result models used by infrastructure scanning utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Annotated, ClassVar, Literal

from flext_cli import m

from flext_infra import c, t
from flext_infra._models.mixins import FlextInfraModelsMixins
from flext_infra._models.refactor_namespace_enforcer import (
    FlextInfraModelsNamespaceEnforcer,
)


class FlextInfraModelsScan:
    """Shared utility domain models for scanning and analysis."""

    class DetectorContext(m.ArbitraryTypesModel):
        """Bundles common parameters passed to every detect_file classmethod."""

        file_path: Path = m.Field(
            description="Filesystem path of the file being scanned.",
        )
        rope_project: t.Infra.RopeProject = m.Field(
            description="Initialized Rope project for semantic metadata.",
        )
        parse_failures: Annotated[
            (
                t.MutableSequenceOf[
                    FlextInfraModelsNamespaceEnforcer.ParseFailureViolation
                ]
                | None
            ),
            m.SkipValidation,
            m.Field(
                description="Shared parse-failure collector across detector passes.",
            ),
        ] = None
        project_name: Annotated[
            str,
            m.Field(description="Optional project name for the scanned file."),
        ] = ""
        project_root: Annotated[
            Path | None,
            m.Field(description="Optional project root containing the scanned file."),
        ] = None

    class ScanViolation(FlextInfraModelsMixins.PositiveLineMixin, m.ContractModel):
        """A single violation found during file scanning."""

        message: Annotated[
            str,
            m.Field(description="Human-readable violation description"),
        ]
        severity: Annotated[str, m.Field(description="Violation severity level")]
        rule_id: Annotated[
            str | None,
            m.Field(description="Optional rule identifier"),
        ] = None

    class ScanResult(m.ArbitraryTypesModel):
        """Result of scanning a single file."""

        file_path: Annotated[Path, m.Field(description="Path to the scanned file")]
        violations: Annotated[
            t.SequenceOf[FlextInfraModelsScan.ScanViolation],
            m.Field(description="Violations found in the file"),
        ] = m.Field(default_factory=tuple)
        detector_name: Annotated[
            str,
            m.Field(description="Name of the detector that produced this result"),
        ]

    class ModScanFinding(m.ArbitraryTypesModel):
        """One complete ast-grep JSONL finding with canonical evidence keys."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        rule_file: Annotated[
            t.NonEmptyStr,
            m.Field(description="Rule document file producing the finding"),
        ]
        rule_id: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact ast-grep rule identifier"),
        ]
        repository: Annotated[
            t.NonEmptyStr,
            m.Field(description="Workspace repository owning the file"),
        ]
        file: Annotated[Path, m.Field(description="Workspace-relative finding path")]
        source_owner: Annotated[
            Literal["authored", "generator"],
            m.Field(description="Writable authority for the finding source"),
        ] = "authored"
        source_state: Annotated[
            m.Cli.AtomicFileState | None,
            m.Field(description="Exact source snapshot authenticated before scanning"),
        ] = None
        binding_states: Annotated[
            tuple[m.Cli.AtomicFileState, ...],
            m.Field(
                default_factory=tuple,
                description="Closed occurrence-binding source receipts",
            ),
        ]
        range: Annotated[
            t.JsonMapping,
            m.Field(description="Exact ast-grep source range payload"),
        ]
        text: Annotated[str, m.Field(description="Exact matched source text")]
        replacement: Annotated[
            str | None,
            m.Field(description="Exact replacement when the rule provides one"),
        ] = None
        actionable: Annotated[
            bool,
            m.Field(description="Whether applying the rule changes source bytes"),
        ]
        classification: Annotated[
            c.Infra.ModScanFindingClass,
            m.Field(description="Rule mutability and byte-change classification"),
        ]
        payload: Annotated[
            t.JsonMapping,
            m.Field(
                description="Complete validated ast-grep finding without field loss",
            ),
        ]

    class ModReplacementOffsets(m.ContractModel):
        """UTF-8 byte coordinates supplied by the ast-grep JSON contract."""

        start: Annotated[
            int,
            m.Field(ge=0, strict=True, description="Inclusive start byte"),
        ]
        end: Annotated[
            int,
            m.Field(ge=0, strict=True, description="Exclusive end byte"),
        ]

    class ModScanReport(m.ArbitraryTypesModel):
        """Verified structural findings and actionable rewrite targets."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        findings: Annotated[
            t.NonNegativeInt,
            m.Field(description="Complete finding count"),
        ]
        actionable: Annotated[
            t.NonNegativeInt,
            m.Field(description="Byte-changing rewrite count"),
        ]
        detection_only: Annotated[
            t.NonNegativeInt,
            m.Field(description="Findings produced by rules without a fix"),
        ]
        non_actionable_with_fix: Annotated[
            t.NonNegativeInt,
            m.Field(description="Findings whose declared fix is byte-identical"),
        ]
        files: Annotated[
            frozenset[Path],
            m.Field(description="Files containing findings"),
        ]
        entries: Annotated[
            t.VariadicTuple[FlextInfraModelsScan.ModScanFinding],
            m.Field(description="Every validated ast-grep finding in stable order"),
        ]

    class ModTextRule(m.ArbitraryTypesModel):
        """One declarative sed-by-list entry with its exact rewrite receipt."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        rule_id: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact unique text-rule identifier"),
        ]
        description: Annotated[
            str,
            m.Field(description="Human-readable rewrite intent"),
        ] = ""
        include: Annotated[
            t.StrSequence,
            m.Field(description="fnmatch globs a target path must match"),
        ] = ()
        exclude: Annotated[
            t.StrSequence,
            m.Field(description="fnmatch globs a target path must not match"),
        ] = ()
        distributions: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Declared project distributions selected "
                    "for this rule; empty selects all"
                ),
            ),
        ] = ()
        find: Annotated[
            t.NonEmptyStr,
            m.Field(description="Regex source pattern to locate"),
        ]
        replace: Annotated[
            str,
            m.Field(description="Expansion template replacing each match"),
        ] = ""
        flags: Annotated[
            t.StrSequence,
            m.Field(description="Regex flag names from the SSOT map"),
        ] = ()
        capture_equals: Annotated[
            t.MappingKV[str, str],
            m.Field(description="Named regex captures and their required exact values"),
        ] = m.Field(default_factory=lambda: MappingProxyType[str, str]({}))
        expected: Annotated[
            int | None,
            m.Field(
                ge=0,
                description="Exact finding count the rule must produce when set",
            ),
        ] = None

    class ModTextFinding(m.ArbitraryTypesModel):
        """One text-rule match with its computed replacement."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        rule_id: Annotated[
            t.NonEmptyStr,
            m.Field(description="Exact text-rule identifier"),
        ]
        file: Annotated[Path, m.Field(description="Workspace-relative target path")]
        line: Annotated[t.NonNegativeInt, m.Field(description="One-based match line")]
        text: Annotated[str, m.Field(description="Exact matched source text")]
        replacement: Annotated[
            str,
            m.Field(description="Expanded replacement for the match"),
        ]

    class ModTextReport(m.ArbitraryTypesModel):
        """Complete text-rule findings for one fixed-point pass."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        findings: Annotated[
            t.NonNegativeInt,
            m.Field(description="Complete finding count"),
        ]
        actionable: Annotated[
            t.NonNegativeInt,
            m.Field(description="Matches whose replacement differs from the text"),
        ]
        files: Annotated[
            frozenset[Path],
            m.Field(description="Files containing findings"),
        ]
        entries: Annotated[
            t.VariadicTuple[FlextInfraModelsScan.ModTextFinding],
            m.Field(description="Every validated text finding in stable order"),
        ]

    class ModScanEvidence(m.ArbitraryTypesModel):
        """Complete replace-on-run evidence for one public mod scan."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        schema_version: Annotated[
            Literal[1],
            m.Field(description="Exact structured evidence schema"),
        ]
        command: Annotated[
            c.Infra.ModScanCommand,
            m.Field(description="Public mod scan mode"),
        ]
        root: Annotated[Path, m.Field(description="Absolute scanned workspace root")]
        scope: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Exact ast-grep target scope"),
        ]
        findings: Annotated[
            t.NonNegativeInt,
            m.Field(description="Complete finding count"),
        ]
        actionable: Annotated[
            t.NonNegativeInt,
            m.Field(description="Byte-changing rewrite count"),
        ]
        detection_only: Annotated[
            t.NonNegativeInt,
            m.Field(description="Findings produced by rules without a fix"),
        ]
        non_actionable_with_fix: Annotated[
            t.NonNegativeInt,
            m.Field(description="Findings whose declared fix is byte-identical"),
        ]
        totals_by_class: Annotated[
            t.MappingKV[c.Infra.ModScanFindingClass, t.NonNegativeInt],
            m.Field(description="Complete finding totals by mutability class"),
        ]
        totals_by_repository: Annotated[
            t.MappingKV[str, t.NonNegativeInt],
            m.Field(description="Complete finding totals by repository"),
        ]
        totals_by_rule: Annotated[
            t.MappingKV[str, t.NonNegativeInt],
            m.Field(description="Complete finding totals by rule identifier"),
        ]
        entries: Annotated[
            t.VariadicTuple[FlextInfraModelsScan.ModScanFinding],
            m.Field(description="Every finding in deterministic scan order"),
        ]

    class ModScanEvidenceReceipt(m.ArbitraryTypesModel):
        """Authenticated publication identity and its exact evidence payload."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        path: Annotated[Path, m.Field(description="Published evidence destination")]
        sha256: Annotated[t.NonEmptyStr, m.Field(description="Published byte digest")]
        evidence: Annotated[
            FlextInfraModelsScan.ModScanEvidence,
            m.Field(description="Exact structured evidence that was published"),
        ]


__all__: list[str] = ["FlextInfraModelsScan"]
