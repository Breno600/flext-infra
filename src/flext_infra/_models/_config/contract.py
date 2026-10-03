"""Shared contract base and root aliases for config models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Self

from flext_cli import m, u

from flext_infra import t
from flext_infra._constants.validate import FlextInfraConstantsSharedInfra
from flext_infra._models.mise_toolchain import FlextInfraModelsMiseToolchain


class FlextInfraConfigModelsContract:
    """Shared contract base and root aliases for config models."""

    class ConfigContract(m.ContractModel):
        """Public declarative base for schema-loaded codegen records."""

        # Rendered file payloads are
        # byte contracts; Pydantic must never trim their final newline.
        model_config = m.ConfigDict(
            strict=False,
            frozen=True,
            extra="forbid",
            str_strip_whitespace=False,
        )

    class DocsAuditOverridesSpec(ConfigContract):
        """Repository-specific exceptions and stale-symbol declarations."""

        stale_symbols: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Public symbols retired from current documentation"),
        ] = ()
        stale_symbol_exempt_paths: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Exact generated API paths retaining live symbols"),
        ] = ()
        historical_evidence_files: Annotated[
            t.VariadicTuple[Path],
            m.Field(
                description="Exact dated Markdown records preserving observed paths",
            ),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_evidence_files(self) -> Self:
            files = self.historical_evidence_files
            if len(set(files)) != len(files):
                msg = "historical evidence files must be unique"
                raise ValueError(msg)
            for path in files:
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not path.parts
                    or path.parts[0] != FlextInfraConstantsSharedInfra.DIR_DOCS
                    or path.suffix != ".md"
                ):
                    msg = (
                        "historical evidence must be "
                        f"an exact docs Markdown file: {path}"
                    )
                    raise ValueError(msg)
            return self

    class DocsAuditPolicySpec(DocsAuditOverridesSpec):
        """Complete rendered documentation policy accepted by the auditor."""

        placeholder_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Regexes recognizing unfinished document markers"),
        ] = ()
        forbidden_terms: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Literal terms forbidden in current documentation"),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_patterns(self) -> Self:
            for pattern in self.placeholder_patterns:
                re.compile(pattern)
            return self

    BeadsEndpointSpec = FlextInfraModelsMiseToolchain.BeadsEndpointSpec
    BeadsToolSpec = FlextInfraModelsMiseToolchain.BeadsToolSpec
    MiseBootstrapEnvironmentSpec = (
        FlextInfraModelsMiseToolchain.MiseBootstrapEnvironmentSpec
    )
    ToolchainSpec = FlextInfraModelsMiseToolchain.ToolchainSpec
