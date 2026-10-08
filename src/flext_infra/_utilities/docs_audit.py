"""Audit helpers for docs services.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from pathlib import Path

from flext_infra import c, config, m, t
from flext_infra._utilities import (
    FlextInfraUtilitiesDocs,
    FlextInfraUtilitiesDocsApi,
    FlextInfraUtilitiesDocsAuditDetectorsMixin,
    FlextInfraUtilitiesDocsCommandContractMixin,
    FlextInfraUtilitiesDocsGithubLinks,
    FlextInfraUtilitiesDocsScope,
)


class FlextInfraUtilitiesDocsAudit(
    FlextInfraUtilitiesDocsAuditDetectorsMixin,
    FlextInfraUtilitiesDocsCommandContractMixin,
):
    """Reusable audit helpers exposed through ``u.Infra``."""

    @staticmethod
    def docs_normalize_link(target: str) -> str:
        """Strip fragments and query strings from a markdown link target.

        Returns:
            The resulting ``str``.

        """
        value = target.strip()
        if value.startswith("<") and value.endswith(">"):
            value = value[1:-1].strip()
        return value.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0]

    @staticmethod
    def docs_should_skip_target(raw: str, target: str) -> bool:
        """Return whether the target should be ignored as prose, not a path.

        Returns:
            Whether the target should be ignored as prose, not a path.

        """
        if FlextInfraUtilitiesDocs.docs_is_secure_web_url(target):
            return False
        looks_like_prose = ".md" not in raw and "/" not in raw
        return looks_like_prose and ("," in raw or " " in raw)

    @staticmethod
    def docs_strip_inline_code(line: str) -> str:
        """Remove inline-code spans from one markdown line.

        Returns:
            The resulting ``str``.

        """
        pieces: list[str] = []
        in_code = False
        for char in line:
            if char == "`":
                in_code = not in_code
                continue
            if not in_code:
                pieces.append(char)
        return "".join(pieces)

    @staticmethod
    def docs_markdown_link_targets(line: str) -> t.StrSequence:
        """Return markdown link targets from one line.

        Returns:
            Markdown link targets from one line.

        """
        targets: list[str] = []
        index = 0
        while index < len(line):
            close_label = line.find("](", index)
            if close_label < 0:
                break
            close_target = line.find(")", close_label + 2)
            if close_target < 0:
                break
            targets.append(line[close_label + 2 : close_target])
            index = close_target + 1
        return targets

    @staticmethod
    def docs_audit_policy(scope: m.Infra.DocScope) -> m.Infra.DocsAuditPolicySpec:
        """Parse the scope's authenticated audit declaration once into its contract.

        Returns:
            The resulting ``m.Infra.DocsAuditPolicySpec``.

        """
        # Why: the scope's own declared `repository_root` (not a `.parent`
        # heuristic) owns docs policy resolution — a workspace-root project
        # scope IS its own repository root, and only a genuine member-project
        # scope carries a `repository_root_override` set at scope build time.

        payload = FlextInfraUtilitiesDocsScope.load_config(scope.repository_root)
        return m.Infra.DocsAuditPolicySpec.model_validate(payload.get("audit", {}))

    @staticmethod
    def docs_generated_api_reference_path(relative_docs_path: str) -> bool:
        """Return whether a docs path is owned by generated API reference.

        Returns:
            Whether a docs path is owned by generated API reference.

        """
        return relative_docs_path.startswith(
            "api-reference/generated/",
        ) and relative_docs_path.endswith(".md")

    @staticmethod
    def docs_live_public_symbol_names(scope: m.Infra.DocScope) -> set[str]:
        """Return public symbol names that are still exported by one docs scope.

        Returns:
            Public symbol names that are still exported by one docs scope.

        """
        if not scope.package_name:
            return set()
        contract = FlextInfraUtilitiesDocsApi.public_contract(
            scope.path,
            scope.package_name,
        )
        names: set[str] = set()
        for key in ("exports", "public_symbols"):
            value = contract.get(key)
            if not isinstance(value, list):
                continue
            names.update(item for item in value if isinstance(item, str))
        return names

    @staticmethod
    def _link_issue(
        issues: t.MutableSequenceOf[m.Infra.AuditIssue],
        md_file: Path,
        rel: str,
        number: int,
        raw: str,
    ) -> None:
        """Append one issue for a single link target when it violates policy."""
        target = FlextInfraUtilitiesDocsAudit.docs_normalize_link(raw)
        if re.match(
            config.Infra.codegen.make.docs.cross_project_relative_link_pattern,
            target,
        ):
            issues.append(
                m.Infra.AuditIssue(
                    file=rel,
                    issue_type="cross_project_relative_link",
                    severity="high",
                    message=(
                        f"line {number}: cross-project links require an "
                        f"absolute repository URL -> {raw}"
                    ),
                ),
            )
            return
        if not target or target.startswith("#"):
            return
        if FlextInfraUtilitiesDocs.docs_is_external(target):
            issues.extend(
                FlextInfraUtilitiesDocsGithubLinks.docs_github_link_issues(
                    file=rel,
                    line_number=number,
                    raw=raw,
                    target=target,
                ),
            )
            return
        if FlextInfraUtilitiesDocsAudit.docs_should_skip_target(raw, target):
            return
        if not (md_file.parent / target).resolve().exists():
            issues.append(
                m.Infra.AuditIssue(
                    file=rel,
                    issue_type="broken_link",
                    severity="high",
                    message=f"line {number}: target not found -> {raw}",
                ),
            )

    @staticmethod
    def _scan_broken_links(
        content: str,
        md_file: Path,
        rel: str,
        issues: t.MutableSequenceOf[m.Infra.AuditIssue],
    ) -> None:
        """Scan one markdown file's non-fenced lines for broken link targets."""
        in_fenced_code = False
        for number, line in enumerate(content.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("```"):
                in_fenced_code = not in_fenced_code
                continue
            if in_fenced_code:
                continue
            clean_line = FlextInfraUtilitiesDocsAudit.docs_strip_inline_code(line)
            for raw in FlextInfraUtilitiesDocsAudit.docs_markdown_link_targets(
                clean_line,
            ):
                FlextInfraUtilitiesDocsAudit._link_issue(
                    issues,
                    md_file,
                    rel,
                    number,
                    raw,
                )

    @staticmethod
    def docs_broken_link_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect broken internal link issues in one docs scope.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        for md_file in FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope):
            rel = md_file.relative_to(scope.path).as_posix()
            content = md_file.read_text(
                encoding=c.Cli.ENCODING_DEFAULT,
                errors=c.Infra.IGNORE,
            )
            FlextInfraUtilitiesDocsAudit._scan_broken_links(
                content,
                md_file,
                rel,
                issues,
            )
        return issues

    @staticmethod
    def docs_stale_symbol_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect stale-symbol issues outside the explicit migration docs.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        policy = FlextInfraUtilitiesDocsAudit.docs_audit_policy(scope)
        tokens = policy.stale_symbols
        exempt_paths = set(policy.stale_symbol_exempt_paths)
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        if not tokens:
            return issues
        live_public_symbols = (
            FlextInfraUtilitiesDocsAudit.docs_live_public_symbol_names(scope)
        )
        for md_file in FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope):
            rel = md_file.relative_to(scope.path / c.Infra.DIR_DOCS).as_posix()
            if rel in exempt_paths:
                continue
            is_generated_api_reference = (
                FlextInfraUtilitiesDocsAudit.docs_generated_api_reference_path(rel)
            )
            text = md_file.read_text(
                encoding=c.Cli.ENCODING_DEFAULT,
                errors=c.Infra.IGNORE,
            )
            for token in tokens:
                if token not in text:
                    continue
                if is_generated_api_reference and token in live_public_symbols:
                    continue
                issues.append(
                    m.Infra.AuditIssue(
                        file=md_file.relative_to(scope.path).as_posix(),
                        issue_type="stale_symbol",
                        severity="medium",
                        message=f"contains `{token}`",
                    ),
                )
        return issues

    @staticmethod
    def docs_audit_markdown(
        scope: m.Infra.DocScope,
        issues: t.SequenceOf[m.Infra.AuditIssue],
        docstring_coverage: m.Infra.DocstringCoverage | None = None,
    ) -> t.StrSequence:
        """Render the standard markdown audit report.

        Returns:
            The resulting ``t.StrSequence``.

        """
        metric_lines: t.MutableSequenceOf[str] = []
        if docstring_coverage is not None:
            metric_lines.append(
                "Docstring coverage: "
                f"{docstring_coverage.percent}% "
                f"({docstring_coverage.documented}/{docstring_coverage.checked})",
            )
        return [
            "# Docs Audit Report",
            "",
            f"Scope: {scope.name}",
            (
                f"Files scanned: "
                f"{len(FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope))}"
            ),
            f"Issues: {len(issues)}",
            *metric_lines,
            "",
            "| file | type | severity | message |",
            "|---|---|---|---|",
            *[
                f"| {issue.file} | {issue.issue_type} | {issue.severity} "
                f"| {issue.message} |"
                for issue in issues
            ],
        ]


__all__: list[str] = ["FlextInfraUtilitiesDocsAudit"]
