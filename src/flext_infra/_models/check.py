"""Domain models for the check subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import Annotated, ClassVar

from flext_core import m, u
from flext_infra import c, t
from flext_infra._models.mixins import FlextInfraModelsMixins


class FlextInfraModelsCheck:
    """Quality-gate check domain models."""

    class RunCommand(FlextInfraModelsMixins.WriteMixin, m.ContractModel):
        """Canonical CLI payload for ``flext-infra check run``.

        Inherits canonical ``repository_root`` (``--repository-root``),
        ``gates`` (parsed to ``t.StrSequence``), ``apply``/``dry_run``,
        ``projects`` and ``verbose`` from ``WriteMixin``; the scope
        root has exactly one owner so an unmapped option can never fall back
        to the current directory.
        """

        fail_fast: Annotated[
            bool,
            m.Field(description="Stop check gates after the first failure"),
        ] = c.Infra.CHECK_FAIL_FAST_DEFAULT
        reports_dir: Annotated[
            str,
            m.Field(
                alias="reports-dir",
                description="Directory used to write check reports",
            ),
        ] = f"{c.Infra.REPORTS_DIR_NAME}/check"
        check_only: Annotated[
            bool,
            m.Field(
                alias="check-only",
                description="Enable check-only mode for supported tools",
            ),
        ] = False
        ruff_args: Annotated[
            str | None,
            m.Field(alias="ruff-args", description="Extra arguments forwarded to Ruff"),
        ] = None
        pyright_args: Annotated[
            str | None,
            m.Field(
                alias="pyright-args",
                description="Extra arguments forwarded to Pyright",
            ),
        ] = None

        @property
        def reports_dir_path(self) -> Path:
            """Resolved reports directory path."""
            reports_dir = Path(self.reports_dir).expanduser()
            if reports_dir.is_absolute():
                return reports_dir.resolve()
            return (self.repository_root / reports_dir).resolve()

    class CheckProjectTarget(m.ArbitraryTypesModel):
        """Resolved project target for workspace gate execution."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            frozen=True,
            validate_default=False,
        )

        name: Annotated[str, m.Field(description="Display/project name")]
        path: Annotated[Path, m.Field(description="Resolved project root path")]

    class MypyResourceLimit(m.ContractModel):
        """Validated memory and wall-time limits for every Mypy process."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        memory_limit_mb: Annotated[
            int,
            m.Field(
                gt=0,
                le=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
                description="Positive Mypy memory limit in MiB (Linux AS; Darwin RSS)",
            ),
        ] = c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT
        timeout_seconds: Annotated[
            int,
            m.Field(
                gt=0,
                description=(
                    "Positive Mypy wall-time limit in seconds, resolved from"
                    " tools.mypy.timeout_seconds in tooling.yaml or the env"
                    " override"
                ),
            ),
        ]

        @m.computed_field
        @property
        def memory_limit_bytes(self) -> int:
            """Validated memory limit converted to bytes for the platform owner.

            Returns:
                The resulting ``int``.
            """
            return self.memory_limit_mb * c.Infra.BYTES_PER_MIB

    class MypyInvocation(m.ContractModel):
        """Checker inputs; callers cannot select an executable or Python program."""

        targets: Annotated[
            t.VariadicTuple[Path],
            m.Field(min_length=1, description="Files or directories to check"),
        ]
        workspace: Annotated[
            Path | None,
            m.Field(description="Workspace owning the checker environment"),
        ] = None
        config_file: Annotated[
            Path | None,
            m.Field(description="Owned Mypy configuration"),
        ] = None
        report_json: Annotated[
            bool,
            m.Field(description="Emit native JSON diagnostics"),
        ] = False
        verbose: Annotated[bool, m.Field(description="Emit Mypy progress")] = False
        profile_output: Annotated[
            Path | None,
            m.Field(description="Optional cProfile output destination"),
        ] = None

    class FixPyreflyConfigCommand(FlextInfraModelsMixins.WriteMixin, m.ContractModel):
        """Canonical CLI payload for ``flext-infra check fix-pyrefly-settings``."""

    class SarifLocation(m.ContractModel):
        """Native SARIF location, including the optional end of its source span."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(validate_by_name=True)

        uri: str = m.Field(
            validation_alias=m.AliasPath("physicalLocation", "artifactLocation", "uri"),
            description="Artifact URI",
        )
        start_line: int | None = m.Field(
            None,
            validation_alias=m.AliasPath("physicalLocation", "region", "startLine"),
            description="Start line (1-based)",
        )
        start_column: int | None = m.Field(
            None,
            validation_alias=m.AliasPath("physicalLocation", "region", "startColumn"),
            description="Native start column",
        )
        end_line: int | None = m.Field(
            None,
            validation_alias=m.AliasPath("physicalLocation", "region", "endLine"),
            description="Native end line when supplied by the scanner",
        )
        end_column: int | None = m.Field(
            None,
            validation_alias=m.AliasPath("physicalLocation", "region", "endColumn"),
            description="Native end column when supplied by the scanner",
        )
        uri_base_id: str = m.Field(
            "%SRCROOT%",
            validation_alias=m.AliasPath(
                "physicalLocation",
                "artifactLocation",
                "uriBaseId",
            ),
            description="URI base identifier",
            validate_default=True,
        )

        @u.model_serializer
        def _serialize(self) -> t.JsonMapping:
            """Emit native optional span coordinates only when present.

            Returns:
                The resulting ``t.JsonMapping``.
            """
            region: t.JsonDict = {}
            if self.start_line is not None:
                region["startLine"] = self.start_line
            if self.start_column is not None:
                region["startColumn"] = self.start_column
            if self.end_line is not None:
                region["endLine"] = self.end_line
            if self.end_column is not None:
                region["endColumn"] = self.end_column
            return {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": self.uri,
                        "uriBaseId": self.uri_base_id,
                    },
                    "region": region,
                },
            }

    class Issue(m.ContractModel):
        """Single issue reported by a quality gate tool."""

        file: Annotated[str, m.Field(description="Source file path")]
        line: Annotated[int, m.Field(description="Line number")]
        column: Annotated[int, m.Field(description="Column number")]
        code: Annotated[str, m.Field(description="Rule or error code")]
        message: Annotated[str, m.Field(description="Human-readable issue description")]
        severity: Annotated[str, m.Field(description="Issue severity level")] = (
            c.Infra.ERROR
        )
        locations: t.VariadicTuple[FlextInfraModelsCheck.SarifLocation] = m.Field(
            (),
            description="Native primary source spans when supplied by the scanner",
            validate_default=True,
        )
        related_locations: t.VariadicTuple[FlextInfraModelsCheck.SarifLocation] = (
            m.Field(
                (),
                description="All native comparison locations, including other projects",
                validate_default=True,
            )
        )

        @m.computed_field
        @property
        def formatted(self) -> str:
            """Format issue as ``file:line:col [code] message``.

            Returns:
                The resulting ``str``.
            """
            code_part = f"[{self.code}] " if self.code else ""
            return (
                f"{self.file}:{self.line}:{self.column} {code_part}{self.message}"
            ).strip()

    class GateResult(FlextInfraModelsMixins.ProjectNameMixin, m.ArbitraryTypesModel):
        """Result summary for a single quality gate execution."""

        gate: Annotated[str, m.Field(description="Gate name")]
        passed: Annotated[bool, m.Field(description="Gate execution status")]
        errors: t.StrSequence = m.Field(
            default_factory=tuple,
            description="Gate error messages",
        )
        duration: float = m.Field(
            0.0,
            description="Duration in seconds",
            validate_default=True,
        )

    class GateExecution(m.ArbitraryTypesModel):
        """Execution result for a single quality gate."""

        result: FlextInfraModelsCheck.GateResult = m.Field(
            description="Gate result model",
        )
        issues: t.VariadicTuple[FlextInfraModelsCheck.Issue] = m.Field(
            default_factory=tuple,
            description="Blocking gate diagnostics",
        )
        raw_output: str = m.Field(
            "",
            description="Raw tool output",
            validate_default=True,
        )

        @m.computed_field
        @property
        def finding_count(self) -> int:
            """Number of findings that fail the gate: every issue blocks.

            Returns:
                The resulting ``int``.
            """
            return len(self.issues)

    class ProjectResult(FlextInfraModelsMixins.ProjectNameMixin, m.ArbitraryTypesModel):
        """Aggregated gate results for a single project.

        Enforcement exemption: ``gates`` is a ``MutableMapping`` populated
        incrementally as each gate completes; no shared state — one fresh
        dict per instance.
        """

        gates: MutableMapping[str, FlextInfraModelsCheck.GateExecution] = m.Field(
            default_factory=dict,
            description="Gate name to execution mapping",
        )
        informational_gates: t.VariadicTuple[str] = m.Field(
            default=(),
            description=(
                "Gate ids whose findings stay reported but never fail the "
                "project (config-owned posture)"
            ),
        )

        @m.computed_field
        @property
        def passed(self) -> bool:
            """Whether every blocking gate passed.

            Informational gates (``informational_gates``) keep their verdict
            and findings in the report, but the project verdict ignores them
            so their debt cannot block `make check` or CI.

            Returns:
                The resulting ``bool``.
            """
            informational = frozenset(self.informational_gates)
            return all(
                v.result.passed
                for gate_id, v in self.gates.items()
                if gate_id not in informational
            )

        @m.computed_field
        @property
        def total_findings(self) -> int:
            """Total blocking findings across all gates.

            Returns:
                The resulting ``int``.
            """
            return sum(v.finding_count for v in self.gates.values())

    class LoopOutcome(m.ArbitraryTypesModel):
        """Bundled results from the project-checking loop."""

        # Why: owned by m.Infra; ArbitraryTypesModel keeps protocol field writability.

        results: Annotated[
            t.VariadicTuple[FlextInfraModelsCheck.ProjectResult],
            m.Field(description="Individual project execution results."),
        ]
        failed: Annotated[
            int,
            m.Field(description="Number of projects that failed one or more gates."),
        ]
        total_elapsed: Annotated[
            float,
            m.Field(description="Total time elapsed in seconds for the entire loop."),
        ]

    # -- SARIF 2.1.0 report models -----------------------------------------
    # Each model keeps flat fields; ``model_serializer`` emits the nested SARIF
    # shape and the matching ``AliasPath`` validation aliases read that same
    # shape back, so an emitted report validates into the model it came from.

    class SarifRule(m.ContractModel):
        """Compact SARIF rule descriptor."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(validate_by_name=True)

        id: Annotated[str, m.Field(description="Rule identifier")]
        short_description: Annotated[
            str,
            m.Field(
                validation_alias=m.AliasPath("shortDescription", "text"),
                description="Rule short description",
            ),
        ]
        help_uri: Annotated[
            str,
            m.Field(
                validation_alias="helpUri",
                description="Documentation URL of the tool behind the gate",
            ),
        ]

        @u.model_serializer
        def _serialize(self) -> t.JsonMapping:
            """Serialize.

            Returns:
                The resulting ``t.JsonMapping``.

            """
            return {
                "id": self.id,
                "shortDescription": {"text": self.short_description},
                "helpUri": self.help_uri,
            }

    class SarifResult(m.ContractModel):
        """SARIF result entry."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(validate_by_name=True)

        rule_id: Annotated[
            str,
            m.Field(validation_alias="ruleId", description="Rule identifier"),
        ]
        level: Annotated[str, m.Field(description="Result level (error/warning/note)")]
        message: Annotated[
            str,
            m.Field(
                validation_alias=m.AliasPath("message", "text"),
                description="Result message",
            ),
        ]
        locations: list[FlextInfraModelsCheck.SarifLocation] = m.Field(
            description="Result locations",
        )
        related_locations: t.VariadicTuple[FlextInfraModelsCheck.SarifLocation] = (
            m.Field(
                (),
                validation_alias="relatedLocations",
                description="Native related source spans",
                validate_default=True,
            )
        )

        @u.model_serializer
        def _serialize(self) -> t.JsonMapping:
            """Serialize.

            Returns:
                The resulting ``t.JsonMapping``.

            """
            result: t.MutableJsonMapping = {
                "ruleId": self.rule_id,
                "level": self.level,
                "message": {"text": self.message},
                "locations": [
                    location.model_dump(by_alias=True) for location in self.locations
                ],
            }
            if self.related_locations:
                result["relatedLocations"] = [
                    location.model_dump(by_alias=True)
                    for location in self.related_locations
                ]
            return result

    class SarifRun(m.ContractModel):
        """SARIF run entry."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(validate_by_name=True)

        tool_name: Annotated[
            str,
            m.Field(
                validation_alias=m.AliasPath("tool", "driver", "name"),
                description="Tool name",
            ),
        ]
        information_uri: str = m.Field(
            "",
            validation_alias=m.AliasPath("tool", "driver", "informationUri"),
            description="Tool documentation URL",
            validate_default=True,
        )
        rules: t.VariadicTuple[FlextInfraModelsCheck.SarifRule] = m.Field(
            default_factory=tuple,
            validation_alias=m.AliasPath("tool", "driver", "rules"),
            description="Rule descriptors",
        )
        results: t.VariadicTuple[FlextInfraModelsCheck.SarifResult] = m.Field(
            default_factory=tuple,
            description="Run results",
        )

        @u.model_serializer
        def _serialize(self) -> t.JsonMapping:
            """Serialize.

            Returns:
                The resulting ``t.JsonMapping``.

            """
            return {
                "tool": {
                    "driver": {
                        "name": self.tool_name,
                        "informationUri": self.information_uri,
                        "rules": [
                            rule.model_dump(by_alias=True) for rule in self.rules
                        ],
                    },
                },
                "results": [
                    result.model_dump(by_alias=True) for result in self.results
                ],
            }

    class SarifReport(m.ArbitraryTypesModel):
        """Complete SARIF 2.1.0 report; serializes and validates the same JSON."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            validate_by_name=True,
            serialize_by_alias=True,
        )

        schema_uri: c.Infra.SarifSchema = m.Field(
            c.Infra.SarifSchema.V2_1_0,
            alias="$schema",
            description="SARIF schema URI",
            validate_default=True,
        )
        version: c.Infra.SarifVersion = m.Field(
            c.Infra.SarifVersion.V2_1_0,
            description="SARIF version",
            validate_default=True,
        )
        runs: t.VariadicTuple[FlextInfraModelsCheck.SarifRun] = m.Field(
            default_factory=tuple,
            description="SARIF runs",
        )


__all__: list[str] = ["FlextInfraModelsCheck"]
