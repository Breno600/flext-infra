"""Public fix-workflow tests for docs services.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.docs.fixer import FlextInfraDocFixer
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsFixer:
    """Public fix-workflow tests for docs services."""

    @staticmethod
    def test_fix_returns_reports_for_root_and_selected_project(
        tmp_path: Path,
    ) -> None:
        """Test fix returns reports for root and selected project."""
        workspace = u.Tests.create_docs_workspace(
            tmp_path,
            project_names=("flext-a", "flext-b"),
            include_fixable_link=True,
        )

        result = FlextInfraDocFixer().fix(workspace, projects=["flext-a"], apply=False)

        tm.ok(result)
        tm.that([report.scope for report in result.value], eq=["root", "flext-a"])

    @staticmethod
    def test_fix_apply_updates_docs_file_and_writes_reports(
        tmp_path: Path,
    ) -> None:
        """Test fix apply updates docs file and writes reports."""
        workspace = u.Tests.create_docs_workspace(tmp_path, include_fixable_link=True)

        result = FlextInfraDocFixer().fix(workspace, apply=True)

        tm.ok(result)
        tm.that((workspace / "docs/README.md").read_text(), has="guides/setup.md")
        tm.that((workspace / ".reports/docs/fix-report.md").exists(), eq=True)

    @staticmethod
    def test_fix_check_apply_check_converges(tmp_path: Path) -> None:
        """Fail on unapplied drift, apply it, then pass at the fixed point."""
        workspace = u.Tests.create_docs_workspace(tmp_path, include_fixable_link=True)
        fixer = FlextInfraDocFixer()

        check = fixer.fix(workspace, apply=False)
        tm.ok(check)
        tm.that(check.value[0].result, eq=c.Infra.ResultStatus.FAIL)
        tm.that(check.value[0].passed, eq=False)
        tm.that(check.value[0].changed_files, gt=0)

        applied = fixer.fix(workspace, apply=True)
        tm.ok(applied)
        tm.that(applied.value[0].result, eq=c.Infra.ResultStatus.OK)
        tm.that(applied.value[0].passed, eq=True)

        fixed_point = fixer.fix(workspace, apply=False)
        tm.ok(fixed_point)
        tm.that(fixed_point.value[0].result, eq=c.Infra.ResultStatus.OK)
        tm.that(fixed_point.value[0].passed, eq=True)
        tm.that(fixed_point.value[0].changed_files, eq=0)

    @staticmethod
    def test_fix_item_model_tracks_link_and_toc_counts() -> None:
        """Test fix item model tracks link and toc counts."""
        item = m.Infra.DocsPhaseItemModel(phase="fix", file="README.md", links=2, toc=1)

        tm.that(item.file, eq="README.md")
        tm.that(item.links, eq=2)
        tm.that(item.toc, eq=1)

    @staticmethod
    def test_fix_repairs_closing_fence_welded_to_code(tmp_path: Path) -> None:
        """A prior malformed projection converges without per-file repair."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        document = workspace / "docs/welded.md"
        document.write_text(
            "# Example\n\n```python\nvalue = 1```\n\n## Next\n",
            encoding="utf-8",
        )

        result = FlextInfraDocFixer().fix(workspace, apply=True)

        tm.ok(result)
        tm.that(document.read_text(encoding="utf-8"), has="value = 1\n```\n\n## Next")

    @staticmethod
    def test_fix_preserves_indented_closes_and_four_backtick_fences(
        tmp_path: Path,
    ) -> None:
        """Only a welded code line is repaired, never a legitimate fence.

        Rewriting an indented closing fence de-indents the block, leaves a
        whitespace-only line and moves the block boundary, which swallows the
        headings that follow and breaks the mkdocs anchors.
        """
        workspace = u.Tests.create_docs_workspace(tmp_path)
        document = workspace / "docs/indented.md"
        document.write_text(
            (
                "# Example\n"
                "\n"
                "1. **Check**\n"
                "\n"
                "   ```bash\n"
                "   make check\n"
                "   ```\n"
                "\n"
                "````\n"
                "\n"
                "## Next\n"
            ),
            encoding="utf-8",
        )

        result = FlextInfraDocFixer().fix(workspace, apply=True)

        tm.ok(result)
        content = document.read_text(encoding="utf-8")
        tm.that("   ```\n" in content, eq=True)
        tm.that("````\n" in content, eq=True)
        tm.that("   \n```\n" in content, eq=False)

    @staticmethod
    def test_fix_rewrites_bare_notest_fences_for_the_mkdocs_build(
        tmp_path: Path,
    ) -> None:
        """A bare ``notest`` qualifier is rewritten to the attr_list form.

        pymdownx.superfences rejects an info string whose second token is not a
        known option, so the fence is not rendered as code, its contents leak
        as prose and the following headings lose their anchors. The attr_list
        form renders and still carries the marker the code gates skip.
        """
        workspace = u.Tests.create_docs_workspace(tmp_path)
        document = workspace / "docs/notest.md"
        document.write_text(
            "# Example\n\n```python notest\n# comment\nimport os\n```\n\n## Next\n",
            encoding="utf-8",
        )

        result = FlextInfraDocFixer().fix(workspace, apply=True)

        tm.ok(result)
        content = document.read_text(encoding="utf-8")
        tm.that("```{.python .notest}" in content, eq=True)
        tm.that("```python notest" in content, eq=False)
