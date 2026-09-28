"""Regression tests for the generated guides index.

The guides index is generated, so every relative link it renders must resolve.
Naming a curated guide the generator never writes produced a broken link
(MD057) in every project that had no such file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsRenderGuidesIndex:
    """Regression tests for the generated guides index."""

    def _scope(self, tmp_path: Path) -> m.Infra.DocScope:
        """Return one isolated doc scope rooted at the fixture directory."""
        return m.Infra.DocScope(
            name="fixture-project", path=tmp_path, report_dir=tmp_path / "reports"
        )

    def test_guides_index_links_only_planned_guides(self, tmp_path: Path) -> None:
        """Include a new planned guide and omit an existing stale destination."""
        guides_dir = tmp_path / "docs" / "guides"
        guides_dir.mkdir(parents=True)
        (guides_dir / "stale.md").write_text("# stale\n", encoding="utf-8")

        rendered = u.Infra.docs_guides_index(
            self._scope(tmp_path), guide_paths=(guides_dir / "topology-conform.md",)
        )

        tm.that(rendered, has="(topology-conform.md)")
        # The index never links itself.
        tm.that("(README.md)" in rendered, eq=False)
        tm.that(rendered, lacks="(stale.md)")
        tm.that((guides_dir / "topology-conform.md").exists(), eq=False)

    def test_guides_index_omits_links_when_no_guide_exists(
        self, tmp_path: Path
    ) -> None:
        """A project without curated guides renders no unresolvable link."""
        (tmp_path / "docs" / "guides").mkdir(parents=True)

        rendered = u.Infra.docs_guides_index(self._scope(tmp_path), guide_paths=())

        tm.that("(topology-conform.md)" in rendered, eq=False)
        tm.that(rendered, has="(../api-reference/README.md)")
