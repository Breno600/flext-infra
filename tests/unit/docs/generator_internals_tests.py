"""Public utility tests used by docs generation flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm
from markdown import Markdown

from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsGeneratorInternals:
    """Public utility tests used by docs generation flows."""

    def test_anchorize_normalizes_headings(self) -> None:
        tm.that(u.Infra.anchorize("Hello World"), eq="hello-world")
        tm.that(u.Infra.anchorize("Test-Case"), eq="test-case")
        tm.that(u.Infra.anchorize(""), eq="")

    @pytest.mark.parametrize(
        "heading",
        ["Contrato público", "Composição de serviços", "Žlutý kůň", "Test--Case"],
    )
    def test_anchorize_matches_rendered_markdown(self, heading: str) -> None:
        """Generated links target the renderer's real Unicode-normalized heading ID."""
        rendered = Markdown(extensions=["toc"]).convert(f"## {heading}")
        anchor = u.Infra.anchorize(heading)
        tm.that(rendered, has=f'id="{anchor}"')
        tm.that(u.Infra.build_toc(f"# API\n\n## {heading}\n"), has=f"](#{anchor})")

    def test_anchorize_keeps_underscores_like_python_markdown(self) -> None:
        tm.that(
            u.Infra.anchorize(r"marts/metrics/met_wms\_\_kpi_dashboard"),
            eq="martsmetricsmet_wms__kpi_dashboard",
        )
        tm.that(u.Infra.anchorize("Config _private_ keys"), eq="config-_private_-keys")

    def test_build_toc_lists_h2_and_h3_sections(self) -> None:
        toc = u.Infra.build_toc("# Main\n\n## Section 1\n\n### Subsection\n")

        tm.that(toc, has="<!-- TOC START -->")
        tm.that(toc, has="Section 1")
        tm.that(toc, has="Subsection")

    def test_build_toc_skips_headings_inside_fenced_code(self) -> None:
        content = (
            "# Main\n\n"
            "## Real Section\n\n"
            "```markdown\n"
            "## Sample Heading\n\n"
            "### Wave Assignment\n"
            "```\n\n"
            "~~~text\n"
            "### Tilde Sample\n"
            "~~~\n\n"
            "### Real Subsection\n"
        )

        toc = u.Infra.build_toc(content)

        tm.that(toc, has="Real Section")
        tm.that(toc, has="Real Subsection")
        tm.that(toc, lacks="Sample Heading")
        tm.that(toc, lacks="Wave Assignment")
        tm.that(toc, lacks="Tilde Sample")

    def test_build_toc_uses_rendered_ids_and_plain_link_labels(self) -> None:
        """Explicit IDs, inline links and duplicates resolve to real rendered anchors."""
        content = (
            "# Main\n\n"
            "## Vault pending {#incident-vault}\n\n"
            "## [Architecture](decisions.md)\n\n"
            "## Architecture\n\n"
            "### Architecture\n"
            "\n## Copyright &copy; {#copyright}\n"
        )
        toc = u.Infra.build_toc(content)
        rendered = Markdown(extensions=["attr_list", "toc"]).convert(content)
        for anchor in (
            "incident-vault",
            "architecture",
            "architecture_1",
            "architecture_2",
            "copyright",
        ):
            tm.that(rendered, has=f'id="{anchor}"')
            tm.that(toc, has=f"](#{anchor})")
        tm.that(toc, has="[Vault pending](#incident-vault)")
        tm.that(toc, has="[Architecture](#architecture)")
        tm.that(toc, lacks="decisions.md")
        tm.that(toc, has="[Copyright ©](#copyright)")
        updated, _ = u.Infra.update_toc(content)
        twice, changed = u.Infra.update_toc(updated)
        tm.that(twice, eq=updated)
        tm.that(changed, eq=0)

    def test_update_toc_replaces_existing_block(self) -> None:
        updated, changed = u.Infra.update_toc(
            "# Main\n\n<!-- TOC START -->\n- stale\n<!-- TOC END -->\n\n## Section\n"
        )

        tm.that(changed, eq=1)
        tm.that(updated, lacks="stale")
        tm.that(updated, has="Section")

    def test_generated_markdown_is_toc_normalized_before_write(
        self, tmp_path: Path
    ) -> None:
        generated = tmp_path / "generated.md"

        result = u.Infra.docs_write_if_needed(
            generated, "# Generated\n\n## Section\n", apply=True
        )

        tm.that(result.changed, eq=True)
        tm.that(generated.read_text(), has="<!-- TOC START -->")
        tm.that(generated.read_text(), has="[Section](#section)")

    def test_update_toc_preserves_single_blank_after_level_one_heading(self) -> None:
        updated, changed = u.Infra.update_toc("# Main\n\n## Section\n")

        tm.that(changed, eq=1)
        tm.that(updated, has="# Main\n\n<!-- TOC START -->")
        tm.that(updated, lacks="# Main\n\n\n<!-- TOC START -->")

    def test_generated_non_markdown_preserves_exact_content(
        self, tmp_path: Path
    ) -> None:
        generated = tmp_path / "mkdocs.yml"
        content = "site_name: Generated\n"

        result = u.Infra.docs_write_if_needed(generated, content, apply=True)

        tm.that(result.changed, eq=True)
        tm.that(generated.read_text(), eq=content)

    def test_generate_creates_selected_project_reports(self, tmp_path: Path) -> None:
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path,
            project_names=("flext-a", "flext-b"),
            selected_projects=["flext-a"],
        )
        _ = u.Tests.prepare_docs_bundle(generator)

        result = generator.generate(
            m.Infra.DocsGenerateRequest(repository_root=workspace, projects=["flext-a"])
        )

        tm.ok(result)
        tm.that([report.scope for report in result.value], eq=["root", "flext-a"])
