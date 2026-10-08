"""Source-level Rope rewrite helpers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import textwrap
from operator import itemgetter
from pathlib import Path

from flext_infra import c, t
from flext_infra._utilities import (
    FlextInfraUtilitiesDiscovery,
    FlextInfraUtilitiesRopeRuntime,
)


class FlextInfraUtilitiesRopeSource:
    """Text-oriented helpers shared by Rope-backed refactors."""

    @staticmethod
    def discover_first_party_namespaces(project_dir: Path) -> t.StrSequence:
        """Discover live regular, namespace, and stub packages under ``src/``.

        Returns:
            The resulting ``t.StrSequence``.

        """
        src_dir = project_dir / c.Infra.DEFAULT_SRC_DIR
        return [
            name
            for name in FlextInfraUtilitiesDiscovery.discover_python_dirs(
                src_dir,
                workspace_excluded_top_dirs=frozenset(),
            )
            if name.isidentifier()
        ]

    @staticmethod
    def find_import_insert_position(
        lines: t.StrSequence,
        *,
        past_existing: bool = True,
    ) -> int:
        """Return the module-level line index where an import may be inserted.

        The position is derived from parsed statements rather than scanned
        lines. A line scan cannot see that a match belongs to a continuation or
        to an indented suite, so it returned positions inside a parenthesized
        import list and inside ``if TYPE_CHECKING:``; inserting a column-zero
        statement at either point produced a file that no longer parses.

        Only top-level imports move the position. ``past_existing`` places it
        after the last of them; otherwise it lands after the module docstring
        and the ``__future__`` imports, before the first regular import.

        A module whose first statement is neither a docstring nor an import
        pins the position just above that statement: returning 0 would insert
        above comment-only header lines (shebang, encoding) and corrupt them.

        ``lines`` may or may not carry trailing newlines (callers feed both
        ``splitlines()`` and ``splitlines(keepends=True)``), so separators are
        normalized here: a ``"".join`` collapse would hand ``ast.parse`` one
        broken line.

        Returns:
            The module-level line index where an import may be inserted.

        """
        source = "\n".join(line.removesuffix("\n") for line in lines)
        module = ast.parse(source)
        position = 0
        for statement in module.body:
            if isinstance(statement, ast.Expr) and isinstance(
                statement.value,
                ast.Constant,
            ):
                if isinstance(statement.value.value, str) and position == 0:
                    position = statement.end_lineno or position
                    continue
                break
            if (
                isinstance(statement, ast.ImportFrom)
                and statement.module == "__future__"
            ):
                position = statement.end_lineno or position
                continue
            if past_existing and isinstance(statement, ast.Import | ast.ImportFrom):
                position = statement.end_lineno or position
                continue
            if position == 0 and statement.lineno:
                position = statement.lineno - 1
            break
        return position

    @staticmethod
    def index_after_docstring_and_future_imports(lines: t.StrSequence) -> int:
        """Return insertion index after module docstring and future imports.

        Returns:
            Insertion index after module docstring and future imports.

        """
        return FlextInfraUtilitiesRopeSource.find_import_insert_position(
            lines,
            past_existing=False,
        )

    @staticmethod
    def parse_import_names(names_str: str) -> t.StrPairSequence:
        """Parse ``A, B as C`` into ``[(name, bound), ...]``.

        Returns:
            The resulting ``t.StrPairSequence``.

        """
        result: t.MutableSequenceOf[t.StrPair] = []
        for part in names_str.split(","):
            candidate = part.strip().rstrip("\\").strip()
            if not candidate or candidate.startswith(("(", ")")):
                continue
            if " as " in candidate:
                name, alias = candidate.split(" as ", 1)
                result.append((name.strip(), alias.strip()))
                continue
            result.append((candidate, candidate))
        return result

    @classmethod
    def hoist_inline_imports(
        cls,
        file_path: Path,
        statement_lines: t.SequenceOf[t.IntPair],
    ) -> bool:
        """Move function-local import statements to the module import block.

        ``statement_lines`` holds the 1-based inclusive line span of each
        import statement a rule found. The statements are removed from their
        function bodies and their dedented text is added once after the
        module's last top-level import. A body left empty, or a result that no
        longer parses, raises: the move is never half-applied.

        Returns:
            The resulting ``bool``.

        """
        if not statement_lines:
            return False
        source = file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        lines = source.splitlines(keepends=True)
        hoisted: list[str] = []
        drop: set[int] = set()
        for start, end in statement_lines:
            text = textwrap.dedent("".join(lines[start - 1 : end])).strip()
            if text not in hoisted:
                hoisted.append(text)
            drop.update(range(start, end + 1))
        kept = [line for index, line in enumerate(lines, start=1) if index not in drop]
        position = cls.find_import_insert_position(kept)
        present = {line.strip() for line in kept[:position]}
        block = [f"{text}\n" for text in hoisted if text not in present]
        updated = "".join([*kept[:position], *block, *kept[position:]])
        ast.parse(updated, filename=str(file_path))
        file_path.write_text(updated, encoding=c.Cli.ENCODING_DEFAULT)
        return True

    @staticmethod
    def statements_at_module_end(
        source: str,
        statement_lines: t.SequenceOf[t.IntPair],
        *,
        filename: str,
    ) -> str:
        """Return ``source`` with top-level statements moved after its last one.

        ``statement_lines`` holds the 1-based inclusive line span of each
        top-level statement to move. The statements keep their text and
        relative order and close the module, separated from what precedes them
        by the blank lines PEP 8 asks for: two after a class or function, one
        otherwise. A result that no longer parses raises.

        Returns:
            The rewritten source; ``source`` itself when nothing moves.

        """
        if not statement_lines:
            return source
        lines = source.splitlines(keepends=True)
        drop = {
            index for start, end in statement_lines for index in range(start, end + 1)
        }
        moved = "".join(
            "".join(lines[start - 1 : end]).rstrip() + "\n"
            for start, end in sorted(statement_lines)
        )
        kept = "".join(
            line for index, line in enumerate(lines, start=1) if index not in drop
        ).rstrip()
        body = ast.parse(kept, filename=filename).body
        closes_definition = bool(body) and isinstance(
            body[-1],
            ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        )
        separator = "\n\n\n" if closes_definition else "\n\n"
        updated = f"{kept}{separator}{moved}" if kept else moved
        ast.parse(updated, filename=filename)
        return updated

    @staticmethod
    def rewrite_source_at_offsets(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeFile,
        changes: t.SequenceOf[t.Triple[int, int, str]],
        *,
        apply: bool = True,
    ) -> str:
        """Apply offset-based edits (start, end, replacement) to source.

        Returns:
            The resulting ``str``.

        Raises:
            TypeError: If the resource is not a Rope file resource.

        """
        _ = rope_project
        if not FlextInfraUtilitiesRopeRuntime.file_resource(resource):
            msg = f"expected a Rope file resource: {resource.path}"
            raise TypeError(msg)
        source: str = resource.read()
        for start, end, replacement in sorted(changes, key=itemgetter(0), reverse=True):
            source = source[:start] + replacement + source[end:]
        if apply and source != resource.read():
            resource.write(source)
        return source


__all__: list[str] = ["FlextInfraUtilitiesRopeSource"]
