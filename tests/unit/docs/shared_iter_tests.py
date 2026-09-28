"""Tests for u.Infra.iter_markdown_files.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsSharedIter:
    """Tests for u.Infra.iter_markdown_files."""

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test iter_markdown_files with empty directory."""
        files = u.Infra.iter_markdown_files(tmp_path)
        tm.that(len(files), gte=0)

    def test_finds_markdown(self, tmp_path: Path) -> None:
        """Test iter_markdown_files finds markdown files."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "README.md").write_text("# Test\n")
        files = u.Infra.iter_markdown_files(tmp_path)
        tm.that(len(files) > 0, eq=True)

    def test_excludes_hidden(self, tmp_path: Path) -> None:
        """Test iter_markdown_files excludes hidden directories."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        hidden_dir = docs_dir / ".hidden"
        hidden_dir.mkdir(parents=True, exist_ok=True)
        (hidden_dir / "test.md").write_text("# Hidden\n")
        files = u.Infra.iter_markdown_files(tmp_path)
        tm.that(not any(".hidden" in str(f) for f in files), eq=True)

    def test_hidden_workspace_ancestor_does_not_exclude_docs(
        self, tmp_path: Path
    ) -> None:
        """Exclude hidden descendants without rejecting a worktree ancestor."""
        workspace = tmp_path / ".worktrees" / "project"
        docs_dir = workspace / "docs"
        docs_dir.mkdir(parents=True)
        visible = docs_dir / "guide.md"
        visible.write_text("# Guide\n")
        hidden_dir = docs_dir / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "private.md").write_text("# Private\n")

        files = u.Infra.iter_markdown_files(workspace)

        tm.that(files, eq=[visible])

    def test_nested_structure(self, tmp_path: Path) -> None:
        """Test iter_markdown_files with nested directory structure."""
        nested_dir = tmp_path / "docs/guides/advanced"
        nested_dir.mkdir(parents=True, exist_ok=True)
        (nested_dir / "guide.md").write_text("# Guide\n")
        files = u.Infra.iter_markdown_files(tmp_path)
        tm.that(len(files) > 0, eq=True)

    def test_returns_sorted_list(self, tmp_path: Path) -> None:
        """Test iter_markdown_files returns sorted list."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "z.md").write_text("# Z")
        (docs_dir / "a.md").write_text("# A")
        files = u.Infra.iter_markdown_files(tmp_path)
        tm.that(len(files), gte=2)
        str_files = [str(f) for f in files]
        tm.that(str_files, eq=sorted(str_files))

    def test_no_docs_dir(self, tmp_path: Path) -> None:
        """Test iter_markdown_files when docs dir doesn't exist."""
        files = u.Infra.iter_markdown_files(tmp_path)
        tm.that(len(files), gte=0)

    def test_docs_at_root(self, tmp_path: Path) -> None:
        """Test iter_markdown_files finds docs at root."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "test.md").write_text("# Test")
        files = u.Infra.iter_markdown_files(tmp_path)
        tm.that(len(files) > 0, eq=True)

    def test_excludes_node_modules(self, tmp_path: Path) -> None:
        """Test iter_markdown_files excludes node_modules."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        nm_dir = docs_dir / "node_modules"
        nm_dir.mkdir(parents=True, exist_ok=True)
        (nm_dir / "test.md").write_text("# Test")
        files = u.Infra.iter_markdown_files(tmp_path)
        tm.that(not any("node_modules" in str(f) for f in files), eq=True)

    def test_excludes_archived_markdown(self, tmp_path: Path) -> None:
        """Test historical backup files and legado roots remain evidence-only."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        backup = docs_dir / "guide.bak-legacy.md"
        backup.write_text("# Archived backup\n")
        legado = docs_dir / "legado"
        legado.mkdir()
        archived = legado / "guide.md"
        archived.write_text("# Archived tree\n")

        files = u.Infra.iter_markdown_files(tmp_path)

        tm.that(backup in files, eq=False)
        tm.that(archived in files, eq=False)

    def test_excludes_generated_crg_reports(self, tmp_path: Path) -> None:
        """Keep graph evidence outside mutable documentation normalization."""
        maintained = tmp_path / "docs/architecture/README.md"
        maintained.parent.mkdir(parents=True)
        maintained.write_text("# Architecture\n")
        generated = tmp_path / "docs/architecture/crg-reports/architecture.md"
        generated.parent.mkdir(parents=True)
        generated.write_text("# CRG report\n")

        files = u.Infra.iter_markdown_files(tmp_path)

        tm.that(maintained in files, eq=True)
        tm.that(generated in files, eq=False)

    def test_excludes_immutable_plan_collection_revisions(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        current = docs_dir / "plans" / "current.md"
        incoming = docs_dir / "plans" / "current" / "incoming" / "digest" / "plan.md"
        incoming.parent.mkdir(parents=True)
        current.write_text("# Current\n")
        incoming.write_text("# Immutable revision\n")

        files = u.Infra.iter_markdown_files(tmp_path)

        tm.that(current in files, eq=True)
        tm.that(incoming in files, eq=False)
