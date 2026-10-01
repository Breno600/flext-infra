"""Docs-audit per-issue-type detectors (token/scope/ownership/docstring/codeblock).

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from flext_cli import u

from flext_infra import c, config, m
from flext_infra._utilities.docs import FlextInfraUtilitiesDocs
from flext_infra._utilities.docs_api import FlextInfraUtilitiesDocsApi
from flext_infra._utilities.docs_scope import FlextInfraUtilitiesDocsScope

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesDocsAuditDetectorsMixin:
    """Self-contained docs-audit issue detectors.

    Composed into FlextInfraUtilitiesDocsAudit via inheritance; each detector
    is an independent ``u.Infra.docs_*_issues`` entry over one ``DocScope``.
    """

    @staticmethod
    def docs_text_token_issues(
        scope: m.Infra.DocScope,
        *,
        tokens: t.StrSequence,
        issue_type: str,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect token-presence issues in the complete Markdown scope.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        if not tokens:
            return issues
        for md_file in FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope):
            rel = md_file.relative_to(scope.path).as_posix()
            text = md_file.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            for token in tokens:
                if token in text:
                    issues.append(
                        m.Infra.AuditIssue(
                            file=rel,
                            issue_type=issue_type,
                            severity="medium",
                            message=f"contains `{token}`",
                        ),
                    )
        return issues

    @staticmethod
    def docs_placeholder_issues(
        scope: m.Infra.DocScope,
        *,
        patterns: t.StrSequence,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Find unfinished markers using declared lexical patterns.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        compiled = tuple(re.compile(pattern) for pattern in patterns)
        for md_file in FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope):
            rel = md_file.relative_to(scope.path).as_posix()
            content = md_file.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            for pattern in compiled:
                if pattern.search(content):
                    issues.append(
                        m.Infra.AuditIssue(
                            file=rel,
                            issue_type="placeholder",
                            severity="medium",
                            message=f"matches placeholder pattern `{pattern.pattern}`",
                        ),
                    )
        return issues

    @staticmethod
    def docs_machine_path_issues(
        scope: m.Infra.DocScope,
        *,
        historical_evidence_files: t.VariadicTuple[Path],
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect per-user absolute paths (``/home/<user>``) frozen into markdown.

        A path rooted at one operator's home binds the document to one machine;
        container and CI identities declared in ``c.Infra.MACHINE_PATH_CONTAINER_USERS``
        are image contracts and pass. Only exact declared dated evidence files
        retain the observed machine path.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        evidence = set(historical_evidence_files)
        for md_file in FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope):
            rel = md_file.relative_to(scope.path).as_posix()
            if Path(rel) in evidence:
                continue
            text = md_file.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            for line_number, line in enumerate(text.splitlines(), start=1):
                for match in c.Infra.MACHINE_PATH_RE.finditer(line):
                    if match.group("user") in c.Infra.MACHINE_PATH_CONTAINER_USERS:
                        continue
                    issues.append(
                        m.Infra.AuditIssue(
                            file=rel,
                            issue_type="machine-path",
                            severity="high",
                            message=(
                                f"line {line_number} embeds machine-local path "
                                f"`{match.group(0)}`"
                            ),
                        ),
                    )
        return issues

    @staticmethod
    def docs_scope_boundary_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect mentions of excluded non-FLEXT roots in root docs.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        if scope.name != c.Infra.RK_ROOT:
            return []
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        excluded = sorted(FlextInfraUtilitiesDocsScope.excluded_roots(scope.path))
        for md_file in [
            scope.path / "README.md",
            *FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope),
        ]:
            if not md_file.exists():
                continue
            text = md_file.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            for token in excluded:
                if token in text:
                    issues.append(
                        m.Infra.AuditIssue(
                            file=md_file.relative_to(scope.path).as_posix(),
                            issue_type="scope_boundary",
                            severity="high",
                            message=f"root docs mention out-of-scope project `{token}`",
                        ),
                    )
        return issues

    @staticmethod
    def docs_generated_ownership_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect manual API pages that duplicate generated ownership.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        candidates: t.MutableSequenceOf[Path] = [scope.path / "docs/api-reference.md"]
        for parent in (scope.path / "docs/api-reference", scope.path / "docs/api"):
            if parent.exists():
                candidates.extend(sorted(parent.rglob("*.md")))
        for path in candidates:
            if not path.exists():
                continue
            rel = path.relative_to(scope.path).as_posix()
            if path.is_relative_to(scope.path / c.Infra.DIR_DOCS) and (
                FlextInfraUtilitiesDocsScope.excluded_doc_path(
                    scope.path,
                    path.relative_to(scope.path / c.Infra.DIR_DOCS),
                )
            ):
                continue
            if rel == "docs/api-reference/README.md" or rel.startswith(
                "docs/api-reference/generated/",
            ):
                continue
            issues.append(
                m.Infra.AuditIssue(
                    file=rel,
                    issue_type="generated_ownership",
                    severity="medium",
                    message="manual API page duplicates generated API ownership",
                ),
            )
        return issues

    @staticmethod
    def docs_public_docstring_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect missing docstring issues for public exports and modules.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        if scope.name == c.Infra.RK_ROOT or not scope.package_name:
            return []
        contract = FlextInfraUtilitiesDocsApi.public_contract(
            scope.path,
            scope.package_name,
        )
        return FlextInfraUtilitiesDocsApi.docstring_issues(scope.path, contract)

    @staticmethod
    def docs_public_docstring_coverage(
        scope: m.Infra.DocScope,
    ) -> m.Infra.DocstringCoverage | None:
        """Aggregate docstring coverage for a project scope (None at root).

        Returns:
            The resulting ``m.Infra.DocstringCoverage | None``.

        """
        if scope.name == c.Infra.RK_ROOT or not scope.package_name:
            return None
        contract = FlextInfraUtilitiesDocsApi.public_contract(
            scope.path,
            scope.package_name,
        )
        return FlextInfraUtilitiesDocsApi.docstring_coverage(scope.path, contract)

    @staticmethod
    def docs_python_codeblock_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Lint embedded ``python`` fenced blocks under one docs scope.

        Captures every ``python`` fenced block via ``c.Infra.PYTHON_FENCE_RE``
        and gates each block through ``ruff check --stdin-filename`` (piped
        body bytes — no temp files). Failures land as ``m.Infra.AuditIssue``
        records flowing through the standard audit report pipeline.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        """
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        for md_file in FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope):
            rel = md_file.relative_to(scope.path).as_posix()
            content = md_file.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            for index, match in enumerate(c.Infra.PYTHON_FENCE_RE.finditer(content)):
                # Ruff via running interpreter (venv SSOT);
                # bare "ruff" breaks when .venv/bin is not on PATH (CI docs audit).
                outcome = u.Cli.run_raw(
                    [
                        sys.executable,
                        "-m",
                        c.Infra.RUFF,
                        c.Infra.VERB_CHECK,
                        *config.Infra.codegen.make.ruff.lint_check,
                        "--extend-ignore",
                        ",".join(c.Infra.PYTHON_FENCE_RUFF_EXTEND_IGNORE),
                        "--stdin-filename",
                        f"{rel}#block{index}.py",
                        "-",
                    ],
                    input_data=match.group("body").encode(),
                )
                if outcome.failure:
                    detail = outcome.error
                elif (
                    u.Cli.process_succeeded(outcome.value.outcome)
                    and not outcome.value.stderr
                ):
                    continue
                else:
                    # Ruff reports parse errors on stderr
                    # only; indexing an empty stdout crashes with IndexError.
                    detail = (
                        f"{outcome.value.stdout}\n{outcome.value.stderr}".strip()
                        or f"ruff exit {outcome.value.outcome.raw_return_code}"
                    )
                issues.append(
                    m.Infra.AuditIssue(
                        file=rel,
                        issue_type="python_codeblock",
                        severity="medium",
                        message=f"block #{index}: {detail}",
                    ),
                )
        return issues


__all__: list[str] = ["FlextInfraUtilitiesDocsAuditDetectorsMixin"]
