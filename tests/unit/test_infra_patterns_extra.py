"""Tests for flext_infra.patterns — pattern types and edge cases."""

from __future__ import annotations

from flext_tests import tm

from tests import c


class TestsFlextInfraInfraPatternsExtra:
    """Tests for pattern type consistency."""

    def test_all_patterns_are_compiled_regex(self) -> None:
        pattern_type = type(c.Infra.MYPY_HINT_RE)
        patterns = [
            c.Infra.MYPY_HINT_RE,
            c.Infra.MYPY_STUB_RE,
            c.Infra.MARKDOWN_LINK_RE,
            c.Infra.MARKDOWN_LINK_URL_RE,
            c.Infra.HEADING_RE,
            c.Infra.HEADING_H2_H3_RE,
            c.Infra.ANCHOR_LINK_RE,
            c.Infra.INLINE_CODE_RE,
            c.Infra.MAKE_ASSIGNMENT_RE,
            c.Infra.MAKE_DIRECTIVE_RE,
            c.Infra.MAKE_CONDITIONAL_RE,
            c.Infra.GITMODULE_SECTION_RE,
            c.Infra.GITMODULE_PATH_RE,
        ]
        for pattern in patterns:
            tm.that(pattern, is_=pattern_type)

    def test_patterns_are_string_patterns(self) -> None:
        patterns = [
            c.Infra.MYPY_HINT_RE,
            c.Infra.MYPY_STUB_RE,
            c.Infra.MARKDOWN_LINK_RE,
        ]
        for pattern in patterns:
            tm.that(pattern.pattern, is_=str)

    def test_markdown_link_with_special_chars_in_url(self) -> None:
        text = "[Link](https://example.com/path?query=value&other=123)"
        match = c.Infra.MARKDOWN_LINK_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(2), has="query=value")

    def test_heading_with_trailing_whitespace(self) -> None:
        text = "## Title   "
        match = c.Infra.HEADING_H2_H3_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(2), eq="Title")

    def test_inline_code_with_special_chars(self) -> None:
        text = "Code: `foo_bar-baz.txt`"
        match = c.Infra.INLINE_CODE_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(0), has="foo_bar-baz.txt")

    def test_anchor_link_with_hyphens(self) -> None:
        text = "[Section](#my-section-name)"
        match = c.Infra.ANCHOR_LINK_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(2), eq="my-section-name")
