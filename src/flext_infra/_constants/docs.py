"""Centralized constants for the docs subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Literal

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsDocs:
    """Docs infrastructure constants."""

    DEFAULT_DOCS_OUTPUT_DIR: ClassVar[str] = ".reports/docs"
    # MkDocs logs every strict-mode warning to this logger before it aborts
    # with only a count; the build captures it so a failure carries its cause.
    MKDOCS_LOGGER_NAME: ClassVar[str] = "mkdocs"
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
    # Structured docs reports: the only report files the audit and validate
    # phases publish, and the only ones generated CI dumps and uploads.
    DOCS_AUDIT_SUMMARY_FILENAME: ClassVar[str] = "audit-summary.json"
    DOCS_AUDIT_REPORT_FILENAME: ClassVar[str] = "audit-report.md"
    DOCS_VALIDATE_SUMMARY_FILENAME: ClassVar[str] = "validate-summary.json"
    DOCS_VALIDATE_REPORT_FILENAME: ClassVar[str] = "validate-report.md"
    DOCS_STRUCTURED_REPORT_FILENAMES: ClassVar[t.VariadicTuple[str]] = (
        DOCS_AUDIT_SUMMARY_FILENAME,
        DOCS_AUDIT_REPORT_FILENAME,
        DOCS_VALIDATE_SUMMARY_FILENAME,
        DOCS_VALIDATE_REPORT_FILENAME,
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
        "undocumented-public-module",
        "undocumented-public-function",
        "undocumented-public-class",
        "undocumented-public-method",
        "undocumented-public-init",
        "missing-copyright-notice",
        "implicit-namespace-package",
        "print",
        "assert",
        "boolean-positional-value-in-call",
        "no-self-use",
        "pytest-assert-in-except",
        "magic-value-comparison",
        "docstring-missing-returns",
        "docstring-missing-exception",
    )
    """Only module-header (docstring, copyright notice) and package rules are
    inapplicable to a standalone Markdown fence, which is not a module file;
    the pydocstyle public-surface family is inapplicable for the same reason
    (the surrounding prose is the fence's documentation), as is the
    docstring-completeness contract (example helpers keep their one-line
    docstrings; full Args/Returns sections are authored-source law),
    ``print`` is the fence demonstrating its output, ``assert`` and the
    pytest-idiom rules are the test-idiom contract of executable fences,
    which the pytest markdown-docs plugin runs as tests during ``make test``
    (the fleet's justified per-rule S101/PT test-idiom exception) — fences
    teaching exception semantics show real ``except`` blocks, the
    boolean-trap call-site rule is inapplicable because a fence must
    faithfully demonstrate the owning API's declared call signature;
    ``no-self-use`` is inapplicable for the same reason on adapter fences,
    where ``self`` is the port protocol's interface contract rather than an
    unused receiver, and magic-value-comparison is inapplicable because a
    fence's concrete
    literals are narrative data illustrating one scenario, never
    config-owned values. All names, behavior, types, and security rules
    remain active and require correction in the authored source."""
    MACHINE_PATH_RE: ClassVar[t.RegexPattern] = re.compile(
        r"(?<![\w./-])/(?:home|Users)/(?P<user>[A-Za-z0-9_.-]+)(?=/|\b)",
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
    convergence plan; it is an image contract, not an operator machine."""
    PYTHON_FENCE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^```python\s*\n(?P<body>.*?)^```\s*$",
        re.MULTILINE | re.DOTALL,
    )
    """Regex matching ``python`` fenced blocks; ``body`` group yields contents."""

    PYTHON_FENCE_FIX_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<indent>[ \t]*)(?P<open>```python[ \t]*\n)(?P<body>.*?)^```[ \t]*$",
        re.MULTILINE | re.DOTALL,
    )
    """Regex matching ``python`` fenced blocks for fix-in-place replacement."""

    WELDED_FENCE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<indent>[ \t]*)(?P<body>.*[^\s`])```[ \t]*$",
        re.MULTILINE,
    )
    """Match a closing fence welded to the final code line by an older fixer.

    The body must end in a non-whitespace, non-backtick character so that a
    legitimately indented closing fence (``   ``` ``) and an existing
    four-backtick fence are never rewritten; only a code line with the fence
    welded onto it matches, and its indentation is preserved on repair.
    """

    FENCE_NOTEST_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^```(\S+)\s+notest\s*$",
        re.MULTILINE,
    )
    """Regex matching fenced code blocks with a ``notest`` info qualifier."""

    FENCE_NOTEST_ATTR_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^```([A-Za-z0-9_+-]+)\s+notest\s*$",
        re.MULTILINE,
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

    # --- Markdown link/heading patterns ---
    MARKDOWN_LINK_RE: ClassVar[t.RegexPattern] = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    """Match markdown links capturing text (group 1) and URL (group 2)."""
    DOCS_GITHUB_BLOB_TREE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^https://github\.com/"
        r"(?P<org>[^/]+)/(?P<repo>[^/]+)/"
        r"(?P<kind>blob|tree)/"
        r"(?P<refpath>[^/?#]+/[^?#]*)"
        r"(?P<suffix>[?#].*)?$",
    )
    """Match a github.com blob/tree documentation URL by its named parts.

    ``refpath`` is the whole ``<ref>/<path>`` remainder: Git refs may contain
    ``/``, so the ref/path boundary is only decidable against the governed
    branch a consumer knows. ``suffix`` keeps a ``?query`` or ``#fragment``
    (for example ``#L10``) out of the filesystem path.
    """
    DOCS_ARTIFACT_MODE: ClassVar[Literal[0o644]] = 0o644
    """File mode every rendered documentation artifact is published with."""
    DOCS_OWNED_HEADER_LINES: ClassVar[int] = 2
    """Lines an owned member guide carries before its body: marker + source."""
    HEADING_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^#{1,6}\s+(.+?)\s*$",
        re.MULTILINE,
    )
    """Match any markdown heading (h1-h6), capturing the text."""
    INLINE_CODE_RE: ClassVar[t.RegexPattern] = re.compile(r"`[^`]*`")
    """Match inline code spans for stripping before analysis."""
    DOCS_INLINE_COMMAND_DIRECTIVE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"\b(?:run|execute|invoke|try|use)(?:\s+the\s+command)?\s*$",
        re.IGNORECASE,
    )
    """Recognize an instruction preceding a shell command in inline code."""
    STRING_LITERAL_RE: ClassVar[t.RegexPattern] = re.compile(
        r"""["']([a-zA-Z0-9_\.]+)["']""",
    )
    """Match quoted string literals, capturing the content."""

    DOCS_MAKE_COMMAND_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*(?:\$\s*)?make\s+(?P<verb>[a-z][a-z0-9_-]*)(?P<args>.*)$",
        re.IGNORECASE,
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
