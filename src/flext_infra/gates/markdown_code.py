"""FLEXT embedded-code gate: ruff format over fenced blocks and docstring examples.

The code inside documentation is still code — parseable embedded sources are
held to the ruff-format contract. This gate extracts fenced ``python`` blocks
and doctest examples into one temporary source tree and runs ONE ruff format
invocation per verb (single-pass law): ``check`` renders the format verdict
read-only, ``fix`` — reached from ``make fix`` — writes formatting back into
fenced blocks when every block of a file round-trips cleanly. Invalid Python
fences fail loudly; docstring write-back stays a human decision.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import fnmatch
import re
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u
from flext_infra.gates.base_gate import FlextInfraGate
from flext_infra.gates.markdown_code_sources import FlextInfraMarkdownCodeSources
from flext_infra.gates.markdown_support import FlextInfraMarkdownGateBase

if TYPE_CHECKING:
    from collections.abc import Iterator

    from flext_infra import p, t


class FlextInfraMarkdownCodeGate(FlextInfraGate):
    """Embedded documentation-code gate."""

    gate_id: ClassVar[str] = c.Infra.MARKDOWN_CODE
    gate_name: ClassVar[str] = "Markdown Code"
    can_fix: ClassVar[bool] = True

    @staticmethod
    def _ignore_filtered(
        project_dir: Path,
        markdown_files: t.SequenceOf[Path],
    ) -> t.SequenceOf[Path]:
        """Drop files the generated ignore projection excludes, like the rumdl gate.

        The rumdl gate forwards ``.markdownlintignore`` patterns via ``--exclude``
        because explicit files bypass directory-scan ignores; this gate feeds
        extracted sources instead, so the same projection is applied to the
        collected list here — all markdown gates share one ignore SSOT.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        """
        patterns = FlextInfraMarkdownGateBase.read_ignore_patterns(
            project_dir,
            c.Infra.MARKDOWNLINT_IGNORE_FILENAME,
        )
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

    def _format_command(
        self,
        project_dir: Path,
        sources_dir: Path,
        *,
        write: bool,
    ) -> t.StrSequence:
        """Build one ruff format invocation (verdict with ``--check``, write otherwise).

        The project's own ``pyproject.toml`` is the format contract owner: embedded
        blocks must satisfy the exact same configuration (notably ``preview``) that
        ``make fmt`` and ``refactor mod`` apply to authored source. ``--isolated``
        ignored that contract and produced a second, divergent formatting, so a
        documented block could never satisfy both surfaces at once.

        Returns:
            The resulting ``t.StrSequence``.

        """
        args = ["format", "--no-cache", "--output-format", "concise"]
        config_path = project_dir / c.PYPROJECT_FILENAME
        args += (
            ["--config", str(config_path)] if config_path.is_file() else ["--isolated"]
        )
        return self._python_console_script_command(
            c.Infra.RUFF,
            *args,
            *(("--check",) if not write else ()),
            str(sources_dir),
        )

    @staticmethod
    def _origin_issue(
        origin: Mapping[str, t.Pair[str, int]],
        source: str,
        *,
        code: str,
        message: str,
        line: int = 1,
    ) -> m.Infra.Issue | None:
        """Map one extracted-source finding back to its documentation location.

        Returns:
            The resulting ``m.Infra.Issue | None``.

        """
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
        origin: Mapping[str, t.Pair[str, int]],
        *,
        default_message: str,
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Translate one ruff result into origin-mapped findings coded with this gate.

        Every ruff line that names an extracted source (verdict, parse error or
        any other diagnostic) maps to its documentation file and line, carrying
        the ruff line as evidence. A failed run naming no source never reads
        as a clean pass: the tool-level error becomes the finding.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.Issue]``.

        """
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            match = c.Infra.MARKDOWN_CODE_SOURCE_RE.search(line)
            issue = (
                self._origin_issue(
                    origin,
                    match.group("file"),
                    code=self.gate_id,
                    message=f"{default_message}: {line.strip()}",
                    line=int(match.group("line") or 1),
                )
                if match
                else None
            )
            if issue is not None:
                issues.append(issue)
        if not u.Cli.process_succeeded(result.outcome) and not issues:
            issues.append(
                self._command_error_issue(
                    result,
                    tool=c.Infra.RUFF,
                    file=str(project_dir),
                    line=1,
                    column=1,
                ),
            )
        return issues

    def _embedded_sources(
        self,
        project_dir: Path,
    ) -> t.MappingKV[str, t.Pair[str, t.Pair[str, int]]]:
        """Name every embedded source with its text and documentation origin.

        Returns:
            The resulting ``t.MappingKV[str, t.Pair[str, t.Pair[str, int]]]``.

        """
        markdown_files = self._ignore_filtered(
            project_dir,
            FlextInfraMarkdownGateBase.collect_markdown_files(project_dir),
        )
        return {
            name: (text, origin)
            for name, text, origin in (
                *FlextInfraMarkdownCodeSources.fenced_block_sources(
                    project_dir,
                    markdown_files,
                ),
                *FlextInfraMarkdownCodeSources.docstring_sources(project_dir),
            )
        }

    @override
    def selected_for(self, project_dir: Path) -> bool:
        """Only a project carrying embedded documentation code selects the gate.

        Returns:
            The resulting ``bool``.

        """
        return bool(self._embedded_sources(project_dir))

    def _run_extracted(
        self,
        project_dir: Path,
        *,
        fix: bool,
    ) -> t.Triple[bool, bool, t.SequenceOf[m.Infra.Issue]]:
        """Run the single format operation over extracted sources.

        Returns ``(ran, passed, issues)``: ``ran`` is False when the project
        carries no parseable embedded documentation code, which the checker
        never selects. Only the format contract lives here — syntax ownership
        belongs to the flext-tests markdown validator, so unparseable fragments
        never enter the extracted tree and cannot turn into gate findings.

        Returns:
            The resulting ``t.Triple[bool, bool, t.SequenceOf[m.Infra.Issue]]``.

        """
        findings: t.MutableSequenceOf[m.Infra.Issue] = []
        embedded = self._embedded_sources(project_dir)
        if not embedded:
            return False, False, ()
        with tempfile.TemporaryDirectory(prefix="flext-markdown-code-") as tmp:
            sources_dir = Path(tmp)
            origin: t.MutableMappingKV[str, t.Pair[str, int]] = {}
            for name, (text, located) in embedded.items():
                (sources_dir / name).write_text(text, c.Cli.ENCODING_DEFAULT)
                origin[name] = located
            ran = True
            formatted = self._run(
                self._format_command(project_dir, sources_dir, write=fix),
                project_dir,
            )
            format_ok = u.Cli.process_succeeded(formatted.outcome)
            if fix:
                findings.extend(
                    self._issues_from_ruff(
                        project_dir,
                        formatted,
                        origin,
                        default_message=(
                            "embedded block does not survive the format round-trip"
                        ),
                    ),
                )
                if format_ok:
                    self._splice_formatted_blocks(project_dir, sources_dir)
            else:
                findings.extend(
                    self._issues_from_ruff(
                        project_dir,
                        formatted,
                        origin,
                        default_message=(
                            "embedded code is not ruff-formatted (fix via `make fix`)"
                        ),
                    ),
                )
            passed = format_ok
        return ran, passed, findings

    def _splice_formatted_blocks(
        self,
        project_dir: Path,
        sources_dir: Path,
    ) -> t.SequenceOf[Path]:
        """Write formatted blocks back into docs whose round-trip recompiles cleanly.

        Enumeration matches the extractor exactly: only parseable non-``notest``
        blocks own a staged source, share its index, and take part in the
        all-or-nothing splice; fragments stay byte-identical.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        """
        rewritten: t.MutableSequenceOf[Path] = []
        for md_path in self._ignore_filtered(
            project_dir,
            FlextInfraMarkdownGateBase.collect_markdown_files(project_dir),
        ):
            spliced = self._splice_document(md_path, project_dir, sources_dir)
            if spliced is not None:
                rewritten.append(spliced)
        return rewritten

    def _splice_document(
        self,
        md_path: Path,
        project_dir: Path,
        sources_dir: Path,
    ) -> Path | None:
        """Write one document's formatted blocks back when its round-trip holds.

        Returns:
            The rewritten path, or ``None`` when the document stayed identical.

        """
        content = md_path.read_text(c.Cli.ENCODING_DEFAULT)
        relative_posix = md_path.relative_to(project_dir).as_posix()
        # Preserve indexes across fragments the formatter does not own.
        staged: t.MutableSequenceOf[t.Pair[int, str]] = []
        for index, match in enumerate(
            match
            for match in c.Infra.MARKDOWN_PY_FENCE_RE.finditer(content)
            if c.Infra.MARKDOWN_CODE_SKIP_MARKER not in match.group("info")
        ):
            code = match.group("code")
            if FlextInfraMarkdownCodeSources.syntax_broken(code, md_path):
                continue
            staged.append((index, code))
        if not staged:
            return None
        blocks, round_trips = self._formatted_blocks(
            staged,
            relative_posix,
            sources_dir,
            md_path,
        )
        if not round_trips:
            return None
        blocks_iter = iter(blocks)

        def _resubstitute(
            match: re.Match[str],
            *,
            origin_path: Path = md_path,
            replacements: Iterator[str] = blocks_iter,
        ) -> str:
            """Splice formatted code; prose fragments stay byte-identical.

            Returns:
                The resulting ``str``.

            """
            keep = c.Infra.MARKDOWN_CODE_SKIP_MARKER in match.group(
                "info",
            ) or FlextInfraMarkdownCodeSources.syntax_broken(
                match.group("code"),
                origin_path,
            )
            if keep:
                return match.group(0)
            return match.group(0).replace(match.group("code"), next(replacements))

        updated = c.Infra.MARKDOWN_PY_FENCE_RE.sub(_resubstitute, content)
        if updated == content:
            return None
        md_path.write_text(updated, c.Cli.ENCODING_DEFAULT)
        return md_path

    @staticmethod
    def _formatted_blocks(
        staged: t.SequenceOf[t.Pair[int, str]],
        relative_posix: str,
        sources_dir: Path,
        md_path: Path,
    ) -> t.Pair[list[str], bool]:
        """Read the formatted sources of one document's parseable blocks.

        Returns:
            The ``(blocks, round_trips)`` pair; a missing or non-recompilable
            staged source ends the round trip.

        """
        blocks: t.MutableSequenceOf[str] = []
        for index, _original in staged:
            source = sources_dir / FlextInfraMarkdownCodeSources.source_name(
                relative_posix,
                index,
            )
            if not source.is_file():
                return (list(blocks), False)
            formatted = source.read_text(c.Cli.ENCODING_DEFAULT)
            if FlextInfraMarkdownCodeSources.syntax_broken(formatted, md_path):
                return (list(blocks), False)
            blocks.append(formatted)
        return (list(blocks), True)

    @override
    def check(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> m.Infra.GateExecution:
        """Validate embedded sources read-only when documentation code exists.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        _ = ctx
        started = time.monotonic()
        ran, passed, issues = self._run_extracted(project_dir, fix=False)
        if not ran:
            return self._skip_result(project_dir, started)
        return self._build_check_gate_execution(
            project_dir,
            passed=passed,
            issues=issues,
            raw_output="\n".join(issue.formatted for issue in issues),
            started=started,
        )

    @override
    def fix(self, project_dir: Path, ctx: m.Infra.GateContext) -> m.Infra.GateExecution:
        """Run the single mutating pass: format blocks and splice clean docs back.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        if ctx.check_only or not ctx.apply_fixes:
            return self._check_only_fix_result(project_dir)
        started = time.monotonic()
        with self._mutation_lease(project_dir):
            ran, passed, issues = self._run_extracted(project_dir, fix=True)
        if not ran:
            return self._skip_result(project_dir, started)
        return self._build_gate_execution(
            project_dir,
            verdict=passed,
            issues=issues,
            raw_output="\n".join(issue.formatted for issue in issues),
            started=started,
        )


__all__: list[str] = ["FlextInfraMarkdownCodeGate"]
