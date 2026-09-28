"""update_toc must preserve YAML frontmatter and real H1 headings."""

from __future__ import annotations

from flext_tests import tm

from tests import u


class TestsFlextInfraDocsUpdateTocFrontmatter:
    """update_toc must preserve YAML frontmatter and real H1 headings."""

    def test_docs_contract_update_toc_inserts_after_h1_beyond_frontmatter(self) -> None:
        content = (
            "---\ntitle: ADR-001\n---\n\n# ADR-001 — Example\n\n## Context\n\nBody.\n"
        )
        updated, changed = u.Infra.update_toc(content)
        tm.that(changed, eq=1)
        tm.that(updated.startswith("---\n"), eq=True)
        tm.that("# Documentation" in updated, eq=False)
        tm.that("<!-- TOC START -->" in updated, eq=True)
        tm.that(
            updated.index("# ADR-001") < updated.index("<!-- TOC START -->"), eq=True
        )

    def test_docs_contract_update_toc_repairs_invented_h1_before_frontmatter(
        self,
    ) -> None:
        mangled = (
            "# Documentation\n"
            "\n"
            "<!-- TOC START -->\n"
            "- [Context](#context)\n"
            "<!-- TOC END -->\n"
            "\n"
            "---\n"
            "title: ADR-001\n"
            "---\n"
            "\n"
            "# ADR-001 — Example\n"
            "\n"
            "## Context\n"
            "\n"
            "Body.\n"
        )
        updated, changed = u.Infra.update_toc(mangled)
        tm.that(changed, eq=1)
        tm.that(updated.startswith("---\n"), eq=True)
        tm.that(updated.startswith("# Documentation"), eq=False)
        tm.that(updated.count("<!-- TOC START -->"), eq=1)
        tm.that(
            updated.index("# ADR-001") < updated.index("<!-- TOC START -->"), eq=True
        )

    def test_docs_contract_update_toc_still_invents_h1_for_headingless_stub(
        self,
    ) -> None:
        content = "<!-- AUTO-GENERATED -->\n\nStub body.\n"
        updated, changed = u.Infra.update_toc(content)
        tm.that(changed, eq=1)
        tm.that(updated.startswith("# Documentation\n"), eq=True)
        tm.that("<!-- TOC START -->" in updated, eq=True)
