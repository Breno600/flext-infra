"""Validated process resource-limit command builders.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import platform
import shutil
import sys
from pathlib import Path
from typing import ClassVar

from flext_cli import u

from flext_infra import c, config, m, p, t
from flext_infra._settings import settings
from flext_infra._utilities import (
    FlextInfraUtilitiesProcess,
    FlextInfraUtilitiesProjectDiscovery,
    FlextInfraUtilitiesPyproject,
)


class FlextInfraUtilitiesResourceLimits:
    """Build resource-bounded commands for memory-intensive quality tools."""

    _MEMORY_FAILURE_MARKERS: ClassVar[t.VariadicTuple[str]] = (
        "cannot allocate memory",
        "failed to map segment",
        "memoryerror",
        "out of memory",
    )

    @staticmethod
    def _required_executable(command: str) -> str:
        """Resolve one required resource-control executable or fail loud.

        Returns:
            The resulting ``str``.

        Raises:
            RuntimeError: If required executable not found.

        """
        executable = shutil.which(command)
        if executable is None:
            msg = f"required executable not found: {command}"
            raise RuntimeError(msg)
        return executable

    @staticmethod
    def _environment_integer(process_env: t.StrMapping, name: str, default: int) -> int:
        """Convert one ASCII integer environment value at the ingress boundary.

        Returns:
            The resulting ``int``.

        Raises:
            ValueError: If ``not raw_value.isascii() or not raw_value.isdecimal()``.

        """
        raw_value = process_env.get(name)
        if raw_value is None:
            return default
        if not raw_value.isascii() or not raw_value.isdecimal():
            msg = f"{name} must be a positive integer"
            raise ValueError(msg)
        return int(raw_value)

    @staticmethod
    def mypy_resource_limit() -> m.Infra.MypyResourceLimit:
        """Validate the external Mypy memory and time settings exactly once.

        The wall-time budget is ``tools.mypy.timeout_seconds`` in the
        ``tooling.yaml`` SSOT; no environment variable can change it.

        Returns:
            The resulting ``m.Infra.MypyResourceLimit``.

        """
        return m.Infra.MypyResourceLimit(
            memory_limit_mb=FlextInfraUtilitiesResourceLimits._environment_integer(
                u.Cli.process_env(),
                c.Infra.MYPY_MEMORY_LIMIT_MB_ENV,
                c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            ),
            timeout_seconds=config.Infra.tooling.tools.mypy.timeout_seconds,
        )

    @staticmethod
    def mypy_arguments(invocation: m.Infra.MypyInvocation) -> t.StrSequence:
        """Build checker options shared by the CLI and public profiling API.

        Returns:
            The resulting ``t.StrSequence``.

        """
        return (
            *(
                ("--config-file", str(invocation.config_file.resolve()))
                if invocation.config_file is not None
                else ()
            ),
            "--no-error-summary",
            "--no-color-output",
            *(("--output", c.Infra.OUTPUT_JSON) if invocation.report_json else ()),
            *(("--verbose",) if invocation.verbose else ()),
            "--",
            *(str(target.resolve()) for target in invocation.targets),
        )

    @staticmethod
    def mypy_command(invocation: m.Infra.MypyInvocation) -> t.StrSequence:
        """Construct the owned checker entrypoint from typed data, never command text.

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            FileNotFoundError: If managed workspace interpreter is missing; or if
                managed workspace checker is missing.

        """
        interpreter = sys.executable
        if invocation.workspace is not None:
            managed_python = FlextInfraUtilitiesProjectDiscovery.runtime_python(
                invocation.workspace,
            )
            if not managed_python.is_file():
                msg = f"managed workspace interpreter is missing: {managed_python}"
                raise FileNotFoundError(msg)
            interpreter = str(managed_python)
            if invocation.profile_output is None:
                managed_mypy = managed_python.with_name(
                    f"{c.Infra.MYPY}.exe" if sys.platform == "win32" else c.Infra.MYPY,
                )
                if not managed_mypy.is_file():
                    msg = f"managed workspace checker is missing: {managed_mypy}"
                    raise FileNotFoundError(msg)
                return (
                    str(managed_mypy),
                    *FlextInfraUtilitiesResourceLimits.mypy_arguments(invocation),
                )
        if invocation.profile_output is not None:
            return (
                interpreter,
                "-m",
                f"{__package__}._mypy_profile",
                invocation.model_dump_json(),
            )
        return (
            interpreter,
            "-m",
            c.Infra.MYPY,
            *FlextInfraUtilitiesResourceLimits.mypy_arguments(invocation),
        )

    @staticmethod
    def mypy_cache_directory(project_dir: Path) -> Path:
        """Resolve the one shared Mypy cache of a project across relocks.

        Mypy keys its cache by module and revalidates each entry by source hash,
        so every checkout and every relock of one project reuse one analysis: a
        dependency bump recomputes only the modules it changed. Keying by lock
        content forced a cold full-fleet analysis after every
        relock and broke the bounded Mypy run. Projects keep distinct
        directories because their ``tests`` packages share one module name.

        Returns:
            The resulting ``Path``.

        Raises:
            ValueError: If ``metadata.failure``.

        """
        metadata = FlextInfraUtilitiesPyproject.read_project_metadata_result(
            project_dir,
        )
        if metadata.failure:
            msg = metadata.error or f"project metadata unreadable: {project_dir}"
            raise ValueError(msg)
        return (
            FlextInfraUtilitiesResourceLimits.external_cache_directory(
                config.Infra.codegen.make.mypy_cache,
            )
            / metadata.value.project.name
        )

    @staticmethod
    def external_cache_directory(
        spec: m.Infra.MypyCacheSpec
        | m.Infra.MakeSpec.MypyCacheSpec
        | m.Infra.MakeSpec.CodemodRulesCacheSpec,
    ) -> Path:
        """Resolve one declared FLEXT cache below the XDG cache home.

        Returns:
            ``$XDG_CACHE_HOME`` (or ``$HOME`` plus the home cache directory)
            joined with the spec's FLEXT-owned storage directory.

        """
        home = settings.env_lookup(str(spec.data_home_environment_variable)) or str(
            Path(settings.env_required(str(spec.user_home_environment_variable)))
            / spec.home_cache_directory,
        )
        return Path(home) / spec.external_storage_directory

    @staticmethod
    def mypy_limited_command(
        invocation: m.Infra.MypyInvocation,
        limit: m.Infra.MypyResourceLimit | None = None,
        *,
        host_system: str | None = None,
    ) -> t.StrSequence:
        """Bound the canonical checker; no caller-provided executable can run.

        Returns:
            The resulting ``t.StrSequence``.

        """
        validated_limit = (
            limit or FlextInfraUtilitiesResourceLimits.mypy_resource_limit()
        )
        if (host_system or platform.system()) == "Darwin":
            return (
                sys.executable,
                "-m",
                f"{__package__}._mypy_supervisor",
                str(validated_limit.memory_limit_bytes),
                str(validated_limit.timeout_seconds),
                str(c.Infra.TIMEOUT_KILL_AFTER_SECONDS),
                invocation.model_dump_json(),
            )
        prlimit_executable = FlextInfraUtilitiesResourceLimits._required_executable(
            c.Infra.PRLIMIT_COMMAND,
        )
        timeout_executable = FlextInfraUtilitiesResourceLimits._required_executable(
            c.Infra.TIMEOUT_COMMAND,
        )
        return (
            timeout_executable,
            "--signal=TERM",
            f"--kill-after={c.Infra.TIMEOUT_KILL_AFTER_SECONDS}s",
            f"{validated_limit.timeout_seconds}s",
            prlimit_executable,
            (
                f"{c.Infra.PRLIMIT_ADDRESS_SPACE_OPTION}="
                f"{validated_limit.memory_limit_bytes}:"
                f"{validated_limit.memory_limit_bytes}"
            ),
            "--",
            *FlextInfraUtilitiesResourceLimits.mypy_command(invocation),
        )

    @staticmethod
    def mypy_runner_timeout(limit: m.Infra.MypyResourceLimit | None = None) -> int:
        """Return the outer runner timeout after the controlled child deadline.

        Returns:
            The outer runner timeout after the controlled child deadline.

        """
        validated_limit = (
            limit or FlextInfraUtilitiesResourceLimits.mypy_resource_limit()
        )
        timeout_seconds: int = (
            validated_limit.timeout_seconds + c.Infra.MYPY_TIMEOUT_GRACE_SECONDS
        )
        return timeout_seconds

    @classmethod
    def mypy_runner_timeout_for_project(cls, project_dir: Path) -> int:
        """Runner timeout honoring the project ``config/tooling.yaml`` budget.

        A project budget may only lower the fleet ``tools.mypy.timeout_seconds``
        bound; a budget above it fails loud.

        Returns:
            The resulting ``int``.

        Raises:
            ValueError: If project mypy budget.

        """
        limit = cls.mypy_resource_limit()
        budget = cls._project_mypy_budget(project_dir)
        if budget is not None:
            if budget > limit.timeout_seconds:
                msg = (
                    f"project mypy budget {budget}s exceeds the fleet bound "
                    f"tools.mypy.timeout_seconds={limit.timeout_seconds}s"
                )
                raise ValueError(msg)
            limit = m.Infra.MypyResourceLimit(
                memory_limit_mb=limit.memory_limit_mb,
                timeout_seconds=budget,
            )
        return cls.mypy_runner_timeout(limit)

    @staticmethod
    def _project_mypy_budget(project_dir: Path) -> int | None:
        """Read ``Infra.tooling.tools.mypy.timeout_seconds`` from the overlay.

        The overlay has the same nesting as the packaged ``tooling.yaml``. A
        level the overlay does not declare is a typed absence (no project
        budget); a declared level that is not a mapping fails loud.

        Returns:
            The resulting ``int | None``.

        Raises:
            TypeError: If project mypy budget must be a plain integer; or if project
                tooling.yaml level above.

        """
        tooling = project_dir / "config" / "tooling.yaml"
        if not tooling.is_file():
            return None
        loaded: t.JsonMapping = u.Cli.yaml_safe_load(tooling).unwrap()
        current: t.JsonValue = dict(loaded)
        for key in ("Infra", "tooling", "tools", "mypy", "timeout_seconds"):
            if not isinstance(current, dict):
                msg = f"project tooling.yaml level above {key!r} is not a mapping"
                raise TypeError(msg)
            if key not in current:
                return None
            current = current[key]
        raw_budget = current
        if not isinstance(raw_budget, int) or isinstance(raw_budget, bool):
            msg = f"project mypy budget must be a plain integer: {raw_budget!r}"
            raise TypeError(msg)
        return raw_budget

    @staticmethod
    def _bounded_mypy_diagnostic(
        limit: m.Infra.MypyResourceLimit,
        *,
        detail: str,
        exit_code: int | str,
        signal: int | str,
    ) -> str:
        """Render the single controlled Mypy resource-failure diagnostic.

        Returns:
            The resulting ``str``.

        """
        return (
            "bounded Mypy execution failed: "
            f"memory_limit={limit.memory_limit_mb} MiB; "
            f"timeout={limit.timeout_seconds}s; "
            f"exit={exit_code}; signal={signal}; detail={detail}"
        )

    @classmethod
    def mypy_launch_failure_diagnostic(
        cls,
        detail: str,
        limit: m.Infra.MypyResourceLimit | None = None,
    ) -> str:
        """Report an outer-runner failure that precluded a process exit status.

        Returns:
            The resulting ``str``.

        """
        validated_limit = limit or cls.mypy_resource_limit()
        return cls._bounded_mypy_diagnostic(
            validated_limit,
            detail=detail,
            exit_code="unavailable",
            signal="none",
        )

    @classmethod
    def mypy_failure_diagnostic(
        cls,
        output: p.Cli.CommandOutput,
        limit: m.Infra.MypyResourceLimit | None = None,
    ) -> str | None:
        """Return a controlled diagnostic only for timeout or memory exhaustion.

        Returns:
            A controlled diagnostic only for timeout or memory exhaustion.

        """
        validated_limit = limit or cls.mypy_resource_limit()
        combined = f"{output.stdout}\n{output.stderr}".lower()
        classification = FlextInfraUtilitiesProcess.process_exit_classification(
            output.outcome.raw_return_code,
        )
        resource_failure = classification != "failure" or any(
            marker in combined for marker in cls._MEMORY_FAILURE_MARKERS
        )
        if not resource_failure:
            return None
        signal = (
            classification.removeprefix("signal=")
            if classification.startswith("signal=")
            else "none"
        )
        detail = (
            "\n".join(
                stream.strip()
                for stream in (output.stdout, output.stderr)
                if stream.strip()
            )
            or "resource limit reached"
        )
        return cls._bounded_mypy_diagnostic(
            validated_limit,
            detail=detail,
            exit_code=output.outcome.raw_return_code,
            signal=signal,
        )


__all__: list[str] = ["FlextInfraUtilitiesResourceLimits"]
