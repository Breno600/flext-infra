"""Public utility tests used by docs fixing flows.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.docs.fixer import FlextInfraDocFixer
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraFixerInternals:
    """Public utility tests used by docs fixing flows."""

    @staticmethod
    def test_docs_maybe_fix_link_adds_md_suffix_when_target_exists(
        tmp_path: Path,
    ) -> None:
        """Test docs maybe fix link adds md suffix when target exists."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        md_file = docs_dir / "README.md"
        md_file.write_text("# Docs\n", encoding="utf-8")
        (docs_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")

        fixed = u.Infra.docs_maybe_fix_link(md_file, "guide")

        tm.that(fixed, eq="guide.md")

    @staticmethod
    def test_docs_maybe_fix_link_rejects_http(tmp_path: Path) -> None:
        """Test docs maybe fix link rejects http."""
        target = f"{c.Infra.DOCS_INSECURE_WEB_SCHEME}://example.invalid"

        with pytest.raises(ValueError, match="use HTTPS"):
            u.Infra.docs_maybe_fix_link(tmp_path / "README.md", target)

    @staticmethod
    def test_anchorize_and_build_toc_are_public_helpers() -> None:
        """Test anchorize and build toc are public helpers."""
        tm.that(u.Infra.anchorize("Hello World"), eq="hello-world")
        tm.that(
            u.Infra.build_toc("# Main\n\nNo sections here.\n"),
            has="No sections found",
        )

    @pytest.mark.parametrize("separator", ["\n", "\n\n", "\n\n\n"])
    def test_fix_keeps_closing_fence_on_its_own_line(
        self,
        tmp_path: Path,
        separator: str,
    ) -> None:
        """Test fix keeps closing fence on its own line.

        The fence carries one auto-fixable defect (the unused ``os`` import);
        every other line is rule-clean, because behavior rules stay active
        inside fences and an unfixable finding fails the fixer.
        """
        workspace = u.Tests.create_docs_workspace(tmp_path, include_fixable_link=True)
        sample = workspace / "docs/fenced.md"
        sample.write_text(
            "# Fenced\n\n"
            "## Sample\n\n"
            "```python\n"
            "import os\n"
            "import sys\n\n"
            "VERSION = sys.version\n"
            f"```{separator}"
            "## After The Block\n",
            encoding="utf-8",
        )

        result = FlextInfraDocFixer().fix(workspace, apply=True)

        tm.ok(result)
        fixed = sample.read_text(encoding="utf-8")
        tm.that(fixed, lacks=")```")
        tm.that(fixed, has=f"\n```{separator}## After The Block")
        tm.that(fixed, has="## After The Block")

    @staticmethod
    def test_fix_updates_docs_readme_when_apply_is_enabled(
        tmp_path: Path,
    ) -> None:
        """Test fix updates docs readme when apply is enabled."""
        workspace = u.Tests.create_docs_workspace(tmp_path, include_fixable_link=True)

        result = FlextInfraDocFixer().fix(workspace, apply=True)

        tm.ok(result)
        tm.that((workspace / "docs/README.md").read_text(), has="guides/setup.md")
