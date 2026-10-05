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

        @staticmethod
        def _is_single_line(marker: str) -> bool:
            """Whether one marker is a complete line with no embedded newline.

            Returns:
                The resulting ``bool``.

            """
            return (
                marker.strip() == marker and "\n" not in marker and "\r" not in marker
            )

        def _overlap(self, other: str) -> bool:
            """Whether one marker collides with or is contained in the other.

            Returns:
                The resulting ``bool``.

            """
            return self.begin == other or self.begin in other or other in self.begin

        @m.model_validator(mode="after")
        def validate_markers(self) -> Self:
            """Require distinct, complete single-line delimiters.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If gitignore preserved block markers must be distinct single
                    lines.

            """
            if self._overlap(self.end) or not (
                self._is_single_line(self.begin) and self._is_single_line(self.end)
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
