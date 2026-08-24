"""Domain models for quality gate execution."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal

from flext_cli import m
from flext_infra import t


class FlextInfraModelsGates:
    """Quality gate execution domain models."""

    class GateContext(m.ContractModel):
        """Quality gate execution context and configuration."""

        fail_fast: Annotated[bool, m.Field(description="Stop on first failure")] = True
        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", arbitrary_types_allowed=True, populate_by_name=True
        )
        workspace_root: Path = m.Field(
            alias="workspace", description="Workspace root directory"
        )
        reports_dir: Annotated[Path, m.Field(description="Reports output directory")]
        apply_fixes: Annotated[
            bool, m.Field(description="Apply supported fixes before checking")
        ] = False
        check_only: Annotated[
            bool,
            m.Field(description="Never write files even when fix mode is requested"),
        ] = False
        gate_mode: Annotated[
            Literal["error", "warn"],
            m.Field(
                description="Gate failure mode: error fails the pipeline, warn reports only"
            ),
        ] = "error"
        ruff_args: Annotated[
            t.StrSequence, m.Field(description="Extra arguments for Ruff")
        ] = ()
        pyright_args: Annotated[
            t.StrSequence, m.Field(description="Extra arguments for Pyright")
        ] = ()


__all__: list[str] = ["FlextInfraModelsGates"]
