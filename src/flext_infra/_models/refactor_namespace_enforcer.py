"""Domain models for the namespace enforcer's relocation reports.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from flext_infra import t
from flext_infra._models.mixins import FlextInfraModelsMixins as mm


class FlextInfraModelsNamespaceEnforcer:
    """Namespace enforcer report models."""

    class ParseFailureViolation(mm.FilePathMixin, mm.ErrorDetailMixin, m.ContractModel):
        """Parse failure violation."""

        stage: Annotated[t.NonEmptyStr, m.Field(description="Parse stage")]
        error_type: Annotated[t.NonEmptyStr, m.Field(description="Error type")]

    class ProjectEnforcementReport(mm.ProjectNameMixin, m.ArbitraryTypesModel):
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
        files_scanned: Annotated[
            t.NonNegativeInt,
            m.Field(description="Files scanned"),
        ] = 0

        @m.computed_field
        @property
        def has_violations(self) -> bool:
            """Whether relocatable findings remain in this project."""
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
            """Whether any project carries a violation."""
            return any(project.has_violations for project in self.projects)


__all__: list[str] = ["FlextInfraModelsNamespaceEnforcer"]
