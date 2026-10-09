"""Offline validation for generated Mise declarations and launchers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, override

from flext_infra import c, m, r, t, u
from flext_infra.codegen._execution import FlextInfraCodegenExecutionBase
from flext_infra.codegen._mise_artifacts_derivation import (
    FlextInfraMiseArtifactsDerivation,
)
from flext_infra.codegen.mise_artifacts_workspace import FlextInfraMiseWorkspacePlanner

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenMiseArtifacts(FlextInfraCodegenExecutionBase[bool]):
    """Validate latest-selector Mise declarations and the upg-written launchers."""

    config_only: Annotated[
        bool,
        m.Field(
            default=False,
            alias="config-only",
            description=(
                "Validate the generated Mise payload before any tool-owned effect"
            ),
        ),
    ] = False

    @staticmethod
    def _read_toml(path: Path) -> p.Result[t.JsonMapping]:
        source = u.Cli.files_read_text(path)
        if source.failure:
            return r[t.JsonMapping].from_failure(source)
        payload = u.Cli.toml_mapping_from_text(source.value)
        if payload is None:
            return r[t.JsonMapping].fail(f"invalid TOML in {path.name}")
        return r[t.JsonMapping].ok(payload)

    @staticmethod
    def _tool_version(raw_tool: t.JsonValue) -> str | None:
        """Return one version selector from either supported Mise tool shape.

        Returns:
            One version selector from either supported Mise tool shape.

        """
        candidate = (
            raw_tool.get("version") if isinstance(raw_tool, Mapping) else raw_tool
        )
        return candidate.strip() if isinstance(candidate, str) else None

    @classmethod
    def _tool_specifiers(cls, payload: t.JsonMapping) -> p.Result[t.StrMapping]:
        raw_tools = payload.get("tools")
        if not isinstance(raw_tools, Mapping):
            return r[t.StrMapping].fail(".mise.toml must declare [tools]")
        specifiers: MutableMapping[str, str] = {}
        for raw_selector, raw_tool in raw_tools.items():
            if not raw_selector.strip():
                return r[t.StrMapping].fail(".mise.toml contains an invalid tool name")
            selector = raw_selector.strip()
            version = cls._tool_version(raw_tool)
            if not version:
                return r[t.StrMapping].fail(
                    f".mise.toml tool lacks a version selector: {selector}",
                )
            specifiers[selector] = version
        if not specifiers:
            return r[t.StrMapping].fail(".mise.toml must declare at least one tool")
        return r[t.StrMapping].ok(specifiers)

    @staticmethod
    def _validate_selector_integrity(configured_tools: t.StrMapping) -> p.Result[bool]:
        """Reject a lockfile annotation leaking into a ``.mise.toml`` selector.

        A generated selector is the declared release; the ``~<hash>`` fragment
        belongs to the lockfile's cache key (``aube.path``). Copied into the
        selector it makes ``mise install`` fail with "not in the lockfile" and
        aborts the fleet's ``make setup`` before any verb can run.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        annotated = tuple(
            f"{selector}={version}"
            for selector, version in sorted(configured_tools.items())
            if c.Infra.MISE_LOCK_ANNOTATION in version
        )
        if annotated:
            return r[bool].fail(
                "Mise payload carries a lockfile annotation in the selector: "
                f"{', '.join(annotated)}",
            )
        return r[bool].ok(value=True)

    @classmethod
    def _validate_config(cls, project_root: Path) -> p.Result[bool]:
        """Validate the generated ``.mise.toml`` declaration offline.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        config_result = cls._read_toml(project_root / c.Infra.CONFIG_SPEC[0])
        if config_result.failure:
            return r[bool].from_failure(config_result)
        tools_result = cls._tool_specifiers(config_result.value)
        if tools_result.failure:
            return r[bool].from_failure(tools_result)
        return cls._validate_selector_integrity(tools_result.value)

    def validate_artifacts(
        self,
        project_root: Path,
        runtime_root: Path,
    ) -> p.Result[bool]:
        """Validate one project's declaration, pin, and launchers offline.

        The pin and launchers derive from the runtime root's `make upg`
        output: every launcher bakes the pinned release, and a member's triple
        is byte-identical to its runtime root's.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        declared = self._validate_config(project_root)
        if declared.failure:
            return declared
        return FlextInfraMiseArtifactsDerivation.validate(project_root, runtime_root)

    @override
    def execute(self) -> p.Result[bool]:
        """Validate generated Mise declarations and launchers entirely offline.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        declared = self._validate_config(self.repository_root)
        if declared.failure or self.config_only:
            return declared
        runtime_root = FlextInfraMiseWorkspacePlanner(self).scope_root()
        if runtime_root.failure:
            return r[bool].from_failure(runtime_root)
        return FlextInfraMiseArtifactsDerivation.validate(
            self.repository_root,
            runtime_root.value,
        )


__all__: list[str] = ["FlextInfraCodegenMiseArtifacts"]
