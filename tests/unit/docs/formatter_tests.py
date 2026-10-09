"""Public format-workflow tests for docs services.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import infra
from flext_infra.docs.fixer import FlextInfraDocFixer
from flext_infra.docs.formatter import FlextInfraDocFormatter
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsFormatter:
    """Public format-workflow tests for docs services."""

    @staticmethod
    def _formatter() -> FlextInfraDocFormatter:
        """Bind the formatter to the facade's markdown format gate.

        Returns:
            The resulting ``FlextInfraDocFormatter``.

        """
        return FlextInfraDocFormatter(format_gate=infra.markdown_format_gate)

    @staticmethod
    def _write_markdown_rules(workspace: Path) -> None:
        """Provide the generated markdown rule projection the gate requires."""
        (workspace / c.Infra.MARKDOWNLINT_CONFIG_FILENAME).write_text(
            "{}\n",
            encoding="utf-8",
        )

    def test_fmt_returns_report_for_root_scope(self, tmp_path: Path) -> None:
        """The format phase reports the root scope like every docs phase."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        self._write_markdown_rules(workspace)

        result = self._formatter().format(workspace, apply=True)

        tm.ok(result)
        tm.that([report.scope for report in result.value], eq=["workspace"])
        tm.that(result.value[0].phase, eq="fmt")

    def test_fmt_check_apply_check_converges(self, tmp_path: Path) -> None:
        """Fail on unformatted drift, format it, then pass at the fixed point."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        self._write_markdown_rules(workspace)
        (workspace / "docs/README.md").write_text(
            "#   Docs\n\n##   Overview\ntrailing spaces   \n",
            encoding="utf-8",
        )
        formatter = self._formatter()

        check = formatter.format(workspace, apply=False)
        tm.ok(check)
        tm.that(check.value[0].result, eq=c.Infra.ResultStatus.FAIL)
        tm.that(check.value[0].passed, eq=False)
        tm.that(check.value[0].reason, eq="pending:1")
        tm.that((workspace / ".reports/docs/fmt-report.md").exists(), eq=True)

        applied = formatter.format(workspace, apply=True)
        tm.ok(applied)
        tm.that(applied.value[0].result, eq=c.Infra.ResultStatus.OK)
        tm.that(applied.value[0].passed, eq=True)
        tm.that(
            (workspace / "docs/README.md").read_text(encoding="utf-8"),
            has="# Docs\n",
        )

        fixed_point = formatter.format(workspace, apply=False)
        tm.ok(fixed_point)
        tm.that(fixed_point.value[0].result, eq=c.Infra.ResultStatus.OK)
        tm.that(fixed_point.value[0].passed, eq=True)
        tm.that(fixed_point.value[0].reason, eq="pending:0")

    def test_toc_fix_and_format_keep_literal_code_symbols(self, tmp_path: Path) -> None:
        """A rendered TOC must survive the real fixer and formatter together."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        self._write_markdown_rules(workspace)
        document = workspace / "docs/toc.md"
        document.write_text(
            "# Docs\n\n"
            "## Config module `<project>/_config.py`\n\n"
            "## Settings `*_dir`\n\n"
            "## Exports `pkg.__all__`\n\n"
            "## Models `m.*`\n\n"
            "## New `flext-*` packages\n",
            encoding="utf-8",
        )
        fixer = FlextInfraDocFixer()
        formatter = self._formatter()

        first_fix = fixer.fix(workspace, apply=True)
        tm.ok(first_fix)
        first_format = formatter.format(workspace, apply=True)
        tm.ok(first_format)
        formatted = document.read_text(encoding="utf-8")

        second_fix = fixer.fix(workspace, apply=True)
        tm.ok(second_fix)
        tm.that(second_fix.value[0].changed_files, eq=0)
        second_format = formatter.format(workspace, apply=True)
        tm.ok(second_format)
        tm.that(second_format.value[0].passed, eq=True)
        tm.that(second_format.value[0].changed_files, eq=0)
        tm.that(document.read_text(encoding="utf-8"), eq=formatted)

    def test_fmt_check_only_never_rewrites_the_tree(self, tmp_path: Path) -> None:
        """The preview pass leaves the pending drift untouched on disk."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        self._write_markdown_rules(workspace)
        drift = "#   Docs\n\n##   Overview\n"
        (workspace / "docs/README.md").write_text(drift, encoding="utf-8")

        result = self._formatter().format(workspace, apply=False)

        tm.ok(result)
        tm.that((workspace / "docs/README.md").read_text(encoding="utf-8"), eq=drift)

    def test_fmt_fails_closed_without_generated_markdown_rules(
        self,
        tmp_path: Path,
    ) -> None:
        """A missing generated .markdownlint.json is a generation gap, never a pass."""
        workspace = u.Tests.create_docs_workspace(tmp_path)

        result = self._formatter().format(workspace, apply=False)

        tm.ok(result)
        tm.that(result.value[0].passed, eq=False)
        tm.that(result.value[0].result, eq=c.Infra.ResultStatus.FAIL)
