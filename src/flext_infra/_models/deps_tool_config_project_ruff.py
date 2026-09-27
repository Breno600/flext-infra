"""Project-owned Ruff configuration models."""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from flext_infra import t


class FlextInfraModelsDepsToolConfigProjectRuff:
    """Ruff configuration slice owned by one project."""

    class ProjectRuffConfig(m.ArbitraryTypesModel):
        """Project-owned Ruff additions for generated managed artifacts."""

        per_file_ignores: Annotated[
            t.Infra.PerFileIgnores,
            m.Field(
                description="Project-local per-file rules merged with global policy."
            ),
        ]


__all__: list[str] = ["FlextInfraModelsDepsToolConfigProjectRuff"]
