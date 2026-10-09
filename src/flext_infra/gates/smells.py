"""Fail-closed qlty code-smell quality gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, r, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraSmellsGate(FlextInfraGate):
    """Report qlty smells for one project from a scan of its check directories.

    Every repository evaluates only itself, locally exactly as in CI: qlty
    receives the project's own paths and the SARIF URI prefix keys each
    finding to that project.
    """

    gate_id: ClassVar[str] = c.Infra.SMELLS
    gate_name: ClassVar[str] = "Code Smells"
    scanner_binary: ClassVar[str] = c.Infra.QLTY_BINARY

    def _scanned_issues(
        self,
        scan: p.Cli.CommandOutput,
        project_dir: Path,
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Filter one scan to the blocking issues owned by ``project``.

        Empty or malformed SARIF is a blocking scan failure, regardless of the
        process status. A valid SARIF document with zero results is a pass.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.Issue]``.

        """
        prefix = (
            ""
            if project_dir.resolve() == self._repository_root.resolve()
            else f"{project_dir.relative_to(self._repository_root).as_posix()}/"
        )
        parsed = self._issues_from_sarif(scan.stdout, prefix)
        issues: t.VariadicTuple[m.Infra.Issue]
        if parsed.success:
            issues = parsed.value
        elif not scan.stdout.strip() and not u.Cli.process_succeeded(scan.outcome):
            issues = (self._tool_failure_issue(scan),)
        else:
            issues = (self._failure_issue(parsed.error),)
        if not issues and not u.Cli.process_succeeded(scan.outcome):
            return (self._tool_failure_issue(scan),)
        return issues

    @override
    def check(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """One qlty scan of ``project_dir``'s check directories.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        _ = ctx
        started = time.monotonic()
        scan = self._scan(project_dir)
        issues = self._scanned_issues(scan, project_dir)
        return self._build_check_gate_execution(
            project_dir,
            passed=not issues,
            issues=issues,
            raw_output=self._raw_output(scan),
            started=started,
        )

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """The project's scan command (check() names its check dirs itself).

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            FileNotFoundError: If ``binary is None``.

        """
        _ = ctx, check_dirs
        binary = self._resolve_binary()
        if binary is None:
            raise FileNotFoundError(c.Infra.QLTY_BINARY)
        return self._scan_command(binary, project_dir)

    @override
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse SARIF stdout into per-project issues (check_files path).

        Returns:
            The resulting ``t.Pair[bool, t.SequenceOf[m.Infra.Issue]]``.

        """
        _ = ctx
        issues = self._scanned_issues(result, project_dir)
        return not issues, issues

    def _scan_command(self, binary: str, project_dir: Path) -> t.StrSequence:
        """Name the project's paths explicitly; qlty scans them in full.

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            ValueError: If smells.

        """
        paths = tuple(
            (project_dir / directory).relative_to(self._repository_root).as_posix()
            for directory in self._existing_check_dirs(project_dir)
        )
        if not paths:
            message = f"smells: no check targets for {project_dir}"
            raise ValueError(message)
        return (binary, *c.Infra.SMELLS_QLTY_ARGS, *paths)

    @staticmethod
    def _unrunnable_scan_output(stderr: str) -> p.Cli.CommandOutput:
        """Synthesize the scan result for a scanner that cannot run at all.

        Returns:
            The resulting ``p.Cli.CommandOutput``.

        """
        return m.Cli.CommandOutput(
            stdout="",
            stderr=stderr,
            outcome=m.Cli.ProcessOutcome(
                raw_return_code=c.Infra.PROCESS_COMMAND_NOT_FOUND_EXIT_CODE,
                timed_out=False,
                forwarded_signal=None,
            ),
        )

    def _scan(self, project_dir: Path) -> p.Cli.CommandOutput:
        """Run one qlty scan, or synthesize the blocking reason it cannot run.

        Codegen renders the qlty config from its template; this gate used to
        rewrite it from a constant at scan time. Two owners writing one path
        disagree by construction: every scan replaced the rendered projection
        with the constant, the next generation put the projection back, and
        the file churned between them — it reached this branch as an
        unexplained `wip` commit. The generator owns the file, so its absence
        is a generation gap reported through the gate result with the exact
        path, never papered over mid-scan and never read as a clean pass.

        Returns:
            The resulting ``p.Cli.CommandOutput``.

        """
        binary = self._resolve_binary()
        if binary is None:
            return self._unrunnable_scan_output(
                f"{c.Infra.QLTY_BINARY} binary not found on PATH",
            )
        config_path = (
            self._repository_root
            / c.Infra.QLTY_CONFIG_DIRNAME
            / c.Infra.QLTY_CONFIG_FILENAME
        )
        if not config_path.is_file():
            return self._unrunnable_scan_output(
                f"generated qlty configuration is absent: {config_path}; run make gen",
            )
        return self._run(
            self._scan_command(binary, project_dir),
            self._repository_root,
            timeout=c.Infra.TIMEOUT_LONG,
        )

    @staticmethod
    def _failure_issue(message: str | None) -> m.Infra.Issue:
        """Represent malformed or absent scanner output as a blocking issue.

        Returns:
            The resulting ``m.Infra.Issue``.

        """
        return m.Infra.Issue(
            file=c.PYPROJECT_FILENAME,
            line=1,
            column=0,
            code=FlextInfraSmellsGate.gate_id,
            message=message or "qlty returned no parseable SARIF output",
            severity=str(c.Infra.GateSeverity.ERROR.value),
        )

    @classmethod
    def _issues_from_sarif(
        cls,
        sarif_json: str,
        prefix: str,
    ) -> p.Result[t.VariadicTuple[m.Infra.Issue]]:
        """Extract one Issue per smell finding inside ``project_name``.

        Pure function over a literal qlty SARIF payload (unit-testable, no
        subprocess) — same strategy as ``loc_cap._files_over_cap``.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.Issue]]``.

        """
        if not sarif_json.strip():
            return r[tuple[m.Infra.Issue, ...]].fail("qlty returned empty SARIF output")
        parsed = u.Cli.json_parse(sarif_json)
        if parsed.failure:
            return r[tuple[m.Infra.Issue, ...]].from_failure(parsed)
        data = u.Cli.json_as_mapping(parsed.value)
        return r[tuple[m.Infra.Issue, ...]].ok(
            tuple(
                cls._issue_from_result(result, prefix)
                for run in u.Cli.json_deep_mapping_list(data, "runs")
                for result in u.Cli.json_deep_mapping_list(run, "results")
                if cls._result_uri(result).startswith(prefix)
            ),
        )

    @classmethod
    def _issue_from_result(cls, result: t.JsonMapping, prefix: str) -> m.Infra.Issue:
        """Map one SARIF result to an Issue enriched with the FLEXT fix text.

        Returns:
            The resulting ``m.Infra.Issue``.

        """
        rule_id = u.Cli.json_pick_str(result, "ruleId")
        code = rule_id.removeprefix(c.Infra.SMELLS_RULE_PREFIX)
        physical = u.Cli.json_deep_mapping(
            cls._first_location(result),
            "physicalLocation",
        )
        sarif_text = u.Cli.json_pick_str(
            u.Cli.json_deep_mapping(result, "message"),
            "text",
        )
        return m.Infra.Issue(
            file=cls._result_uri(result).removeprefix(prefix),
            line=u.Cli.json_nested_int(physical, "region", "startLine", default=1),
            column=u.Cli.json_nested_int(physical, "region", "startColumn"),
            code=code,
            message=cls._enriched_message(code, sarif_text),
            severity=str(c.Infra.GateSeverity.ERROR.value),
        )

    @classmethod
    def _result_uri(cls, result: t.JsonMapping) -> str:
        """Workspace-relative URI of the finding's first location.

        Returns:
            The resulting ``str``.

        """
        uri: str = u.Cli.json_pick_str(
            u.Cli.json_deep_mapping(
                cls._first_location(result),
                "physicalLocation",
                "artifactLocation",
            ),
            "uri",
        )
        return uri

    @staticmethod
    def _first_location(result: t.JsonMapping) -> t.JsonMapping:
        """First SARIF location mapping (empty mapping when absent).

        Returns:
            The resulting ``t.JsonMapping``.

        """
        locations = u.Cli.json_deep_mapping_list(result, "locations")
        return locations[0] if locations else {}

    @staticmethod
    def _enriched_message(code: str, sarif_text: str) -> str:
        """Append the flext-core fix law text when the tag exists.

        The SARIF text already states the concrete problem (name and count);
        the core problem text is a census template whose placeholders qlty
        does not supply, so only the fix is appended.

        Returns:
            The resulting ``str``.

        """
        tag = c.Infra.SMELLS_RULE_TAGS.get(code, "")
        text = c.ENFORCEMENT_RULES_TEXT.get(tag) if tag else None
        if text is None:
            return sarif_text
        _, fix = text
        return f"{sarif_text}. Fix: {fix}"


__all__: list[str] = ["FlextInfraSmellsGate"]
