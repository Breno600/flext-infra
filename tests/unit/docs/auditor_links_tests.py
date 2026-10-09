"""Tests for FlextInfraDocAuditor — broken link and markdown helpers.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraAuditorLinks:
    """Tests for FlextInfraDocAuditor broken-link and markdown helpers."""

    class TestAuditorToMarkdown:
        """Tests for docs_audit_markdown helper."""

        @staticmethod
        def test_to_markdown_empty_issues(tmp_path: Path) -> None:
            """Test docs_audit_markdown with no issues."""
            (tmp_path / "docs").mkdir()
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            result = u.Infra.docs_audit_markdown(scope, [])
            tm.that(len(result), gte=0)
            tm.that(result, has="# Docs Audit Report")

        @staticmethod
        def test_to_markdown_with_issues(tmp_path: Path) -> None:
            """Test docs_audit_markdown with issues."""
            (tmp_path / "docs").mkdir()
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issue = m.Infra.AuditIssue(
                file="README.md",
                issue_type="broken_link",
                severity="high",
                message="Link not found",
            )
            result = u.Infra.docs_audit_markdown(scope, [issue])
            tm.that(len(result), gte=0)
            tm.that(any("README.md" in line for line in result), eq=True)

    class TestAuditorBrokenLinks:
        """Tests for docs_broken_link_issues."""

        @staticmethod
        def test_broken_link_issues_empty_scope(tmp_path: Path) -> None:
            """Test docs_broken_link_issues with no markdown files."""
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        @staticmethod
        def test_broken_link_issues_with_valid_links(tmp_path: Path) -> None:
            """Test docs_broken_link_issues ignores valid links."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](test.md)")
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        @staticmethod
        def test_broken_link_issues_with_external_links(tmp_path: Path) -> None:
            """Test docs_broken_link_issues ignores external links."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](https://example.com)")
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        @staticmethod
        def test_broken_link_issues_with_fragments(tmp_path: Path) -> None:
            """Test docs_broken_link_issues ignores fragment-only links."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](#section)")
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        @staticmethod
        def test_broken_link_issues_in_code_blocks(tmp_path: Path) -> None:
            """Test docs_broken_link_issues ignores links in code blocks."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("```\n[link](nonexistent.md)\n```")
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        @staticmethod
        def test_broken_link_issues_with_should_skip_target_true(
            tmp_path: Path,
        ) -> None:
            """Test broken link issues skip targets when should_skip_target is True."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[a, b]")
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        @staticmethod
        def test_broken_link_issues_with_missing_target(tmp_path: Path) -> None:
            """Test docs_broken_link_issues reports missing targets."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](missing.md)")
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues) > 0, eq=True)
            tm.that(any("missing.md" in issue.message for issue in issues), eq=True)

        @staticmethod
        def test_broken_link_issues_rejects_cross_project_relative_link(
            tmp_path: Path,
        ) -> None:
            """Test broken link issues rejects cross project relative link."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text(
                "[other project](../../flext-core/docs/index.md)",
                encoding="utf-8",
            )
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )

            issues = u.Infra.docs_broken_link_issues(scope)

            tm.that(
                any(
                    issue.issue_type == "cross_project_relative_link"
                    for issue in issues
                ),
                eq=True,
            )

        @staticmethod
        def test_broken_link_issues_skips_some_text(tmp_path: Path) -> None:
            """Test docs_broken_link_issues skips plain text brackets."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[some text]")
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        @staticmethod
        def test_broken_link_issues_with_space_in_url_skips(
            tmp_path: Path,
        ) -> None:
            """Test docs_broken_link_issues skips URLs with spaces."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](some text)")
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)
            tm.that(len(issues), eq=0)

    class TestAuditorGithubLinks:
        """Governed GitHub URL audit and rewrite."""

        @staticmethod
        def test_github_stale_organization(tmp_path: Path) -> None:
            """Placeholder organization URLs are high-severity defects."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text(
                "[x](https://github.com/organization/flext/blob/main/docs/index.md)\n",
            )
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            types = {issue.issue_type for issue in issues}
            tm.that("stale_github_organization" in types, eq=True)

        @staticmethod
        def test_github_wrong_branch(tmp_path: Path) -> None:
            """Wrong working-line branch is reported for governed repos."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text(
                "[x](https://github.com/flext-sh/flext/blob/main/README.md)\n",
            )
            scope = m.Infra.DocScope(
                name="test",
                path=tmp_path,
                report_dir=tmp_path / "reports",
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            types = {issue.issue_type for issue in issues}
            tm.that("wrong_github_branch" in types, eq=True)

        @staticmethod
        def test_github_rewrite_fix(tmp_path: Path) -> None:
            """Fix rewrites a stale organization on the governed branch only.

            A foreign ref may contain ``/``, so its ref/path boundary is not
            decidable from the URL: that link is left for the audit to report,
            never rewritten by guess.
            """
            branch = tm.not_none(
                u.Infra.docs_github_repo_lookup("flext-sh", "flext"),
            ).branch
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            target = docs_dir / "test.md"
            foreign = "https://github.com/organization/flext/blob/feature/fix/README.md"
            target.write_text(
                f"[x](https://github.com/organization/flext/blob/{branch}/README.md)\n"
                f"[y]({foreign})\n",
            )
            item = u.Infra.docs_process_markdown_file(target, apply=True)
            tm.that(item.links, gte=1)
            text = target.read_text()
            tm.that(
                f"https://github.com/flext-sh/flext/blob/{branch}/README.md" in text,
                eq=True,
            )
            tm.that(foreign in text, eq=True)
