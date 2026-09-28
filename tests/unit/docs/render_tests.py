"""Behavior tests for managed mkdocs.yml rendering (exclude_docs / nav404)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm
from mkdocs.config import load_config
from mkdocs.structure.files import get_files
from mkdocs.structure.nav import get_navigation

from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsRender:
    """nav404 regression: exclude_docs must keep nested section READMEs (flext-3o9s).

    MkDocs evaluates ``exclude_docs`` as gitignore-style patterns
    (``pathspec.GitIgnoreSpec``). A bare ``README.md`` drops every section
    README that generated index pages link to, producing 404s in the built
    site nav; the rooted ``/README.md`` excludes only the docs-dir root README.
    """

    def test_project_navigation_discovers_maintained_pages(
        self, tmp_path: Path
    ) -> None:
        """The real MkDocs navigation includes manual guides beyond generated indexes."""
        scope = m.Infra.DocScope(
            name="flext-demo", path=tmp_path, report_dir=tmp_path / ".reports/docs"
        )
        for relative in ("index.md", "security/triage.md", "decisions/ADR-001.md"):
            page = tmp_path / "docs" / relative
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text("# Maintained page\n", encoding="utf-8")
        config_file = tmp_path / "mkdocs.yml"
        config_file.write_text(
            u.Infra.docs_project_mkdocs(scope, {}, []), encoding="utf-8"
        )
        configuration = load_config(config_file=str(config_file), plugins=[])
        files = get_files(configuration)
        navigation = get_navigation(files, configuration)
        tm.that(
            {page.file.src_uri for page in navigation.pages},
            eq={"index.md", "security/triage.md", "decisions/ADR-001.md"},
        )

    def test_project_mkdocs_excludes_root_readme_only(self, tmp_path: Path) -> None:
        """Keep nested README pages while excluding only the docs root README."""
        scope = m.Infra.DocScope(
            name="flext-demo", path=tmp_path, report_dir=tmp_path / ".reports/docs"
        )

        rendered = u.Infra.docs_project_mkdocs(scope, {}, [])

        # flext-i6nq.10: Validate the rendered public artifact through pathspec's
        # documented text-stream boundary, without an ad-hoc extraction helper.
        match = re.search(r"exclude_docs: \|\n((?: {2}\S.*\n)+)", rendered)
        tm.that(match is not None, eq=True)
        if match is None:
            pytest.fail("rendered exclude_docs block was not found")
        patterns = tuple(
            line.strip() for line in match.group(1).splitlines() if line.strip()
        )
        # The rooted pattern excludes only the docs-dir root README; a bare
        # README.md would also hide every nested section README from MkDocs.
        tm.that(patterns, has="/README.md")
        tm.that(patterns, lacks="README.md")

    def test_root_navigation_discovers_maintained_pages(self, tmp_path: Path) -> None:
        """The root portal exposes maintained sections without a fixed nav list."""
        for relative in (
            "index.md",
            "architecture/adr/001-decision.md",
            "guides/development.md",
            "standards/testing.md",
        ):
            page = tmp_path / "docs" / relative
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text("# Maintained page\n", encoding="utf-8")
        config_file = tmp_path / "mkdocs.yml"
        config_file.write_text(
            u.Infra.docs_root_mkdocs({"site_title": "Workspace"}), encoding="utf-8"
        )
        configuration = load_config(config_file=str(config_file), plugins=[])
        files = get_files(configuration)
        navigation = get_navigation(files, configuration)

        tm.that(
            {page.file.src_uri for page in navigation.pages},
            eq={
                "index.md",
                "architecture/adr/001-decision.md",
                "guides/development.md",
                "standards/testing.md",
            },
        )

    def test_mkdocs_repository_name_comes_from_project_metadata(
        self, tmp_path: Path
    ) -> None:
        """Render the repository label from the same URL owner as the link."""
        scope = m.Infra.DocScope(
            name="consumer", path=tmp_path, report_dir=tmp_path / ".reports/docs"
        )
        contract = {
            "repo_url": "https://github.com/example/consumer.git",
            "site_title": "Consumer",
        }

        project = u.Infra.docs_project_mkdocs(scope, contract, [])
        root = u.Infra.docs_root_mkdocs(contract)

        tm.that(project, has="repo_name: example/consumer")
        tm.that(root, has="repo_name: example/consumer")

    def test_project_mkdocs_excludes_generated_api_from_revision_dates(
        self, tmp_path: Path
    ) -> None:
        """Do not derive Git revision dates for generated API pages."""
        scope = m.Infra.DocScope(
            name="flext-demo", path=tmp_path, report_dir=tmp_path / ".reports/docs"
        )

        rendered = u.Infra.docs_project_mkdocs(scope, {}, [])

        tm.that(
            rendered,
            has=(
                "  - git-revision-date-localized:\n"
                "      # Why: enable_creation_date resolves via 'git log --diff-filter=Ar', which returns\n"
                "      # EMPTY for pages whose only add-commit is a merge commit. The plugin then falls back\n"
                "      # to time.time() (build clock), making first_revision > last_revision always true,\n"
                "      # which logs a warning that mkdocs --strict turns into a build failure. Revision date\n"
                "      # from the last commit touching the page is the intended and robust behavior.\n"
                "      # enable_git_follow is off for the same reason: following renames re-reads\n"
                "      # history per page and reintroduces the same empty-result fallback.\n"
                "      enable_creation_date: false\n"
                "      enable_git_follow: false\n"
                "      type: date\n"
                "      exclude:\n"
                "        - api-reference/generated/**\n"
            ),
        )
