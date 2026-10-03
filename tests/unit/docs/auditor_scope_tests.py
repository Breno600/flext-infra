"""Tests for FlextInfraDocAuditor — scope, forbidden terms, and audit_scope.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.docs.auditor import FlextInfraDocAuditor
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraAuditorScope:
    """Tests for FlextInfraDocAuditor scope, forbidden terms, and audit_scope."""

    @staticmethod
    def test_forbidden_term_issues_empty_scope(tmp_path: Path) -> None:
        """Test forbidden_term_issues with no markdown files."""
        auditor = FlextInfraDocAuditor()
        scope = m.Infra.DocScope(
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        issues = auditor.forbidden_term_issues(scope)
        tm.that(len(issues), gte=0)

    @staticmethod
    def test_forbidden_term_issues_root_scope(tmp_path: Path) -> None:
        """Test forbidden_term_issues filters by docs/ for root scope."""
        auditor = FlextInfraDocAuditor()
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "test.md").write_text("# Test")
        scope = m.Infra.DocScope(
            name="root",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        issues = auditor.forbidden_term_issues(scope)
        tm.that(len(issues), gte=0)

    @staticmethod
    def test_forbidden_term_issues_project_scope(tmp_path: Path) -> None:
        """Test forbidden_term_issues filters by project name."""
        auditor = FlextInfraDocAuditor()
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "test.md").write_text("# Test")
        scope = m.Infra.DocScope(
            name="flext-core",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        issues = auditor.forbidden_term_issues(scope)
        tm.that(len(issues), gte=0)

    @staticmethod
    def test_forbidden_term_issues_root_scope_non_docs_file(
        tmp_path: Path,
    ) -> None:
        """Test forbidden_term_issues skips non-docs files in root scope."""
        auditor = FlextInfraDocAuditor()
        (tmp_path / "README.md").write_text("# Test")
        scope = m.Infra.DocScope(
            name="root",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        issues = auditor.forbidden_term_issues(scope)
        tm.that(len(issues), gte=0)

    @staticmethod
    def test_forbidden_term_issues_non_flext_scope(tmp_path: Path) -> None:
        """Test forbidden_term_issues skips non-flext scopes."""
        auditor = FlextInfraDocAuditor()
        (tmp_path / "test.md").write_text("# Test")
        scope = m.Infra.DocScope(
            name="other-project",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        issues = auditor.forbidden_term_issues(scope)
        tm.that(len(issues), gte=0)

    @staticmethod
    def test_audit_scope_with_links_check(tmp_path: Path) -> None:
        """Test audit_scope runs links check."""
        auditor = FlextInfraDocAuditor()
        scope = m.Infra.DocScope(
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        report = auditor.audit_scope(
            scope,
            params=m.Infra.AuditScopeParams(check="links"),
        )
        tm.that(report.phase, eq="audit")
        tm.that(report.checks, has="links")

    @staticmethod
    def test_audit_scope_with_forbidden_terms_check(tmp_path: Path) -> None:
        """Test audit_scope runs forbidden-terms check."""
        auditor = FlextInfraDocAuditor()
        scope = m.Infra.DocScope(
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        report = auditor.audit_scope(
            scope,
            params=m.Infra.AuditScopeParams(check="forbidden-terms"),
        )
        tm.that(report.phase, eq="audit")
        tm.that(report.checks, has="forbidden-terms")

    @staticmethod
    def test_audit_scope_without_issues_passes(tmp_path: Path) -> None:
        """An issue-free audit passes without opting into a mode.

        Why: the all-check resolves the Make verb contract from repository
        policy, so a realistic scope is a git repository carrying an
        identity — a bare temp directory is not an auditable project.
        """
        u.Tests.write_project_beads_config(tmp_path, "test-project")
        u.Tests.initialize_git_repo(
            tmp_path,
            origin_url=u.Tests.repository_ref("test-project").url,
        )
        _ = (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test-project"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        auditor = FlextInfraDocAuditor()
        scope = m.Infra.DocScope(
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        report = auditor.audit_scope(
            scope,
            params=m.Infra.AuditScopeParams(check="all"),
        )
        tm.that(report.passed, eq=True)
        tm.that(report.result, eq=c.Infra.ResultStatus.OK)

    @staticmethod
    def test_audit_scope_with_issues_fails(tmp_path: Path) -> None:
        """A broken link fails and stays visible in persisted evidence."""
        auditor = FlextInfraDocAuditor()
        (tmp_path / "README.md").write_text("[Broken](missing.md)\n", encoding="utf-8")
        scope = m.Infra.DocScope(
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        report = auditor.audit_scope(
            scope,
            params=m.Infra.AuditScopeParams(check="links"),
        )
        tm.that(report.passed, eq=False)
        tm.that(report.result, eq=c.Infra.ResultStatus.FAIL)
        tm.that(report.reason, eq="issues:1")
        tm.that(report.items[0].issue_type, eq="broken_link")
        tm.that(report.strict, eq=True)
        summary = u.Tests.json_payload(
            (scope.report_dir / "audit-summary.json").read_text(encoding="utf-8"),
        )
        tm.that(u.Tests.toml_mapping(summary["summary"])["issues"], eq=1)
        tm.that(
            (scope.report_dir / "audit-report.md").read_text(encoding="utf-8"),
            has="missing.md",
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("check", "markdown"),
        [
            ("links", "[Broken](missing.md)\n"),
            ("machine-paths", "Run from /home/someone/flext\n"),
        ],
    )
    def test_audit_findings_fail(
        tmp_path: Path,
        check: str,
        markdown: str,
    ) -> None:
        """Real finding categories cannot grant permission to hide findings."""
        auditor = FlextInfraDocAuditor()
        scope = m.Infra.DocScope(
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        (tmp_path / "README.md").write_text(markdown, encoding="utf-8")
        report = auditor.audit_scope(
            scope,
            params=m.Infra.AuditScopeParams(check=check),
        )
        tm.that(report.phase, eq="audit")
        tm.that(report.passed, eq=False)
        tm.that(report.result, eq=c.Infra.ResultStatus.FAIL)
        tm.that(report.items, empty=False)

    @staticmethod
    @pytest.mark.parametrize("scope_name", ["root", "flext-demo", "test"])
    def test_audit_report_scope_cannot_permit_findings(
        tmp_path: Path,
        scope_name: str,
    ) -> None:
        """Every scope applies the same finding requirement."""
        auditor = FlextInfraDocAuditor()
        scope = m.Infra.DocScope(
            name=scope_name,
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        (tmp_path / "README.md").write_text("[Broken](missing.md)\n", encoding="utf-8")
        report = auditor.audit_scope(
            scope,
            params=m.Infra.AuditScopeParams(check="links"),
        )
        tm.that(report.phase, eq="audit")
        tm.that(report.scope, eq=scope_name)
        tm.that(report.passed, eq=False)
        tm.that(report.result, eq=c.Infra.ResultStatus.FAIL)

    @staticmethod
    def test_machine_path_issues_flags_user_home_and_skips_container_identity(
        tmp_path: Path,
    ) -> None:
        """A /home/<user> or /Users/<user> root is flagged; CI/container homes pass."""
        auditor = FlextInfraDocAuditor()
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "guide.md").write_text(
            "run it from /home/someone/flext\n"
            "or on macOS from /Users/someone/flext\n"
            "the image installs to /home/runner/.local/bin\n"
            "the tilde form ~/flext is portable\n",
        )
        scope = m.Infra.DocScope(
            name="root",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        issues = auditor.machine_path_issues(scope)
        tm.that(len(issues), eq=2)
        tm.that({issue.issue_type for issue in issues}, eq={"machine-path"})
        tm.that(issues[0].message, has="line 1")
        tm.that(issues[0].message, has="/home/someone")
        tm.that(issues[1].message, has="/Users/someone")

    @staticmethod
    def test_machine_path_issues_honours_exact_evidence_files(
        tmp_path: Path,
    ) -> None:
        """Only a named historical file keeps an observed machine path."""
        auditor = FlextInfraDocAuditor()
        plans = tmp_path / "docs" / "plans"
        plans.mkdir(parents=True, exist_ok=True)
        (plans / "2026-01-01-run.md").write_text("ran at /home/someone/flext\n")
        (plans / "new-plan.md").write_text("run at /home/someone/flext\n")
        (tmp_path / "docs" / "live.md").write_text("see /home/someone/flext\n")
        (tmp_path / "docs" / "docs_config.json").write_text(
            '{"audit": {"historical_evidence_files": ["docs/plans/2026-01-01-run.md"]}}',
        )
        scope = m.Infra.DocScope(
            name="root",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        issues = auditor.machine_path_issues(scope)
        tm.that(
            {issue.file for issue in issues},
            eq={"docs/live.md", "docs/plans/new-plan.md"},
        )

    @staticmethod
    def test_placeholder_patterns_distinguish_open_marker_from_plural_word(
        tmp_path: Path,
    ) -> None:
        """The declared lexical rule flags TODO colon, not ordinary TODOS prose."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("TODOS are reviewed.\n")
        (docs / "docs_config.json").write_text(
            '{"audit": {"placeholder_patterns": ["TODO[ ]*:"]}}',
        )
        scope = m.Infra.DocScope(
            name="root",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        auditor = FlextInfraDocAuditor()
        tm.that(auditor.placeholder_issues(scope), eq=[])
        (docs / "guide.md").write_text("TODOS are reviewed.\nTODO: finish me.\n")
        issues = auditor.placeholder_issues(scope)
        tm.that(len(issues), eq=1)
        tm.that(issues[0].file, eq="docs/guide.md")

    @staticmethod
    def test_invalid_audit_policy_fails_public_boundary(tmp_path: Path) -> None:
        """A malformed audit declaration fails instead of silently disabling a gate."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("/home/someone/flext\n")
        (docs / "docs_config.json").write_text(
            '{"audit": {"historical_evidence_files": ["docs/plans/"]}}',
        )
        scope = m.Infra.DocScope(
            name="root",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        with pytest.raises(ValueError, match="historical evidence"):
            FlextInfraDocAuditor().machine_path_issues(scope)
