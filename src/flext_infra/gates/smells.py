"""Fail-closed qlty code-smell quality gate."""

from __future__ import annotations

import time
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_core import r
from flext_infra import c, m, u
from flext_infra.gates.base_gate import FlextInfraGate
from flext_infra.transformers.smells.boolean_logic import FlextInfraBooleanLogicFixer

from ..transformers.smells.base import FlextInfraSmellFixer

# flext-0ftd.3.5: the empty package initializer is not a compatibility export;
# consume the declaration at its canonical owner after the lazy-init cutover.

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraSmellsGate(FlextInfraGate):
    """Report qlty smells per project from one fresh workspace scan.

    A single ``qlty smells --all`` scan covers the whole workspace so
    cross-project duplication clusters stay visible; per-project results are
    filtered by SARIF URI prefix.
    """

    gate_id: ClassVar[str] = "smells"
    gate_name: ClassVar[str] = "Code Smells"
    can_fix: ClassVar[bool] = True
    scanner_binary: ClassVar[str] = c.Infra.QLTY_BINARY

    # flext-pulj: process results stay structural outside the Pydantic boundary.
    _scan_cache: ClassVar[MutableMapping[str, p.Cli.CommandOutput]] = {}

    @override
    def fix(self, project_dir: Path, ctx: m.Infra.GateContext) -> m.Infra.GateExecution:
        """Apply AST-based fixers for auto-fixable smell findings.

        Runs the same scan as ``check()``, then attempts a registered fixer
        for every issue whose code has ``auto=true`` in flext-core metadata.
        Only rewrites files when a fixer actually changes the source.
        """
        if ctx.check_only or not ctx.apply_fixes:
            return self._check_only_fix_result(project_dir)
        started = time.monotonic()
        scan = self._workspace_scan()
        issues = self._scanned_issues(scan, project_dir.name)
        auto_issues = [issue for issue in issues if self._is_auto_fixable(issue)]
        changes: list[str] = []
        for issue in auto_issues:
            tag = c.Infra.SMELLS_RULE_TAGS.get(issue.code, "")
            fixer = (
                FlextInfraBooleanLogicFixer()
                if tag == FlextInfraBooleanLogicFixer.tag
                else FlextInfraSmellFixer.smell_fixer_for(tag)
            )
            if fixer is None:
                continue
            fixed, fix_changes = fixer.fix(project_dir, issue)
            if fixed:
                changes.extend(fix_changes)
        self._scan_cache.pop(str(self._repository_root), None)
        verified_scan = self._workspace_scan()
        remaining = self._scanned_issues(verified_scan, project_dir.name)
        return self._build_check_gate_execution(
            project_dir,
            passed=not remaining,
            issues=remaining,
            raw_output="\n".join(changes) if changes else verified_scan.stderr,
            started=started,
            errors=[issue.formatted for issue in remaining] if remaining else (),
        )

    def _scanned_issues(
        self, scan: p.Cli.CommandOutput, project: str
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Filter one workspace scan to the blocking issues owned by ``project``.

        The process outcome decides what an unusable payload means: a
        successful scan that emits no SARIF payload is a zero-findings pass,
        while a scanner that crashed or could not run at all is a blocking
        issue carrying its own error, never a clean pass. Non-blank output
        that fails to parse stays a loud parse failure.
        """
        parsed = self._issues_from_sarif(scan.stdout, project)
        issues: t.VariadicTuple[m.Infra.Issue]
        if parsed.success:
            issues = parsed.value
        elif not scan.stdout.strip():
            issues = ()
        else:
            issues = (self._failure_issue(parsed.error),)
        issues = self._drop_generated_projections(issues, project)
        if not issues and not u.Cli.process_succeeded(scan.outcome):
            return (self._tool_failure_issue(scan),)
        return issues

    @staticmethod
    def _is_auto_fixable(issue: m.Infra.Issue) -> bool:
        """Return True when flext-core marks this smell tag as auto-fixable."""
        tag = c.Infra.SMELLS_RULE_TAGS.get(issue.code, "")
        return tag in FlextInfraSmellFixer.auto_fixable_smell_tags()

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """One cached full-workspace qlty scan, filtered to ``project_dir``."""
        _ = ctx
        started = time.monotonic()
        scan = self._workspace_scan()
        issues = self._scanned_issues(scan, project_dir.name)
        return self._build_check_gate_execution(
            project_dir,
            passed=not issues,
            issues=issues,
            raw_output=self._raw_output(scan),
            started=started,
        )

    @override
    def _build_check_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, check_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Full-workspace scan command (check() bypasses per-project dirs)."""
        _ = project_dir, ctx, check_dirs
        binary = self._resolve_binary()
        if binary is None:
            raise FileNotFoundError(c.Infra.QLTY_BINARY)
        return [binary, *c.Infra.SMELLS_QLTY_ARGS]

    @override
    def _parse_check_output(
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse SARIF stdout into per-project issues (check_files path)."""
        _ = ctx
        issues = self._scanned_issues(result, project_dir.name)
        return not issues, issues

    def _workspace_scan(self) -> p.Cli.CommandOutput:
        """Scan the workspace once per root and preserve its exact process result."""
        key = str(self._repository_root)
        cached = self._scan_cache.get(key)
        if cached is not None:
            return cached
        output = self._uncached_workspace_scan()
        self._scan_cache[key] = output
        return output

    @staticmethod
    def _unrunnable_scan_output(stderr: str) -> p.Cli.CommandOutput:
        """Synthesize the scan result for a scanner that cannot run at all."""
        return m.Cli.CommandOutput(
            stdout="",
            stderr=stderr,
            outcome=m.Cli.ProcessOutcome(
                raw_return_code=c.Infra.PROCESS_COMMAND_NOT_FOUND_EXIT_CODE,
                timed_out=False,
                forwarded_signal=None,
            ),
        )

    def _uncached_workspace_scan(self) -> p.Cli.CommandOutput:
        """Run one qlty scan, or synthesize the blocking reason it cannot run.

        Codegen renders the qlty config from its template; this gate used to
        rewrite it from a constant at scan time. Two owners writing one path
        disagree by construction: every scan replaced the rendered projection
        with the constant, the next generation put the projection back, and
        the file churned between them — it reached this branch as an
        unexplained `wip` commit. The generator owns the file, so its absence
        is a generation gap reported through the gate result with the exact
        path, never papered over mid-scan and never read as a clean pass.
        """
        binary = self._resolve_binary()
        if binary is None:
            return self._unrunnable_scan_output(
                f"{c.Infra.QLTY_BINARY} binary not found on PATH"
            )
        config_path = (
            self._repository_root
            / c.Infra.QLTY_CONFIG_DIRNAME
            / c.Infra.QLTY_CONFIG_FILENAME
        )
        if not config_path.is_file():
            return self._unrunnable_scan_output(
                f"generated qlty configuration is absent: {config_path}; run make gen"
            )
        return self._run(
            [binary, *c.Infra.SMELLS_QLTY_ARGS],
            self._repository_root,
            timeout=c.Infra.TIMEOUT_LONG,
        )

    @staticmethod
    def _failure_issue(message: str | None) -> m.Infra.Issue:
        """Represent malformed or absent scanner output as a blocking issue."""
        return m.Infra.Issue(
            file=c.PYPROJECT_FILENAME,
            line=1,
            column=0,
            code=FlextInfraSmellsGate.gate_id,
            message=message or "qlty returned no parseable SARIF output",
            severity=str(c.Infra.GateSeverity.ERROR.value),
        )

    def _drop_generated_projections(
        self, issues: t.VariadicTuple[m.Infra.Issue], project: str
    ) -> t.VariadicTuple[m.Infra.Issue]:
        """Drop findings in generated projections; their owner is the generator.

        A file whose first line carries the canonical AUTO-GENERATED header is a
        projection of one codegen source, so duplication between projections is
        by construction and the smell gate reports only hand-written source.
        ``Issue.file`` is project-relative while ``qlty`` URIs are
        workspace-relative, so the project directory is joined to the workspace
        root before reading the header. Unreadable files keep their findings
        (fail-closed).
        """
        visible: list[m.Infra.Issue] = []
        for issue in issues:
            path = self._repository_root / project / issue.file
            try:
                with path.open("r", encoding=c.Cli.ENCODING_DEFAULT) as handle:
                    first_line = handle.readline()
            except OSError:
                visible.append(issue)
                continue
            if c.Infra.AUTOGEN_HEADER not in first_line:
                visible.append(issue)
        return tuple(visible)

    @classmethod
    def _issues_from_sarif(
        cls, sarif_json: str, project_name: str
    ) -> p.Result[t.VariadicTuple[m.Infra.Issue]]:
        """Extract one Issue per smell finding inside ``project_name``.

        Pure function over a literal qlty SARIF payload (unit-testable, no
        subprocess) — same strategy as ``loc_cap._files_over_cap``.
        """
        if not sarif_json.strip():
            return r[tuple[m.Infra.Issue, ...]].fail("qlty returned empty SARIF output")
        parsed = u.Cli.json_parse(sarif_json)
        if parsed.failure:
            return r[tuple[m.Infra.Issue, ...]].from_failure(parsed)
        data = u.Cli.json_as_mapping(parsed.value)
        prefix = f"{project_name}/"
        return r[tuple[m.Infra.Issue, ...]].ok(
            tuple(
                cls._issue_from_result(result, prefix)
                for run in u.Cli.json_deep_mapping_list(data, "runs")
                for result in u.Cli.json_deep_mapping_list(run, "results")
                if cls._result_uri(result).startswith(prefix)
            )
        )

    @classmethod
    def _issue_from_result(cls, result: t.JsonMapping, prefix: str) -> m.Infra.Issue:
        """Map one SARIF result to an Issue enriched with the FLEXT fix text."""
        rule_id = u.Cli.json_pick_str(result, "ruleId")
        code = rule_id.removeprefix(c.Infra.SMELLS_RULE_PREFIX)
        physical = u.Cli.json_deep_mapping(
            cls._first_location(result), "physicalLocation"
        )
        sarif_text = u.Cli.json_pick_str(
            u.Cli.json_deep_mapping(result, "message"), "text"
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
        """Workspace-relative URI of the finding's first location."""
        uri: str = u.Cli.json_pick_str(
            u.Cli.json_deep_mapping(
                cls._first_location(result), "physicalLocation", "artifactLocation"
            ),
            "uri",
        )
        return uri

    @staticmethod
    def _first_location(result: t.JsonMapping) -> t.JsonMapping:
        """First SARIF location mapping (empty mapping when absent)."""
        locations = u.Cli.json_deep_mapping_list(result, "locations")
        return locations[0] if locations else {}

    @staticmethod
    def _enriched_message(code: str, sarif_text: str) -> str:
        """Append the flext-core (problem, fix) law text when the tag exists."""
        tag = c.Infra.SMELLS_RULE_TAGS.get(code, "")
        text = c.ENFORCEMENT_RULES_TEXT.get(tag) if tag else None
        if text is None:
            return sarif_text
        problem, fix = text
        return f"{sarif_text} — {problem}. Fix: {fix}"


__all__: list[str] = ["FlextInfraSmellsGate"]
