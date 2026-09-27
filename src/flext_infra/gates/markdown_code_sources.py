"""Embedded-Python source extraction for the ``markdown-code`` gate.

Fenced ``python``` blocks on the governed markdown surface and doctest
examples inside tracked docstrings are extracted once into a temporary source
tree, so ruff validates and formats them in single invocations. Every
temporary file maps back through the returned origin dictionary.
"""

from __future__ import annotations

import ast
from doctest import DocTestParser
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, u

if TYPE_CHECKING:
    from flext_infra import t


def is_syntax_broken(code: str, origin: Path) -> bool:
    """True when one embedded source does not compile (documentation fragment)."""
    try:
        compile(code, str(origin), "exec")
    except SyntaxError:
        return True
    return False


def source_name(relative_posix: str, index: int) -> str:
    """Encode one block's documentation location into a temp source filename."""
    return c.Infra.MARKDOWN_CODE_SOURCE_FORMAT.format(
        relative_posix.replace("/", "__").replace(".", "_"), index
    )


def write_fenced_block_sources(
    project_dir: Path, markdown_files: t.SequenceOf[Path], target_dir: Path
) -> dict[str, t.Pair[str, int]]:
    """Write one temp source per parseable fenced ``python`` block.

    Blocks carrying the ``notest`` fence marker are skipped (opted out of
    code validation by declaration). Every other block must compile: an
    unparseable block in a python fence is a documentation defect and its
    ``SyntaxError`` escapes unchanged.
    """
    origin_by_source: dict[str, t.Pair[str, int]] = {}
    for md_path in markdown_files:
        relative_posix = md_path.relative_to(project_dir).as_posix()
        content = md_path.read_text(c.Cli.ENCODING_DEFAULT)
        for index, match in enumerate(
            match
            for match in c.Infra.MARKDOWN_PY_FENCE_RE.finditer(content)
            if c.Infra.MARKDOWN_CODE_SKIP_MARKER not in match.group("info")
        ):
            source_text = match.group("code")
            # A python fence that cannot compile is a documentation fragment,
            # not a formatting subject: its syntax findings belong to the
            # flext-tests markdown validator (MD-001 with approved
            # exceptions), and the ``notest`` marker is the declared way to
            # keep a deliberate non-Python snippet out of every probe. The
            # fragment keeps its enumeration slot so a later parseable block
            # never shifts its source name.
            if is_syntax_broken(source_text, md_path):
                continue
            name = source_name(relative_posix, index)
            (target_dir / name).write_text(source_text, c.Cli.ENCODING_DEFAULT)
            origin_by_source[name] = (
                relative_posix,
                content[: match.start()].count("\n") + 1,
            )
    return origin_by_source


def write_docstring_sources(
    project_dir: Path, target_dir: Path
) -> dict[str, t.Pair[str, int]]:
    """Write one temp source per doctest example found in tracked docstrings.

    Docstring write-back stays outside the fix contract on purpose: a
    formatter rewrite inside prose is a semantics risk, so docstring findings
    remain manual repairs. Example line numbers are approximate within the
    docstring (stdlib ``doctest`` reports positions relative to its input).
    """
    origin_by_source: dict[str, t.Pair[str, int]] = {}
    parser = DocTestParser()
    for py_path in u.Infra.iter_matching_files(project_dir, includes=["*.py"]):
        relative_parts = py_path.relative_to(project_dir).parts
        if any(part in c.Infra.CHECK_EXCLUDED_DIRS for part in relative_parts):
            continue
        tree = ast.parse(py_path.read_text(c.Cli.ENCODING_DEFAULT))
        for node in ast.walk(tree):
            # Only these carry docstrings; ast.walk also yields expression
            # nodes and ast.get_docstring raises TypeError on those.
            if not isinstance(
                node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
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
                name = source_name(relative_posix, index)
                (target_dir / name).write_text(source_text, c.Cli.ENCODING_DEFAULT)
                origin_by_source[name] = (relative_posix, body_start + example.lineno)
    return origin_by_source


__all__: list[str] = [
    "is_syntax_broken",
    "source_name",
    "write_docstring_sources",
    "write_fenced_block_sources",
]
