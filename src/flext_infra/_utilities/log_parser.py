"""Extract error information from verb log files and check reports.

Provides utilities for reading the tail of orchestration log files,
extracting error-like lines for display in orchestrator output, and
reading the SARIF check report back into typed findings.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_cli import u

from flext_core import r
from flext_infra import c, m, t

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesLogParser:
    """Extract error information from verb log files and check reports."""

    # Inline patterns moved to c.Infra.LogParser

    @staticmethod
    def extract_errors(
        log_path: Path, *, max_lines: int = 5
    ) -> t.Pair[int, t.StrSequence]:
        """Read log tail and extract error lines.

        Args:
            log_path: Path to the log file.
            max_lines: Maximum number of error lines to return.

        Returns:
            Tuple of (total_error_count, first_n_error_lines).

        """
        if not log_path.exists():
            return (0, [])
        text = log_path.read_text(encoding=c.Cli.ENCODING_DEFAULT, errors="replace")
        tail = text.splitlines()[-c.Infra.LOG_TAIL_LINES :]
        error_lines: t.MutableSequenceOf[str] = []
        for line in tail:
            stripped = line.strip()
            if not stripped:
                continue
            if any(pattern.search(stripped) for pattern in c.Infra.LOG_NOISE_PATTERNS):
                continue
            if any(pattern.search(stripped) for pattern in c.Infra.LOG_ERROR_PATTERNS):
                error_lines.append(stripped)
        total = len(error_lines)
        return (total, error_lines[:max_lines])

    @staticmethod
    def extract_make_child_exit_code(log_path: Path) -> int | None:
        """Return the recipe exit code GNU make reported, when present.

        GNU make always exits 2 on a failed recipe, so the child's real exit
        code survives only in make's own error line. Returns None when the log
        is absent or carries no such line; read failures escape loudly.
        """
        if not log_path.is_file():
            return None
        content = log_path.read_text(encoding="utf-8", errors="replace")
        matches = tuple(c.Infra.LOG_MAKE_CHILD_EXIT_PATTERN.finditer(content))
        if not matches:
            return None
        return int(matches[-1].group("code"))

    @staticmethod
    def check_report_findings(
        repository_root: Path, *, reports_dir: Path | None = None
    ) -> p.Result[t.VariadicTuple[m.Infra.SarifResult]]:
        """Read the SARIF report ``check run`` wrote into typed findings.

        ``reports_dir`` mirrors ``check run --reports-dir``: a relative value is
        anchored at ``repository_root``; omitted, it is the canonical project
        check report directory the checker writes by default.
        """
        report_dir = (
            u.Cli.resolve_report_dir(
                repository_root, c.Infra.PROJECT, c.Infra.VERB_CHECK
            )
            if reports_dir is None
            else (repository_root / reports_dir).resolve()
        )
        sarif_path = report_dir / c.Infra.CHECK_REPORT_SARIF_FILENAME
        if not sarif_path.is_file():
            return r[t.VariadicTuple[m.Infra.SarifResult]].fail(
                f"check report not found: {sarif_path}"
            )
        return u.validate_value(
            m.Infra.SarifReport,
            sarif_path.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            from_json=True,
        ).map(lambda report: tuple(res for run in report.runs for res in run.results))


__all__: list[str] = ["FlextInfraUtilitiesLogParser"]
