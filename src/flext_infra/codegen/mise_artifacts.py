"""Offline validation for generated Mise declarations and launchers."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, override

from flext_core import r

from .. import c, config, m, t, u
from ._execution import FlextInfraCodegenExecutionBase

if TYPE_CHECKING:
    from .. import p


class FlextInfraCodegenMiseArtifacts(FlextInfraCodegenExecutionBase[bool]):
    """Validate latest-selector Mise declarations and the bootstrap launchers."""

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
        """Return one version selector from either supported Mise tool shape."""
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
                    f".mise.toml tool lacks a version selector: {selector}"
                )
            specifiers[selector] = version
        if not specifiers:
            return r[t.StrMapping].fail(".mise.toml must declare at least one tool")
        return r[t.StrMapping].ok(specifiers)

    @staticmethod
    def _validate_suspended_selectors(configured_tools: t.StrMapping) -> p.Result[bool]:
        """Reject dormant capabilities before download or publication."""
        patterns = config.Infra.codegen.toolchain.suspended_mise_selector_patterns
        suspended = tuple(
            selector
            for selector in configured_tools
            if any(fnmatchcase(selector, pattern) for pattern in patterns)
        )
        if suspended:
            return r[bool].fail(
                "Mise payload selects a suspended toolchain: "
                f"{', '.join(sorted(suspended))}"
            )
        return r[bool].ok(True)

    @classmethod
    def validate_seed(cls, path: Path) -> p.Result[bool]:
        """Validate one native staged bootstrap seed without executing live bytes."""
        source = u.Cli.files_read_text(path)
        if source.failure:
            return r[bool].from_failure(source)
        content = source.value
        for declaration in (
            c.Infra.MISE_UNLOCKED_RESOLUTION_URL,
            c.Infra.MISE_UNLOCKED_FAIL_LOUD_CLAUSE,
            c.Infra.MISE_UNLOCKED_CHECKSUM_URI,
        ):
            if declaration not in content:
                return r[bool].fail(
                    f"Mise seed lacks the unlocked resolution contract "
                    f"({declaration}): {path}"
                )
        try:
            mode = path.stat().st_mode
        except OSError as exc:
            return r[bool].fail(
                f"cannot inspect generated Mise seed: {exc}", exception=exc
            )
        windows = path.name == c.Infra.MISE_WINDOWS_LAUNCHER_FILENAME
        if not windows and not mode & 0o100:
            return r[bool].fail("generated Unix Mise seed is not executable")
        return r[bool].ok(True)

    @classmethod
    def validate_launchers(cls, root: Path) -> p.Result[bool]:
        """Validate both generated launchers and their identical contract."""
        shell = cls.validate_seed(
            root / c.Infra.MISE_LAUNCHER_DIRECTORY / c.Infra.MISE_UNIX_LAUNCHER_FILENAME
        )
        windows = cls.validate_seed(
            root
            / c.Infra.MISE_LAUNCHER_DIRECTORY
            / c.Infra.MISE_WINDOWS_LAUNCHER_FILENAME
        )
        if shell.failure or windows.failure:
            return (
                r[bool].from_failure(shell)
                if shell.failure
                else r[bool].from_failure(windows)
            )
        return r[bool].ok(True)

    def validate_artifacts(self, project_root: Path) -> p.Result[bool]:
        """Validate one project's committed Mise artifacts entirely offline."""
        config_result = self._read_toml(project_root / ".mise.toml")
        if config_result.failure:
            return r[bool].from_failure(config_result)
        tools_result = self._tool_specifiers(config_result.value)
        if tools_result.failure:
            return r[bool].from_failure(tools_result)
        suspended = self._validate_suspended_selectors(tools_result.value)
        if suspended.failure:
            return suspended
        launcher_result = self.validate_launchers(project_root)
        if launcher_result.failure:
            return launcher_result
        return r[bool].ok(True)

    @override
    def execute(self) -> p.Result[bool]:
        """Validate generated Mise declarations and launchers entirely offline."""
        config_result = self._read_toml(self.repository_root / ".mise.toml")
        if config_result.failure:
            return r[bool].from_failure(config_result)
        tools_result = self._tool_specifiers(config_result.value)
        if tools_result.failure:
            return r[bool].from_failure(tools_result)
        suspended = self._validate_suspended_selectors(tools_result.value)
        if suspended.failure:
            return suspended
        if self.config_only:
            return r[bool].ok(True)
        launcher_result = self.validate_launchers(self.repository_root)
        if launcher_result.failure:
            return launcher_result
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraCodegenMiseArtifacts"]
