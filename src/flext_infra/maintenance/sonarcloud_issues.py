"""Read unresolved new-code issues from the published SonarCloud branch.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra import c, config, m, r, u
from flext_infra.maintenance.sonarcloud_client import FlextInfraSonarcloudClient

if TYPE_CHECKING:
    from flext_infra import p, t


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

        Returns:
            The resulting ``p.Result[bool]``.
        """
        token = self.required_token()
        if token.failure:
            return r[bool].from_failure(token)
        key = self.project_key(self.repository_root)
        if key.failure:
            return r[bool].from_failure(key)
        branch = u.Infra.repository_baseline_branch(
            self.repository_root,
            preference=config.Infra.codegen.branch_policy.integration_branch_preference,
        )
        if branch.failure:
            return r[bool].from_failure(branch)
        sonarcloud = config.Infra.codegen.sonarcloud
        findings: list[m.Infra.SonarcloudIssue] = []
        seen: set[str] = set()
        page = 1
        total: int | None = None
        while total is None or len(findings) < total:
            body = self.call(
                sonarcloud.api_url,
                sonarcloud.api_timeout_seconds,
                token.value,
                "GET",
                c.Infra.SONARCLOUD_API_ISSUES_SEARCH_PATH,
                self.search_form(key.value, branch.value, page),
            )
            if body.failure:
                return r[bool].from_failure(body)
            parsed = u.validate_value(
                m.Infra.SonarcloudIssueSearch,
                body.value,
                from_json=True,
            )
            if parsed.failure:
                return r[bool].from_failure(parsed)
            response = parsed.value
            if response.paging.page_index != page:
                return r[bool].fail(
                    f"SonarCloud returned page {response.paging.page_index}; "
                    f"requested {page}",
                )
            if total is not None and response.paging.total != total:
                return r[bool].fail(
                    "SonarCloud issue total changed while reading pages",
                )
            total = response.paging.total
            if total >= c.Infra.SONARCLOUD_ISSUES_SEARCH_LIMIT:
                return r[bool].fail(
                    "SonarCloud issue search reached its result-window limit; "
                    "the issue set cannot be reported as complete",
                )
            if len(response.issues) > response.paging.page_size:
                return r[bool].fail(
                    "SonarCloud returned more issues than its page size",
                )
            if not response.issues and len(findings) < total:
                return r[bool].fail(
                    "SonarCloud returned an empty page before its total",
                )
            for issue in response.issues:
                if issue.key in seen:
                    return r[bool].fail(f"SonarCloud repeated issue {issue.key}")
                seen.add(issue.key)
                findings.append(issue)
            if len(findings) > total:
                return r[bool].fail("SonarCloud returned more issues than its total")
            page += 1
        u.Cli.info(
            f"sonarcloud-issues: {key.value} branch={branch.value} "
            f"unresolved-new-code={total}",
        )
        for issue in findings:
            u.Cli.info(issue.model_dump_json())
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraSonarcloudIssues"]
