"""Fix helpers for docs services."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from flext_cli import u

from flext_infra import c, m, t

from ._docs_github_links import FlextInfraUtilitiesDocsGithubLinks
from .docs import FlextInfraUtilitiesDocs
from .docs_contract import FlextInfraUtilitiesDocsContract

if TYPE_CHECKING:
    import re
    from pathlib import Path


class FlextInfraUtilitiesDocsFix:
    """Reusable fix helpers exposed through ``u.Infra``."""

    @staticmethod
    def docs_maybe_fix_link(md_file: Path, raw_link: str) -> str | None:
        """Return a corrected link target when a simple fix is possible."""
        if FlextInfraUtilitiesDocs.docs_is_secure_web_url(raw_link):
            return FlextInfraUtilitiesDocsGithubLinks.docs_rewrite_github_url(raw_link)
        result: str | None = None
        if not (
            FlextInfraUtilitiesDocs.docs_is_external(raw_link)
            or raw_link.startswith(c.Infra.DOCS_FRAGMENT_PREFIX)
        ):
            base = raw_link.split("#", maxsplit=1)[0]
            if (
                base
                and not (md_file.parent / base).exists()
                and not base.endswith(".md")
            ):
                md_candidate = md_file.parent / f"{base}.md"
                if md_candidate.exists():
                    result = f"{base}.md{raw_link[len(base) :]}"
        return result

    @staticmethod
    def docs_fix_python_codeblocks(
        scope: m.Infra.DocScope, *, apply: bool
    ) -> t.SequenceOf[m.Infra.GeneratedFile]:
        """Auto-fix ``python`` fenced code blocks using ``ruff check --fix``.

        Only fixes issues that ``ruff`` can resolve automatically; blocks that
        still contain unfixable diagnostics are left untouched so the audit
        gate reports them.
        """
        changed: t.MutableSequenceOf[m.Infra.GeneratedFile] = []
        for md_file in FlextInfraUtilitiesDocs.iter_scope_markdown_files(scope):
            original = md_file.read_text(
                encoding=c.Cli.ENCODING_DEFAULT, errors=c.Infra.IGNORE
            )

            def _replace_fence(
                match: re.Match[str], source_file: Path = md_file
            ) -> str:
                body = match.group("body")
                rel = source_file.relative_to(scope.path).as_posix()
                # flext-o6h5 (agent: kimi) — ruff via running interpreter (venv SSOT);
                # bare "ruff" breaks when .venv/bin is not on PATH (CI docs fix).
                outcome = u.Cli.run_raw(
                    [
                        sys.executable,
                        "-m",
                        c.Infra.RUFF,
                        c.Infra.VERB_CHECK,
                        "--fix",
                        "--extend-ignore",
                        ",".join(c.Infra.PYTHON_FENCE_RUFF_EXTEND_IGNORE),
                        "--stdin-filename",
                        f"{rel}#block.py",
                        "-",
                    ],
                    input_data=body.encode(),
                )
                if outcome.failure:
                    return match.group(0)
                fixed_body = outcome.value.stdout
                if fixed_body == body:
                    return match.group(0)
                # A closing fence only closes the block when it starts its own
                # line; ruff may return a body without the trailing newline, so
                # reassembling blindly welds the fence onto the last code line
                # and the block swallows every heading that follows it.
                closed_body = (
                    fixed_body if fixed_body.endswith("\n") else f"{fixed_body}\n"
                )
                indent = match.group("indent")
                return f"{indent}{match.group('open')}{closed_body}{indent}```"

            repaired = c.Infra.WELDED_FENCE_RE.sub(
                lambda match: (
                    f"{match.group('indent')}{match.group('body')}"
                    f"\n{match.group('indent')}```"
                ),
                original,
            )
            sanitized = c.Infra.PYTHON_FENCE_FIX_RE.sub(_replace_fence, repaired)
            if sanitized == original:
                continue
            changed.append(
                FlextInfraUtilitiesDocsContract.docs_write_if_needed(
                    md_file, sanitized, apply=apply
                )
            )
        return changed

    @staticmethod
    def docs_process_markdown_file(
        md_file: Path, *, apply: bool
    ) -> m.Infra.DocsPhaseItemModel:
        """Fix one markdown file and return the phase item summary."""
        original = md_file.read_text(
            encoding=c.Cli.ENCODING_DEFAULT, errors=c.Infra.IGNORE
        )
        link_count = 0

        def replace_link(match: t.RegexMatch) -> str:
            """Replace link."""
            nonlocal link_count
            text, link = match.groups()
            fixed = FlextInfraUtilitiesDocsFix.docs_maybe_fix_link(md_file, link)
            if fixed is None:
                original_match: str = match.group(0)
                return original_match
            link_count += 1
            return f"[{text}]({fixed})"

        updated = c.Infra.MARKDOWN_LINK_RE.sub(replace_link, original)
        fence_changed = c.Infra.FENCE_NOTEST_ATTR_RE.subn(r"```{.\1 .notest}", updated)
        updated = fence_changed[0]
        updated, toc_changed = FlextInfraUtilitiesDocs.update_toc(updated)
        if apply and updated != original:
            _ = md_file.write_text(updated, encoding=c.Cli.ENCODING_DEFAULT)
        return m.Infra.DocsPhaseItemModel(
            phase="fix",
            file=md_file.as_posix(),
            links=link_count + fence_changed[1],
            toc=toc_changed,
        )

    @staticmethod
    def docs_write_fix_reports(
        scope: m.Infra.DocScope,
        *,
        items: t.SequenceOf[m.Infra.DocsPhaseItemModel],
        apply: bool,
    ) -> None:
        """Persist the standard fix summary and markdown report."""
        FlextInfraUtilitiesDocs.docs_write_phase_reports(
            scope,
            phase="fix",
            heading="Docs Fix Report",
            columns=("file", "link_fixes", "toc_updates"),
            rows=tuple((item.file, str(item.links), str(item.toc)) for item in items),
            items=items,
            apply=apply,
        )


__all__: list[str] = ["FlextInfraUtilitiesDocsFix"]
