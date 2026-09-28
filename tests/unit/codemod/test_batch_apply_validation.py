"""Fixed-point validation for staged ast-grep rule cascades."""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import c, m
from flext_infra.codemod.batch_apply import FlextInfraCodemodBatchApply


class TestsFlextInfraCodemodBatchApplyValidation:
    """Keep staged rules distinct from a rewrite that recreates its own finding."""

    @staticmethod
    def _report(path: Path, rule_id: str) -> m.Infra.ModScanReport:
        """Build one actionable ast-grep finding report."""
        finding = m.Infra.ModScanFinding(
            rule_file="fixture.yml",
            rule_id=rule_id,
            repository="fixture",
            file=path,
            source_owner="authored",
            source_state=None,
            range={},
            text="before",
            replacement="after",
            actionable=True,
            classification=c.Infra.ModScanFindingClass.ACTIONABLE,
            payload={},
        )
        return m.Infra.ModScanReport(
            findings=1,
            actionable=1,
            detection_only=0,
            non_actionable_with_fix=0,
            files=frozenset({path}),
            entries=(finding,),
        )

    def test_allows_a_later_rule_enabled_by_a_prior_rewrite(
        self, tmp_path: Path
    ) -> None:
        """A staged rule becomes work for the next fixed-point iteration."""
        before = self._report(tmp_path / "subject.py", "bind-test-utility-alias")
        after = self._report(tmp_path / "subject.py", "rewire-test-utility-receiver")

        FlextInfraCodemodBatchApply.validate_fix_match(before, after)

    def test_rejects_a_rewrite_that_introduces_its_own_rule_again(
        self, tmp_path: Path
    ) -> None:
        """A still-active rule proves that its own fix did not converge."""
        before = self._report(tmp_path / "subject.py", "rewrite-test-utility-receiver")
        after = self._report(tmp_path / "other.py", "rewrite-test-utility-receiver")

        with pytest.raises(RuntimeError, match="introduced 1 new actionable"):
            FlextInfraCodemodBatchApply.validate_fix_match(before, after)
