"""Lint fix recipes repair the findings Ruff reports without a fix.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, m, t, u


class TestsFlextInfraLintRecipes:
    """Each recipe derives its repair from the source the finding points at."""

    @staticmethod
    def _apply(
        source: str,
        *issues: t.Triple[str, int, str],
        path: Path = Path("sample.py"),
    ) -> str:
        recipes = config.Infra.tooling.tools.ruff.lint.fix_recipes
        findings = tuple(
            m.Infra.Issue(
                file=str(path),
                line=line,
                column=1,
                code=code,
                message=message,
            )
            for code, line, message in issues
        )
        hooks = u.Infra.overridden_findings(
            source,
            findings,
            path=path,
            recipes=recipes,
            overridden=u.Infra.overridden_methods((source,)),
        )
        return u.Infra.apply_lint_recipes(
            source,
            tuple(finding for finding in findings if finding not in hooks),
            path=path,
            recipes=recipes,
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

    def test_raises_condition_with_quotes_keeps_the_literal_intact(self) -> None:
        """A derived condition holding triple quotes stays inside the docstring."""
        source = (
            "def literal(body: str) -> str:\n"
            '    """Return the literal."""\n'
            '    if not body.startswith(\'"""\'):\n'
            '        msg = f"{body} is not a literal"\n'
            "        raise ValueError(msg)\n"
            "    return body\n"
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

        function = ast.parse(repaired).body[0]
        tm.that(function, is_=ast.FunctionDef)
        assert isinstance(function, ast.FunctionDef)
        tm.that(
            ast.get_docstring(function) or "",
            has='ValueError: If ``not body.startswith(\'"""\')``.',
        )

    def test_raises_condition_drops_the_opener_its_placeholder_left(self) -> None:
        """A message prefix cut at a placeholder keeps no dangling bracket."""
        source = (
            "def select(code: int) -> int:\n"
            '    """Select one outcome."""\n'
            "    if code:\n"
            '        msg = f"selection failed ({code}): rejected"\n'
            "        raise RuntimeError(msg)\n"
            "    return code\n"
        )

        repaired = self._apply(
            source,
            ("docstring-missing-returns", 2, "`return` is not documented"),
            (
                "docstring-missing-exception",
                5,
                "Raised exception `RuntimeError` missing from docstring",
            ),
        )

        function = ast.parse(repaired).body[0]
        tm.that(function, is_=ast.FunctionDef)
        assert isinstance(function, ast.FunctionDef)
        docstring = ast.get_docstring(function) or ""
        tm.that(docstring, has="RuntimeError: If selection failed.")
        tm.that(docstring, lacks="failed (")

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

    def test_summary_docstring_expands_an_inline_protocol_body(self) -> None:
        """An inline protocol stub is legal Python and receives a summary."""
        source = (
            "class Sample:\n"
            '    """Define the sample."""\n'
            "\n"
            "    def __call__(self) -> int: ...\n"
        )

        repaired = self._apply(
            source,
            ("undocumented-public-method", 4, "Missing docstring in public method"),
        )

        tm.that(
            repaired,
            eq=(
                "class Sample:\n"
                '    """Define the sample."""\n'
                "\n"
                "    def __call__(self) -> int:\n"
                '        """Provide ``__call__``."""\n'
                "        ...\n"
            ),
        )
        ast.parse(repaired)

    def test_summary_docstring_expands_a_wrapped_signature_stub(self) -> None:
        """A stub whose suite shares the signature's last line expands there."""
        source = (
            "class Sample:\n"
            "    def __call__[T](\n"
            "        self,\n"
            "        operation: Callable[[], T],\n"
            "    ) -> T: ...\n"
        )

        repaired = self._apply(
            source,
            ("undocumented-public-method", 2, "Missing docstring in public method"),
        )

        tm.that(
            repaired,
            eq=(
                "class Sample:\n"
                "    def __call__[T](\n"
                "        self,\n"
                "        operation: Callable[[], T],\n"
                "    ) -> T:\n"
                '        """Provide ``__call__``."""\n'
                "        ...\n"
            ),
        )
        ast.parse(repaired)

    def test_summary_docstring_expands_an_inline_body_under_its_class(self) -> None:
        """A class summary stays before the method its inline body expands into."""
        source = "class Sample:\n    def __call__(self) -> int: ...\n"

        repaired = self._apply(
            source,
            ("undocumented-public-class", 1, "Missing docstring in public class"),
            ("undocumented-public-method", 2, "Missing docstring in public method"),
        )

        tm.that(
            repaired,
            eq=(
                "class Sample:\n"
                '    """Define ``Sample``."""\n'
                "    def __call__(self) -> int:\n"
                '        """Provide ``__call__``."""\n'
                "        ...\n"
            ),
        )
        ast.parse(repaired)

    def test_copyright_notice_follows_the_module_summary(
        self,
        tmp_path: Path,
    ) -> None:
        """The notice is signed by the author the owning manifest declares."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "sample"\nversion = "1.0.0"\n'
            'authors = [{ name = "Sample Author" }]\n',
            encoding="utf-8",
        )
        module = tmp_path / "sample.py"

        repaired = self._apply(
            '"""Sample module."""\n\nVALUE = 1\n',
            ("missing-copyright-notice", 1, "Missing copyright notice"),
            path=module,
        )

        notice = u.Infra.copyright_notice(tmp_path, module=module)
        sibling = u.Infra.copyright_notice(tmp_path, module=tmp_path / "other.py")
        tm.that(notice, has="Sample Author")
        tm.that(notice, has="\nsample\nSPDX-License-Identifier:")
        tm.that(sibling, has="\nother\nSPDX-License-Identifier:")
        tm.that(repaired, eq=f'"""Sample module.\n\n{notice}\n"""\n\nVALUE = 1\n')

    def test_a_module_without_a_copyright_finding_needs_no_author(
        self,
        tmp_path: Path,
    ) -> None:
        """Other recipes repair a project whose manifest declares no author."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "sample"\nversion = "1.0.0"\n',
            encoding="utf-8",
        )
        source = (
            "def name_of(path: str) -> str:\n"
            '    """Return the module name for a file."""\n'
            "    return path\n"
        )

        repaired = self._apply(
            source,
            ("docstring-missing-returns", 2, "`return` is not documented"),
            path=tmp_path / "sample.py",
        )

        tm.that(repaired, has="    Returns:\n")

    @staticmethod
    def _unused_receiver(source: str, *names: str) -> str:
        """Apply the static-method recipe to each named method as Ruff reports it.

        Returns:
            The repaired source.

        """
        tree = ast.parse(source)
        lines = {
            node.name: node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        return TestsFlextInfraLintRecipes._apply(
            source,
            *(
                (
                    "no-self-use",
                    lines[name],
                    (
                        f"Method `{name}` could be a function, class method, "
                        "or static method"
                    ),
                )
                for name in names
            ),
        )

    @staticmethod
    def test_static_method_keeps_every_body_byte() -> None:
        """Only the receiver and the decorator list change; the body is verbatim."""
        source = (
            "class TestsSample:\n"
            '    @pytest.mark.parametrize("value", [1, 2])\n'
            "    def test_value(self, value: int) -> None:\n"
            "        # a comment stays\n"
            "\n"
            '        text = "  spaced  "\n'
            "        assert value, text\n"
            "\n"
            "    def keyword(self, *, flag: bool) -> bool:\n"
            "        return flag\n"
            "\n"
            "    class Inner:\n"
            "        async def coro(self, /, value: int) -> int:\n"
            "            return value\n"
        )

        repaired = TestsFlextInfraLintRecipes._unused_receiver(
            source,
            "test_value",
            "keyword",
            "coro",
        )

        tm.that(
            repaired,
            eq=(
                "class TestsSample:\n"
                "    @staticmethod\n"
                '    @pytest.mark.parametrize("value", [1, 2])\n'
                "    def test_value(value: int) -> None:\n"
                "        # a comment stays\n"
                "\n"
                '        text = "  spaced  "\n'
                "        assert value, text\n"
                "\n"
                "    @staticmethod\n"
                "    def keyword(*, flag: bool) -> bool:\n"
                "        return flag\n"
                "\n"
                "    class Inner:\n"
                "        @staticmethod\n"
                "        async def coro(value: int) -> int:\n"
                "            return value\n"
            ),
        )

    @staticmethod
    def test_static_method_collapses_a_sole_receiver() -> None:
        """A receiver that was the only parameter leaves empty parentheses."""
        source = (
            "class TestsSample:\n"
            "    def test_sole(\n"
            "        self,\n"
            "    ) -> None:\n"
            "        assert True\n"
        )

        repaired = TestsFlextInfraLintRecipes._unused_receiver(source, "test_sole")

        tm.that(
            repaired,
            eq=(
                "class TestsSample:\n"
                "    @staticmethod\n"
                "    def test_sole() -> None:\n"
                "        assert True\n"
            ),
        )

    @staticmethod
    def test_static_method_refuses_a_comment_beside_the_receiver() -> None:
        """A comment the removal would drop stops the recipe with nothing written."""
        source = (
            "class TestsSample:\n"
            "    def test_note(\n"
            "        self,  # the receiver\n"
            "        value: int,\n"
            "    ) -> None:\n"
            "        assert value\n"
        )

        with pytest.raises(ValueError, match="comment or continuation"):
            TestsFlextInfraLintRecipes._unused_receiver(source, "test_note")

    @staticmethod
    def test_static_method_leaves_a_hook_a_subclass_overrides() -> None:
        """A base method a subclass redefines keeps its receiver."""
        source = (
            "class Base:\n"
            "    def hook(self) -> int:\n"
            "        return 1\n"
            "\n"
            "\n"
            "class Child(Base):\n"
            "    def hook(self) -> int:\n"
            "        return id(self)\n"
        )

        repaired = TestsFlextInfraLintRecipes._apply(
            source,
            ("no-self-use", 2, "Method `hook` could be a function"),
        )

        tm.that(repaired, eq=source)

    @staticmethod
    def test_static_method_leaves_an_override_of_a_parent_method() -> None:
        """A subclass method that redefines its base method keeps its receiver."""
        source = (
            "class Base:\n"
            "    def hook(self) -> int:\n"
            "        return id(self)\n"
            "\n"
            "\n"
            "class Child(Base):\n"
            "    def hook(self) -> int:\n"
            "        return 1\n"
        )

        repaired = TestsFlextInfraLintRecipes._apply(
            source,
            ("no-self-use", 7, "Method `hook` could be a function"),
        )

        tm.that(repaired, eq=source)

    @staticmethod
    def test_static_method_leaves_a_method_that_reads_its_receiver() -> None:
        """Zero-argument ``super()`` reads the receiver, so the method keeps it."""
        source = (
            "class Sample(Base):\n"
            "    def run(self) -> int:\n"
            "        return super().run() + 1\n"
        )

        repaired = TestsFlextInfraLintRecipes._apply(
            source,
            ("no-self-use", 2, "Method `run` could be a function"),
        )

        tm.that(repaired, eq=source)
