"""Census violations come from the one rule engine's namespace report.

The namespace report is the engine's catalog scan of one project; the census
parses each report line into a typed violation whose fixability is the
declaring rule's own fix or relocation in the project's rule plan.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_core import r
from flext_infra.codegen.census import FlextInfraCodegenCensus
from flext_infra.validate.namespace_validator import FlextInfraNamespaceValidator
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraCodegenCensus:
    """Parse the engine's namespace report into census violations."""

    _FIXABLE_RULE = "census-fixable"
    _DETECT_RULE = "census-detect-only"

    @classmethod
    def _project(cls, tmp_path: Path) -> Path:
        project = tmp_path / "census-contract"
        config_path = project / c.Infra.CODEMOD_CONFIG_RELPATH
        rules = config_path.parent / c.Cli.RULES_DIR_NAME
        rules.mkdir(parents=True)
        (project / "src").mkdir()
        (project / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "census-contract"\nversion = "1.0.0"\n'
            "dependencies = []\n",
            encoding="utf-8",
        )
        config_path.write_text(
            f"ruleDirs: [{c.Cli.RULES_DIR_NAME}]\n",
            encoding="utf-8",
        )
        (rules / "fixable.yml").write_text(
            f"id: {cls._FIXABLE_RULE}\nlanguage: Python\nseverity: error\n"
            "message: Observed fixable\nrule:\n  pattern: first($VALUE)\n"
            "fix: second($VALUE)\n",
            encoding="utf-8",
        )
        (rules / "detect.yml").write_text(
            f"id: {cls._DETECT_RULE}\nlanguage: Python\nseverity: error\n"
            "message: Observed detect-only\nrule:\n  pattern: third($VALUE)\n",
            encoding="utf-8",
        )
        (project / "src" / "subject.py").write_text(
            "first(1)\nthird(2)\n",
            encoding="utf-8",
        )
        # A governed project carries its Mise declaration: the census runs
        # ast-grep from the project, and the shim resolves the pinned tool
        # from that declaration, never from a developer's global config.
        u.Tests.copy_tracked_mise_seeds(project)
        return project

    def test_report_violations_carry_rule_location_and_fixability(
        self,
        tmp_path: Path,
    ) -> None:
        """Test report violations carry rule location and fixability."""
        project = self._project(tmp_path)
        report = FlextInfraNamespaceValidator(repository_root=project).build_report()

        violations = tm.ok(u.Infra.parse_namespace_validation(report, project))

        observed = {
            violation.rule: violation
            for violation in violations
            if violation.rule in {self._FIXABLE_RULE, self._DETECT_RULE}
        }
        tm.that(sorted(observed), eq=sorted((self._FIXABLE_RULE, self._DETECT_RULE)))
        fixable = observed[self._FIXABLE_RULE]
        detect = observed[self._DETECT_RULE]
        tm.that((fixable.module, fixable.line), eq=("src/subject.py", 1))
        tm.that((detect.module, detect.line), eq=("src/subject.py", 2))
        tm.that(fixable.message, eq="Observed fixable")
        tm.that(fixable.fixable, eq=True)
        tm.that(detect.fixable, eq=False)

    @pytest.mark.parametrize(
        "violation",
        [
            "",
            "random text without brackets",
            "[census-fixable] src/file.py:10 - wrong dash instead of em-dash",
            "src/file.py:10 — Missing rule prefix",
            "[census-fixable] src/file.py:notanumber — message",
        ],
        ids=["empty", "no-brackets", "wrong-dash", "missing-rule", "non-numeric"],
    )
    def test_malformed_report_line_raises(self, tmp_path: Path, violation: str) -> None:
        """Test malformed report line raises."""
        project = self._project(tmp_path)
        report = r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(passed=False, violations=[violation]),
        )

        with pytest.raises(ValueError, match="report format"):
            u.Infra.parse_namespace_validation(report, project)

    def test_report_failure_propagates(self, tmp_path: Path) -> None:
        """Test report failure propagates."""
        project = self._project(tmp_path)
        report = r[m.Infra.ValidationReport].fail("scan failed")

        tm.fail(u.Infra.parse_namespace_validation(report, project), has="scan failed")

    @staticmethod
    def test_execute_fails_when_apply_changes_requested(tmp_path: Path) -> None:
        """Test execute fails when apply changes requested."""
        result = FlextInfraCodegenCensus(
            repository_root=tmp_path,
            apply_changes=True,
        ).execute()

        tm.fail(
            result,
            has="census is read-only; use flext-infra codegen auto-fix --apply",
        )
