"""FLEXT mypy quality gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, config, m, t, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraMypyGate(FlextInfraGate):
    """Gate for Mypy type checking."""

    gate_id: ClassVar[str] = c.Infra.MYPY
    gate_name: ClassVar[str] = "Mypy"
    can_fix: ClassVar[bool] = False
    checker_info_prefixes: ClassVar[t.StrSequence] = (
        "LOG:",
        "TRACE:",
        "[pydantic-mypy]:",
    )

    @staticmethod
    def _config_exclude(config_path: Path) -> re.Pattern[str] | None:
        """Return the compiled [tool.mypy].exclude regex, if configured.

        Returns:
            The compiled [tool.mypy].exclude regex, if configured.

        """
        doc = u.Cli.toml_read(config_path)
        if doc is None:
            return None
        tool_table = u.Cli.toml_table_child(doc, c.Infra.TOOL)
        if tool_table is None:
            return None
        mypy_table = u.Cli.toml_table_child(tool_table, c.Infra.MYPY)
        if mypy_table is None:
            return None
        exclude = mypy_table.get("exclude")
        if not isinstance(exclude, str) or not exclude:
            return None
        return re.compile(exclude)

    @staticmethod
    def _has_real_module(directory: Path) -> bool:
        """True when the dir holds a Python module other than __init__.py.

        Returns:
            The resulting ``bool``.

        """
        for py_file in directory.rglob(c.Infra.EXT_PYTHON_GLOB):
            if py_file.name != c.Infra.INIT_PY:
                return True
        return any(directory.rglob("*.pyi"))

    @override
    def _get_check_dirs(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.StrSequence:
        """Check local Python roots directly instead of recursively scanning ``.``.

        Returns:
            The resulting ``t.StrSequence``.

        """
        # Empty or explicitly excluded roots are omitted because Mypy aborts
        # when they are passed positionally.
        exclude = self._config_exclude(self._resolve_config(project_dir, ctx))
        discovered_dirs = [
            directory
            for directory in self._dirs_with_py(
                project_dir,
                config.Infra.source_scan.roots,
            )
            if self._has_real_module(project_dir / directory)
            and (exclude is None or not exclude.match(f"{directory}/"))
        ]
        root_files = [
            path.name
            for path in sorted(project_dir.iterdir())
            if path.is_file() and path.suffix in {".py", ".pyi"}
        ]
        if discovered_dirs or root_files:
            return [*discovered_dirs, *root_files]
        return []

    @staticmethod
    def _resolve_config(project_dir: Path, ctx: m.Infra.GateContext) -> Path:
        """Resolve Mypy settings from the project, then the workspace.

        Returns:
            The resulting ``Path``.

        """
        pyproject_name: str = c.PYPROJECT_FILENAME
        proj_py = project_dir / pyproject_name
        doc = u.Cli.toml_read(proj_py)
        if doc is not None:
            tool_table = u.Cli.toml_table_child(doc, c.Infra.TOOL)
            if (
                tool_table is not None
                and u.Cli.toml_table_child(tool_table, c.Infra.MYPY) is not None
            ):
                return proj_py
        repository_root: Path = ctx.repository_root
        return repository_root / pyproject_name

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Build check command.

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            ValueError: If Mypy profile output requires an absolute path in an existing
                directory.

        """
        cfg = self._resolve_config(project_dir, ctx)
        machine_report = self._machine_report_path(project_dir, ctx)
        # The report file belongs to exactly one run: a stale receipt from a
        # previous invocation must never masquerade as this run's diagnostics.
        machine_report.unlink(missing_ok=True)
        profile_output = u.Cli.process_env().get(c.Infra.MYPY_PROFILE_OUTPUT_ENV)
        destination = None
        if profile_output is not None:
            destination = Path(profile_output)
            if not destination.is_absolute() or not destination.parent.is_dir():
                msg = (
                    "Mypy profile output requires an absolute path "
                    "in an existing directory"
                )
                raise ValueError(msg)
        return u.Infra.mypy_limited_command(
            m.Infra.MypyInvocation(
                targets=tuple(project_dir / target for target in check_dirs),
                config_file=cfg,
                report_json=True,
                profile_output=destination,
                report_file=machine_report,
            ),
        )

    @staticmethod
    def _machine_report_path(project_dir: Path, ctx: m.Infra.GateContext) -> Path:
        """Name the owned file receiving the machine-channel JSON diagnostics.

        Returns:
            The resulting ``Path``.

        """
        return (
            ctx.reports_dir / f"{project_dir.name}-{c.Infra.MYPY}-machine-report.jsonl"
        )

    @override
    def _validate_check_report(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        targets: t.StrSequence,
    ) -> None:
        """Account for every submitted target from Mypy's native build trace.

        Raises:
            TypeError: If Mypy native source path is not a string.
            ValueError: If Mypy native build trace contains no selected sources; or if
                Mypy native build trace lacks completion evidence; or if Malformed Mypy
                native source entry; or if Mypy native report did not account for
                target; or if Mypy native report contains an unsubmitted source.

        """
        _ = ctx
        source_lines = (
            line for line in result.stderr.splitlines() if "Found source:" in line
        )
        sources: list[Path] = []
        for line in source_lines:
            match = re.search(r"Found source:\s+BuildSource\(path=(.+?), module=", line)
            if match is None:
                msg = f"Malformed Mypy native source entry: {line}"
                raise ValueError(msg)
            raw_path = ast.literal_eval(match.group(1))
            if not isinstance(raw_path, str):
                msg = f"Mypy native source path is not a string: {line}"
                raise TypeError(msg)
            sources.append((project_dir / raw_path).resolve())
        if not sources:
            msg = "Mypy native build trace contains no selected sources"
            raise ValueError(msg)
        if not any("Build finished in " in line for line in result.stderr.splitlines()):
            msg = "Mypy native build trace lacks completion evidence"
            raise ValueError(msg)
        submitted = tuple((project_dir / target).resolve() for target in targets)
        for target in submitted:
            if not any(
                source == target or (target.is_dir() and source.is_relative_to(target))
                for source in sources
            ):
                msg = f"Mypy native report did not account for target: {target}"
                raise ValueError(msg)
        for source in sources:
            if not any(
                source == target or (target.is_dir() and source.is_relative_to(target))
                for target in submitted
            ):
                msg = f"Mypy native report contains an unsubmitted source: {source}"
                raise ValueError(msg)

    @override
    def _check_timeout(self, project_dir: Path, ctx: m.Infra.GateContext) -> int:
        """Keep the outer runner alive through the controlled Mypy deadline.

        Returns:
            The resulting ``int``.

        """
        _ = ctx
        return u.Infra.mypy_runner_timeout_for_project(project_dir)

    @override
    def _check_env(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.StrMapping | None:
        """Run Mypy against the project's shared analysis cache.

        Returns:
            The resulting ``t.StrMapping | None``.

        """
        overrides = {
            c.Infra.MypyCacheEnvironment.CACHE_DIR.value: str(
                u.Infra.mypy_cache_directory(project_dir),
            ),
        }
        typings_generated = ctx.repository_root / c.Infra.DIR_TYPINGS / "generated"
        if typings_generated.is_dir():
            existing = u.Cli.process_env().get("MYPYPATH", "")
            overrides["MYPYPATH"] = str(typings_generated) + (
                f":{existing}" if existing else ""
            )
        return u.Cli.process_env(overrides=overrides)

    @override
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse check output.

        The machine channel is the owned report file the report runner wrote:
        every diagnostic line is a JSON object there, whatever the checker
        release shares its standard-output stream with. Without the file the
        standard output remains the channel, and its verbose progress lines
        stay the tool's own human stream, never diagnostics.

        Returns:
            The resulting ``t.Pair[bool, t.SequenceOf[m.Infra.Issue]]``.

        """
        _ = ctx
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        if resource_diagnostic := u.Infra.mypy_failure_diagnostic(result):
            return (
                False,
                (
                    m.Infra.Issue(
                        file=c.PYPROJECT_FILENAME,
                        line=1,
                        column=1,
                        code="mypy-resource-limit",
                        message=resource_diagnostic,
                        severity=c.Infra.ERROR,
                    ),
                ),
            )
        machine_report = self._machine_report_path(project_dir, ctx)
        report_lines: t.StrSequence = (
            machine_report.read_text(encoding=c.Cli.ENCODING_DEFAULT).splitlines()
            if machine_report.is_file()
            else result.stdout.splitlines()
        )
        for raw_line in report_lines:
            if not raw_line.strip():
                continue
            if not machine_report.is_file() and raw_line.startswith("LOG:"):
                # Mypy verbose progress channel (--verbose runs). LOG lines are
                # the tool's own human stream, never diagnostics; the machine
                # contract of this gate is one JSON object per line.
                continue
            validated: p.Result[m.Infra.MypyDiagnostic] = u.validate_value(
                m.Infra.MypyDiagnostic,
                raw_line,
                from_json=True,
                strict=True,
            )
            if validated.failure:
                return False, (
                    self._malformed_report_issue(
                        f"{validated.error}\nstdout: {raw_line}\n"
                        f"stderr: {result.stderr}",
                        tool=c.Infra.MYPY,
                        file=str(project_dir),
                    ),
                )
            diagnostic = validated.value
            issues.append(
                m.Infra.Issue(
                    file=diagnostic.file,
                    line=diagnostic.line,
                    column=diagnostic.column,
                    code=diagnostic.code or "",
                    message=(
                        f"{diagnostic.message}\n{diagnostic.hint}"
                        if diagnostic.hint
                        else diagnostic.message
                    ),
                    severity=diagnostic.severity,
                ),
            )
        issues.extend(self._checker_stderr_issues(result, project_dir))
        if (not issues) and not u.Cli.process_succeeded(result.outcome):
            message = (result.stderr or result.stdout).strip()
            if not message:
                message = (
                    f"mypy exited with code {result.outcome.raw_return_code} "
                    f"without JSON diagnostics"
                )
            issues.append(
                m.Infra.Issue(
                    file=c.PYPROJECT_FILENAME,
                    line=1,
                    column=1,
                    code="mypy-exec",
                    message=message,
                    severity=c.Infra.ERROR,
                ),
            )
        return (
            u.Cli.process_succeeded(result.outcome)
            and not any(issue.severity.lower() == "error" for issue in issues),
            issues,
        )


__all__: list[str] = ["FlextInfraMypyGate"]
