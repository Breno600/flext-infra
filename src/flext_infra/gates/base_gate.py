"""Shared gate template abstraction for workspace quality checks."""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraGate:
    """Abstract template implementing common check/fix execution flow for gates."""

    gate_id: ClassVar[str] = ""
    gate_name: ClassVar[str] = ""
    can_fix: ClassVar[bool] = False
    # A gate whose check command is one fixed ``python -m`` invocation wrapped
    # around its resolved check dirs declares the invocation here instead of
    # restating the ``_build_check_command`` override.
    check_module_command_prefix: ClassVar[t.StrSequence] = ()
    check_module_command_suffix: ClassVar[t.StrSequence] = ()
    # Name of the external scanner a gate provisions on PATH, when it uses one.
    scanner_binary: ClassVar[str] = ""
    checker_info_prefixes: ClassVar[t.StrSequence] = ()

    def __init__(
        self, repository_root: Path, *, runner: p.Cli.CommandRunner | None = None
    ) -> None:
        """Bind repository root and optional command runner override."""
        self._repository_root = repository_root
        self._runner = runner

    @staticmethod
    def _python_module_command(module: str, *args: str) -> t.StrSequence:
        """Canonical venv-anchored tool invocation.

        Every linter/type-checker runs through the workspace interpreter
        (``sys.executable -m <module>``) so tool resolution is bound to the
        active ``.venv`` and never depends on ``PATH`` ordering or an external
        mise/system shim. This is the single source for building a Python
        module command shared by all gates.
        """
        return (sys.executable, "-m", module, *args)

    @staticmethod
    def _python_console_script_command(tool: str, *args: str) -> t.StrSequence:
        """Invoke a uv-managed console script from the active interpreter directory."""
        return (str(Path(sys.executable).with_name(tool)), *args)

    # ------------------------------------------------------------------
    # Template method: check
    # ------------------------------------------------------------------

    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Template method: timing + dirs + skip + run + parse + result."""
        started = time.monotonic()
        check_dirs = self._get_check_dirs(project_dir, ctx)
        if not check_dirs:
            return self._empty_targets_result(project_dir, started)
        return self._execute_check_command(project_dir, ctx, check_dirs, started)

    def _empty_targets_result(
        self, project_dir: Path, started: float
    ) -> m.Infra.GateExecution:
        """Outcome when a gate collects no check targets.

        Failing loud is the default: a selected gate with no inputs did not
        establish acceptance. A gate whose targets are conditional on the
        project topology (absent by declared design, not by accident)
        overrides this with a neutral skip naming the condition.
        """
        return self._skip_result(project_dir, started)

    def check_files(
        self, files: t.SequenceOf[Path], project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Check specific files instead of whole directory.

        Passes file paths directly to the tool CLI for scoped validation.
        Falls back to directory check if no files provided.
        """
        if not files:
            return self.check(project_dir, ctx)
        started = time.monotonic()
        file_strs = [str(f.relative_to(project_dir)) for f in files if f.exists()]
        if not file_strs:
            return self._skip_result(project_dir, started)
        return self._execute_check_command(project_dir, ctx, file_strs, started)

    def _execute_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        targets: t.StrSequence,
        started: float,
    ) -> m.Infra.GateExecution:
        """Build, run, and parse the check command — shared by ``check`` and ``check_files``."""
        report_path = self._check_report_path(project_dir, ctx)
        if report_path is not None:
            report_path.unlink(missing_ok=True)
        cmd = self._build_check_command(project_dir, ctx, targets)
        result = self._run(
            cmd,
            project_dir,
            timeout=self._check_timeout(project_dir, ctx),
            env=self._check_env(project_dir, ctx),
            remove_env_keys=self._check_remove_env_keys(project_dir, ctx),
        )
        if u.Cli.process_succeeded(result.outcome):
            self._validate_check_report(project_dir, ctx, targets)
        return self._parsed_gate_execution(project_dir, ctx, result, started)

    @classmethod
    def _resolve_binary(cls) -> str | None:
        """Locate the provisioned scanner on PATH; None when absent."""
        return shutil.which(cls.scanner_binary)

    def _tool_failure_issue(self, scan: p.Cli.CommandOutput) -> m.Infra.Issue:
        """Scanner absence/crash must never read as a clean pass."""
        return m.Infra.Issue(
            file=c.PYPROJECT_FILENAME,
            line=1,
            column=0,
            code=self.gate_id,
            message=scan.stderr or f"{self.scanner_binary} execution failed",
            severity=str(c.Infra.GateSeverity.ERROR.value),
        )

    @staticmethod
    def _command_error_issue(
        result: p.Cli.CommandOutput, *, tool: str, file: str, line: int, column: int
    ) -> m.Infra.Issue:
        """Report an unsuccessful command that supplied no structured issues."""
        detail = (result.stderr or result.stdout).strip() or "no diagnostics"
        return m.Infra.Issue(
            file=file,
            line=line,
            column=column,
            code="TOOL_ERROR",
            message=f"{tool} exited with code {result.outcome.raw_return_code}: {detail}",
            severity="ERROR",
        )

    def _finalize_parse_result(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        issues: t.SequenceOf[m.Infra.Issue],
        tool: str,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Apply the standard tool-error fallback to parsed issues.

        If the tool exited unsuccessfully and no issues were parsed, synthesize a
        TOOL_ERROR issue so the failure is visible rather than silently passing.
        """
        if not u.Cli.process_succeeded(result.outcome) and not issues:
            issues = (
                *issues,
                self._command_error_issue(
                    result, tool=tool, file=str(project_dir), line=1, column=1
                ),
            )
        return u.Cli.process_succeeded(result.outcome), issues

    @staticmethod
    def _malformed_report_issue(detail: str, *, tool: str, file: str) -> m.Infra.Issue:
        """Report a checker whose structured report failed typed validation."""
        return m.Infra.Issue(
            file=file,
            line=0,
            column=0,
            code="TOOL_ERROR",
            message=f"{tool} report is not a valid structured report: {detail}",
            severity="ERROR",
        )

    def _checker_stderr_issues(
        self, result: p.Cli.CommandOutput, project_dir: Path
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Retain checker failures while accounting for native informational logs."""
        return tuple(
            m.Infra.Issue(
                file=str(project_dir),
                line=0,
                column=0,
                code=f"{self.gate_id}-stderr",
                message=line,
                severity="ERROR",
            )
            for line in result.stderr.splitlines()
            if line.strip()
            and line.lstrip().split(maxsplit=1)[0] not in self.checker_info_prefixes
        )

    def _parsed_gate_execution(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        result: p.Cli.CommandOutput,
        started: float,
    ) -> m.Infra.GateExecution:
        """Parse one tool result and assemble the gate execution it reports."""
        passed, issues = self._parse_check_output(result, project_dir, ctx)
        return self._build_check_gate_execution(
            project_dir,
            passed=passed,
            issues=issues,
            raw_output=self._raw_output(result),
            started=started,
            ctx=ctx,
        )

    def _detected_gate_execution(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        *,
        issues: t.SequenceOf[m.Infra.Issue],
        started: float,
    ) -> m.Infra.GateExecution:
        """Assemble one gate execution from detector-produced issues."""
        return self._build_check_gate_execution(
            project_dir,
            passed=len(issues) == 0,
            issues=issues,
            raw_output="\n".join(issue.formatted for issue in issues),
            started=started,
            ctx=ctx,
        )

    def _build_check_gate_execution(
        self,
        project_dir: Path,
        *,
        passed: bool,
        issues: t.SequenceOf[m.Infra.Issue],
        raw_output: str,
        started: float,
        ctx: m.Infra.GateContext | None = None,
        errors: t.StrSequence | None = None,
        accept_reported_issues: bool = False,
        observational_issues: t.SequenceOf[m.Infra.Issue] = (),
    ) -> m.Infra.GateExecution:
        """Assemble a gate execution from parsed check output.

        Diagnostic presentation never overrides acceptance. ``errors``
        overrides the default issue-derived report
        lines (fix paths report applied changes there).
        ``accept_reported_issues`` is the fix contract: reported issues are
        the residue a fixer could not repair and do not decide acceptance.
        Explicit observational findings remain visible in the report but do
        not change the verdict of blocking ``issues`` or native execution.
        """
        _ = ctx
        verdict = passed and (accept_reported_issues or not issues)
        return m.Infra.GateExecution(
            result=m.Infra.GateResult(
                gate=self.gate_id,
                project=project_dir.name,
                passed=verdict,
                errors=(
                    list(errors)
                    if errors is not None
                    else [issue.formatted for issue in issues]
                ),
                duration=round(time.monotonic() - started, 3),
            ),
            issues=tuple(issues),
            observational_issues=tuple(observational_issues),
            raw_output=raw_output,
        )

    def _build_project_error_gate_result(
        self,
        project_dir: Path,
        *,
        passed: bool,
        errors: t.SequenceOf[str],
        started: float,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Preserve project-level failures as blocking structured diagnostics."""
        issues = [
            m.Infra.Issue(
                file=str(project_dir),
                line=1,
                column=1,
                code=self.gate_id,
                message=error,
                severity=c.Infra.GateSeverity.ERROR.value,
            )
            for error in errors
        ]
        return self._build_check_gate_execution(
            project_dir,
            passed=passed,
            issues=issues,
            raw_output="\n".join(errors),
            started=started,
            ctx=ctx,
        )

    def _build_single_issue_result(
        self,
        project_dir: Path,
        file_path: Path,
        message: str,
        *,
        passed: bool,
        started: float,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Build a gate execution from a single issue (scan-failure / fix-failure)."""
        issue = m.Infra.Issue(
            file=str(file_path),
            line=1,
            column=1,
            code=self.gate_id,
            message=message,
            severity="ERROR",
        )
        return self._build_check_gate_execution(
            project_dir,
            passed=passed,
            issues=[issue],
            raw_output=issue.message,
            started=started,
            ctx=ctx,
        )

    # ------------------------------------------------------------------
    # Template hooks — subclasses override these
    # ------------------------------------------------------------------

    def _get_check_dirs(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Return directories to check. Default: discover + filter for .py files."""
        _ = ctx
        return self._dirs_with_py(project_dir, self._existing_check_dirs(project_dir))

    def _build_check_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, check_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Build the tool CLI command from the declared module invocation.

        Default: none, so a gate that overrides ``check`` directly still gets no
        command.
        """
        _ = project_dir, ctx
        if not self.check_module_command_prefix:
            return []
        return self._python_module_command(
            *self.check_module_command_prefix,
            *check_dirs,
            *self.check_module_command_suffix,
        )

    def _parse_check_output(
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse tool output into (passed, issues). Default: no-op (check overridden)."""
        _ = result, project_dir, ctx
        return True, ()

    def _check_timeout(self, project_dir: Path, ctx: m.Infra.GateContext) -> int:
        """Timeout for the check command. Override for long-running tools."""
        _ = project_dir, ctx
        timeout: int = c.Infra.TIMEOUT_DEFAULT
        return timeout

    def _check_report_path(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> Path | None:
        """Name the native output replaced by this invocation, when required."""
        _ = project_dir, ctx
        return None

    def _validate_check_report(
        self, project_dir: Path, ctx: m.Infra.GateContext, targets: t.StrSequence
    ) -> None:
        """Validate native execution evidence against the exact submitted targets."""
        _ = project_dir, ctx, targets

    def _check_env(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrMapping | None:
        """Return a custom environment for the check command. Default: None (inherit)."""
        _ = project_dir, ctx
        return None

    def _check_remove_env_keys(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Return inherited environment keys removed for this tool invocation.

        Every gate parses its tool's output, so the host color-forcing signal is
        never inherited: with the orchestrator's NO_COLOR it made Node-based
        tools print a warning on stderr that the gate then counted as a finding.
        """
        _ = project_dir, ctx
        return (c.Infra.ENV_VAR_FORCE_COLOR,)

    # ------------------------------------------------------------------
    # Template method: fix
    # ------------------------------------------------------------------

    def fix(self, project_dir: Path, ctx: m.Infra.GateContext) -> m.Infra.GateExecution:
        """Template method: timing + targets + skip + run fix + result."""
        if ctx.check_only or not ctx.apply_fixes:
            return self._check_only_fix_result(project_dir)
        if not self.can_fix:
            return self._build_check_gate_execution(
                project_dir,
                passed=True,
                issues=(),
                raw_output=f"Gate {self.gate_id} does not support fix",
                started=time.monotonic(),
            )
        started = time.monotonic()
        targets = self._get_fix_targets(project_dir, ctx)
        if not targets:
            return self._skip_result(project_dir, started)
        cmd = self._build_fix_command(project_dir, ctx, targets)
        result = self._run(cmd, project_dir)
        # A fixer repairs what it can and succeeds on its own exit status;
        # what remains is reported here and enforced by ``check``.
        _, issues = self._parse_check_output(result, project_dir, ctx)
        return self._build_check_gate_execution(
            project_dir,
            passed=u.Cli.process_succeeded(result.outcome),
            issues=issues,
            raw_output=self._raw_output(result),
            started=started,
            ctx=ctx,
            accept_reported_issues=True,
        )

    def _check_only_fix_result(self, project_dir: Path) -> m.Infra.GateExecution:
        """Return a non-mutating fix preview for check-only gate contexts."""
        return self._build_check_gate_execution(
            project_dir,
            passed=True,
            issues=(),
            raw_output=f"Gate {self.gate_id} fix preview only; no files written",
            started=time.monotonic(),
        )

    # ------------------------------------------------------------------
    # Fix hooks — subclasses override these
    # ------------------------------------------------------------------

    def _get_fix_targets(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Targets for fix. Default: same as check dirs."""
        return self._get_check_dirs(project_dir, ctx)

    def _build_fix_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, targets: t.StrSequence
    ) -> t.StrSequence:
        """Build the fix CLI command. Must override if can_fix is True."""
        _ = project_dir, ctx, targets
        msg = f"Gate {self.gate_id} set can_fix=True but did not implement _build_fix_command"
        raise NotImplementedError(msg)

    def _fix_raw_output(self, result: p.Cli.CommandOutput) -> str:
        """Assemble raw output from fix result. Default: stderr only."""
        stderr: str = result.stderr
        return stderr

    @staticmethod
    def _raw_output(result: p.Cli.CommandOutput) -> str:
        """Preserve diagnostics regardless of the stream selected by a tool."""
        return "\n".join(output for output in (result.stdout, result.stderr) if output)

    def _run(
        self,
        cmd: t.StrSequence,
        cwd: Path,
        timeout: int = c.Infra.TIMEOUT_DEFAULT,
        env: t.StrMapping | None = None,
        remove_env_keys: t.StrSequence = (),
    ) -> p.Cli.CommandOutput:
        """Run."""
        runner = self._runner or u.Cli
        result = runner.run_raw(
            cmd, cwd=cwd, timeout=timeout, env=env, remove_env_keys=remove_env_keys
        )
        if result.failure:
            # A failed Result here means the tool never ran -- it could not be
            # spawned, or the runner itself failed. Synthesizing a
            # CommandOutput with an invented raw_return_code=1 made that
            # indistinguishable from the tool running and reporting findings,
            # so a missing binary was reported as a code violation against
            # `<scc>` and an operator chased a finding in a file that was
            # never scanned. A nonzero exit from a tool that did run still
            # reaches the parser as a real outcome; this path did not run.
            msg = result.error or "command execution failed"
            raise RuntimeError(msg)
        return result.value

    def _existing_check_dirs(self, project_dir: Path) -> t.StrSequence:
        """Return every first-class project-owned Python directory."""
        return self._dirs_with_py(project_dir, c.Infra.CHECK_DIRS_REPOSITORY)

    @staticmethod
    def _dirs_with_py(project_dir: Path, dirs: t.StrSequence) -> t.StrSequence:
        """Dirs with py."""
        out: t.MutableSequenceOf[str] = []
        for directory in dirs:
            path = project_dir / directory
            if not path.is_dir():
                continue
            if next(path.rglob(c.Infra.EXT_PYTHON_GLOB), None) or next(
                path.rglob("*.pyi"), None
            ):
                out.append(directory)
        return out

    def _skip_result(self, project_dir: Path, started: float) -> m.Infra.GateExecution:
        """A selected gate with no inputs did not establish acceptance."""
        message = f"{self.gate_id}: no check targets were collected"
        return self._build_check_gate_execution(
            project_dir,
            passed=False,
            issues=(),
            errors=(message,),
            raw_output=message,
            started=started,
        )

    def _neutral_skip_result(
        self, project_dir: Path, started: float, *, message: str = ""
    ) -> m.Infra.GateExecution:
        """An intentional skip (e.g. source package) that passes by design."""
        detail = message or f"{self.gate_id}: intentionally skipped"
        return self._build_check_gate_execution(
            project_dir,
            passed=True,
            issues=(),
            errors=(),
            raw_output=detail,
            started=started,
        )


class FlextInfraScannerGateMixin(FlextInfraGate):
    """Mixin for gates that detect per-file issues via a rope-backed scanner.

    Subclasses provide ``scan_error_message`` and implement
    ``_detect_file_issues``.  The shared ``check`` method handles file
    discovery, rope-project lifecycle, and result assembly.
    """

    scan_error_message: ClassVar[str] = ""

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Scan all Python files in ``project_dir`` and report detected issues."""
        _ = ctx
        started = time.monotonic()
        files_result = u.Infra.iter_python_files(
            m.Infra.SourceScanRequest(project_roots=(project_dir,))
        )
        if files_result.failure:
            return self._build_single_issue_result(
                project_dir,
                Path(c.PYPROJECT_FILENAME),
                files_result.error or self.scan_error_message,
                passed=False,
                started=started,
                ctx=ctx,
            )
        rope_project = u.Infra.init_rope_project(project_dir)
        try:
            issues = [
                issue
                for file_path in files_result.value
                for issue in self._detect_file_issues(
                    file_path, project_dir, rope_project
                )
            ]
        finally:
            rope_project.close()
        return self._detected_gate_execution(
            project_dir, ctx, issues=issues, started=started
        )

    def _detect_file_issues(
        self, file_path: Path, project_dir: Path, rope_project: t.Infra.RopeProject
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Override in subclass to detect issues for a single file."""
        _ = file_path, project_dir, rope_project
        return ()


__all__: list[str] = ["FlextInfraGate", "FlextInfraScannerGateMixin"]
