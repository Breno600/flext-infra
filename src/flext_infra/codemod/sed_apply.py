"""Sed-by-list mass replacement for the mod verb.

Applies declared literal regex substitutions from config.infra.sed_patterns
across the repository scope with dry-run, fixed-point, and gate validation.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import override

from flext_cli import cli

from flext_core import r

from .. import FlextInfraServiceBase, c, config, m, p, t, u


class FlextInfraCodemodSedApply(FlextInfraServiceBase[t.Cli.ResultValue]):
    """Apply declared sed patterns with fixed-point proof and gate validation."""

    @override
    def execute(self) -> p.Result[t.Cli.ResultValue]:
        """Inspect or apply sed patterns with visible phases."""
        sed_config = config.Infra.sed_patterns
        if not sed_config.patterns:
            cli.display_text("sed: no patterns declared in config.infra.sed_patterns")
            return r[t.Cli.ResultValue].ok(True)

        if self.effective_dry_run:
            cli.display_text(
                f"sed: scan {len(sed_config.patterns)} declared pattern(s)"
            )
            return self._dry_run()
        return self._execute_apply()

    def _dry_run(self) -> p.Result[t.Cli.ResultValue]:
        """Report what would change without mutating."""
        total_changes = 0
        total_files = 0
        for pattern_spec in config.Infra.sed_patterns.patterns:
            file_count, change_count = self._scan_pattern(pattern_spec)
            if change_count:
                cli.display_text(
                    f"sed: pattern '{pattern_spec.pattern}' -> "
                    f"'{pattern_spec.replacement}' would modify {change_count} occurrence(s) "
                    f"in {file_count} file(s)"
                )
            total_changes += change_count
            total_files += file_count
        if total_changes == 0:
            cli.display_text("sed: no changes would be made")
        else:
            cli.display_text(
                f"sed: dry-run complete — {total_changes} change(s) across "
                f"{total_files} file(s)"
            )
        return r[t.Cli.ResultValue].ok(True)

    def _execute_apply(self) -> p.Result[t.Cli.ResultValue]:
        """Apply patterns in place with fixed-point iteration."""
        cli.display_text("sed: validate pattern syntax")
        self._validate_patterns()

        cli.display_text("sed: preflight scan")
        seen: dict[t.VariadicTuple[t.Quad[str, str, str, str]], int] = {}
        iteration = 0

        while True:
            iteration += 1
            fingerprint = self._compute_fingerprint()
            if fingerprint in seen:
                prev_iter = seen[fingerprint]
                return r[t.Cli.ResultValue].fail(
                    f"sed iteration {iteration} made no progress since iteration {prev_iter}; "
                    f"fixed-point proof failed — changes retained for mandatory owner repair"
                )
            seen[fingerprint] = iteration

            changes_made = self._apply_all_patterns()
            if not changes_made:
                cli.display_text(f"sed: fixed point reached at iteration {iteration}")
                break

            cli.display_text(
                f"sed: iteration {iteration} — {changes_made} file(s) modified"
            )

        cli.display_text(
            "sed: require canonical formatting and zero Ruff, Pyrefly, and LSP diagnostics"
        )
        gated = self._run_gates()
        if gated.failure:
            return r[t.Cli.ResultValue].from_failure(gated)
        cli.display_text("sed: fixed point verified with zero findings")
        return r[t.Cli.ResultValue].ok(True)

    def _validate_patterns(self) -> None:
        """Validate all declared pattern regexes compile."""
        for idx, pattern_spec in enumerate(config.Infra.sed_patterns.patterns):
            flags = self._compile_flags(pattern_spec.flags)
            try:
                re.compile(pattern_spec.pattern, flags)
            except re.error as exc:
                msg = f"sed pattern {idx} invalid regex {pattern_spec.pattern!r}: {exc}"
                raise ValueError(msg) from exc

    def _compile_flags(self, flags: t.StrSequence) -> int:
        """Compile regex flags from string names."""
        flag_map = {
            "IGNORECASE": re.IGNORECASE,
            "MULTILINE": re.MULTILINE,
            "DOTALL": re.DOTALL,
        }
        combined = 0
        for name in flags:
            if name not in flag_map:
                msg = f"unknown regex flag {name!r}"
                raise ValueError(msg)
            combined |= flag_map[name]
        return combined

    def _scan_pattern(self, pattern_spec: m.Infra.SedPatternSpec) -> t.Pair[int, int]:
        """Scan for matches without applying. Returns (file_count, change_count)."""
        flags = self._compile_flags(pattern_spec.flags)
        compiled = re.compile(pattern_spec.pattern, flags)
        file_count = 0
        change_count = 0
        for file_path in self._iter_target_files(pattern_spec.file_glob):
            source = file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            matches = list(compiled.finditer(source))
            if matches:
                file_count += 1
                change_count += len(matches)
        return file_count, change_count

    def _iter_target_files(self, file_glob: str | None) -> list[Path]:
        """Iterate Python files in source roots, optionally filtered by glob."""
        roots = u.Infra.governed_project_roots(self.repository_root)
        files: list[Path] = []
        for root in roots:
            src_root = root / c.Infra.DEFAULT_SRC_DIR
            if not src_root.is_dir():
                continue
            if file_glob:
                files.extend(src_root.rglob(file_glob))
            else:
                files.extend(src_root.rglob("*.py"))
        return sorted(set(files))

    def _apply_all_patterns(self) -> int:
        """Apply all patterns once. Returns number of files modified."""
        modified_files: set[Path] = set()
        for pattern_spec in config.Infra.sed_patterns.patterns:
            flags = self._compile_flags(pattern_spec.flags)
            compiled = re.compile(pattern_spec.pattern, flags)
            for file_path in self._iter_target_files(pattern_spec.file_glob):
                source = file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
                updated, count = compiled.subn(pattern_spec.replacement, source)
                if count > 0 and updated != source:
                    if self.apply_changes:
                        u.Cli.atomic_write_text_file(file_path, updated).unwrap()
                    modified_files.add(file_path)
        return len(modified_files)

    def _compute_fingerprint(self) -> t.VariadicTuple[t.Quad[str, str, str, str]]:
        """Compute a fingerprint of all pattern matches across the repository."""
        entries: list[t.Quad[str, str, str, str]] = []
        for pattern_spec in config.Infra.sed_patterns.patterns:
            flags = self._compile_flags(pattern_spec.flags)
            compiled = re.compile(pattern_spec.pattern, flags)
            for file_path in self._iter_target_files(pattern_spec.file_glob):
                source = file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
                entries.extend(
                    (
                        pattern_spec.pattern,
                        pattern_spec.replacement,
                        file_path.as_posix(),
                        match.group(0),
                    )
                    for match in compiled.finditer(source)
                )
        return tuple(sorted(entries))

    def _run_gates(self) -> p.Result[bool]:
        """Run Ruff format, Ruff lint, Pyrefly, and LSP diagnostics gates."""
        # Format
        fmt_result = u.Cli.run_raw(
            [c.Infra.RUFF, "format", "--check", "."],
            cwd=self.repository_root,
            timeout=c.Infra.TIMEOUT_SHORT,
            capture=True,
        )
        if fmt_result.failure:
            return r[bool].fail(f"Ruff format failed: {fmt_result.error}")
        if fmt_result.value.outcome.raw_return_code != 0:
            return r[bool].fail(f"Ruff format check failed: {fmt_result.value.stdout}")

        # Lint
        lint_result = u.Cli.run_raw(
            [c.Infra.RUFF, "check", "."],
            cwd=self.repository_root,
            timeout=c.Infra.TIMEOUT_SHORT,
            capture=True,
        )
        if lint_result.failure:
            return r[bool].fail(f"Ruff lint failed: {lint_result.error}")
        if lint_result.value.outcome.raw_return_code != 0:
            return r[bool].fail(f"Ruff lint failed: {lint_result.value.stdout}")

        # Pyrefly
        pyrefly_result = u.Cli.run_raw(
            [c.Infra.PYREFLY, "check", "."],
            cwd=self.repository_root,
            timeout=c.Infra.TIMEOUT_SHORT,
            capture=True,
        )
        if pyrefly_result.failure:
            return r[bool].fail(f"Pyrefly check failed: {pyrefly_result.error}")
        if pyrefly_result.value.outcome.raw_return_code != 0:
            return r[bool].fail(f"Pyrefly check failed: {pyrefly_result.value.stdout}")

        # LSP diagnostics (via pyright)
        lsp_result = u.Cli.run_raw(
            [c.Infra.PYRIGHT, "."],
            cwd=self.repository_root,
            timeout=c.Infra.TIMEOUT_SHORT,
            capture=True,
        )
        if lsp_result.failure:
            return r[bool].fail(f"LSP diagnostics failed: {lsp_result.error}")
        if lsp_result.value.outcome.raw_return_code != 0:
            return r[bool].fail(f"LSP diagnostics failed: {lsp_result.value.stdout}")

        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraCodemodSedApply"]
