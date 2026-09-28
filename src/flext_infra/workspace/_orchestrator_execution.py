"""Workspace orchestration execution behavior for CLI services.

Executes per-project make calls, progress reporting, and error summarization.
"""

from __future__ import annotations

import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, p, t, u


class FlextInfraWorkspaceOrchestratorExecutionMixin:
    """Project orchestration execution logic."""

    if TYPE_CHECKING:

        @property
        def root(self) -> Path:
            """Workspace root supplied by the composing orchestrator service."""

    @staticmethod
    def _project_child_env() -> t.StrMapping:
        """Return child process env overrides for project make execution."""
        inherited = u.Cli.process_env()
        path = inherited.get(c.Infra.ORCHESTRATOR_ENV_PATH, "")
        blocked_path_entries = frozenset(
            entry
            for entry in (inherited.get(c.Infra.ORCHESTRATOR_ENV_MISE_SHIMS, ""),)
            if entry
        )
        path_entries = tuple(
            entry
            for entry in path.split(c.Infra.ORCHESTRATOR_ENV_PATH_SEPARATOR)
            if entry and entry not in blocked_path_entries
        )
        env: MutableMapping[str, str] = {c.Infra.ORCHESTRATOR_ENV_NO_COLOR: "1"}
        if path_entries:
            env[c.Infra.ORCHESTRATOR_ENV_PATH] = (
                c.Infra.ORCHESTRATOR_ENV_PATH_SEPARATOR.join(path_entries)
            )
        return env

    @staticmethod
    def _exit_classification(exit_code: int) -> str:
        """Name the process outcome behind a non-zero exit status."""
        if exit_code == c.Infra.PROCESS_TIMEOUT_EXIT_CODE:
            return " timeout"
        if exit_code > c.Infra.PROCESS_SIGNAL_EXIT_OFFSET:
            return f" signal={exit_code - c.Infra.PROCESS_SIGNAL_EXIT_OFFSET}"
        return ""

    @staticmethod
    def _project_log_filename(project: str) -> str:
        """Return a report filename for project targets that may contain path parts."""
        project_path = Path(project)
        excluded_parts = frozenset({project_path.anchor, ".", "..", ""})
        safe_stem = "__".join(
            part for part in project_path.parts if part not in excluded_parts
        )
        return f"{safe_stem or 'workspace'}.log"

    def orchestrate(
        self, projects: t.StrSequence, verb: str
    ) -> p.Result[t.SequenceOf[p.Cli.CommandOutput]]:
        """Execute ``make <verb>`` across projects and return collected outputs."""
        u.Cli.header("Workspace Orchestration")
        return self._orchestrate_checked(projects, verb)

    def _orchestrate_checked(
        self, projects: t.StrSequence, verb: str
    ) -> p.Result[t.SequenceOf[p.Cli.CommandOutput]]:
        """Execute a validated orchestration run with progress accounting."""
        allowed_verbs = c.Infra.ORCHESTRATED_VERBS
        if verb not in allowed_verbs:
            allowed = ", ".join(allowed_verbs)
            return r[t.SequenceOf[p.Cli.CommandOutput]].fail(
                f"unsupported orchestrate verb '{verb}' (allowed: {allowed})"
            )
        preflight = self._preflight_projects(projects)
        if preflight.failure:
            return r[t.SequenceOf[p.Cli.CommandOutput]].from_failure(preflight)
        results: t.MutableSequenceOf[p.Cli.CommandOutput] = []
        total = len(projects)
        # flext-9v0d: emit a deterministic, machine-parseable orchestration report
        # so a caller can attribute every project outcome and the child exit code.
        u.Cli.emit_raw(
            f"scope={c.Infra.RK_WORKSPACE} verb={verb} "
            f"projects={','.join(projects)}" + "\n"
        )
        # Why (operator 2026-09-14): one failing project never hides the rest of
        # the fleet; every project runs, the summary names every failure, and the
        # run still exits non-zero when any project failed.
        failures: list[str] = []
        first_failure_code = 0
        for idx, project in enumerate(projects, start=1):
            u.Cli.emit_raw(f"[{idx}/{total}] START {project} {verb}\n")
            cmd_output = self._run_project(project, verb, idx).unwrap()
            results.append(cmd_output)
            code = cmd_output.outcome.raw_return_code
            succeeded = u.Cli.process_succeeded(cmd_output.outcome)
            state = "PASS" if succeeded else "FAIL"
            u.Cli.emit_raw(
                f"[{idx}/{total}] {state} {project} {verb} "
                f"exit={code} duration={cmd_output.duration:.2f}s\n"
            )
            if not succeeded:
                if not failures:
                    first_failure_code = code
                failures.append(
                    f"{project} exit={code}{self._exit_classification(code)}"
                )
        u.Cli.emit_raw(
            f"summary scope={c.Infra.RK_WORKSPACE} verb={verb} total={total} "
            f"completed={total} passed={total - len(failures)} "
            f"failed={len(failures)} exit={first_failure_code}\n"
        )
        if failures:
            return r[t.SequenceOf[p.Cli.CommandOutput]].fail(
                f"workspace {verb} failed for: {', '.join(failures)}"
            )
        return r[t.SequenceOf[p.Cli.CommandOutput]].ok(results)

    def _run_project(
        self, project: str, verb: str, _index: int
    ) -> p.Result[p.Cli.CommandOutput]:
        """Execute make verb for one project and capture output path/metrics."""
        log_path = u.Cli.resolve_report_path(
            Path.cwd(), c.Infra.RK_WORKSPACE, verb, self._project_log_filename(project)
        )
        _ = u.Cli.ensure_dir(log_path.parent)
        started = time.monotonic()
        target = (
            f"_builtin-self-{verb}"
            if project == c.Infra.ROOT_PROJECT_SELECTOR
            else verb
        )
        proc_result = u.Cli.run_to_file(
            [
                c.Infra.MAKE,
                "-C",
                project,
                target,
                f"{c.Infra.MAKE_REPOSITORY_ROOT}={self.root}",
            ],
            log_path,
            env=self._project_child_env(),
            remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            live=True,
        )
        return_code = proc_result.unwrap().raw_return_code
        # flext-9v0d: GNU make exits 2 for any failed recipe, so recover the
        # child's real exit code from make's own error line in the log.
        if return_code != 0:
            child_code = u.Infra.extract_make_child_exit_code(log_path)
            if child_code is not None:
                return_code = child_code
        stderr = "" if proc_result.success else proc_result.error or ""
        elapsed = time.monotonic() - started
        if return_code == 0:
            u.Cli.info(f"  ✓ {project} completed in {int(elapsed)}s  ({log_path})")
        else:
            error_count, error_lines = u.Infra.extract_errors(log_path)
            u.Cli.project_failure(
                m.Infra.ProjectFailureInfo(
                    project=project,
                    elapsed=elapsed,
                    log_path=log_path,
                    error_count=error_count,
                    errors=error_lines,
                )
            )
            if error_lines:
                stderr = "\n".join(error_lines)
        return r[p.Cli.CommandOutput].ok(
            m.Cli.CommandOutput(
                stdout=str(log_path),
                stderr=stderr,
                outcome=m.Cli.ProcessOutcome(
                    raw_return_code=return_code, timed_out=False, forwarded_signal=None
                ),
                duration=round(elapsed, 2),
            )
        )

    @staticmethod
    def _preflight_projects(projects: t.StrSequence) -> p.Result[bool]:
        """Validate the complete fanout before starting any child effect."""
        if not projects:
            return r[bool].fail("workspace orchestration discovered no projects")
        duplicates = len(projects) != len(frozenset(projects))
        if duplicates:
            return r[bool].fail("workspace orchestration discovered duplicate projects")
        missing = tuple(
            project
            for project in projects
            if not (Path(project) / c.Infra.MAKEFILE_FILENAME).is_file()
        )
        if missing:
            return r[bool].fail(
                "workspace orchestration requires generated Makefiles: "
                + ", ".join(missing)
            )
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraWorkspaceOrchestratorExecutionMixin"]
