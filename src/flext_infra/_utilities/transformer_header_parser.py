"""Fail-fast structural parsing for Python module headers."""

from __future__ import annotations

import io
import token
import tokenize
from typing import TYPE_CHECKING

from flext_infra import c, m

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesTransformerHeaderParser:
    """Parse module-header boundaries without normalizing tokenizer failures."""

    @classmethod
    def _parse_header(cls, source: str) -> m.Infra.HeaderInfo:
        """Parse a module header and let the first tokenizer exception escape."""
        tokens = tuple(tokenize.tokenize(io.BytesIO(source.encode()).readline))
        span = m.Infra.HeaderSpan(shebang_end=cls._shebang_end(source))
        span.encoding_end = cls._encoding_end(source, span.shebang_end)
        span.comments_end = cls._leading_comments_end(source, span.encoding_end)
        aliases: set[str] = set()
        has_future_annotations = False
        seen_non_header_token = False
        for index, current in enumerate(tokens):
            if current.type in {
                token.ENCODING,
                token.NL,
                token.NEWLINE,
                token.COMMENT,
                token.ENDMARKER,
            }:
                continue
            if (
                current.type == token.STRING
                and not seen_non_header_token
                and span.docstring_end == 0
            ):
                span.docstring_end = cls._line_end_offset(source, current.end)
                continue
            seen_non_header_token = True
            if current.type != token.NAME or current.string != "from":
                continue
            # Only a module-level import may move the header boundary. An import
            # nested in a suite — `if TYPE_CHECKING:` above all — is not the end
            # of the header, and treating it as one made callers splice a
            # column-zero statement into the middle of that block, producing an
            # unexpected indent and a file that no longer parses.
            if current.start[1] != 0:
                continue
            if index + 2 >= len(tokens):
                continue
            module_token = tokens[index + 1]
            import_token = tokens[index + 2]
            if (
                module_token.type != token.NAME
                or import_token.type != token.NAME
                or import_token.string != "import"
            ):
                continue
            span.last_import_end = max(
                span.last_import_end, cls._find_import_line_end(source, tokens, index)
            )
            imported_aliases = cls._extract_imported_aliases(tokens, index)
            if module_token.string == "__future__":
                has_future_annotations = "annotations" in imported_aliases
            else:
                aliases.update(imported_aliases)
        return m.Infra.HeaderInfo(
            has_future_annotations=has_future_annotations,
            aliases=frozenset(aliases),
            span=span,
        )

    @staticmethod
    def _shebang_end(source: str) -> int:
        """Return the offset after a shebang line."""
        if not source.startswith("#!"):
            return 0
        newline = source.find("\n")
        return len(source) if newline == -1 else newline + 1

    @staticmethod
    def _encoding_end(source: str, start: int) -> int:
        """Return the offset after an encoding cookie."""
        if start >= len(source):
            return start
        head = source[start:]
        if c.Infra.ENCODING_COOKIE_RE.match(head) is None:
            return start
        line_end = head.find("\n")
        return start + (len(head) if line_end == -1 else line_end + 1)

    @staticmethod
    def _leading_comments_end(source: str, start: int) -> int:
        """Return the offset after leading comments and their blank separator."""
        index = start
        saw_comment = False
        while index < len(source):
            line_end = source.find("\n", index)
            line = source[index:] if line_end == -1 else source[index:line_end]
            stripped = line.strip()
            if stripped.startswith("#"):
                saw_comment = True
            elif stripped or not saw_comment:
                break
            index = len(source) if line_end == -1 else line_end + 1
        return index

    @classmethod
    def _find_import_line_end(
        cls, source: str, tokens: t.SequenceOf[tokenize.TokenInfo], from_index: int
    ) -> int:
        """Return the offset after the selected import statement."""
        for current in tokens[from_index:]:
            if current.type in {token.NEWLINE, token.ENDMARKER}:
                return cls._position_offset(source, current.end)
        return 0

    @classmethod
    def _line_end_offset(cls, source: str, position: t.Pair[int, int]) -> int:
        """Return the offset after the line containing a token position."""
        offset = cls._position_offset(source, position)
        newline = source.find("\n", offset)
        return len(source) if newline == -1 else newline + 1

    @staticmethod
    def _position_offset(source: str, position: t.Pair[int, int]) -> int:
        """Convert a tokenizer line and column into a source offset."""
        line, column = position
        if line <= 1:
            return min(column, len(source))
        offset = 0
        for _line_number in range(1, line):
            newline = source.find("\n", offset)
            if newline == -1:
                return len(source)
            offset = newline + 1
        return min(offset + column, len(source))

    @staticmethod
    def _extract_imported_aliases(
        tokens: t.SequenceOf[tokenize.TokenInfo], from_index: int
    ) -> frozenset[str]:
        """Return local names bound by a from-import statement."""
        aliases: set[str] = set()
        index = from_index + 3
        while index < len(tokens):
            current = tokens[index]
            if current.type in {token.NEWLINE, token.ENDMARKER}:
                break
            if current.type == token.NAME:
                alias = current.string
                if (
                    index + 2 < len(tokens)
                    and tokens[index + 1].type == token.NAME
                    and tokens[index + 1].string == "as"
                ):
                    alias = tokens[index + 2].string
                    index += 2
                aliases.add(alias)
            index += 1
        return frozenset(aliases)


__all__: list[str] = ["FlextInfraUtilitiesTransformerHeaderParser"]
