"""Read unresolved new-code issues from the published SonarCloud branch.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra import c, config, m, r, t, u
from flext_infra.maintenance.sonarcloud_client import FlextInfraSonarcloudClient

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraSonarcloudIssues(FlextInfraSonarcloudClient[bool]):
    """Report every unresolved new-code issue without changing SonarCloud."""

    @staticmethod
    def search_form(
        project_key: str,
        branch: str,
        page: int,
    ) -> t.VariadicTuple[t.Pair[str, str]]:
        """Constrain the search to one project and its integration branch.

        Returns:
            The resulting ``t.VariadicTuple[t.Pair[str, str]]``.
        """
        return (
            ("componentKeys", project_key),
            ("branch", branch),
            ("inNewCodePeriod", "true"),
            ("resolved", "false"),
            ("p", str(page)),
        )

    @override
    def execute(self) -> p.Result[bool]:
        """Read every page, then print findings only after complete accounting.

        A missing ``SONAR_TOKEN`` is the operator-ruled declared skip
        (run-if-available-else-skip, 2026-10-08): loud, green, and never a
        failure; a present but malformed token still fails.

        Returns:
            The resulting ``p.Result[bool]``.
        """
        token_result = self.optional_token()
        if token_result.failure:
            return r[bool].from_failure(token_result)
        if not token_result.value.get_secret_value():
            u.Cli.info(
                "SKIP: sonarcloud-issues — SONAR_TOKEN not available "
                "(ai-hub credential ingress); operator ruling 2026-10-08 "
                "run-if-available-else-skip",
            )
            return r[bool].ok(value=False)
        authenticated = self._authenticated_scope()
        if authenticated.failure:
            return r[bool].from_failure(authenticated)
        token, key, branch_value = authenticated.value
        findings = self._read_all_pages(token, key, branch_value)
        if findings.failure:
            return r[bool].from_failure(findings)
        u.Cli.info(
            f"sonarcloud-issues: {key} branch={branch_value} "
            f"unresolved-new-code={len(findings.value)}",
        )
        for issue in findings.value:
            u.Cli.info(issue.model_dump_json())
        return r[bool].ok(value=True)

    def _authenticated_scope(self) -> p.Result[t.Triple[t.SecretStr, str, str]]:
        """Resolve the token, project key, and baseline branch of the audit.

        Returns:
            The resulting ``(token, project_key, branch)`` triple.

        """
        result_type = r[t.Triple[t.SecretStr, str, str]]
        credentials = self.project_credentials()
        if credentials.failure:
            return result_type.from_failure(credentials)
        token, key = credentials.value
        branch = u.Infra.repository_baseline_branch(
            self.repository_root,
            preference=config.Infra.codegen.branch_policy.integration_branch_preference,
        )
        if branch.failure:
            return result_type.from_failure(branch)
        return result_type.ok((token, key, branch.value))

    def _read_all_pages(
        self,
        token: t.SecretStr,
        key: str,
        branch_value: str,
    ) -> p.Result[t.SequenceOf[m.Infra.SonarcloudIssue]]:
        """Read every search page with complete-accounting guarantees.

        Returns:
            The resulting deduplicated issue sequence.

        """
        sonarcloud = config.Infra.codegen.sonarcloud
        findings: list[m.Infra.SonarcloudIssue] = []
        seen: set[str] = set()
        page = 1
        total: int | None = None
        while total is None or len(findings) < total:
            body = self.call(
                sonarcloud.api_url,
                sonarcloud.api_timeout_seconds,
                token,
                (
                    "GET",
                    c.Infra.SONARCLOUD_API_ISSUES_SEARCH_PATH,
                    self.search_form(key, branch_value, page),
                ),
            )
            if body.failure:
                return r[t.SequenceOf[m.Infra.SonarcloudIssue]].from_failure(body)
            parsed = u.validate_value(
                m.Infra.SonarcloudIssueSearch,
                body.value,
                from_json=True,
            )
            if parsed.failure:
                return r[t.SequenceOf[m.Infra.SonarcloudIssue]].from_failure(parsed)
            response = parsed.value
            page_verdict = self._page_verdict(
                response,
                findings,
                page,
                total,
            )
            if page_verdict is not None:
                return page_verdict
            total = response.paging.total
            for issue in response.issues:
                if issue.key in seen:
                    return r[t.SequenceOf[m.Infra.SonarcloudIssue]].fail(
                        f"SonarCloud repeated issue {issue.key}",
                    )
                seen.add(issue.key)
                findings.append(issue)
            if total is not None and len(findings) > total:
                return r[t.SequenceOf[m.Infra.SonarcloudIssue]].fail(
                    "SonarCloud returned more issues than its total",
                )
            page += 1
        return r[t.SequenceOf[m.Infra.SonarcloudIssue]].ok(findings)

    @staticmethod
    def _page_verdict(
        response: m.Infra.SonarcloudIssueSearch,
        findings: t.SequenceOf[m.Infra.SonarcloudIssue],
        page: int,
        total: int | None,
    ) -> p.Result[t.SequenceOf[m.Infra.SonarcloudIssue]] | None:
        """Judge one search page against the paging and completeness contract.

        Returns:
            The page's failure, or ``None`` when the page is contract-clean.

        """
        if response.paging.page_index != page:
            return r[t.SequenceOf[m.Infra.SonarcloudIssue]].fail(
                f"SonarCloud returned page {response.paging.page_index}; "
                f"requested {page}",
            )
        if total is not None and response.paging.total != total:
            return r[t.SequenceOf[m.Infra.SonarcloudIssue]].fail(
                "SonarCloud issue total changed while reading pages",
            )
        if response.paging.total >= c.Infra.SONARCLOUD_ISSUES_SEARCH_LIMIT:
            return r[t.SequenceOf[m.Infra.SonarcloudIssue]].fail(
                "SonarCloud issue search reached its result-window limit; "
                "the issue set cannot be reported as complete",
            )
        if len(response.issues) > response.paging.page_size:
            return r[t.SequenceOf[m.Infra.SonarcloudIssue]].fail(
                "SonarCloud returned more issues than its page size",
            )
        if not response.issues and (total is None or len(findings) < total):
            return r[t.SequenceOf[m.Infra.SonarcloudIssue]].fail(
                "SonarCloud returned an empty page before its total",
            )
        return None


__all__: list[str] = ["FlextInfraSonarcloudIssues"]
