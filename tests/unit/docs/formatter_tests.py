"""Public format-workflow tests for docs services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.docs.formatter import FlextInfraDocFormatter
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsFormatter:
    """Public format-workflow tests for docs services."""

    @staticmethod
    def _write_prettier_policy(workspace: Path) -> None:
        """Provide the generated prettier settings owner the gate requires."""
        (workspace / c.Infra.PRETTIER_CONFIG_FILENAME).write_text(
            "{}\n", encoding="utf-8"
        )

    def test_fmt_returns_report_for_root_scope(self, tmp_path: Path) -> None:
        """The format phase reports the root scope like every docs phase."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        self._write_prettier_policy(workspace)

        result = FlextInfraDocFormatter().format(workspace, apply=True)

        tm.ok(result)
        tm.that([report.scope for report in result.value], eq=["workspace"])
        tm.that(result.value[0].phase, eq="fmt")

    def test_fmt_check_apply_check_converges(self, tmp_path: Path) -> None:
        """Fail on unformatted drift, format it, then pass at the fixed point."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        self._write_prettier_policy(workspace)
        (workspace / "docs/README.md").write_text(
            "#   Docs\n\n##   Overview\ntrailing spaces   \n", encoding="utf-8"
        )
        formatter = FlextInfraDocFormatter()

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
            (workspace / "docs/README.md").read_text(encoding="utf-8"), has="# Docs\n"
        )

        fixed_point = formatter.format(workspace, apply=False)
        tm.ok(fixed_point)
        tm.that(fixed_point.value[0].result, eq=c.Infra.ResultStatus.OK)
        tm.that(fixed_point.value[0].passed, eq=True)
        tm.that(fixed_point.value[0].reason, eq="pending:0")

    def test_fmt_check_only_never_rewrites_the_tree(self, tmp_path: Path) -> None:
        """The preview pass leaves the pending drift untouched on disk."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        self._write_prettier_policy(workspace)
        drift = "#   Docs\n\n##   Overview\n"
        (workspace / "docs/README.md").write_text(drift, encoding="utf-8")

        result = FlextInfraDocFormatter().format(workspace, apply=False)

        tm.ok(result)
        tm.that((workspace / "docs/README.md").read_text(encoding="utf-8"), eq=drift)

    def test_fmt_fails_closed_without_generated_prettier_config(
        self, tmp_path: Path
    ) -> None:
        """A missing generated .prettierrc is a generation gap, never a pass."""
        workspace = u.Tests.create_docs_workspace(tmp_path)

        result = FlextInfraDocFormatter().format(workspace, apply=False)

        tm.ok(result)
        tm.that(result.value[0].passed, eq=False)
        tm.that(result.value[0].result, eq=c.Infra.ResultStatus.FAIL)
