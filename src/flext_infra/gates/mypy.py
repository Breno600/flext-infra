"""FLEXT mypy quality gate."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, t, u

from .base_gate import FlextInfraGate

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
        """Return the compiled [tool.mypy].exclude regex, if configured."""
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
        """True when the dir holds a Python module other than __init__.py."""
        for py_file in directory.rglob(c.Infra.EXT_PYTHON_GLOB):
            if py_file.name != c.Infra.INIT_PY:
                return True
        return any(directory.rglob("*.pyi"))

    @override
    def _get_check_dirs(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Check local Python roots directly instead of recursively scanning ``.``."""
        # Empty or explicitly excluded roots are omitted because Mypy aborts
        # when they are passed positionally.
        exclude = self._config_exclude(self._resolve_config(project_dir, ctx))
        discovered_dirs = [
            directory
            for directory in self._dirs_with_py(
                project_dir, c.Infra.CHECK_DIRS_REPOSITORY
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

    def _resolve_config(self, project_dir: Path, ctx: m.Infra.GateContext) -> Path:
        """Resolve Mypy settings from the project, then the workspace."""
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
        self, project_dir: Path, ctx: m.Infra.GateContext, check_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Build check command."""
        cfg = self._resolve_config(project_dir, ctx)
        return u.Infra.mypy_limited_command(
            self._python_module_command(
                c.Infra.MYPY,
                *check_dirs,
                "--config-file",
                str(cfg),
                "--output",
                c.Infra.OUTPUT_JSON,
                "--no-error-summary",
                "--no-color-output",
                "--linecoverage-report",
                str(self._check_report_path(project_dir, ctx).parent),
            )
        )

    @override
    def _check_report_path(self, project_dir: Path, ctx: m.Infra.GateContext) -> Path:
        """Keep Mypy's native source inventory within the existing report root."""
        return ctx.reports_dir / f"{project_dir.name}-mypy" / "coverage.json"

    @override
    def _validate_check_report(
        self, project_dir: Path, ctx: m.Infra.GateContext, targets: t.StrSequence
    ) -> None:
        """Account for every submitted target using Mypy's native source set."""
        report = m.Infra.MypyCoverageReport.model_validate_json(
            self._check_report_path(project_dir, ctx).read_text(encoding="utf-8"),
            strict=True,
        )
        sources = tuple(Path(source).resolve() for source in report.lines)
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
        """Keep the outer runner alive through the controlled Mypy deadline."""
        _ = project_dir, ctx
        return u.Infra.mypy_runner_timeout()

    @override
    def _check_env(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrMapping | None:
        """Check env."""
        _ = project_dir
        typings_generated = ctx.repository_root / c.Infra.DIR_TYPINGS / "generated"
        if not typings_generated.is_dir():
            return None
        base_env = u.Cli.process_env()
        existing = base_env.get("MYPYPATH", "")
        mypy_path = str(typings_generated) + (f":{existing}" if existing else "")
        return u.Cli.process_env(overrides={"MYPYPATH": mypy_path})

    @override
    def _parse_check_output(
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse check output."""
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
        for raw_line in result.stdout.splitlines():
            if not raw_line.strip():
                continue
            validated: p.Result[m.Infra.MypyDiagnostic] = u.validate_value(
                m.Infra.MypyDiagnostic, raw_line, from_json=True, strict=True
            )
            if validated.failure:
                return False, (
                    self._malformed_report_issue(
                        f"{validated.error}\nstdout: {raw_line}\nstderr: {result.stderr}",
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
                )
            )
        issues.extend(self._checker_stderr_issues(result, project_dir))
        if (not issues) and not u.Cli.process_succeeded(result.outcome):
            message = (result.stderr or result.stdout).strip()
            if not message:
                message = f"mypy exited with code {result.outcome.raw_return_code} without JSON diagnostics"
            issues.append(
                m.Infra.Issue(
                    file=c.PYPROJECT_FILENAME,
                    line=1,
                    column=1,
                    code="mypy-exec",
                    message=message,
                    severity=c.Infra.ERROR,
                )
            )
        return (
            u.Cli.process_succeeded(result.outcome)
            and not any(issue.severity.lower() == "error" for issue in issues),
            issues,
        )


__all__: list[str] = ["FlextInfraMypyGate"]
