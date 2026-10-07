"""Domain models for the namespace enforcer's relocation reports.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from flext_infra import t
from flext_infra._models import FlextInfraModelsMixins


class FlextInfraModelsNamespaceEnforcer:
    """Namespace enforcer report models."""

    class ParseFailureViolation(
        FlextInfraModelsMixins.FilePathMixin,
        FlextInfraModelsMixins.ErrorDetailMixin,
        m.ContractModel,
    ):
        """Parse failure violation."""

        stage: Annotated[t.NonEmptyStr, m.Field(description="Parse stage")]
        error_type: Annotated[t.NonEmptyStr, m.Field(description="Error type")]

    class ProjectEnforcementReport(
        FlextInfraModelsMixins.ProjectNameMixin,
        m.ArbitraryTypesModel,
    ):
        """Rule-catalog relocation outcome of one project."""

        project_root: Annotated[str, m.Field(description="Project root path")]
        relocation_findings: Annotated[
            t.NonNegativeInt,
            m.Field(
                description=(
                    "Rule-catalog findings whose rule declares a rope relocation "
                    "and that remain after the namespace pass."
                ),
            ),
        ] = 0
        applied_relocations: Annotated[
            t.NonNegativeInt,
            m.Field(
                description=(
                    "Relocations the apply pass performed in this project: the "
                    "captured findings minus the residue the rescan counts."
                ),
            ),
        ] = 0
        warnings: Annotated[
            t.NonNegativeInt,
            m.Field(
                description=(
                    "Detection-only and non-actionable findings surfaced for "
                    "repair by their owners; they never abort the sweep."
                ),
            ),
        ] = 0
        files_scanned: Annotated[
            t.NonNegativeInt,
            m.Field(description="Files scanned"),
        ] = 0
        error: Annotated[
            str | None,
            m.Field(
                description=(
                    "Why this project's enforcement pass failed; the sweep "
                    "continues to the remaining projects either way."
                ),
            ),
        ] = None

        @m.computed_field
        @property
        def has_violations(self) -> bool:
            """Whether relocatable findings remain in this project.

            Returns:
                The resulting ``bool``.
            """
            return self.relocation_findings > 0

    class WorkspaceEnforcementReport(m.ArbitraryTypesModel):
        """Workspace enforcement report."""

        workspace: Annotated[t.NonEmptyStr, m.Field(description="Repository root path")]
        projects: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.ProjectEnforcementReport],
            m.Field(
                default_factory=tuple,
                description="Per-project enforcement reports for the workspace.",
            ),
        ]

        @m.computed_field
        @property
        def has_violations(self) -> bool:
            """Whether any project carries a violation.

            Returns:
                The resulting ``bool``.
            """
            return any(project.has_violations for project in self.projects)

        @m.computed_field
        @property
        def has_errors(self) -> bool:
            """Whether any project's enforcement pass itself failed.

            Returns:
                The resulting ``bool``.
            """
            return any(project.error is not None for project in self.projects)


__all__: list[str] = ["FlextInfraModelsNamespaceEnforcer"]
