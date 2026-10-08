"""GitHub cross-repo doc URL policy for the flext-infra docs engine.

Resolves governed org/repo/branch maps from ``make.docs.github_repos`` and
rewrites stale placeholder organizations / wrong working-line branches.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from pathlib import Path

from flext_infra import c, m, t
from flext_infra._config import FlextInfraConfig, config

# Concrete-owner imports: this module resolves during the root's lazy ``u``
# export, when the root namespace is still initializing — a root from-import
# would re-enter the partial namespace and fail.


class FlextInfraUtilitiesDocsGithubLinks:
    """Governed GitHub URL helpers for docs audit and fix."""

    @staticmethod
    def _config() -> FlextInfraConfig:

        return config

    @staticmethod
    def docs_github_repos() -> t.VariadicTuple[m.Infra.DocsGithubRepoSpec]:
        """Return the typed GitHub repo map from make.docs SSOT.

        Returns:
            The typed GitHub repo map from make.docs SSOT.

        """
        return config.Infra.codegen.make.docs.github_repos

    @staticmethod
    def docs_stale_github_organizations() -> frozenset[str]:
        """Placeholder organizations that must not appear in doc URLs.

        Returns:
            The resulting ``frozenset[str]``.

        """
        return frozenset(
            FlextInfraUtilitiesDocsGithubLinks._config().Infra.codegen.make.docs.stale_github_organizations,
        )

    @staticmethod
    def docs_github_repo_lookup(
        organization: str,
        repository: str,
    ) -> m.Infra.DocsGithubRepoSpec | None:
        """Find one governed repo by organization and repository name.

        Returns:
            The resulting ``m.Infra.DocsGithubRepoSpec | None``.

        """
        for repo in FlextInfraUtilitiesDocsGithubLinks.docs_github_repos():
            if repo.organization == organization and repo.repository == repository:
                return repo
        # Monorepo members published under flext-sh/<member> map to flext checkout.
        if organization == "flext-sh" and repository.startswith("flext-"):
            for repo in FlextInfraUtilitiesDocsGithubLinks.docs_github_repos():
                if repo.organization == "flext-sh" and repo.repository == "flext":
                    return m.Infra.DocsGithubRepoSpec(
                        organization=repo.organization,
                        repository=repository,
                        branch=repo.branch,
                        local_checkout=repo.local_checkout,
                    )
        return None

    @staticmethod
    def docs_expand_local_checkout(path: str) -> Path | None:
        """Expand ``~`` local_checkout paths; empty means no local check.

        Returns:
            The resulting ``Path | None``.

        """
        value = path.strip()
        if not value:
            return None
        return Path(value).expanduser()

    @staticmethod
    def docs_parse_github_doc_url(target: str) -> re.Match[str] | None:
        """Parse a github.com blob/tree documentation URL.

        Returns:
            The resulting ``re.Match[str] | None``.

        """
        return c.Infra.DOCS_GITHUB_BLOB_TREE_RE.match(target.strip())

    @staticmethod
    def docs_github_governed_path(refpath: str, branch: str) -> str | None:
        """Return the path after ``branch`` when ``refpath`` starts with it.

        Git refs may contain ``/`` (``feature/fix``), so a URL alone cannot say
        where the ref ends. Only the governed branch is a trusted boundary; any
        other ref is unresolvable and yields ``None``.

        Returns:
            The path after ``branch`` when ``refpath`` starts with it.

        """
        prefix = f"{branch}/"
        if not refpath.startswith(prefix):
            return None
        return refpath[len(prefix) :]

    @staticmethod
    def docs_canonical_github_url(
        organization: str,
        repository: str,
        path: str,
        *,
        is_dir: bool = False,
    ) -> str | None:
        """Build a canonical GitHub URL for a governed repository path.

        Returns:
            The resulting ``str | None``.

        """
        repo = FlextInfraUtilitiesDocsGithubLinks.docs_github_repo_lookup(
            organization,
            repository,
        )
        if repo is None:
            return None
        kind = "tree" if is_dir else "blob"
        return (
            f"https://github.com/{repo.organization}/{repo.repository}/"
            f"{kind}/{repo.branch}/{path}"
        )

    @staticmethod
    def docs_rewrite_github_url(target: str) -> str | None:
        """Rewrite a stale org placeholder when the ref is the governed branch.

        A different ref is never rewritten: refs may contain ``/``, so its
        extent (and thus the path) is undecidable from the URL alone. Any
        ``?query``/``#fragment`` suffix is carried over unchanged.

        Returns:
            The resulting ``str | None``.

        """
        match = FlextInfraUtilitiesDocsGithubLinks.docs_parse_github_doc_url(target)
        if match is None:
            stale = FlextInfraUtilitiesDocsGithubLinks.docs_stale_github_organizations()
            for org in stale:
                needle = f"https://github.com/{org}/"
                if target.startswith(needle):
                    # Cannot rewrite without knowing the real org/repo.
                    return None
            return None
        org = match.group("org")
        repository = match.group("repo")
        refpath = match.group("refpath")
        suffix = match.group("suffix") or ""
        kind = match.group("kind")
        stale = FlextInfraUtilitiesDocsGithubLinks.docs_stale_github_organizations()
        lookup_org = org
        if org in stale:
            # Prefer flext-sh for flext-* repos; otherwise leave unresolved.
            if repository == "flext" or repository.startswith("flext-"):
                lookup_org = "flext-sh"
            else:
                return None
        repo = FlextInfraUtilitiesDocsGithubLinks.docs_github_repo_lookup(
            lookup_org,
            repository,
        )
        if repo is None:
            return None
        path = FlextInfraUtilitiesDocsGithubLinks.docs_github_governed_path(
            refpath,
            repo.branch,
        )
        # A foreign ref has no decidable ref/path boundary: the audit reports it
        # as a wrong branch, and no rewrite is guessed.
        if path is None or org == repo.organization:
            return None
        return (
            f"https://github.com/{repo.organization}/{repo.repository}/"
            f"{kind}/{repo.branch}/{path}{suffix}"
        )

    @staticmethod
    def docs_github_local_path(target: str) -> Path | None:
        """Resolve a governed GitHub URL to a local checkout path when configured.

        Returns:
            The resulting ``Path | None``.

        """
        match = FlextInfraUtilitiesDocsGithubLinks.docs_parse_github_doc_url(target)
        if match is None:
            return None
        org = match.group("org")
        repository = match.group("repo")
        if org in FlextInfraUtilitiesDocsGithubLinks.docs_stale_github_organizations():
            return None
        repo = FlextInfraUtilitiesDocsGithubLinks.docs_github_repo_lookup(
            org,
            repository,
        )
        if repo is None:
            return None
        governed_path = FlextInfraUtilitiesDocsGithubLinks.docs_github_governed_path(
            match.group("refpath"),
            repo.branch,
        )
        if governed_path is None:
            return None
        root = FlextInfraUtilitiesDocsGithubLinks.docs_expand_local_checkout(
            repo.local_checkout,
        )
        if root is None:
            return None
        return FlextInfraUtilitiesDocsGithubLinks._github_member_path(
            root,
            repo,
            repository,
            governed_path,
        )

    @staticmethod
    def _github_member_path(
        root: Path,
        repo: m.Infra.DocsGithubRepoSpec,
        repository: str,
        path: str,
    ) -> Path:
        """Join one local checkout root with its governed relative path.

        Returns:
            The resulting ``Path``.

        """
        # Member repos under flext monorepo: flext-sh/flext-core -> ~/flext/flext-core
        if (
            repo.organization == "flext-sh"
            and repository.startswith("flext-")
            and repository != "flext"
            and repo.repository == repository
        ):
            member_root = root / repository if root.name == "flext" else root
            return member_root / path
        if repository.startswith("flext-") and repo.repository == "flext":
            return root / repository / path
        return root / path

    @staticmethod
    def docs_github_link_issues(
        *,
        file: str,
        line_number: int,
        raw: str,
        target: str,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Emit audit issues for stale or locally-missing GitHub doc URLs.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        issues: list[m.Infra.AuditIssue] = []
        match = FlextInfraUtilitiesDocsGithubLinks.docs_parse_github_doc_url(target)
        if match is None:
            return issues
        org = match.group("org")
        if org in FlextInfraUtilitiesDocsGithubLinks.docs_stale_github_organizations():
            issues.append(
                m.Infra.AuditIssue(
                    file=file,
                    issue_type="stale_github_organization",
                    severity="high",
                    message=(
                        f"line {line_number}: placeholder GitHub organization "
                        f"must be rewritten -> {raw}"
                    ),
                ),
            )
            return issues
        repository = match.group("repo")
        repo = FlextInfraUtilitiesDocsGithubLinks.docs_github_repo_lookup(
            org,
            repository,
        )
        if (
            repo is not None
            and FlextInfraUtilitiesDocsGithubLinks.docs_github_governed_path(
                match.group("refpath"),
                repo.branch,
            )
            is None
        ):
            issues.append(
                m.Infra.AuditIssue(
                    file=file,
                    issue_type="wrong_github_branch",
                    severity="high",
                    message=(
                        f"line {line_number}: GitHub branch must be "
                        f"{repo.branch} -> {raw}"
                    ),
                ),
            )
        local = FlextInfraUtilitiesDocsGithubLinks.docs_github_local_path(target)
        if local is not None and not local.exists():
            issues.append(
                m.Infra.AuditIssue(
                    file=file,
                    issue_type="broken_github_link",
                    severity="high",
                    message=(
                        f"line {line_number}: governed GitHub path missing locally "
                        f"({local}) -> {raw}"
                    ),
                ),
            )
        return issues


__all__: list[str] = ["FlextInfraUtilitiesDocsGithubLinks"]
