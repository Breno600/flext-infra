"""Project-owned gitignore configuration models."""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from flext_infra import t

from .deps_tool_config_project_mise import FlextInfraModelsDepsToolConfigProjectMise


class FlextInfraModelsDepsToolConfigProjectGitignore(
    FlextInfraModelsDepsToolConfigProjectMise
):
    """Project-local ignore patterns appended to generated gitignore output."""

    class ProjectGitignoreConfig(m.ArbitraryTypesModel):
        """Repository-owned ignore patterns the fleet scaffold cannot know."""

        patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Ignore patterns appended, in declaration order, as one "
                    "project-owned section of the generated .gitignore."
                )
            ),
        ] = ()


__all__: list[str] = ["FlextInfraModelsDepsToolConfigProjectGitignore"]
