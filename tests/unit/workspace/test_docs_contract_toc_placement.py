"""Managed TOC placement must never precede the document's level-1 heading."""

from __future__ import annotations

from flext_tests import tm

from tests import u


class TestsFlextInfraDocsContractTocPlacement:
    """Contract for managed TOC insertion relative to the document H1."""

    def test_toc_is_inserted_after_h1_preceded_by_html_comment(self) -> None:
        """Keep the H1 first when an HTML comment banner precedes it.

        Generated API reference pages start with an ``AUTO-GENERATED`` banner
        before the H1. Prepending the TOC pushes the heading down and violates
        MD041.
        """
        content = (
            "<!-- AUTO-GENERATED - DO NOT EDIT MANUALLY -->\n"
            "\n"
            "# cosmos_charts.constants\n"
            "\n"
            "## Usage\n"
        )

        updated, changed = u.Infra.docs_contract_update_toc(content)

        first_meaningful = next(line for line in updated.splitlines() if line.strip())
        tm.that(first_meaningful.startswith("<!-- AUTO-GENERATED"), eq=True)
        tm.that(
            updated.index("# cosmos_charts.constants")
            < updated.index("<!-- TOC START -->"),
            eq=True,
        )
        tm.that(changed, eq=1)

    def test_toc_without_h1_injects_documentation_heading(self) -> None:
        """MD041: invent an H1 before TOC when the body has no level-1 heading."""
        content = "<!-- AUTO-GENERATED -->\n\n## Usage\n"

        updated, changed = u.Infra.docs_contract_update_toc(content)

        lines = [line for line in updated.splitlines() if line.strip()]
        tm.that(lines[0], eq="# Documentation")
        tm.that(
            updated.index("# Documentation") < updated.index("<!-- TOC START -->"),
            eq=True,
        )
        tm.that(changed, eq=1)
