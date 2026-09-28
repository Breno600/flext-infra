"""Typed common execution inputs for codegen services."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, override

from flext_infra import m, t
from flext_infra.base import FlextInfraServiceBase


class FlextInfraCodegenExecutionBase[TResult: t.Cli.ResultValue](
    FlextInfraServiceBase[TResult]
):
    """Own explicit repository execution state shared by codegen services."""

    repository_root: Annotated[
        Path,
        m.Field(
            default=Path(), description="Repository selected for codegen execution"
        ),
    ] = Path()
    dry_run: Annotated[
        bool, m.Field(default=False, description="Whether the service may mutate files")
    ] = False
    check_only: Annotated[
        bool, m.Field(default=False, description="Whether the service validates only")
    ] = False
    apply_changes: Annotated[
        bool,
        m.Field(
            default=True, description="Whether the requested operation applies changes"
        ),
    ] = True
    output_format: Annotated[
        str,
        m.Field(default="text", description="Output format (json|text)"),
        m.BeforeValidator(lambda value: value.strip().lower()),
    ] = "text"

    @property
    @override
    def effective_dry_run(self) -> bool:
        """The one execution mode that forbids mutation."""
        return self.dry_run or self.check_only or not self.apply_changes


__all__: list[str] = ["FlextInfraCodegenExecutionBase"]
