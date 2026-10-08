"""Canonical command and test-boundary checks for documentation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from flext_infra import c, config, m
from flext_infra._utilities import (
    FlextInfraUtilitiesDocs,
    FlextInfraUtilitiesWorkspaceManifest,
)

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesDocsCommandContractMixin:
    """Detect documentation that bypasses canonical Make and test ownership."""

    @staticmethod
    def _docs_command_candidates(
        line: str,
        *,
        fence_marker: str,
        fence_language: str,
    ) -> t.StrSequence:
        """Return executable shell snippets, excluding surrounding prose.

        Returns:
            Executable shell snippets, excluding surrounding prose.

        """
        if fence_marker:
            return (
                (line,) if fence_language in c.Infra.DOCS_SHELL_FENCE_LANGUAGES else ()
            )
        stripped = line.lstrip()
        if stripped.startswith("$ "):
            return (stripped[2:],)
        return tuple(
            match.group(0)[1:-1]
            for match in c.Infra.INLINE_CODE_RE.finditer(line)
            if len(match.group(0)[1:-1].split()) > 1
            and c.Infra.DOCS_INLINE_COMMAND_DIRECTIVE_RE.search(line[: match.start()])
            is not None
        )

    @staticmethod
    def _docs_fence_transition(
        line: str,
        fence_marker: str,
        fence_language: str,
    ) -> t.Pair[str, str] | None:
        """Return the fence state after one line, or ``None`` outside fences.

        Returns:
            The resulting ``(fence marker, fence language)`` pair.

        """
        stripped = line.lstrip()
        if not stripped.startswith(("```", "~~~")):
            return None
        marker = stripped[:3]
        if fence_marker:
            return (
                (fence_marker, fence_language) if marker != fence_marker else ("", "")
            )
        return (marker, stripped[3:].strip().partition(" ")[0].lower())

    @staticmethod
    def _make_selector_issue(selector: re.Match[str] | None) -> str:
        """Return the issue of one forbidden Make selector, else empty text.

        Returns:
            The resulting ``str``.

        """
        if selector is None:
            return ""
        selector_name = selector.group(0).split("=", maxsplit=1)[0].strip()
        return f"invented Make selector `{selector_name}`"

    @staticmethod
    def _candidate_issue(
        candidate: str,
        effective_verbs: t.SequenceOf[m.Infra.MakeVerbSpec],
    ) -> str:
        """Return the command-contract issue one candidate command violates.

        Returns:
            The resulting ``str``.

        """
        make_match = c.Infra.DOCS_MAKE_COMMAND_RE.match(candidate)
        if c.Infra.DOCS_RAW_PYTEST_COMMAND_RE.match(candidate):
            return "direct pytest command bypasses `make test`"
        if c.Infra.DOCS_RAW_TOOL_COMMAND_RE.match(candidate):
            return "direct tool command bypasses the root Make dispatcher"
        if make_match is None:
            return ""
        selector = c.Infra.DOCS_FORBIDDEN_MAKE_SELECTOR_RE.search(
            make_match.group("args"),
        )
        verb = make_match.group("verb").lower()
        verb_spec = next(
            (spec for spec in effective_verbs if spec.name == verb),
            None,
        )
        if c.Infra.DOCS_APPLY_RE.search(make_match.group("args")) is not None:
            return (
                "legacy `APPLY` flag is exterminated: verbs always "
                "execute their declared operation"
            )
        if verb_spec is None:
            return f"Make verb `{verb}` is not declared by the config SSOT"
        return FlextInfraUtilitiesDocsCommandContractMixin._make_selector_issue(
            selector,
        )

    @classmethod
    def _docs_line_issue(
        cls,
        line: str,
        *,
        fence_marker: str,
        fence_language: str,
        effective_verbs: t.SequenceOf[m.Infra.MakeVerbSpec],
    ) -> str:
        """Return the command-contract issue one document line violates.

        Returns:
            The resulting ``str``.

        """
        issue = ""
        for (
            candidate
        ) in FlextInfraUtilitiesDocsCommandContractMixin._docs_command_candidates(
            line,
            fence_marker=fence_marker,
            fence_language=fence_language,
        ):
            issue = cls._candidate_issue(candidate, effective_verbs)
            if issue:
                break
        if not issue and c.Infra.DOCS_TEST_DOUBLE_HEADING_RE.match(line):
            return "test-double guidance is prohibited"
        if (
            not issue
            and fence_language in {"py", "python", "python3"}
            and (c.Infra.DOCS_TEST_DOUBLE_CODE_RE.search(line) is not None)
        ):
            return "test-double code bypasses public-facade test ownership"
        return issue

    @classmethod
    def docs_command_contract_content_issues(
        cls,
        content: str,
        *,
        relative_path: str,
        effective_verbs: t.SequenceOf[m.Infra.MakeVerbSpec],
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Return command-contract issues from one Markdown document.

        Returns:
            Command-contract issues from one Markdown document.

        """
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        fence_marker = ""
        fence_language = ""
        for number, line in enumerate(content.splitlines(), start=1):
            fence = cls._docs_fence_transition(line, fence_marker, fence_language)
            if fence is not None:
                fence_marker, fence_language = fence
                continue
            issue = cls._docs_line_issue(
                line,
                fence_marker=fence_marker,
                fence_language=fence_language,
                effective_verbs=effective_verbs,
            )
            if issue:
                issues.append(
                    m.Infra.AuditIssue(
                        file=relative_path,
                        issue_type="command_contract",
                        severity="high",
                        message=f"line {number}: {issue}",
                    ),
                )
        return issues

    @staticmethod
    def docs_command_contract_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect live guide/standard issues through typed scope discovery.

        ``iter_scope_markdown_files`` owns every formal scope exclusion; this
        detector carries no path allowlist or bypass.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.AuditIssue]``.

        Raises:
            ValueError: If ``loaded.failure``.

        """
        loaded = FlextInfraUtilitiesWorkspaceManifest.load_workspace_manifest(
            scope.path,
        )
        if loaded.failure:
            raise ValueError(loaded.error)
        effective_verbs = (
            *config.Infra.codegen.make.verbs,
            *(
                verb
                for manifest in loaded.value
                for verb in manifest.repository.extra_verbs
            ),
        )
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        docs_root = scope.path / c.Infra.DIR_DOCS
        for path in FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope):
            if not path.is_relative_to(docs_root):
                continue
            relative_docs_path = path.relative_to(docs_root)
            relative_path = path.relative_to(scope.path).as_posix()
            if (
                not relative_docs_path.parts
                or relative_docs_path.parts[0]
                not in c.Infra.DOCS_COMMAND_CONTRACT_DIRNAMES
            ):
                continue
            content = path.read_text(
                encoding=c.Cli.ENCODING_DEFAULT,
                errors=c.Infra.IGNORE,
            )
            issues.extend(
                FlextInfraUtilitiesDocsCommandContractMixin.docs_command_contract_content_issues(
                    content,
                    relative_path=relative_path,
                    effective_verbs=effective_verbs,
                ),
            )
        return issues


__all__: list[str] = ["FlextInfraUtilitiesDocsCommandContractMixin"]
