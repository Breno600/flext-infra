"""Embedded-Python source collection for the ``markdown-code`` gate.

Fenced ``python``` blocks on the governed markdown surface and doctest
examples inside tracked docstrings are collected once as named sources, each
mapped back to its documentation origin. The gate writes them into one
temporary tree so ruff validates and formats them in single invocations, and
selects itself only for a project whose content yields at least one source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from doctest import DocTestParser
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, u

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraMarkdownCodeSources:
    """Collect embedded Python from documentation as named, located sources."""

    @staticmethod
    def syntax_broken(code: str, origin: Path) -> bool:
        """Identify documentation fragments owned by the Markdown syntax validator.

        Returns:
            The resulting ``bool``.

        """
        try:
            compile(code, str(origin), "exec")
        except SyntaxError:
            return True
        return False

    @staticmethod
    def source_name(relative_posix: str, index: int) -> str:
        """Encode one block's documentation location into a temp source filename.

        Returns:
            The resulting ``str``.

        """
        return c.Infra.MARKDOWN_CODE_SOURCE_FORMAT.format(
            relative_posix.replace("/", "__").replace(".", "_"),
            index,
        )

    @staticmethod
    def fenced_block_sources(
        project_dir: Path,
        markdown_files: t.SequenceOf[Path],
    ) -> t.VariadicTuple[t.Triple[str, str, t.Pair[str, int]]]:
        """Collect one named source per parseable fenced ``python`` block.

        Blocks carrying the ``notest`` fence marker and unparseable fragments
        are excluded. The Markdown validator owns syntax errors; this gate owns
        only formatting of Python blocks that compile.

        Returns:
            The resulting ``t.VariadicTuple[t.Triple[str, str, t.Pair[str, int]]]``.

        """
        collected: list[t.Triple[str, str, t.Pair[str, int]]] = []
        for md_path in markdown_files:
            relative_posix = md_path.relative_to(project_dir).as_posix()
            content = md_path.read_text(c.Cli.ENCODING_DEFAULT)
            for index, match in enumerate(
                match
                for match in c.Infra.MARKDOWN_PY_FENCE_RE.finditer(content)
                if c.Infra.MARKDOWN_CODE_SKIP_MARKER not in match.group("info")
            ):
                source_text = match.group("code")
                if FlextInfraMarkdownCodeSources.syntax_broken(source_text, md_path):
                    continue
                collected.append((
                    FlextInfraMarkdownCodeSources.source_name(relative_posix, index),
                    source_text,
                    (relative_posix, content[: match.start()].count("\n") + 1),
                ))
        return tuple(collected)

    @staticmethod
    def docstring_sources(
        project_dir: Path,
    ) -> t.VariadicTuple[t.Triple[str, str, t.Pair[str, int]]]:
        """Collect one named source per doctest example in tracked docstrings.

        Docstring write-back stays outside the fix contract on purpose: a
        formatter rewrite inside prose is a semantics risk, so docstring
        findings remain manual repairs. Example line numbers are approximate
        within the docstring (stdlib ``doctest`` reports positions relative to
        its input).

        Returns:
            The resulting ``t.VariadicTuple[t.Triple[str, str, t.Pair[str, int]]]``.

        """
        collected: list[t.Triple[str, str, t.Pair[str, int]]] = []
        parser = DocTestParser()
        for py_path in u.Infra.iter_matching_files(project_dir, includes=["*.py"]):
            relative_parts = py_path.relative_to(project_dir).parts
            if any(part in c.Infra.CHECK_EXCLUDED_DIRS for part in relative_parts):
                continue
            if ".github" in relative_parts and any(
                part in c.Infra.GITHUB_AGENT_PROJECTION_DIRS for part in relative_parts
            ):
                # Agent-toolhome projections under .github are regenerated
                # distributions, never governed source.
                continue
            tree = ast.parse(py_path.read_text(c.Cli.ENCODING_DEFAULT))
            for node in ast.walk(tree):
                # Only these carry docstrings; ast.walk also yields expression
                # nodes and ast.get_docstring raises TypeError on those.
                if not isinstance(
                    node,
                    ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
                ):
                    continue
                docstring = ast.get_docstring(node, clean=False)
                if docstring is None or not node.body:
                    continue
                body_start = node.body[0].lineno
                relative_posix = py_path.relative_to(project_dir).as_posix()
                for index, example in enumerate(parser.get_examples(docstring)):
                    source_text = example.source
                    compile(source_text, str(py_path), "exec")
                    collected.append((
                        FlextInfraMarkdownCodeSources.source_name(
                            relative_posix,
                            index,
                        ),
                        source_text,
                        (relative_posix, body_start + example.lineno),
                    ))
        return tuple(collected)


__all__: list[str] = ["FlextInfraMarkdownCodeSources"]
