"""Canonical command and test-boundary checks for documentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, config, m

from .docs import FlextInfraUtilitiesDocs

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesDocsCommandContractMixin:
    """Detect documentation that bypasses canonical Make and test ownership."""

    @staticmethod
    def _docs_command_candidates(
        line: str, *, fence_marker: str, fence_language: str
    ) -> t.StrSequence:
        """Return executable shell snippets, excluding surrounding prose."""
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
        )

    @staticmethod
    def docs_command_contract_content_issues(
        content: str,
        *,
        relative_path: str,
        effective_verbs: t.SequenceOf[m.Infra.MakeVerbSpec],
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Return command-contract issues from one Markdown document."""
        issues: t.MutableSequenceOf[m.Infra.AuditIssue] = []
        fence_marker = ""
        fence_language = ""
        for number, line in enumerate(content.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith(("```", "~~~")):
                marker = stripped[:3]
                if fence_marker:
                    if marker == fence_marker:
                        fence_marker = ""
                        fence_language = ""
                else:
                    fence_marker = marker
                    fence_language = stripped[3:].strip().partition(" ")[0].lower()
                continue

            issue = ""
            for (
                candidate
            ) in FlextInfraUtilitiesDocsCommandContractMixin._docs_command_candidates(
                line, fence_marker=fence_marker, fence_language=fence_language
            ):
                make_match = c.Infra.DOCS_MAKE_COMMAND_RE.match(candidate)
                if c.Infra.DOCS_RAW_PYTEST_COMMAND_RE.match(candidate):
                    issue = "direct pytest command bypasses `make test`"
                elif c.Infra.DOCS_RAW_TOOL_COMMAND_RE.match(candidate):
                    issue = "direct tool command bypasses the root Make dispatcher"
                elif make_match is not None:
                    selector = c.Infra.DOCS_FORBIDDEN_MAKE_SELECTOR_RE.search(
                        make_match.group("args")
                    )
                    verb = make_match.group("verb").lower()
                    verb_spec = next(
                        (spec for spec in effective_verbs if spec.name == verb), None
                    )
                    legacy_apply = (
                        c.Infra.DOCS_APPLY_RE.search(make_match.group("args"))
                        is not None
                    )
                    if legacy_apply:
                        issue = (
                            "legacy `APPLY` flag is exterminated: verbs always "
                            "execute their declared operation"
                        )
                    elif verb_spec is None:
                        issue = f"Make verb `{verb}` is not declared by the config SSOT"
                    elif selector is not None:
                        selector_name = (
                            selector.group(0).split("=", maxsplit=1)[0].strip()
                        )
                        issue = f"invented Make selector `{selector_name}`"
                if issue:
                    break
            if not issue and c.Infra.DOCS_TEST_DOUBLE_HEADING_RE.match(line):
                issue = "test-double guidance is prohibited"
            elif (
                not issue
                and fence_language in {"py", "python", "python3"}
                and (c.Infra.DOCS_TEST_DOUBLE_CODE_RE.search(line) is not None)
            ):
                issue = "test-double code bypasses public-facade test ownership"

            if issue:
                issues.append(
                    m.Infra.AuditIssue(
                        file=relative_path,
                        issue_type="command_contract",
                        severity="high",
                        message=f"line {number}: {issue}",
                    )
                )
        return issues

    @staticmethod
    def docs_command_contract_issues(
        scope: m.Infra.DocScope,
    ) -> t.SequenceOf[m.Infra.AuditIssue]:
        """Collect live guide/standard issues through typed scope discovery.

        ``iter_scope_markdown_files`` owns every formal scope exclusion; this
        detector carries no path allowlist or bypass.
        """
        from flext_infra import u

        loaded = u.Infra.workspace_spec_load(scope.path)
        if loaded.failure:
            raise ValueError(loaded.error)
        effective_verbs = (
            *config.Infra.codegen.make.verbs,
            *loaded.value.repository.extra_verbs,
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
                encoding=c.Cli.ENCODING_DEFAULT, errors=c.Infra.IGNORE
            )
            issues.extend(
                FlextInfraUtilitiesDocsCommandContractMixin.docs_command_contract_content_issues(
                    content,
                    relative_path=relative_path,
                    effective_verbs=effective_verbs,
                )
            )
        return issues


__all__: list[str] = ["FlextInfraUtilitiesDocsCommandContractMixin"]
