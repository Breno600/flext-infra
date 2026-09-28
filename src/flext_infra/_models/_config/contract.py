"""Shared contract base and root aliases for config models."""

from __future__ import annotations

from flext_cli import m

from ..mise_toolchain import FlextInfraModelsMiseToolchain


class FlextInfraConfigModelsContract:
    """Shared contract base and root aliases for config models."""

    class ConfigContract(m.ContractModel):
        """Public declarative base for schema-loaded codegen records."""

        # Rendered file payloads are
        # byte contracts; Pydantic must never trim their final newline.
        model_config = m.ConfigDict(
            strict=False, frozen=True, extra="forbid", str_strip_whitespace=False
        )

    BeadsEndpointSpec = FlextInfraModelsMiseToolchain.BeadsEndpointSpec
    BeadsToolSpec = FlextInfraModelsMiseToolchain.BeadsToolSpec
    MiseBootstrapEnvironmentSpec = (
        FlextInfraModelsMiseToolchain.MiseBootstrapEnvironmentSpec
    )
    ToolchainSpec = FlextInfraModelsMiseToolchain.ToolchainSpec
