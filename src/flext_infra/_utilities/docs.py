"""Documentation shared utilities for the u.Infra FLEXT chain.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from flext_cli import u

from flext_infra import c, m, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesDocsContract,
    FlextInfraUtilitiesDocsScope,
    FlextInfraUtilitiesDocsScopeBuildMixin,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesDocs(FlextInfraUtilitiesDocsScopeBuildMixin):
    """Documentation-related utility methods exposed via u.Infra."""

    @staticmethod
    def docs_url_scheme(target: str) -> str:
        """Return the normalized scheme and reject insecure documentation URLs.

        Returns:
            The normalized scheme and reject insecure documentation URLs.

        Raises:
            ValueError: If insecure documentation URL is prohibited; use HTTPS.

        """
        normalized = u.norm_str(target, case="lower").lstrip("<")
        scheme = urlsplit(normalized).scheme
        if scheme == c.Infra.DOCS_INSECURE_WEB_SCHEME:
            msg = f"insecure documentation URL is prohibited; use HTTPS: {target}"
            raise ValueError(msg)
        return scheme

    @staticmethod
    def docs_is_secure_web_url(target: str) -> bool:
        """Return whether a documentation target is an HTTPS URL.

        Returns:
            Whether a documentation target is an HTTPS URL.

        """
        secure_scheme: str = c.Infra.DOCS_SECURE_WEB_SCHEME
        return FlextInfraUtilitiesDocs.docs_url_scheme(target) == secure_scheme

    @staticmethod
    def docs_is_external(target: str) -> bool:
        """Return whether a target has a permitted external scheme.

        Returns:
            Whether a target has a permitted external scheme.

        """
        return (
            FlextInfraUtilitiesDocs.docs_url_scheme(target)
            in c.Infra.DOCS_EXTERNAL_SCHEMES
        )

    @staticmethod
    def iter_markdown_files(repository_root: Path) -> t.SequenceOf[Path]:
        """Recursively collect markdown files under the docs scope.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        """
        docs_root = repository_root / c.Infra.DIR_DOCS
        search_root = docs_root if docs_root.is_dir() else repository_root
        return sorted(
            path
            for path in search_root.rglob("*.md")
            if not any(
                part in c.Infra.DOC_EXCLUDED_DIRS or part.startswith(".")
                for part in path.relative_to(search_root).parts
            )
        )

    @staticmethod
    def iter_scope_markdown_files(scope: m.Infra.DocScope) -> t.SequenceOf[Path]:
        """Collect markdown files governed by one docs scope.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        """
        scope_root = scope.path
        files = FlextInfraUtilitiesDocs.iter_markdown_files(scope_root)
        if scope.name == c.Infra.RK_ROOT:
            return [
                path
                for path in files
                if not FlextInfraUtilitiesDocsScope.excluded_doc_path(
                    scope_root,
                    path.relative_to(scope_root / c.Infra.DIR_DOCS)
                    if path.is_relative_to(scope_root / c.Infra.DIR_DOCS)
                    else path.relative_to(scope_root),
                )
            ]
        docs_root = scope_root / c.Infra.DIR_DOCS
        return [
            path
            for path in files
            if not (
                path.is_relative_to(docs_root)
                and FlextInfraUtilitiesDocsScope.excluded_doc_path(
                    scope_root,
                    path.relative_to(docs_root),
                )
            )
        ]

    @staticmethod
    def write_markdown(path: Path, lines: t.StrSequence) -> p.Result[bool]:
        """Write markdown lines to path, creating parent dirs as needed.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            u.write_file(
                path,
                "\n".join(lines).rstrip() + "\n",
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            return r[bool].ok(value=True)
        except OSError as exc:
            return r[bool].fail(f"markdown write error: {exc}", exception=exc)

    @staticmethod
    def docs_write_phase_reports(
        scope: m.Infra.DocScope,
        *,
        phase: str,
        table: m.Cli.TableRenderRequest,
        apply: bool,
    ) -> None:
        """Persist one phase summary and markdown report from its titled table.

        Every table row is one changed file, so the row count is the changed
        file count both reports publish.
        """
        summary_payload = t.Cli.JSON_MAPPING_ADAPTER.validate_python({
            c.Infra.RK_SUMMARY: {
                c.Infra.RK_SCOPE: scope.name,
                "changed_files": len(table.rows),
                "apply": apply,
            },
            "changes": [list(row) for row in table.rows],
        })
        _ = u.Cli.json_write(
            scope.report_dir / f"{phase}-summary.json",
            summary_payload,
        )
        header = "| " + " | ".join(table.columns) + " |"
        divider = "|---|" + "---:|" * (len(table.columns) - 1)
        _ = FlextInfraUtilitiesDocs.write_markdown(
            scope.report_dir / f"{phase}-report.md",
            [
                f"# {table.title}",
                "",
                f"Scope: {scope.name}",
                f"Apply: {int(apply)}",
                f"Changed files: {len(table.rows)}",
                "",
                header,
                divider,
                *(" | ".join(row) + " |" for row in table.rows),
            ],
        )

    @staticmethod
    def docs_write_fmt_reports(
        scope: m.Infra.DocScope,
        *,
        items: t.SequenceOf[m.Infra.DocsPhaseItemModel],
        apply: bool,
    ) -> None:
        """Persist the standard fmt summary and markdown report."""
        FlextInfraUtilitiesDocs.docs_write_phase_reports(
            scope,
            phase="fmt",
            table=m.Cli.TableRenderRequest(
                title="Docs Format Report",
                columns=("file",),
                rows=tuple((item.file,) for item in items),
            ),
            apply=apply,
        )

    @staticmethod
    def anchorize(text: str) -> str:
        """Convert heading text to the anchor consumed by MkDocs.

        Returns:
            The resulting ``str``.

        """
        return FlextInfraUtilitiesDocsContract.docs_contract_anchorize(text)

    @staticmethod
    def build_toc(content: str) -> str:
        """Generate a TOC block from ## and ### headings in content.

        Returns:
            The resulting ``str``.

        """
        return FlextInfraUtilitiesDocsContract.docs_contract_build_toc(content)

    @staticmethod
    def update_toc(content: str) -> t.StrIntPair:
        """Insert or replace the TOC in content, returning (updated, changed).

        Returns:
            The resulting ``t.StrIntPair``.

        """
        return FlextInfraUtilitiesDocsContract.docs_contract_update_toc(content)

    @staticmethod
    def run_scoped(
        repository_root: Path,
        *,
        projects: t.StrSequence | None,
        output_dir: Path | str,
        handler: Callable[[m.Infra.DocScope], m.Infra.DocsPhaseReport],
    ) -> p.Result[t.SequenceOf[m.Infra.DocsPhaseReport]]:
        """Build scopes and run handler on each, collecting reports.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.DocsPhaseReport]]``.

        """
        scopes_result = FlextInfraUtilitiesDocs.build_scopes(
            repository_root=repository_root,
            projects=projects,
            output_dir=output_dir,
        )
        if scopes_result.failure:
            return r[t.SequenceOf[m.Infra.DocsPhaseReport]].from_failure(scopes_result)
        return r[t.SequenceOf[m.Infra.DocsPhaseReport]].ok([
            handler(scope) for scope in scopes_result.value
        ])


__all__: list[str] = ["FlextInfraUtilitiesDocs"]
