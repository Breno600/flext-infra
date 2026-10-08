"""Cohesive external-tool-runner mixin (deptry, mypy stubs, pip-check) for detection.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from flext_infra import c, m, r, t, u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraDependencyDetectionRunnersMixin:
    """Mixin holding raw-run contract plus external analysis-tool runners."""

    if TYPE_CHECKING:
        # Conversion helper provided by the concrete analyzer; declared for static
        # resolution only (runtime impl lives on the concrete via FLEXT).
        def _to_toml_config(
            self,
            payload: t.MappingKV[str, t.JsonValue],
        ) -> t.JsonMapping: ...

    def run_deptry(
        self,
        project_path: Path,
        venv_bin: Path,
        *,
        config_path: Path | None = None,
        json_output_path: Path | None = None,
        extend_exclude: t.StrSequence | None = None,
    ) -> p.Result[t.Pair[t.SequenceOf[t.JsonMapping], int]]:
        """Run deptry analysis on a project and parse JSON output.

        Returns:
            The resulting ``p.Result[t.Pair[t.SequenceOf[t.JsonMapping], int]]``.

        """
        settings = config_path or project_path / c.PYPROJECT_FILENAME
        if not settings.exists():
            return r[t.Pair[t.SequenceOf[t.JsonMapping], int]].ok(([], 0))
        out_file = json_output_path or project_path / ".deptry-report.json"
        result = u.Cli.run_raw(
            self._deptry_command(venv_bin, settings, out_file, extend_exclude),
            cwd=project_path,
            timeout=c.Infra.TIMEOUT_MEDIUM,
        )
        if result.failure:
            return r[t.Pair[t.SequenceOf[t.JsonMapping], int]].from_failure(result)
        issues: t.SequenceOf[t.JsonMapping] = []
        if out_file.exists():
            loaded_result = u.Cli.files_read_json(out_file)
            if loaded_result.failure:
                return r[t.Pair[t.SequenceOf[t.JsonMapping], int]].from_failure(
                    loaded_result,
                )
            normalized = self._normalized_deptry_issues(loaded_result)
            if normalized.failure:
                return r[t.Pair[t.SequenceOf[t.JsonMapping], int]].from_failure(
                    normalized,
                )
            issues = normalized.value
            cleaned = self._cleanup_deptry_output(out_file, json_output_path)
            if cleaned.failure:
                return r[t.Pair[t.SequenceOf[t.JsonMapping], int]].from_failure(cleaned)
        cmd_result: p.Cli.CommandOutput = result.value
        return r[t.Pair[t.SequenceOf[t.JsonMapping], int]].ok((
            issues,
            cmd_result.outcome.raw_return_code,
        ))

    @staticmethod
    def _deptry_command(
        venv_bin: Path,
        settings: Path,
        out_file: Path,
        extend_exclude: t.StrSequence | None,
    ) -> t.MutableSequenceOf[str]:
        """Compose the deptry invocation for one project.

        Returns:
            The composed deptry command line.

        """
        cmd: t.MutableSequenceOf[str] = [
            str(venv_bin / c.Infra.DEPTRY),
            ".",
            "--config",
            str(settings),
            "--json-output",
            str(out_file),
            "--no-ansi",
        ]
        if extend_exclude:
            for excluded in extend_exclude:
                cmd.extend(["--extend-exclude", excluded])
        return cmd

    def _normalized_deptry_issues(
        self,
        loaded_result: p.Result[t.JsonValue],
    ) -> p.Result[t.SequenceOf[t.JsonMapping]]:
        """Validate and convert every deptry JSON issue mapping.

        Returns:
            The resulting converted issues, keeping only issues whose conversion
            preserves the declared key surface.

        """
        if not isinstance(loaded_result.value, list):
            return r[t.SequenceOf[t.JsonMapping]].ok(())
        normalized: t.MutableSequenceOf[t.JsonMapping] = []
        for index, item in enumerate(loaded_result.value):
            if not isinstance(item, Mapping):
                return r[t.SequenceOf[t.JsonMapping]].fail(
                    f"deptry JSON issue {index} must be a mapping",
                )
            try:
                typed_item = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(item)
            except c.ValidationError as exc:
                return r[t.SequenceOf[t.JsonMapping]].fail_op(
                    "validate deptry issue",
                    exc,
                )
            converted_issue = self._to_toml_config(typed_item)
            if len(converted_issue) == len(typed_item):
                normalized.append(converted_issue)
        return r[t.SequenceOf[t.JsonMapping]].ok(normalized)

    @staticmethod
    def _cleanup_deptry_output(
        out_file: Path,
        json_output_path: Path | None,
    ) -> p.Result[bool]:
        """Remove the deptry temp report unless the caller owns the output path.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if json_output_path is None:
            try:
                out_file.unlink()
            except OSError as exc:
                return r[bool].fail(
                    f"failed to cleanup deptry temp output: {exc}",
                    exception=exc,
                )
        return r[bool].ok(value=True)

    @staticmethod
    def run_mypy_stub_hints(
        project_path: Path,
    ) -> p.Result[t.Pair[t.StrSequence, t.StrSequence]]:
        """Run mypy via the command runner to detect missing stubs and hint packages.

        Returns:
            The resulting ``p.Result[t.Pair[t.StrSequence, t.StrSequence]]``.

        """
        # Why: current mypy emits ANSI color codes around quoted module/package
        # names even when stdout is a pipe, splicing escape sequences inside
        # the literal `for "name"` text that MYPY_STUB_RE/MYPY_HINT_RE match —
        # silently zeroing every detected stub hint. `--no-color-output`
        # matches the plain-text contract the regexes already assume (see
        # gates/mypy.py, which disables color for the same reason).
        cmd = u.Infra.mypy_limited_command(
            m.Infra.MypyInvocation(
                targets=(project_path / c.Infra.DEFAULT_SRC_DIR,),
                config_file=project_path / c.PYPROJECT_FILENAME,
            ),
        )
        result = u.Cli.run_raw(
            cmd,
            cwd=project_path,
            timeout=u.Infra.mypy_runner_timeout(),
        )
        if result.failure:
            return r[t.Pair[t.StrSequence, t.StrSequence]].fail(
                u.Infra.mypy_launch_failure_diagnostic(
                    result.error or "Mypy process launch failed",
                ),
            )
        command_output: p.Cli.CommandOutput = result.value
        if resource_diagnostic := u.Infra.mypy_failure_diagnostic(command_output):
            return r[t.Pair[t.StrSequence, t.StrSequence]].fail(resource_diagnostic)
        output = f"{command_output.stdout}\n{command_output.stderr}"
        hinted = {
            match.group(1).strip()
            for match in c.Infra.MYPY_HINT_RE.finditer(output)
            if match.group(1).strip()
        }
        missing = {
            match.group(1).strip()
            for match in c.Infra.MYPY_STUB_RE.finditer(output)
            if match.group(1).strip()
        }
        return r[t.Pair[t.StrSequence, t.StrSequence]].ok((
            sorted(hinted),
            sorted(missing),
        ))

    @staticmethod
    def run_pip_check(
        repository_root: Path,
        venv_bin: Path,
    ) -> p.Result[t.Pair[t.StrSequence, int]]:
        """Run pip check to detect dependency conflicts in workspace.

        Returns:
            The resulting ``p.Result[t.Pair[t.StrSequence, int]]``.

        """
        pip = venv_bin / "pip"
        if not pip.exists():
            return r[t.Pair[t.StrSequence, int]].ok(([], 0))
        env = {"VIRTUAL_ENV": str(venv_bin.parent)}
        result = u.Cli.run_raw(
            [str(pip), c.Infra.VERB_CHECK],
            cwd=repository_root,
            timeout=c.Infra.TIMEOUT_SHORT,
            options=m.Cli.ProcessOptions(env=env),
        )
        if result.failure:
            return r[t.Pair[t.StrSequence, int]].from_failure(result)
        cmd_result: p.Cli.CommandOutput = result.value
        output = cmd_result.stdout
        lines = output.strip().splitlines() if output else []
        return r[t.Pair[t.StrSequence, int]].ok((
            lines,
            cmd_result.outcome.raw_return_code,
        ))


__all__: list[str] = ["FlextInfraDependencyDetectionRunnersMixin"]
