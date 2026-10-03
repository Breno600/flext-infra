"""Public markdown-format (prettier) and markdown-code (embedded ruff) gates.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import c, m
from flext_infra.gates.markdown_code import FlextInfraMarkdownCodeGate
from flext_infra.gates.markdown_format import FlextInfraMarkdownFormatGate
from tests import TestsFlextInfraUtilities as u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraMarkdownFormatAndCodeGates:
    """Declarative public-contract tests for the markdown formatting gates."""

    FORMATTED_MARKDOWN = "# Test\n"
    UNFORMATTED_MARKDOWN = "#    Test\n"
    FORMATTED = "# Test\n\n```python\nx = 1\n```\n"
    UNFORMATTED = "# Test\n\n```python\nx=1\n```\n"
    SYNTAX_BROKEN = "# Test\n\n```python\ndef broken(:\n    return 1\n```\n"
    NOTEST_PSEUDO = "# Test\n\n```python notest\nthis is @@@ not python\n```\n"
    FRAGMENT_THEN_UNFORMATTED = (
        "# Test\n\n```python notest\ndef broken(:\n    return 1\n```\n\n"
        "```python\nx=1\n```\n"
    )
    FRAGMENT_THEN_FORMATTED = (
        "# Test\n\n```python notest\ndef broken(:\n    return 1\n```\n\n"
        "```python\nx = 1\n```\n"
    )
    # Prettier only rewraps prose under proseWrap=always (the projected fleet
    # contract); fixtures materialize that config the way `make gen` does.
    PROSE_CONFIG = '{"printWidth": 40, "proseWrap": "always"}'
    LONG_PROSE = (
        "# Test\n\nLorem ipsum dolor sit amet consectetur adipiscing elit"
        " sed do eiusmod tempor incididunt ut labore magna.\n"
    )
    WRAPPED_PROSE_HEAD = "# Test\n\nLorem ipsum dolor sit amet consectetur"

    def test_format_gate_reports_unformatted_markdown(self, tmp_path: Path) -> None:
        """Test format gate reports unformatted markdown."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-format-project")
        (project_dir / "README.md").write_text(self.LONG_PROSE, encoding="utf-8")
        (project_dir / c.Infra.PRETTIER_CONFIG_FILENAME).write_text(
            self.PROSE_CONFIG,
            encoding="utf-8",
        )

        result = u.Tests.check_gate_asserting(
            FlextInfraMarkdownFormatGate,
            tmp_path,
            project_dir,
            passed=False,
            issues_len=1,
        )

        tm.that(result.issues[0].code, eq=c.Infra.MARKDOWN_FORMAT)
        tm.that(result.issues[0].file, eq="README.md")

    @staticmethod
    def test_format_gate_without_markdown_is_red(tmp_path: Path) -> None:
        """Zero collected markdown is red, never a neutral pass."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-format-empty")

        result = FlextInfraMarkdownFormatGate(tmp_path).check(
            project_dir,
            u.Tests.gate_context(tmp_path),
        )

        tm.that(result.result.passed, eq=False)

    def test_format_gate_fix_is_the_single_writer(self, tmp_path: Path) -> None:
        """`make fmt` drives prettier --write once and the tree reaches green."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-format-fix")
        readme = project_dir / "README.md"
        readme.write_text(self.LONG_PROSE, encoding="utf-8")
        (project_dir / c.Infra.PRETTIER_CONFIG_FILENAME).write_text(
            self.PROSE_CONFIG,
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(project_dir)
        context = m.Infra.GateContext(
            repository_root=tmp_path,
            reports_dir=tmp_path,
            apply_fixes=True,
        )

        result = FlextInfraMarkdownFormatGate(tmp_path).fix(project_dir, context)

        tm.that(result.result.passed, eq=True)
        tm.that(readme.read_text(encoding="utf-8"), has=self.WRAPPED_PROSE_HEAD)
        _ = u.Tests.check_gate_asserting(
            FlextInfraMarkdownFormatGate,
            tmp_path,
            project_dir,
            passed=True,
            issues_len=0,
        )

    def test_format_gate_fails_closed_without_provisioned_binary(
        self,
        tmp_path: Path,
    ) -> None:
        """A missing mise-provisioned binary is a tool error, never a clean pass."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-format-no-binary")
        (project_dir / "README.md").write_text(self.FORMATTED, encoding="utf-8")
        empty_path = tmp_path / "empty-path"
        empty_path.mkdir()

        with tm.scope(env={"PATH": str(empty_path)}):
            result = u.Tests.run_gate_check(
                FlextInfraMarkdownFormatGate,
                tmp_path,
                project_dir,
            )

        tm.that(result.result.passed, eq=False)
        tm.that(len(result.issues), eq=1)
        tm.that("make setup" in result.issues[0].message, eq=True)

    def test_code_gate_clean_block_passes(self, tmp_path: Path) -> None:
        """Test code gate clean block passes."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-code-clean")
        (project_dir / "README.md").write_text(self.FORMATTED, encoding="utf-8")

        _ = u.Tests.check_gate_asserting(
            FlextInfraMarkdownCodeGate,
            tmp_path,
            project_dir,
            passed=True,
            issues_len=0,
        )

    def test_code_gate_notest_only_blocks_do_not_select_the_gate(
        self,
        tmp_path: Path,
    ) -> None:
        """A ``notest`` fence is not embedded code to check (#1223 selection)."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-code-notest")
        (project_dir / "README.md").write_text(self.NOTEST_PSEUDO, encoding="utf-8")

        tm.that(
            FlextInfraMarkdownCodeGate(tmp_path).selected_for(project_dir),
            eq=False,
        )

    def test_code_gate_fix_splices_formatted_block_back(self, tmp_path: Path) -> None:
        """`make fix` formats fenced blocks whose round-trip recompiles cleanly."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-code-fix")
        readme = project_dir / "README.md"
        readme.write_text(self.UNFORMATTED, encoding="utf-8")
        u.Tests.initialize_git_repo(project_dir)
        context = m.Infra.GateContext(
            repository_root=tmp_path,
            reports_dir=tmp_path,
            apply_fixes=True,
        )

        result = FlextInfraMarkdownCodeGate(tmp_path).fix(project_dir, context)

        tm.that(result.result.passed, eq=True)
        tm.that(readme.read_text(encoding="utf-8"), eq=self.FORMATTED)

    def test_code_gate_fix_splices_block_after_fragment(self, tmp_path: Path) -> None:
        """A parseable block keeps its extractor index after a ``notest`` fragment.

        Regression: enumerating only parseable blocks shifted every later
        source name, so a valid block after a fragment was never spliced.
        """
        project_dir = u.Tests.mk_project(tmp_path, "markdown-code-fix-after-fragment")
        readme = project_dir / "README.md"
        readme.write_text(self.FRAGMENT_THEN_UNFORMATTED, encoding="utf-8")
        u.Tests.initialize_git_repo(project_dir)
        context = m.Infra.GateContext(
            repository_root=tmp_path,
            reports_dir=tmp_path,
            apply_fixes=True,
        )

        result = FlextInfraMarkdownCodeGate(tmp_path).fix(project_dir, context)

        tm.that(result.result.passed, eq=True)
        tm.that(readme.read_text(encoding="utf-8"), eq=self.FRAGMENT_THEN_FORMATTED)

    def test_code_gate_fix_preserves_fragment_for_syntax_owner(
        self,
        tmp_path: Path,
    ) -> None:
        """Formatting never rewrites a fence it cannot parse.

        The invalid fence stays byte-identical for the gate that owns its
        syntax verdict; the code formatter only formats what it can parse.
        """
        project_dir = u.Tests.mk_project(tmp_path, "markdown-code-no-splice")
        readme = project_dir / "README.md"
        readme.write_text(self.SYNTAX_BROKEN, encoding="utf-8")
        context = m.Infra.GateContext(
            repository_root=tmp_path,
            reports_dir=tmp_path,
            apply_fixes=True,
        )

        FlextInfraMarkdownCodeGate(tmp_path).fix(project_dir, context)
        tm.that(readme.read_text(encoding="utf-8"), eq=self.SYNTAX_BROKEN)

    @staticmethod
    def test_code_gate_reports_unformatted_docstring_example(
        tmp_path: Path,
    ) -> None:
        """Parseable docstring examples answer to the format contract."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-code-docstring")
        source_dir = project_dir / c.Infra.DEFAULT_SRC_DIR
        source_dir.mkdir()
        (source_dir / "widget.py").write_text(
            '"""Widget.\n\n>>> x=1\n\n"""',
            encoding="utf-8",
        )

        result = u.Tests.check_gate_asserting(
            FlextInfraMarkdownCodeGate,
            tmp_path,
            project_dir,
            passed=False,
            issues_len=1,
        )

        tm.that(result.issues[0].file, eq="src/widget.py")

    @staticmethod
    def test_code_gate_is_not_selected_without_embedded_code(
        tmp_path: Path,
    ) -> None:
        """Prose-only documentation never selects the embedded-code gate."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-code-empty")
        (project_dir / "README.md").write_text("# Prose only\n", encoding="utf-8")
        gate = FlextInfraMarkdownCodeGate(tmp_path)

        tm.that(gate.selected_for(project_dir), eq=False)
        tm.that(
            gate.check(project_dir, u.Tests.gate_context(tmp_path)).result.passed,
            eq=False,
        )

    def test_code_gate_is_selected_with_embedded_code(self, tmp_path: Path) -> None:
        """A parseable fenced Python block selects the embedded-code gate."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-code-present")
        (project_dir / "README.md").write_text(self.FORMATTED, encoding="utf-8")

        tm.that(FlextInfraMarkdownCodeGate(tmp_path).selected_for(project_dir), eq=True)
