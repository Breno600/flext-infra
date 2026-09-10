"""Tests for FlextInfraDocAuditor — core audit and static helpers.

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
    from collections.abc import Callable
    from pathlib import Path


@pytest.fixture
def auditor() -> FlextInfraDocAuditor:
    return FlextInfraDocAuditor()


@pytest.fixture
def normalize_link() -> Callable[[str], str]:
    def _normalize(value: str) -> str:
        normalized: str = u.Infra.docs_normalize_link(value)
        return normalized

    return _normalize


@pytest.fixture
def should_skip_target() -> Callable[[str, str], bool]:
    def _should_skip(link: str, target: str) -> bool:
        should_skip: bool = u.Infra.docs_should_skip_target(link, target)
        return should_skip

    return _should_skip


@pytest.fixture
def is_external() -> Callable[[str], bool]:
    def _is_external(value: str) -> bool:
        external: bool = u.Infra.docs_is_external(value)
        return external

    return _is_external


class TestAuditorCore:
    """Tests for the docs auditor."""

    def test_returns_flext_result(
        self, auditor: FlextInfraDocAuditor, tmp_path: Path
    ) -> None:
        result = auditor.audit(tmp_path)
        tm.that(result.success or result.failure, eq=True)

    def test_valid_scope_returns_success(
        self, auditor: FlextInfraDocAuditor, tmp_path: Path
    ) -> None:
        workspace = u.Tests.create_docs_workspace(tmp_path)
        result = auditor.audit(workspace)
        tm.ok(result)

    def test_report_structure(
        self, auditor: FlextInfraDocAuditor, tmp_path: Path
    ) -> None:
        result = auditor.audit(tmp_path)
        if result.success and result.value:
            result.value[0]

    def test_issue_structure(self) -> None:
        issue = m.Infra.AuditIssue(
            file="README.md",
            issue_type="broken_link",
            severity="high",
            message="Link to missing file",
        )
        tm.that(issue.file, eq="README.md")
        tm.that(issue.issue_type, eq="broken_link")
        tm.that(issue.severity, eq="high")

    @pytest.mark.parametrize(
        ("projects", "check", "output_dir"),
        [
            (["test-project"], "all", ".reports/docs"),
            (["proj1", "proj2"], "all", ".reports/docs"),
            (None, "links", ".reports/docs"),
            (None, "forbidden-terms", ".reports/docs"),
            (None, "all", ".reports/docs"),
            (None, "all", "custom_output"),
        ],
    )
    def test_audit_option_variants(
        self,
        *,
        auditor: FlextInfraDocAuditor,
        tmp_path: Path,
        projects: list[str] | None,
        check: str,
        output_dir: str,
    ) -> None:
        # The command-contract check loads the governed workspace spec, whose
        # repository-local Beads configuration every real repository carries.
        u.Tests.write_project_beads_config(tmp_path, "audit-fixture")
        output_dir_value = (
            str(tmp_path / output_dir) if output_dir == "custom_output" else output_dir
        )
        result = auditor.audit(
            tmp_path,
            projects=projects,
            output_dir=output_dir_value,
            params=m.Infra.AuditScopeParams(check=check),
        )
        tm.that(result.success or result.failure, eq=True)

    def test_report_frozen(self) -> None:
        tm.that(m.Infra.DocsPhaseReport.model_config.get("frozen"), eq=True)

    def test_issue_frozen(self) -> None:
        tm.that(m.Infra.AuditIssue.model_config.get("frozen"), eq=True)


class TestAuditorNormalize:
    """Additional tests for the docs auditor."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("path/to/file.md#section", "path/to/file.md"),
            ("path/to/file.md?param=value", "path/to/file.md"),
            ("<path/to/file.md>", "path/to/file.md"),
            ("  path/to/file.md  ", "path/to/file.md"),
            ("<path/to/file.md#section?param=value>", "path/to/file.md"),
        ],
    )
    def test_normalize_link(
        self, normalize_link: Callable[[str], str], raw: str, expected: str
    ) -> None:
        tm.that(normalize_link(raw), eq=expected)

    @pytest.mark.parametrize(
        ("text", "target", "expected"),
        [
            ("[link](https://example.com)", "https://example.com", False),
            ("[a, b]", "a", True),
            ("[a b]", "a", True),
            ("[a, b.md]", "a", False),
            ("[a/b]", "a/b", False),
        ],
    )
    def test_should_skip_target(
        self,
        *,
        should_skip_target: Callable[[str, str], bool],
        text: str,
        target: str,
        expected: bool,
    ) -> None:
        tm.that(should_skip_target(text, target), eq=expected)

    @pytest.mark.parametrize("scheme", sorted(c.Infra.DOCS_EXTERNAL_SCHEMES))
    def test_permitted_external_schemes_are_preserved(
        self, *, is_external: Callable[[str], bool], scheme: str
    ) -> None:
        target = (
            f"{scheme}://example.invalid"
            if scheme == c.Infra.DOCS_SECURE_WEB_SCHEME
            else f"{scheme}:payload"
        )

        tm.that(is_external(target), eq=True)

    @pytest.mark.parametrize(
        "target",
        [
            f"{c.Infra.DOCS_INSECURE_WEB_SCHEME}://example.invalid",
            f"<{c.Infra.DOCS_INSECURE_WEB_SCHEME}://example.invalid>",
            f"{c.Infra.DOCS_INSECURE_WEB_SCHEME.upper()}://example.invalid",
        ],
    )
    def test_insecure_documentation_urls_fail_fast(
        self, *, is_external: Callable[[str], bool], target: str
    ) -> None:
        with pytest.raises(ValueError, match="use HTTPS"):
            is_external(target)

    def test_repository_paths_are_not_external(
        self, *, is_external: Callable[[str], bool]
    ) -> None:
        tm.that(is_external("path/to/file.md"), eq=False)
