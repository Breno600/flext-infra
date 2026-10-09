"""Public markdown-format (rumdl fmt) and markdown-code (embedded ruff) gates.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, m
from flext_infra.gates.markdown_code import FlextInfraMarkdownCodeGate
from flext_infra.gates.markdown_code_sources import FlextInfraMarkdownCodeSources
from flext_infra.gates.markdown_format import FlextInfraMarkdownFormatGate
from tests import u

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
    # rumdl fmt reads the generated .markdownlint.json; the fixtures
    # materialize that projection the way `make gen` does.
    RULES_CONFIG = "{}"
    UNFORMATTED_LIST = "# Test\n\n*   item one\n*   item two\n"
    FORMATTED_LIST = "# Test\n\n* item one\n* item two\n"

    def _project(self, tmp_path: Path, name: str, content: str) -> Path:
        """Create one project carrying README.md and the rule projection.

        Returns:
            The project directory.

        """
        project_dir = u.Tests.mk_project(tmp_path, name)
        (project_dir / "README.md").write_text(content, encoding="utf-8")
        (project_dir / c.Infra.MARKDOWNLINT_CONFIG_FILENAME).write_text(
            self.RULES_CONFIG,
            encoding="utf-8",
        )
        return project_dir

    @pytest.mark.parametrize("force_color", ["0", "1"])
    def test_format_gate_reports_unformatted_markdown(
        self,
        tmp_path: Path,
        force_color: str,
    ) -> None:
        """The real formatter's plain and colored findings name the same file."""
        project_dir = self._project(
            tmp_path,
            "markdown-format-project",
            self.UNFORMATTED_LIST,
        )

        with tm.scope(env={"FORCE_COLOR": force_color}):
            result = u.Tests.check_gate_asserting(
                FlextInfraMarkdownFormatGate,
                tmp_path,
                project_dir,
                passed=False,
                issues_len=1,
            )

        tm.that(
            result.issues[0].code,
            eq=c.Infra.MARKDOWN_FORMAT,
            msg=result.issues[0].message,
        )
        tm.that(result.issues[0].file, eq="README.md")

    def test_format_gate_passes_formatted_markdown(self, tmp_path: Path) -> None:
        """Formatted markdown leaves nothing for the formatter to rewrite."""
        project_dir = self._project(
            tmp_path,
            "markdown-format-clean",
            self.FORMATTED_LIST,
        )

        _ = u.Tests.check_gate_asserting(
            FlextInfraMarkdownFormatGate,
            tmp_path,
            project_dir,
            passed=True,
            issues_len=0,
        )

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
        """`make fmt` drives `rumdl fmt` once and the tree reaches green."""
        project_dir = self._project(
            tmp_path,
            "markdown-format-fix",
            self.UNFORMATTED_LIST,
        )
        readme = project_dir / "README.md"
        u.Tests.initialize_git_repo(project_dir)
        context = m.Infra.GateContext(
            repository_root=tmp_path,
            reports_dir=tmp_path,
            apply_fixes=True,
        )

        result = FlextInfraMarkdownFormatGate(tmp_path).fix(project_dir, context)

        tm.that(result.result.passed, eq=True)
        tm.that(readme.read_text(encoding="utf-8"), eq=self.FORMATTED_LIST)
        _ = u.Tests.check_gate_asserting(
            FlextInfraMarkdownFormatGate,
            tmp_path,
            project_dir,
            passed=True,
            issues_len=0,
        )

    def test_format_gate_fails_closed_without_generated_rules(
        self,
        tmp_path: Path,
    ) -> None:
        """A missing generated rule projection is a generation gap, never a pass."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-format-no-rules")
        (project_dir / "README.md").write_text(self.FORMATTED_LIST, encoding="utf-8")

        result = u.Tests.run_gate_check(
            FlextInfraMarkdownFormatGate,
            tmp_path,
            project_dir,
        )

        tm.that(result.result.passed, eq=False)
        tm.that(len(result.issues), eq=1)
        tm.that(result.issues[0].message, has="make gen")

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

    def test_code_gate_names_the_unformatted_block(self, tmp_path: Path) -> None:
        """The finding names the offending fence and carries ruff's own line."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-code-located")
        content = self.FORMATTED + "\nProse.\n\n```python\ny=2\n```\n"
        (project_dir / "README.md").write_text(content, encoding="utf-8")

        result = u.Tests.check_gate_asserting(
            FlextInfraMarkdownCodeGate,
            tmp_path,
            project_dir,
            passed=False,
            issues_len=1,
        )

        issue = result.issues[0]
        tm.that(issue.file, eq="README.md")
        tm.that(issue.line, eq=content[: content.rindex("```python")].count("\n") + 1)
        tm.that(
            issue.message,
            has=FlextInfraMarkdownCodeSources.source_name("README.md", 1),
        )

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
