"""Direct tests for FlextInfraUtilitiesDocsGithubLinks.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import u


class TestsFlextInfraUtilitiesDocsGithubLinks:
    """Direct unit tests for GitHub cross-repo doc URL policy helpers."""

    class TestDocsGithubRepos:
        """Verify the governed GitHub repo map from make.docs SSOT."""

        def test_repos_nonempty(self) -> None:
            repos = u.Infra.docs_github_repos()
            tm.that(len(repos) > 0, eq=True)

        def test_repos_carry_distinct_governed_identities(self) -> None:
            repos = u.Infra.docs_github_repos()
            identities = {(repo.organization, repo.repository) for repo in repos}
            tm.that(all(identities), eq=True)
            tm.that(len(identities), eq=len(repos))
            tm.that(
                all(repo.organization and repo.repository for repo in repos), eq=True
            )

        def test_repos_contain_flext(self) -> None:
            repos = u.Infra.docs_github_repos()
            orgs_repos = {(repo.organization, repo.repository) for repo in repos}
            tm.that(("flext-sh", "flext") in orgs_repos, eq=True)

    class TestStaleGithubOrganizations:
        """Verify placeholder organizations that must be rewritten."""

        def test_stale_organizations_exclude_governed_org(self) -> None:
            stale = u.Infra.docs_stale_github_organizations()
            tm.that("flext-sh" in stale, eq=False)
            tm.that(all(org for org in stale), eq=True)

        def test_stale_organizations_contains_placeholder(self) -> None:
            stale = u.Infra.docs_stale_github_organizations()
            tm.that("organization" in stale, eq=True)

    class TestDocsGithubRepoLookup:
        """Verify repo lookup by organization and repository name."""

        def test_lookup_known_repo(self) -> None:
            repo = u.Infra.docs_github_repo_lookup("flext-sh", "flext")
            tm.that(repo is not None, eq=True)
            if repo is not None:
                tm.that(repo.organization, eq="flext-sh")
                tm.that(repo.repository, eq="flext")

        def test_lookup_member_repo_returns_copy(self) -> None:
            repo = u.Infra.docs_github_repo_lookup("flext-sh", "flext-core")
            tm.that(repo is not None, eq=True)
            if repo is not None:
                tm.that(repo.organization, eq="flext-sh")
                tm.that(repo.repository, eq="flext-core")
                tm.that(repo.branch, eq="0.12.0-dev")

        def test_lookup_unknown_org_returns_none(self) -> None:
            repo = u.Infra.docs_github_repo_lookup("unknown", "repo")
            tm.that(repo is None, eq=True)

        def test_lookup_unknown_repo_returns_none(self) -> None:
            repo = u.Infra.docs_github_repo_lookup("example-org", "nonexistent-repo")
            tm.that(repo is None, eq=True)

    class TestDocsExpandLocalCheckout:
        """Verify local checkout path expansion."""

        def test_empty_path_returns_none(self) -> None:
            tm.that(u.Infra.docs_expand_local_checkout(""), none=True)

        def test_whitespace_path_returns_none(self) -> None:
            tm.that(u.Infra.docs_expand_local_checkout("   "), none=True)

        def test_expand_home_path(self) -> None:
            result = u.Infra.docs_expand_local_checkout("~/flext")
            tm.that(result, eq=Path("~/flext").expanduser())

        def test_expand_absolute_path(self) -> None:
            checkout = Path.home() / "checkout"
            result = u.Infra.docs_expand_local_checkout(str(checkout))
            tm.that(result, eq=checkout)

    class TestDocsParseGithubDocUrl:
        """Verify GitHub blob/tree URL parsing."""

        def test_parse_valid_blob_url(self) -> None:
            match = u.Infra.docs_parse_github_doc_url(
                "https://github.com/flext-sh/flext/blob/main/README.md"
            )
            tm.that(match is not None, eq=True)
            if match is not None:
                tm.that(match.group("org"), eq="flext-sh")
                tm.that(match.group("repo"), eq="flext")
                tm.that(match.group("kind"), eq="blob")
                tm.that(match.group("branch"), eq="main")
                tm.that(match.group("path"), eq="README.md")

        def test_parse_valid_tree_url(self) -> None:
            match = u.Infra.docs_parse_github_doc_url(
                "https://github.com/example-org/example-repo/tree/feature-line/src/"
            )
            tm.that(match is not None, eq=True)
            if match is not None:
                tm.that(match.group("kind"), eq="tree")
                tm.that(match.group("branch"), eq="feature-line")

        def test_parse_non_github_url_returns_none(self) -> None:
            tm.that(
                u.Infra.docs_parse_github_doc_url("https://example.com/foo/bar"),
                none=True,
            )

        def test_parse_invalid_url_returns_none(self) -> None:
            tm.that(u.Infra.docs_parse_github_doc_url("not a url"), none=True)

        def test_parse_strips_surrounding_whitespace(self) -> None:
            match = u.Infra.docs_parse_github_doc_url(
                "  https://github.com/flext-sh/flext/blob/main/README.md  "
            )
            tm.that(match is not None, eq=True)

    class TestDocsCanonicalGithubUrl:
        """Verify canonical URL construction for governed repos."""

        def test_canonical_blob_url(self) -> None:
            url = u.Infra.docs_canonical_github_url("flext-sh", "flext", "README.md")
            tm.that(url is not None, eq=True)
            if url is not None:
                tm.that(
                    url,
                    eq="https://github.com/flext-sh/flext/blob/0.12.0-dev/README.md",
                )

        def test_canonical_tree_url(self) -> None:
            url = u.Infra.docs_canonical_github_url(
                "flext-sh", "flext", "src/", is_dir=True
            )
            tm.that(url is not None, eq=True)
            if url is not None:
                tm.that(
                    url, eq="https://github.com/flext-sh/flext/tree/0.12.0-dev/src/"
                )

        def test_canonical_unknown_repo_returns_none(self) -> None:
            tm.that(
                u.Infra.docs_canonical_github_url("unknown", "repo", "path"), none=True
            )

        def test_canonical_member_repo_url(self) -> None:
            url = u.Infra.docs_canonical_github_url(
                "flext-sh", "flext-core", "src/__init__.py"
            )
            tm.that(url is not None, eq=True)
            if url is not None:
                tm.that(
                    url,
                    eq=(
                        "https://github.com/flext-sh/flext-core/"
                        "blob/0.12.0-dev/src/__init__.py"
                    ),
                )

    class TestDocsRewriteGithubUrl:
        """Verify stale placeholder and wrong-branch URL rewriting."""

        def test_rewrite_stale_org_to_governed(self) -> None:
            rewritten = u.Infra.docs_rewrite_github_url(
                "https://github.com/organization/flext/blob/main/README.md"
            )
            tm.that(rewritten is not None, eq=True)
            if rewritten is not None:
                tm.that(
                    rewritten,
                    eq="https://github.com/flext-sh/flext/blob/0.12.0-dev/README.md",
                )

        def test_rewrite_wrong_branch(self) -> None:
            rewritten = u.Infra.docs_rewrite_github_url(
                "https://github.com/flext-sh/flext/blob/main/README.md"
            )
            tm.that(rewritten is not None, eq=True)
            if rewritten is not None:
                tm.that(
                    rewritten,
                    eq="https://github.com/flext-sh/flext/blob/0.12.0-dev/README.md",
                )

        def test_rewrite_already_correct_returns_none(self) -> None:
            tm.that(
                u.Infra.docs_rewrite_github_url(
                    "https://github.com/flext-sh/flext/blob/0.12.0-dev/README.md"
                ),
                none=True,
            )

        def test_rewrite_member_repo_stale_org(self) -> None:
            rewritten = u.Infra.docs_rewrite_github_url(
                "https://github.com/organization/flext-core/blob/main/README.md"
            )
            tm.that(rewritten is not None, eq=True)
            if rewritten is not None:
                tm.that(
                    rewritten,
                    eq=(
                        "https://github.com/flext-sh/flext-core/"
                        "blob/0.12.0-dev/README.md"
                    ),
                )

        def test_rewrite_stale_org_non_flext_returns_none(self) -> None:
            tm.that(
                u.Infra.docs_rewrite_github_url(
                    "https://github.com/organization/example-org/foo"
                ),
                none=True,
            )

        def test_rewrite_stale_org_unparseable_returns_none(self) -> None:
            tm.that(
                u.Infra.docs_rewrite_github_url(
                    "https://github.com/organization/unknown-repo/blob/main/README.md"
                ),
                none=True,
            )

        def test_rewrite_non_github_url_returns_none(self) -> None:
            tm.that(
                u.Infra.docs_rewrite_github_url("https://example.com/foo/bar"),
                none=True,
            )

    class TestDocsGithubLocalPath:
        """Verify local checkout path resolution for governed URLs."""

        def test_shared_policy_does_not_require_personal_checkouts(self) -> None:
            """Standalone consumers do not depend on the policy author's home tree."""
            for repo in u.Infra.docs_github_repos():
                target = u.Infra.docs_canonical_github_url(
                    repo.organization, repo.repository, "README.md"
                )
                assert target is not None
                assert u.Infra.docs_github_local_path(target) is None
                issues = u.Infra.docs_github_link_issues(
                    file="example.md", line_number=1, raw=target, target=target
                )
                assert not issues

        def test_local_path_stale_org_returns_none(self) -> None:
            tm.that(
                u.Infra.docs_github_local_path(
                    "https://github.com/organization/flext/blob/main/README.md"
                ),
                none=True,
            )

        def test_local_path_unknown_repo_returns_none(self) -> None:
            tm.that(
                u.Infra.docs_github_local_path(
                    "https://github.com/unknown/repo/blob/main/README.md"
                ),
                none=True,
            )

        def test_local_path_non_github_url_returns_none(self) -> None:
            tm.that(
                u.Infra.docs_github_local_path("https://example.com/foo/bar"), none=True
            )

    class TestDocsGithubLinkIssues:
        """Verify audit issue emission for GitHub doc URLs."""

        def test_stale_organization_issue(self) -> None:
            issues = u.Infra.docs_github_link_issues(
                file="test.md",
                line_number=1,
                raw="[x](https://github.com/organization/flext/blob/main/docs/index.md)",
                target=(
                    "https://github.com/organization/flext/blob/main/docs/index.md"
                ),
            )
            tm.that(len(issues) > 0, eq=True)
            tm.that(issues[0].issue_type, eq="stale_github_organization")
            tm.that(issues[0].severity, eq="high")
            tm.that("test.md" in issues[0].file, eq=True)

        def test_wrong_branch_issue(self) -> None:
            issues = u.Infra.docs_github_link_issues(
                file="test.md",
                line_number=3,
                raw="[x](https://github.com/flext-sh/flext/blob/main/README.md)",
                target="https://github.com/flext-sh/flext/blob/main/README.md",
            )
            types = {issue.issue_type for issue in issues}
            tm.that("wrong_github_branch" in types, eq=True)
            for issue in issues:
                if issue.issue_type == "wrong_github_branch":
                    tm.that("0.12.0-dev" in issue.message, eq=True)

        def test_non_url_returns_empty(self) -> None:
            issues = u.Infra.docs_github_link_issues(
                file="test.md",
                line_number=5,
                raw="plain text",
                target="relative/path.md",
            )
            tm.that(len(issues), eq=0)

        def test_correct_url_no_branch_issue(self) -> None:
            target = tm.not_none(
                u.Infra.docs_canonical_github_url("flext-sh", "flext", "README.md")
            )
            issues = u.Infra.docs_github_link_issues(
                file="test.md", line_number=1, raw=f"[x]({target})", target=target
            )
            tm.that(
                [
                    issue
                    for issue in issues
                    if issue.issue_type == "wrong_github_branch"
                ],
                eq=[],
            )

        def test_unknown_repo_no_issues(self) -> None:
            issues = u.Infra.docs_github_link_issues(
                file="test.md",
                line_number=1,
                raw="[x](https://github.com/unknown/repo/blob/main/path.md)",
                target="https://github.com/unknown/repo/blob/main/path.md",
            )
            tm.that(len(issues), eq=0)
