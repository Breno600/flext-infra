"""Centralized constants for the docs subpackage."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsDocs:
    """Docs infrastructure constants."""

    DEFAULT_DOCS_OUTPUT_DIR: ClassVar[str] = ".reports/docs"
    # Registered docs CLI action names; make.docs.actions must stay inside this
    # surface so the generated Makefile loop can never dispatch a missing verb.
    DOCS_ACTION_IDS: ClassVar[frozenset[str]] = frozenset({
        "audit",
        "build",
        "collect",
        "fix",
        "fmt",
        "generate",
        "serve",
        "validate",
    })
    DOCS_CONFIG_FILENAME: ClassVar[str] = "docs_config.json"
    # Prettier --write lists every processed file as "<path> <duration>ms";
    # the fmt phase report surfaces exactly that surface per scope.
    DOCS_PRETTIER_WRITE_LINE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<file>\S+)\s+\d+(?:\.\d+)?ms$"
    )
    DOCS_INSECURE_WEB_SCHEME: ClassVar[str] = "http"
    DOCS_SECURE_WEB_SCHEME: ClassVar[str] = "https"
    # A generated document may point outward, never carry a payload: a `data:`
    # target embeds its content in the link and can execute in a rendered page,
    # which is why the sanitizer has always stripped it. Declaring it here as a
    # preserved scheme made the catalog disagree with the only consumer.
    DOCS_EXTERNAL_SCHEMES: ClassVar[frozenset[str]] = frozenset({
        DOCS_SECURE_WEB_SCHEME,
        "mailto",
        "tel",
    })
    DOCS_FRAGMENT_PREFIX: ClassVar[str] = "#"
    PYTHON_FENCE_RUFF_EXTEND_IGNORE: ClassVar[t.StrSequence] = (
        "D100",
        "D101",
        "D102",
        "D103",
        "PLR2004",
        "S101",
        "INP001",
        "T201",
        "T203",
        "ANN001",
        "ANN002",
        "ANN003",
        "ANN201",
        "ANN202",
        "ANN204",
        "ANN205",
        "PLC0415",
    )
    """Rules ignored for executable docs snippets that are not full modules/tests."""
    MACHINE_PATH_RE: ClassVar[t.RegexPattern] = re.compile(
        r"(?<![\w./-])/(?:home|Users)/(?P<user>[A-Za-z0-9_.-]+)(?=/|\b)"
    )
    """Regex matching a per-user absolute root (``/home/<user>``, ``/Users/<user>``)."""
    MACHINE_PATH_CONTAINER_USERS: ClassVar[t.StrSequence] = (
        "runner",
        "vscode",
        "agent",
        "barman",
        "scanner",
        "argocd",
    )
    """Container/CI identities whose home is part of the image contract, not a machine.

    ``argocd`` is the in-container HOME of the Argo CD side images
    (argocd-cmp-plugin / repo-server) referenced in ADR_024 and the release
    convergence plan; it is an image contract, not an operator machine
    (flext-9v0d.3 / cosmos-iracn.7)."""
    PYTHON_FENCE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^```python\s*\n(?P<body>.*?)^```\s*$", re.MULTILINE | re.DOTALL
    )
    """Regex matching ``python`` fenced blocks; ``body`` group yields contents."""

    PYTHON_FENCE_FIX_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<indent>[ \t]*)(?P<open>```python[ \t]*\n)(?P<body>.*?)^```[ \t]*$",
        re.MULTILINE | re.DOTALL,
    )
    """Regex matching ``python`` fenced blocks for fix-in-place replacement."""

    WELDED_FENCE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<indent>[ \t]*)(?P<body>.*[^\s`])```[ \t]*$", re.MULTILINE
    )
    """Match a closing fence welded to the final code line by an older fixer.

    The body must end in a non-whitespace, non-backtick character so that a
    legitimately indented closing fence (``   ``` ``) and an existing
    four-backtick fence are never rewritten; only a code line with the fence
    welded onto it matches, and its indentation is preserved on repair.
    """

    FENCE_NOTEST_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^```(\S+)\s+notest\s*$", re.MULTILINE
    )
    """Regex matching fenced code blocks with a ``notest`` info qualifier."""

    FENCE_NOTEST_ATTR_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^```([A-Za-z0-9_+-]+)\s+notest\s*$", re.MULTILINE
    )
    """Regex matching a bare ``notest`` qualifier for the buildable rewrite.

    ``pymdownx.superfences`` rejects an info string whose second token is not a
    known option, so a bare ``python notest`` fence is not rendered as code and
    its contents leak into the page as prose, swallowing the headings that
    follow. The fix phase rewrites it to the ``attr_list`` form
    ``{.python .notest}``, which superfences renders and whose info string still
    carries the marker the code gates skip. The language token excludes ``{``
    so an already-rewritten fence never matches again.
    """

    MANUAL_TOC_RE: ClassVar[t.RegexPattern] = re.compile(
        r"<!--\s*TOC\s+START\s*-->.*?<!--\s*TOC\s+END\s*-->", re.DOTALL
    )
    """Regex matching a manually inserted table-of-contents block."""

    FENCED_BLOCK_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<fence>```+|~~~+)[^\n]*\n.*?^(?P=fence)[ \t]*$\n?",
        re.MULTILINE | re.DOTALL,
    )
    """Match a whole fenced code block, backtick or tilde, with its info string."""

    # --- Markdown link/heading patterns ---
    MARKDOWN_LINK_RE: ClassVar[t.RegexPattern] = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    """Match markdown links capturing text (group 1) and URL (group 2)."""
    MARKDOWN_LINK_URL_RE: ClassVar[t.RegexPattern] = re.compile(
        r"\[[^\]]+\]\(([^)]+)\)"
    )
    """Match markdown links capturing only the URL (group 1)."""
    HEADING_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE
    )
    """Match any markdown heading (h1-h6), capturing the text."""
    HEADING_H2_H3_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(##|###)\s+(.+?)\s*$", re.MULTILINE
    )
    """Match h2/h3 headings, capturing level (group 1) and text (group 2)."""
    ANCHOR_LINK_RE: ClassVar[t.RegexPattern] = re.compile(r"\[([^\]]+)\]\(#([^)]+)\)")
    """Match internal anchor links, capturing text and anchor."""
    INLINE_CODE_RE: ClassVar[t.RegexPattern] = re.compile(r"`[^`]*`")
    """Match inline code spans for stripping before analysis."""
    STRING_LITERAL_RE: ClassVar[t.RegexPattern] = re.compile(
        r"""["']([a-zA-Z0-9_\.]+)["']"""
    )
    """Match quoted string literals, capturing the content."""

    DOCS_MAKE_COMMAND_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*(?:\$\s*)?make\s+(?P<verb>[a-z][a-z0-9_-]*)(?P<args>.*)$", re.IGNORECASE
    )
    """Match an executable Make command and capture its verb and arguments."""
    DOCS_SHELL_FENCE_LANGUAGES: ClassVar[frozenset[str]] = frozenset({
        "",
        "bash",
        "console",
        "fish",
        "sh",
        "shell",
        "zsh",
    })
    """Markdown fence languages whose lines are executable shell commands."""
    DOCS_FORBIDDEN_MAKE_SELECTOR_RE: ClassVar[t.RegexPattern] = re.compile(
        r"\b(?:PROJECTS?|MATCH|WHAT|FILES?|FIX|CHANGED_ONLY|CHECK_GATES|"
        r"DOCS_PHASE|VALIDATE_SCOPE)\s*=",
        re.IGNORECASE,
    )
    """Match selectors outside the canonical root Make grammar."""
    DOCS_APPLY_RE: ClassVar[t.RegexPattern] = re.compile(r"\bAPPLY\s*=")
    """Reject the removed mutation selector for every supplied value."""
    DOCS_COMMAND_CONTRACT_DIRNAMES: ClassVar[frozenset[str]] = frozenset({
        "guides",
        "standards",
    })
    """Live documentation trees governed by the command contract."""
    DOCS_RAW_PYTEST_COMMAND_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*(?:\$\s*)?(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S+)\s+)*"
        r"(?:(?:uv|poetry|pdm)\s+run\s+|"
        r"python(?:3(?:\.\d+)?)?\s+-m\s+)?pytest(?:\s|$)",
        re.IGNORECASE,
    )
    """Match direct pytest execution that bypasses the root Testmon verb."""
    DOCS_RAW_TOOL_COMMAND_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*(?:\$\s*)?(?:(?:[A-Za-z_][A-Za-z0-9_]*=\S+)\s+)*"
        r"(?:(?:ruff|pyrefly|mypy|pyright|mkdocs|uv|poetry|pdm|tox|nox|pre-commit)(?=\s|$)|"
        r"python(?:3(?:\.\d+)?)?(?:\s+-m|\s+[^\s]+\.py\b))",
        re.IGNORECASE,
    )
    """Match tool and script commands that bypass the root Make dispatcher."""
    ISO_DATE_STRING_LENGTH: ClassVar[int] = 10
    """Length of an ISO date string ``YYYY-MM-DD``."""
    DOCS_TEST_DOUBLE_CODE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"(?:from\s+unittest(?:\.mock)?\s+import|import\s+unittest\.mock|"
        r"(?:^|\W)(?:MagicMock|Mock|patch)\s*\(|mock\.patch\s*\(|"
        r"monkeypatch\.[A-Za-z_]|class\s+(?:Fake|Stub)[A-Za-z0-9_]*|"
        r"(?:^|\W)(?:fake|stub)_[A-Za-z0-9_]+)",
        re.IGNORECASE,
    )
    """Match test-double construction inside executable Python examples."""
    DOCS_TEST_DOUBLE_HEADING_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*#{1,6}\s+.*\b(?:mock(?:ing|s)?|fake(?:s)?|stub(?:bing|s)?|"
        r"patch(?:ing)?)\b",
        re.IGNORECASE,
    )
    """Match headings that introduce test-double guidance."""


__all__: list[str] = ["FlextInfraConstantsDocs"]
