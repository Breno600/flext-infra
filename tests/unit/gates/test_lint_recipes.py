"""Lint fix recipes repair the findings Ruff reports without a fix."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config, m, t, u


class TestsFlextInfraLintRecipes:
    """Each recipe derives its repair from the source the finding points at."""

    @staticmethod
    def _apply(source: str, *issues: t.Triple[str, int, str]) -> str:
        return u.Infra.apply_lint_recipes(
            source,
            tuple(
                m.Infra.Issue(
                    file="sample.py",
                    line=line,
                    column=1,
                    code=code,
                    message=message,
                )
                for code, line, message in issues
            ),
            path=Path("sample.py"),
            recipes=config.Infra.tooling.tools.ruff.lint.fix_recipes,
            notice="Copyright (c) 2026 Sample. All rights reserved.\nSPDX: MIT",
        )

    def test_returns_section_takes_the_summary_object(self) -> None:
        """Test returns section takes the summary object."""
        source = (
            "def name_of(path: str) -> str:\n"
            '    """Return the module name for a file."""\n'
            "    return path\n"
        )

        repaired = self._apply(
            source,
            ("docstring-missing-returns", 2, "`return` is not documented"),
        )

        tm.that(
            repaired,
            eq=(
                "def name_of(path: str) -> str:\n"
                '    """Return the module name for a file.\n'
                "\n"
                "    Returns:\n"
                "        The module name for a file.\n"
                '    """\n'
                "    return path\n"
            ),
        )

    def test_raises_section_states_the_message_condition(self) -> None:
        """Test raises section states the message condition."""
        source = (
            "def load(path: str) -> str:\n"
            '    """Load one source."""\n'
            "    if not path:\n"
            '        msg = f"source path is empty: {path}"\n'
            "        raise ValueError(msg)\n"
            "    return path\n"
        )

        repaired = self._apply(
            source,
            ("docstring-missing-returns", 2, "`return` is not documented"),
            (
                "docstring-missing-exception",
                5,
                "Raised exception `ValueError` missing from docstring",
            ),
        )

        tm.that(
            repaired,
            eq=(
                "def load(path: str) -> str:\n"
                '    """Load one source.\n'
                "\n"
                "    Returns:\n"
                "        The resulting ``str``.\n"
                "\n"
                "    Raises:\n"
                "        ValueError: If source path is empty.\n"
                '    """\n'
                "    if not path:\n"
                '        msg = f"source path is empty: {path}"\n'
                "        raise ValueError(msg)\n"
                "    return path\n"
            ),
        )

    def test_summary_docstring_derives_from_the_name(self) -> None:
        """Test summary docstring derives from the name."""
        source = (
            "class TestsSample:\n"
            "    def test_reads_the_lock(self) -> None:\n"
            "        assert self\n"
        )

        repaired = self._apply(
            source,
            ("undocumented-public-class", 1, "Missing docstring in public class"),
            ("undocumented-public-method", 2, "Missing docstring in public method"),
        )

        tm.that(
            repaired,
            eq=(
                "class TestsSample:\n"
                '    """Tests for ``Sample``."""\n'
                "    def test_reads_the_lock(self) -> None:\n"
                '        """Test reads the lock."""\n'
                "        assert self\n"
            ),
        )

    def test_copyright_notice_follows_the_module_summary(self) -> None:
        """Test copyright notice follows the module summary."""
        source = '"""Sample module."""\n\nVALUE = 1\n'

        repaired = self._apply(
            source,
            ("missing-copyright-notice", 1, "Missing copyright notice"),
        )

        tm.that(
            repaired,
            eq=(
                '"""Sample module.\n'
                "\n"
                "Copyright (c) 2026 Sample. All rights reserved.\n"
                "SPDX: MIT\n"
                '"""\n'
                "\n"
                "VALUE = 1\n"
            ),
        )
