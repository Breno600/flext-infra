"""Tests for flext_infra.patterns — tooling and markdown regex patterns."""

from __future__ import annotations

from flext_tests import tm

from tests import c


class TestsFlextInfraInfraPatternsCore:
    """Tests for tooling-related regex patterns."""

    def test_mypy_hint_pattern_matches_valid_hint(self) -> None:
        text = 'note: Hint: "python3 -m pip install types-requests"'
        match = c.Infra.MYPY_HINT_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="types-requests")

    def test_mypy_hint_pattern_captures_package_name(self) -> None:
        text = 'note: Hint: "python3 -m pip install mypy-extensions"'
        match = c.Infra.MYPY_HINT_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="mypy-extensions")

    def test_mypy_hint_pattern_matches_stub_package_wording(self) -> None:
        text = "note: hint: install stub package `types-requests`"
        match = c.Infra.MYPY_HINT_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="types-requests")

    def test_mypy_hint_pattern_no_match_without_hint(self) -> None:
        text = "some other mypy output"
        match = c.Infra.MYPY_HINT_RE.search(text)
        tm.that(match, none=True)

    def test_mypy_stub_pattern_matches_missing_stubs(self) -> None:
        text = 'Library stubs not installed for "requests"'
        match = c.Infra.MYPY_STUB_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="requests")

    def test_mypy_stub_pattern_captures_library_name(self) -> None:
        text = 'Library stubs not installed for "django"'
        match = c.Infra.MYPY_STUB_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="django")

    def test_mypy_stub_pattern_no_match_without_message(self) -> None:
        text = "stubs are installed"
        match = c.Infra.MYPY_STUB_RE.search(text)
        tm.that(match, none=True)

    def test_internal_prefixes_contains_flext(self) -> None:
        tm.that(c.Infra.INTERNAL_PREFIXES, has="flext_")

    def test_internal_prefixes_is_tuple(self) -> None:
        tm.that(c.Infra.INTERNAL_PREFIXES, is_=tuple)

    def test_markdown_link_pattern_matches_link(self) -> None:
        text = "[Click here](https://example.com)"
        match = c.Infra.MARKDOWN_LINK_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="Click here")
        tm.that(match.group(2), eq="https://example.com")

    def test_markdown_link_pattern_captures_text_and_url(self) -> None:
        text = "[Documentation](./docs/README.md)"
        match = c.Infra.MARKDOWN_LINK_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="Documentation")
        tm.that(match.group(2), eq="./docs/README.md")

    def test_markdown_link_pattern_multiple_matches(self) -> None:
        text = "[Link1](url1) and [Link2](url2)"
        matches = c.Infra.MARKDOWN_LINK_RE.findall(text)
        tm.that(len(matches), eq=2)
        tm.that(matches[0], eq=("Link1", "url1"))
        tm.that(matches[1], eq=("Link2", "url2"))

    def test_markdown_link_url_pattern_captures_url_only(self) -> None:
        text = "[Click here](https://example.com)"
        match = c.Infra.MARKDOWN_LINK_URL_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="https://example.com")

    def test_markdown_link_url_pattern_ignores_text(self) -> None:
        text = "[Some text](path/to/file.md)"
        match = c.Infra.MARKDOWN_LINK_URL_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="path/to/file.md")

    def test_heading_pattern_matches_h1(self) -> None:
        text = "# Main Title"
        match = c.Infra.HEADING_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="Main Title")

    def test_heading_pattern_matches_h6(self) -> None:
        text = "###### Small Heading"
        match = c.Infra.HEADING_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="Small Heading")

    def test_heading_pattern_multiline(self) -> None:
        text = "# Title 1\nSome content\n## Title 2"
        matches = c.Infra.HEADING_RE.findall(text)
        tm.that(len(matches), eq=2)
        tm.that(matches, has="Title 1")
        tm.that(matches, has="Title 2")

    def test_heading_h2_h3_pattern_matches_h2(self) -> None:
        text = "## Section Title"
        match = c.Infra.HEADING_H2_H3_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="##")
        tm.that(match.group(2), eq="Section Title")

    def test_heading_h2_h3_pattern_matches_h3(self) -> None:
        text = "### Subsection"
        match = c.Infra.HEADING_H2_H3_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="###")
        tm.that(match.group(2), eq="Subsection")

    def test_heading_h2_h3_pattern_ignores_h1(self) -> None:
        text = "# Title"
        match = c.Infra.HEADING_H2_H3_RE.search(text)
        tm.that(match, none=True)

    def test_heading_h2_h3_pattern_ignores_h4(self) -> None:
        text = "#### Deep Heading"
        match = c.Infra.HEADING_H2_H3_RE.search(text)
        tm.that(match, none=True)

    def test_anchor_link_pattern_matches_anchor(self) -> None:
        text = "[Go to section](#section-name)"
        match = c.Infra.ANCHOR_LINK_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="Go to section")
        tm.that(match.group(2), eq="section-name")

    def test_anchor_link_pattern_captures_text_and_anchor(self) -> None:
        text = "[Back to top](#top)"
        match = c.Infra.ANCHOR_LINK_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(1), eq="Back to top")
        tm.that(match.group(2), eq="top")

    def test_inline_code_pattern_matches_backticks(self) -> None:
        text = "Use `function_name()` in your code"
        match = c.Infra.INLINE_CODE_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(0), eq="`function_name()`")

    def test_inline_code_pattern_multiple_matches(self) -> None:
        text = "Use `foo()` and `bar()` together"
        matches = c.Infra.INLINE_CODE_RE.findall(text)
        tm.that(len(matches), eq=2)
        tm.that(matches, has="`foo()`")
        tm.that(matches, has="`bar()`")

    def test_inline_code_pattern_empty_code(self) -> None:
        text = "Empty code: ``"
        match = c.Infra.INLINE_CODE_RE.search(text)
        match = tm.not_none(match)
        tm.that(match.group(0), eq="``")

    def test_make_assignment_matches_operators(self) -> None:
        for line in ("FOO = 1", "FOO:=1", "FOO ::= 1", "FOO ?= 1", "FOO += 1"):
            tm.not_none(c.Infra.MAKE_ASSIGNMENT_RE.match(line))
        tm.that(c.Infra.MAKE_ASSIGNMENT_RE.match("\tFOO = 1"), none=True)
        tm.that(c.Infra.MAKE_ASSIGNMENT_RE.match("all:"), none=True)

    def test_make_directive_and_conditional_match(self) -> None:
        tm.not_none(c.Infra.MAKE_DIRECTIVE_RE.match("include shared.mk"))
        tm.not_none(c.Infra.MAKE_DIRECTIVE_RE.match("-include custom.mk"))
        tm.not_none(c.Infra.MAKE_DIRECTIVE_RE.match("export PATH"))
        tm.not_none(c.Infra.MAKE_CONDITIONAL_RE.match("ifeq ($(A),$(B))"))
        tm.not_none(c.Infra.MAKE_CONDITIONAL_RE.match("endif"))
        tm.that(c.Infra.MAKE_CONDITIONAL_RE.match("FOO = 1"), none=True)

    def test_gitmodule_section_and_path_match(self) -> None:
        section = '[submodule "flext-core"]\n\tpath = flext-core\n'
        section_match = tm.not_none(c.Infra.GITMODULE_SECTION_RE.search(section))
        tm.that(section_match.group(0), eq='[submodule "flext-core"]')
        path_match = tm.not_none(c.Infra.GITMODULE_PATH_RE.search(section))
        tm.that(path_match.group(1), eq="flext-core")
