"""Line-length repair for the lines Ruff format cannot wrap.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import io
import textwrap
import tokenize
from collections.abc import MutableMapping
from itertools import pairwise

from flext_infra import m, t


class FlextInfraUtilitiesLineWrap:
    """Wrap long string literals and comments without changing the module AST.

    Ruff format wraps expressions but never splits a string literal or a
    comment. A long single-line string literal is split after spaces into
    implicit concatenation, inside its enclosing brackets or inside new
    parentheses; a long full-line comment is reflowed at the same indent. The
    parser folds implicit concatenation and drops comments, so the repaired
    module's AST must equal the original one, and a difference raises. A line
    holding neither keeps its text and its finding.
    """

    @classmethod
    def wrap_long_lines(
        cls,
        source: str,
        line_numbers: t.SequenceOf[int],
        *,
        limit: int,
    ) -> str:
        """Return ``source`` with every wrappable long line wrapped.

        Returns:
            The repaired source.

        Raises:
            ValueError: If a repair would change the module AST.

        """
        before = ast.dump(ast.parse(source))
        lines = source.splitlines(keepends=True)
        tokens = tuple(tokenize.generate_tokens(io.StringIO(source).readline))
        for number in sorted(set(line_numbers), reverse=True):
            line = lines[number - 1]
            if len(line.rstrip("\r\n")) <= limit:
                continue
            replacement = cls._wrapped_comment(
                line,
                number,
                tokens,
                limit,
            ) or cls._wrapped_literal(line, number, tokens, limit)
            if replacement is not None:
                lines[number - 1] = replacement
        repaired = "".join(lines)
        if ast.dump(ast.parse(repaired)) != before:
            msg = "line wrap changed the module AST"
            raise ValueError(msg)
        return repaired

    @staticmethod
    def _wrapped_comment(
        line: str,
        number: int,
        tokens: t.SequenceOf[tokenize.TokenInfo],
        limit: int,
    ) -> str | None:
        """Reflow one full-line comment into lines within the limit.

        Returns:
            The reflowed comment lines, or ``None`` when the line is no
            full-line comment or one of its words alone exceeds the limit.

        """
        comment = next(
            (
                token
                for token in tokens
                if token.start[0] == number and token.type == tokenize.COMMENT
            ),
            None,
        )
        indent = line[: len(line) - len(line.lstrip())]
        if comment is None or comment.start[1] != len(indent):
            return None
        prefix = f"{indent}{comment.string[:1]} "
        wrapped = textwrap.wrap(
            comment.string[1:].strip(),
            width=limit - len(prefix),
            break_long_words=False,
            break_on_hyphens=False,
        )
        if len(wrapped) <= 1 or any(
            len(prefix) + len(part) > limit for part in wrapped
        ):
            return None
        newline = line[len(line.rstrip("\r\n")) :]
        return "".join(f"{prefix}{part}{newline}" for part in wrapped)

    @classmethod
    def _wrapped_literal(
        cls,
        line: str,
        number: int,
        tokens: t.SequenceOf[tokenize.TokenInfo],
        limit: int,
    ) -> str | None:
        """Split the longest splittable single-line string literal of one line.

        Returns:
            The line with its literal split, or ``None`` when no literal on the
            line can be split within the limit.

        """
        literals = sorted(
            cls._literals(tokens, number),
            key=lambda literal: literal.end - literal.start,
            reverse=True,
        )
        for literal in literals:
            text = line[literal.start : literal.end]
            column = literal.start if literal.bracketed else literal.start + 1
            cuts = cls._cuts(text, literal, column, limit)
            if not cuts:
                continue
            pieces = cls._pieces(text, literal, cuts)
            joined = f"\n{' ' * column}".join(pieces)
            body = joined if literal.bracketed else f"({joined})"
            return f"{line[: literal.start]}{body}{line[literal.end :]}"
        return None

    @staticmethod
    def _cuts(
        text: str,
        literal: m.Infra.LineWrapLiteral,
        column: int,
        limit: int,
    ) -> t.SequenceOf[int]:
        """Pick split offsets after spaces so every piece fits the limit.

        A split never lands inside an escape sequence or an f-string
        replacement field.

        Returns:
            The split offsets, or an empty sequence when the literal cannot fit.

        """
        opening = len(literal.prefix) + len(literal.quote)
        closing = len(literal.quote)
        safe: list[int] = []
        braces = 0
        escaped = False
        for index in range(opening, len(text) - closing):
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "{":
                braces += 1
            elif char == "}":
                braces = max(braces - 1, 0)
            elif char == " " and not braces:
                safe.append(index + 1)
        cuts: list[int] = []
        anchor = 0
        while column + (opening if cuts else 0) + len(text) - anchor > limit:
            reopen = opening if cuts else 0
            fitting = [
                cut
                for cut in safe
                if cut > anchor and column + reopen + cut - anchor + closing <= limit
            ]
            if not fitting:
                return ()
            anchor = fitting[-1]
            cuts.append(anchor)
        return tuple(cuts)

    @staticmethod
    def _pieces(
        text: str,
        literal: m.Infra.LineWrapLiteral,
        cuts: t.SequenceOf[int],
    ) -> t.StrSequence:
        """Split one literal at the given offsets into closed literals.

        Returns:
            The literal pieces, each with its own prefix and quotes.

        """
        reopen = f"{literal.prefix}{literal.quote}"
        bounds = (0, *cuts, len(text))
        return tuple(
            (reopen if index else "")
            + text[start:end]
            + (literal.quote if index < len(bounds) - 2 else "")
            for index, (start, end) in enumerate(pairwise(bounds))
        )

    @classmethod
    def _literals(
        cls,
        tokens: t.SequenceOf[tokenize.TokenInfo],
        number: int,
    ) -> t.SequenceOf[m.Infra.LineWrapLiteral]:
        """Return each single-quoted single-line string literal of one line.

        Returns:
            The literals of the line with their bracket context.

        """
        depths = cls._bracket_depths(tokens, number)
        literals: list[m.Infra.LineWrapLiteral] = []
        for start, end, head in cls._literal_spans(tokens, number):
            body = head.lstrip("rRbBuUfFtT")
            quote = body[:1]
            if body[:3] == quote * 3:
                continue
            literals.append(
                m.Infra.LineWrapLiteral(
                    start=start,
                    end=end,
                    prefix=head[: len(head) - len(body)],
                    quote=quote,
                    bracketed=depths.get(start, 0) > 0,
                ),
            )
        return tuple(literals)

    @staticmethod
    def _bracket_depths(
        tokens: t.SequenceOf[tokenize.TokenInfo],
        number: int,
    ) -> t.MappingKV[int, int]:
        """Map each token column of one line to its bracket nesting depth.

        Returns:
            Column to bracket depth for every token starting on the line.

        """
        depth = 0
        depths: MutableMapping[int, int] = {}
        for token in tokens:
            if token.start[0] > number:
                break
            if token.start[0] == number:
                depths.setdefault(token.start[1], depth)
            if token.type == tokenize.OP and token.string in {"(", "[", "{"}:
                depth += 1
            elif token.type == tokenize.OP and token.string in {")", "]", "}"}:
                depth -= 1
        return depths

    @staticmethod
    def _literal_spans(
        tokens: t.SequenceOf[tokenize.TokenInfo],
        number: int,
    ) -> t.SequenceOf[t.Triple[int, int, str]]:
        """Return the column span and opening text of each literal on one line.

        Returns:
            ``(start, end, opening)`` per plain or f-string literal of the line.

        """
        spans: list[t.Triple[int, int, str]] = []
        opened: tokenize.TokenInfo | None = None
        for token in tokens:
            if token.type == tokenize.FSTRING_START:
                opened = token
            elif token.type == tokenize.FSTRING_END and opened is not None:
                if opened.start[0] == token.end[0] == number:
                    spans.append((opened.start[1], token.end[1], opened.string))
                opened = None
            elif (
                opened is None
                and token.type == tokenize.STRING
                and token.start[0] == token.end[0] == number
            ):
                spans.append((token.start[1], token.end[1], token.string))
        return tuple(spans)


__all__: list[str] = ["FlextInfraUtilitiesLineWrap"]
