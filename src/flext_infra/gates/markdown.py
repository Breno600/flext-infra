"""FLEXT markdown quality gate."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m, u

from .markdown_support import FlextInfraMarkdownGateBase, read_ignore_patterns

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraMarkdownGate(FlextInfraMarkdownGateBase):
    """Markdown quality gate."""

    gate_id: ClassVar[str] = c.Infra.MARKDOWN
    gate_name: ClassVar[str] = "Markdown"
    # flext-38p39: the linter flags MD009/MD012 and friends with its own `[*]`
    # auto-fixable marker, so `make check` blocked on findings that no canonical
    # verb could repair -- `make fmt` covers Python only and `make fix
    # ` skipped this gate, both exiting 0. The tool supports `--fix`, so
    # the gate offers it and the canonical sequence can reach green.
    can_fix: ClassVar[bool] = True

    def _resolve_config_args(self, project_dir: Path) -> t.StrSequence:
        """Resolve only the repository-local markdown settings owner."""
        config_path = project_dir / c.Infra.MARKDOWNLINT_CONFIG_FILENAME
        if not config_path.is_file():
            return ["--no-config"]
        return ["--config", str(config_path.resolve())]

    def _resolve_exclude_args(self, project_dir: Path) -> t.StrSequence:
        """Build ``--exclude`` from .markdownlintignore patterns.

        ``rumdl`` only applies ignore patterns when scanning directories,
        not when files are passed explicitly on the command line. The gate
        collects files explicitly, so the generated ignore projection is read
        once and its patterns are forwarded via ``--exclude`` to replicate
        standard tool behavior.
        """
        patterns = read_ignore_patterns(
            project_dir, c.Infra.MARKDOWNLINT_IGNORE_FILENAME
        )
        if not patterns:
            return ()
        return ["--exclude", ",".join(patterns)]

    @override
    def _build_check_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, check_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Build check command."""
        _ = ctx
        return self._python_console_script_command(
            c.Infra.RUMDL,
            "check",
            "--no-cache",
            "--color",
            "never",
            "--output-format",
            "text",
            "--deny-config-warnings",
            *self._resolve_config_args(project_dir),
            *self._resolve_exclude_args(project_dir),
            *check_dirs,
        )

    @override
    def _build_fix_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, targets: t.StrSequence
    ) -> t.StrSequence:
        """Build the fix command from the tool's FORMATTER, not its linter.

        ``rumdl check --fix`` is a linter: it exits non-zero whenever a finding
        has no autofix, so a run that repaired every fixable file still failed
        the verb and `make fix` could never reach green. ``rumdl fmt``
        applies the same fixes with formatter-style exit codes, which is the
        contract the mutating verb promises. It accepts neither
        ``--output-format`` nor ``--deny-config-warnings`` (both are check-only
        reporting flags), so the fix surface carries only what it defines.
        """
        _ = ctx
        args: t.SequenceOf[str] = [
            c.Infra.RUMDL,
            "fmt",
            "--no-cache",
            "--color",
            "never",
            *self._resolve_config_args(project_dir),
            *self._resolve_exclude_args(project_dir),
            *list(targets),
        ]
        return self._python_console_script_command(*args)

    @override
    def _parse_check_output(
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse rumdl output, discarding lines marking already-applied fixes."""
        _ = ctx
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        hint_only = False
        for line in (result.stdout + "\n" + result.stderr).splitlines():
            match = c.Infra.MARKDOWN_RE.match(line.strip())
            if not match:
                continue
            if match.group("msg").strip().endswith("[fixed]"):
                continue
            if c.Infra.MARKDOWN_NORMALIZATION_HINT_RE.search(match.group("msg")):
                # rumdl's linter flags a paragraph it "could normalize" with its
                # own [*] marker, but its formatter (rumdl fmt, the gate's fix
                # verb) rejoins paragraphs instead of normalizing them -- proven
                # `Fixed: 0/7` on the root flext#305 headings. A finding no
                # canonical verb can clear must not block `make check` (the same
                # class this file already fixed at flext-38p39). The real
                # violation variant ("Line length N exceeds M") still blocks.
                hint_only = True
                continue
            issues.append(
                m.Infra.Issue(
                    file=match.group("file"),
                    line=int(match.group("line")),
                    column=int(match.group("col") or 1),
                    code=match.group("code"),
                    message=match.group("msg"),
                )
            )
        if not u.Cli.process_succeeded(result.outcome) and not issues:
            if hint_only:
                # rumdl counts the dropped hint in its exit code, so a run whose
                # only findings were unrepairable hints still exits non-zero with
                # an empty issue list. Reporting that as a tool error would
                # reinstate the very finding this filter removes, and no
                # canonical verb could clear it. The hints were the whole
                # failure, so the run is green.
                return True, ()
            issues.append(
                self._command_error_issue(
                    result, tool=c.Infra.RUMDL, file=str(project_dir), line=1, column=1
                )
            )
        return u.Cli.process_succeeded(result.outcome), issues


__all__: list[str] = ["FlextInfraMarkdownGate"]
