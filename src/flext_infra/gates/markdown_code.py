"""FLEXT embedded-code gate: ruff format over fenced blocks and docstring examples.

The code inside documentation is still code — parseable embedded sources are
held to the ruff-format contract. This gate extracts fenced ``python`` blocks
and doctest examples into one temporary source tree and runs ONE ruff format
invocation per verb (single-pass law): ``check`` renders the format verdict
read-only, ``fix`` — reached from ``make fix`` — writes formatting back into
fenced blocks when every block of a file round-trips cleanly. Unparseable
documentation fragments stay out of scope by design: their syntax findings
belong to the flext-tests markdown validator (MD-001 with approved
exceptions), and docstring write-back stays a human decision.
"""

from __future__ import annotations

import fnmatch
import re
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u

from .base_gate import FlextInfraGate
from .markdown_code_sources import (
    source_name,
    write_docstring_sources,
    write_fenced_block_sources,
)
from .markdown_support import collect_markdown_files, read_ignore_patterns


def _ignore_filtered(
    project_dir: Path, markdown_files: t.SequenceOf[Path]
) -> t.SequenceOf[Path]:
    """Drop files the generated ignore projection excludes, like the rumdl gate.

    The rumdl gate forwards ``.markdownlintignore`` patterns via ``--exclude``
    because explicit files bypass directory-scan ignores; this gate feeds
    extracted sources instead, so the same projection is applied to the
    collected list here — all markdown gates share one ignore SSOT.
    """
    patterns = read_ignore_patterns(project_dir, c.Infra.MARKDOWNLINT_IGNORE_FILENAME)
    if not patterns:
        return markdown_files

    def _excluded(path: Path) -> bool:
        relative = path.relative_to(project_dir).as_posix()
        return any(
            fnmatch.fnmatch(relative, pattern)
            or relative.startswith(pattern.rstrip("/*") + "/")
            for pattern in patterns
        )

    return tuple(path for path in markdown_files if not _excluded(path))


def _is_syntax_broken(code: str, origin: Path) -> bool:
    """True when one embedded source does not compile (documentation fragment)."""
    try:
        compile(code, str(origin), "exec")
    except SyntaxError:
        return True
    return False


if TYPE_CHECKING:
    from collections.abc import Iterator

    from flext_infra import p, t


