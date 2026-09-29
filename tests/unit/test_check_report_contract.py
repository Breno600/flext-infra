"""Public contract of the ``check`` verb: read-only gates and a readable report.

``make check`` renders ``check run`` without ``--apply`` so validation never
rewrites the tree; ``make fix`` keeps ``--apply``. Findings survive the run in
the SARIF report, which validates back into ``m.Infra.SarifReport`` and is read
through ``u.Infra.check_report_findings``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import c, m, main
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraCheckReportContract:
    """Prove the check verb leaves sources intact and its report round-trips."""

    @staticmethod
    def _project(tmp_path: Path) -> Path:
        project = u.Tests.mk_project(
            tmp_path,
            "p1",
            pyproject='[project]\nname = "p1"\nversion = "0.1.0"\n',
            with_src=True,
        )
        # One fixable lint finding (unused import) that only --apply rewrites.
        (project / "src" / "p1" / "module.py").write_text(
            '"""Fixture module."""\n\nimport os\n', encoding="utf-8"
        )
        return project

    @staticmethod
    def _sources(project: Path) -> t.StrMapping:
        return {
            str(path.relative_to(project)): path.read_text(encoding="utf-8")
            for path in sorted((project / "src").rglob("*.py"))
        }

    @staticmethod
    def _check_run(project: Path, reports: Path, *mode: str) -> int:
        """Run the same ``check run`` argument vector the generated verbs render."""
        return main([
            "check",
            "run",
            "--repository-root",
            str(project),
            "--gates",
            c.Infra.LINT,
            "--projects",
            ".",
            "--reports-dir",
            str(reports),
            *mode,
        ])

    def test_sarif_report_validates_its_own_emitted_json(self) -> None:
        report = m.Infra.SarifReport(
            runs=(
                m.Infra.SarifRun(
                    tool_name="flext-infra-check",
                    information_uri="https://example.invalid/tool",
                    rules=(
                        m.Infra.SarifRule(
                            id="F401",
                            short_description="Ruff Linter (lint) issue",
                            helpUri="https://example.invalid/rule",
                        ),
                    ),
                    results=(
                        m.Infra.SarifResult(
                            ruleId="F401",
                            level="error",
                            message="`os` imported but unused",
                            locations=[
                                m.Infra.SarifLocation(
                                    uri="src/p1/module.py", start_line=3, start_column=8
                                )
                            ],
                        ),
                    ),
                ),
            )
        )

        emitted = report.model_dump_json()

        tm.that(emitted, has='"$schema":')
        tm.that(m.Infra.SarifReport.model_validate_json(emitted), eq=report)

    def test_check_without_apply_leaves_sources_and_reports_findings(
        self, tmp_path: Path
    ) -> None:
        project = self._project(tmp_path)
        reports = tmp_path / "reports"
        before = self._sources(project)

        tm.that(self._check_run(project, reports), eq=1)

        tm.that(self._sources(project), eq=before)
        findings = tm.ok(u.Infra.check_report_findings(project, reports_dir=reports))
        tm.that(
            [
                location.uri
                for finding in findings
                for location in finding.locations
                if location.uri.endswith("module.py")
            ],
            empty=False,
        )

    def test_check_with_apply_is_the_mutating_fix_path(self, tmp_path: Path) -> None:
        project = self._project(tmp_path)
        before = self._sources(project)

        tm.that(self._check_run(project, tmp_path / "reports", "--apply"), eq=0)

        tm.that(self._sources(project), ne=before)
