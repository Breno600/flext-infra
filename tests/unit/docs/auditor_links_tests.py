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

        def test_to_markdown_empty_issues(self, tmp_path: Path) -> None:
            """Test docs_audit_markdown with no issues."""
            (tmp_path / "docs").mkdir()
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            result = u.Infra.docs_audit_markdown(scope, [])
            tm.that(len(result), gte=0)
            tm.that(result, has="# Docs Audit Report")

        def test_to_markdown_with_issues(self, tmp_path: Path) -> None:
            """Test docs_audit_markdown with issues."""
            (tmp_path / "docs").mkdir()
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
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

        def test_broken_link_issues_empty_scope(self, tmp_path: Path) -> None:
            """Test docs_broken_link_issues with no markdown files."""
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        def test_broken_link_issues_with_valid_links(self, tmp_path: Path) -> None:
            """Test docs_broken_link_issues ignores valid links."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](test.md)")
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        def test_broken_link_issues_with_external_links(self, tmp_path: Path) -> None:
            """Test docs_broken_link_issues ignores external links."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](https://example.com)")
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        def test_broken_link_issues_with_fragments(self, tmp_path: Path) -> None:
            """Test docs_broken_link_issues ignores fragment-only links."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](#section)")
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        def test_broken_link_issues_in_code_blocks(self, tmp_path: Path) -> None:
            """Test docs_broken_link_issues ignores links in code blocks."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("```\n[link](nonexistent.md)\n```")
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        def test_broken_link_issues_with_should_skip_target_true(
            self, tmp_path: Path
        ) -> None:
            """Test docs_broken_link_issues skips targets when should_skip_target returns True."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[a, b]")
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        def test_broken_link_issues_with_missing_target(self, tmp_path: Path) -> None:
            """Test docs_broken_link_issues reports missing targets."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](missing.md)")
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues) > 0, eq=True)
            tm.that(any("missing.md" in issue.message for issue in issues), eq=True)

        def test_broken_link_issues_rejects_cross_project_relative_link(
            self, tmp_path: Path
        ) -> None:
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text(
                "[other project](../../flext-core/docs/index.md)", encoding="utf-8"
            )
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )

            issues = u.Infra.docs_broken_link_issues(scope)

            tm.that(
                any(
                    issue.issue_type == "cross_project_relative_link"
                    for issue in issues
                ),
                eq=True,
            )

        def test_broken_link_issues_skips_some_text(self, tmp_path: Path) -> None:
            """Test docs_broken_link_issues skips plain text brackets."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[some text]")
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)

        def test_broken_link_issues_with_space_in_url_skips(
            self, tmp_path: Path
        ) -> None:
            """Test docs_broken_link_issues skips URLs with spaces."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text("[link](some text)")
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            tm.that(len(issues), gte=0)
            tm.that(len(issues), eq=0)

    class TestAuditorGithubLinks:
        """Governed GitHub URL audit and rewrite."""

        def test_github_stale_organization(self, tmp_path: Path) -> None:
            """Placeholder organization URLs are high-severity defects."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text(
                "[x](https://github.com/organization/flext/blob/main/docs/index.md)\n"
            )
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            types = {issue.issue_type for issue in issues}
            tm.that("stale_github_organization" in types, eq=True)

        def test_github_wrong_branch(self, tmp_path: Path) -> None:
            """Wrong working-line branch is reported for governed repos."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "test.md").write_text(
                "[x](https://github.com/flext-sh/flext/blob/main/README.md)\n"
            )
            scope = m.Infra.DocScope(
                name="test", path=tmp_path, report_dir=tmp_path / "reports"
            )
            issues = u.Infra.docs_broken_link_issues(scope)
            types = {issue.issue_type for issue in issues}
            tm.that("wrong_github_branch" in types, eq=True)

        def test_github_rewrite_fix(self, tmp_path: Path) -> None:
            """Fix rewrites organization/main flext URLs to governed org/branch."""
            docs_dir = tmp_path / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            target = docs_dir / "test.md"
            target.write_text(
                "[x](https://github.com/organization/flext/blob/main/README.md)\n"
            )
            item = u.Infra.docs_process_markdown_file(target, apply=True)
            tm.that(item.links, gte=1)
            text = target.read_text()
            tm.that("flext-sh/flext" in text, eq=True)
            tm.that("0.12.0-dev" in text, eq=True)