class FlextInfraMarkdownCodeGate(FlextInfraGate):
    """Embedded documentation-code gate."""

    gate_id: ClassVar[str] = c.Infra.MARKDOWN_CODE
    gate_name: ClassVar[str] = "Markdown Code"
    can_fix: ClassVar[bool] = True

    def _format_command(
        self, project_dir: Path, sources_dir: Path, *, write: bool
    ) -> t.StrSequence:
        """Build one ruff format invocation (verdict with ``--check``, write otherwise).

        The project's own ``pyproject.toml`` is the format contract owner: embedded
        blocks must satisfy the exact same configuration (notably ``preview``) that
        ``make fmt`` and ``refactor mod`` apply to authored source. ``--isolated``
        ignored that contract and produced a second, divergent formatting, so a
        documented block could never satisfy both surfaces at once.
        """
        args = ["format", "--no-cache", "--output-format", "concise"]
        config_path = project_dir / c.PYPROJECT_FILENAME
        args += (
            ["--config", str(config_path)] if config_path.is_file() else ["--isolated"]
        )
        return self._python_console_script_command(
            c.Infra.RUFF, *args, *(("--check",) if not write else ()), str(sources_dir)
        )

    def _origin_issue(
        self,
        origin: dict[str, t.Pair[str, int]],
        source: str,
        *,
        code: str,
        message: str,
        line: int = 1,
    ) -> m.Infra.Issue | None:
        """Map one extracted-source finding back to its documentation location."""
        if (location := origin.get(Path(source).name)) is None:
            return None
        return m.Infra.Issue(
            file=location[0],
            line=location[1] + line - 1,
            column=1,
            code=code,
            message=message,
        )

    def _issues_from_ruff(
        self,
        project_dir: Path,
        result: p.Cli.CommandOutput,
        origin: dict[str, t.Pair[str, int]],
        *,
        default_code: str,
        default_message: str,
        file_pattern: re.Pattern[str],
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Translate one ruff result into origin-mapped gate findings.

        A failed run without mapped findings never reads as a clean pass: the
        tool-level error becomes the finding.
        """
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            match = file_pattern.match(line.strip())
            issue = (
                self._origin_issue(
                    origin,
                    match.group("file"),
                    code=default_code,
                    message=default_message,
                    line=int(match.groupdict().get("line", 1) or 1),
                )
                if match
                else None
            )
            if issue is not None:
                issues.append(issue)
        if not u.Cli.process_succeeded(result.outcome) and not issues:
            issues.append(
                self._command_error_issue(
                    result, tool=c.Infra.RUFF, file=str(project_dir), line=1, column=1
                )
            )
        return issues

    def _run_extracted(
        self, project_dir: Path, markdown_files: t.SequenceOf[Path], *, fix: bool
    ) -> t.Triple[bool, bool, t.SequenceOf[m.Infra.Issue]]:
        """Run the single format operation over extracted sources.

        Returns ``(ran, passed, issues)``: ``ran`` is False when the project
        carries no parseable embedded documentation code at all, which is the
        neutral skip both verbs report instead of an empty verdict. Only the
        format contract lives here — syntax ownership belongs to the
        flext-tests markdown validator, so unparseable fragments never enter
        the extracted tree and cannot turn into gate findings.
        """
        findings: t.MutableSequenceOf[m.Infra.Issue] = []
        ran = False
        with tempfile.TemporaryDirectory(prefix="flext-markdown-code-") as tmp:
            sources_dir = Path(tmp)
            origin = write_fenced_block_sources(
                project_dir, markdown_files, sources_dir
            )
            origin.update(write_docstring_sources(project_dir, sources_dir))
            if not origin:
                return False, True, ()
            ran = True
            formatted = self._run(
                self._format_command(project_dir, sources_dir, write=fix), project_dir
            )
            format_ok = u.Cli.process_succeeded(formatted.outcome)
            if fix:
                findings.extend(
                    self._issues_from_ruff(
                        project_dir,
                        formatted,
                        origin,
                        default_code=self.gate_id,
                        default_message=(
                            "embedded block does not survive the format round-trip"
                        ),
                        file_pattern=c.Infra.MARKDOWN_CODE_FORMAT_ERROR_RE,
                    )
                )
                if format_ok:
                    self._splice_formatted_blocks(project_dir, sources_dir)
            else:
                findings.extend(
                    self._issues_from_ruff(
                        project_dir,
                        formatted,
                        origin,
                        default_code=self.gate_id,
                        default_message=(
                            "embedded code is not ruff-formatted (repair belongs to `make fix`)"
                        ),
                        file_pattern=c.Infra.MARKDOWN_CODE_FORMAT_FILE_RE,
                    )
                )
            passed = format_ok
        return ran, passed, findings

    def _splice_formatted_blocks(
        self, project_dir: Path, sources_dir: Path
    ) -> t.SequenceOf[Path]:
        """Write formatted blocks back into docs whose round-trip recompiles cleanly.

        Enumeration matches the extractor exactly: only parseable non-``notest``
        blocks own a staged source, share its index, and take part in the
        all-or-nothing splice; fragments stay byte-identical.
        """
        rewritten: t.MutableSequenceOf[Path] = []
        for md_path in _ignore_filtered(
            project_dir, collect_markdown_files(project_dir)
        ):
            content = md_path.read_text(c.Cli.ENCODING_DEFAULT)
            relative_posix = md_path.relative_to(project_dir).as_posix()
            # Enumerate every non-``notest`` fence exactly like
            # ``write_fenced_block_sources``: the extraction index counts
            # fragments that do not compile, so the splice must preserve that
            # same index. Re-enumerating only parseable blocks shifted every
            # later source name and silently skipped whole files whenever a
            # fragment preceded a valid block.
            staged: t.MutableSequenceOf[t.Pair[int, str]] = []
            for index, match in enumerate(
                match
                for match in c.Infra.MARKDOWN_PY_FENCE_RE.finditer(content)
                if c.Infra.MARKDOWN_CODE_SKIP_MARKER not in match.group("info")
            ):
                code = match.group("code")
                if _is_syntax_broken(code, md_path):
                    continue
                staged.append((index, code))
            if not staged:
                continue
            blocks: t.MutableSequenceOf[str] = []
            round_trips = True
            for index, _original in staged:
                source = sources_dir / source_name(relative_posix, index)
                if not source.is_file():
                    round_trips = False
                    break
                formatted = source.read_text(c.Cli.ENCODING_DEFAULT)
                try:
                    compile(formatted, str(md_path), "exec")
                except SyntaxError:
                    round_trips = False
                    break
                blocks.append(formatted)
            if not round_trips:
                continue
            blocks_iter = iter(blocks)

            def _resubstitute(
                match: re.Match[str],
                *,
                origin_path: Path = md_path,
                replacements: Iterator[str] = blocks_iter,
            ) -> str:
                """Splice one formatted block; fragments and markers stay verbatim."""
                keep = c.Infra.MARKDOWN_CODE_SKIP_MARKER in match.group(
                    "info"
                ) or _is_syntax_broken(match.group("code"), origin_path)
                if keep:
                    return match.group(0)
                return match.group(0).replace(match.group("code"), next(replacements))

            updated = c.Infra.MARKDOWN_PY_FENCE_RE.sub(_resubstitute, content)
            if updated != content:
                md_path.write_text(updated, c.Cli.ENCODING_DEFAULT)
                rewritten.append(md_path)
        return rewritten

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Validate embedded sources read-only when documentation code exists."""
        _ = ctx
        started = time.monotonic()
        ran, passed, issues = self._run_extracted(
            project_dir,
            _ignore_filtered(project_dir, collect_markdown_files(project_dir)),
            fix=False,
        )
        if not ran:
            return self._neutral_skip_result(
                project_dir,
                started,
                message=f"{self.gate_id}: no embedded documentation code found",
            )
        return self._build_check_gate_execution(
            project_dir,
            passed=passed,
            issues=issues,
            raw_output="\n".join(issue.formatted for issue in issues),
            started=started,
        )

    @override
    def fix(self, project_dir: Path, ctx: m.Infra.GateContext) -> m.Infra.GateExecution:
        """Run the single mutating pass: format extracted blocks and splice clean docs back."""
        if ctx.check_only or not ctx.apply_fixes:
            return self._check_only_fix_result(project_dir)
        started = time.monotonic()
        ran, passed, issues = self._run_extracted(
            project_dir,
            _ignore_filtered(project_dir, collect_markdown_files(project_dir)),
            fix=True,
        )
        if not ran:
            return self._neutral_skip_result(
                project_dir,
                started,
                message=f"{self.gate_id}: no embedded documentation code found",
            )
        return self._build_check_gate_execution(
            project_dir,
            passed=passed,
            issues=issues,
            raw_output="\n".join(issue.formatted for issue in issues),
            started=started,
            accept_reported_issues=True,
        )


__all__: list[str] = ["FlextInfraMarkdownCodeGate"]
