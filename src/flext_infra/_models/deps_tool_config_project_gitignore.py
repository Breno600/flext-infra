"""Project-owned gitignore configuration models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Annotated, Self

from flext_cli import m

from flext_infra import t
from flext_infra._models.deps_tool_config_project_mise import (
    FlextInfraModelsDepsToolConfigProjectMise,
)


class FlextInfraModelsDepsToolConfigProjectGitignore(
    FlextInfraModelsDepsToolConfigProjectMise,
):
    """Project-local ignore patterns appended to generated gitignore output."""

    class ProjectGitignorePreservedBlock(m.ArbitraryTypesModel):
        """Delimit one section written by another declared generator."""

        begin: Annotated[t.NonEmptyStr, m.Field(description="Opening marker line")]
        end: Annotated[t.NonEmptyStr, m.Field(description="Closing marker line")]

        @m.model_validator(mode="after")
        def validate_markers(self) -> Self:
            """Require distinct, complete single-line delimiters.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If gitignore preserved block markers must be distinct single
                    lines.

            """
            if (
                self.begin == self.end
                or self.begin in self.end
                or self.end in self.begin
                or self.begin.strip() != self.begin
                or self.end.strip() != self.end
                or "\n" in self.begin
                or "\r" in self.begin
                or "\n" in self.end
                or "\r" in self.end
            ):
                msg = "gitignore preserved block markers must be distinct single lines"
                raise ValueError(msg)
            return self

    class ProjectGitignoreConfig(m.ArbitraryTypesModel):
        """Repository-owned ignore patterns the fleet scaffold cannot know."""

        patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Ignore patterns appended, in declaration order, as one "
                    "project-owned section of the generated .gitignore."
                ),
            ),
        ] = ()
        preserved_blocks: Annotated[
            t.VariadicTuple[
                FlextInfraModelsDepsToolConfigProjectGitignore.ProjectGitignorePreservedBlock
            ],
            m.Field(
                description=(
                    "External generated blocks preserved from the live .gitignore; "
                    "the external owner alone supplies their contents."
                ),
            ),
        ] = ()


__all__: list[str] = ["FlextInfraModelsDepsToolConfigProjectGitignore"]
