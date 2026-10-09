"""Centralized constants for the check subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from enum import StrEnum, unique
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsCheck:
    """Check infrastructure constants."""

    CHECK_FAIL_FAST_DEFAULT: ClassVar[bool] = False
    """Run every independent quality gate unless fail-fast is requested."""
    SERVICE_FAIL_FAST: ClassVar[bool] = True
    """Stop mutating service workflows at the first failed project or rule."""

    PYTEST_SELECTED_COLLECTION_OPTION: ClassVar[str] = "--flext-selected-collection"
    PYTEST_SUITE_STOP_OPTION: ClassVar[str] = "--flext-suite-stop-monotonic"
    PYTEST_COLLECTION_MANIFEST_OPTION: ClassVar[str] = "--flext-collection-manifest"
    PYTEST_PROFILE_LAUNCHER: ClassVar[str] = (
        "import cProfile, runpy, sys\n"
        "output = sys.argv.pop(1)\n"
        "profile = cProfile.Profile()\n"
        "try:\n"
        "    profile.runcall(\n"
        "        runpy.run_module, 'pytest', run_name='__main__', alter_sys=True\n"
        "    )\n"
        "finally:\n"
        "    profile.dump_stats(output)\n"
    )
    """``python -c`` profiled pytest child: ``<output.pstats> <pytest args...>``.

    Stdlib only, so pytest installs assertion rewriting before any plugin
    package (``flext_infra`` included) is imported; pytest's ``SystemExit``
    still sets the exit status, unlike ``python -m cProfile``.
    """

    @unique
    class SarifSchema(StrEnum):
        """Supported SARIF schema identities."""

        V2_1_0 = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/Schemata/sarif-schema-2.1.0.json"

    @unique
    class SarifVersion(StrEnum):
        """Supported SARIF format versions."""

        V2_1_0 = "2.1.0"

    @unique
    class GateSeverity(StrEnum):
        """Severity levels accepted by gate output parsers."""

        ERROR = "error"
        WARNING = "warning"
        NOTE = "note"

    @unique
    class ToolOutcome(StrEnum):
        """How a completed tool run ended, read from its exit and its report.

        ``CLEAN`` and ``FINDINGS`` are runs the tool completed; only ``ERROR``
        (a status the tool does not declare, a timeout, a signal, or a findings
        status with nothing reported) breaks a repair verb. Findings stay
        reported and are enforced by ``make check``.
        """

        CLEAN = "clean"
        FINDINGS = "findings"
        ERROR = "error"

    @unique
    class GateKind(StrEnum):
        """Who owns a gate's rule catalog.

        ``EXTERNAL`` is an external tool applying its own per-file rule
        catalog, ``TYPE_CHECKER`` a whole-program type checker, and ``INFRA``
        a validator whose rules this package owns. The CI partition is
        declared by ``make.ci.local_check_gates``, not by the kind.
        """

        EXTERNAL = "external"
        TYPE_CHECKER = "type-checker"
        INFRA = "infra"

    @unique
    class LintFixRecipe(StrEnum):
        """Repair the lint gate applies to a finding Ruff reports without a fix.

        The tooling owner maps each Ruff rule name to one recipe; ``make fix``
        applies Ruff's own fixes first and then the recipe of every finding
        left, so no rule code or repair text lives in the gate.
        """

        RETURNS_SECTION = "returns-section"
        YIELDS_SECTION = "yields-section"
        RAISES_SECTION = "raises-section"
        SUMMARY_DOCSTRING = "summary-docstring"
        COPYRIGHT_NOTICE = "copyright-notice"
        STATIC_METHOD = "static-method"
        NORMALIZE_IMPORTS = "normalize-imports"
        WRAP_LONG_LINE = "wrap-long-line"

    AST_GREP_DOCS_URL: ClassVar[str] = "https://ast-grep.github.io/"
    "Canonical ast-grep documentation URL for gate metadata."
    # Quality gate identifiers shared with the tool-name vocabulary.
    LINT: ClassVar[str] = "lint"
    FORMAT: ClassVar[str] = "format"
    MARKDOWN: ClassVar[str] = "markdown"
    MARKDOWN_FORMAT: ClassVar[str] = "markdown-format"
    MARKDOWN_CODE: ClassVar[str] = "markdown-code"
    SMELLS: ClassVar[str] = "smells"
    RUNTIME_CENSUS: ClassVar[str] = "runtime-census"
    "Gate id whose census rule families no other gate owns."
    FRESH_IMPORT: ClassVar[str] = "fresh-import"
    "Gate id of the fresh-process import proof over the provisioned runtime."
    GATE_TOOLS_BY_KIND: ClassVar[t.MappingKV[GateKind, t.MappingKV[str, t.StrPair]]] = (
        MappingProxyType({
            GateKind.EXTERNAL: MappingProxyType({
                "lint": ("Ruff Linter", "https://docs.astral.sh/ruff/"),
                "format": ("Ruff Formatter", "https://docs.astral.sh/ruff/formatter/"),
                "security": ("Bandit", "https://bandit.readthedocs.io/"),
                "markdown": ("rumdl", "https://rumdl.dev/"),
                "markdown-format": ("rumdl", "https://rumdl.dev/"),
                "markdown-code": ("Ruff", "https://docs.astral.sh/ruff/"),
                "duplication": ("jscpd", "https://github.com/kucherenko/jscpd"),
            }),
            GateKind.TYPE_CHECKER: MappingProxyType({
                "pyrefly": ("Pyrefly", "https://github.com/facebook/pyrefly"),
                "mypy": ("Mypy", "https://mypy.readthedocs.io/"),
                "pyright": ("Pyright", "https://github.com/microsoft/pyright"),
            }),
            GateKind.INFRA: MappingProxyType({
                "loc-cap": ("scc", "https://github.com/boyter/scc"),
                "runtime-census": (
                    "Flext Runtime Enforcement Census",
                    "internal://flext-infra/runtime-census",
                ),
                FRESH_IMPORT: (
                    "Flext Fresh-Process Import Gate",
                    "internal://flext-infra/fresh-import",
                ),
                "index-declarations": (
                    "Flext Index Declarations Gate",
                    "internal://flext-infra/index-declarations",
                ),
                SMELLS: ("Flext Code Smell Detector", "internal://flext-infra/smells"),
                "codemod": ("ast-grep", AST_GREP_DOCS_URL),
                "layout": (
                    "Flext Project Layout Gate",
                    "internal://flext-infra/layout",
                ),
                "direnv": (
                    "Flext Direnv Environment Contract Gate",
                    "internal://flext-infra/direnv",
                ),
            }),
        })
    )
    """The gate registry: each gate is declared once, under its kind.

    ``loc-cap`` and ``codemod`` drive an external engine (scc, ast-grep) over a
    rule catalog this package owns, so they are ``INFRA``. Every other gate
    vocabulary below is derived from this declaration.
    """
    GATE_KINDS: ClassVar[t.MappingKV[str, GateKind]] = MappingProxyType({
        gate: kind for kind, tools in GATE_TOOLS_BY_KIND.items() for gate in tools
    })
    "Gate id -> kind, derived from the registry declaration."
    TYPE_CHECKER_GATES: ClassVar[frozenset[str]] = frozenset(
        GATE_TOOLS_BY_KIND[GateKind.TYPE_CHECKER],
    )
    "Native type-checker gates, derived from the registry declaration."
    SARIF_TOOL_INFO: ClassVar[t.MappingKV[str, t.StrPair]] = MappingProxyType({
        gate: tool
        for tools in GATE_TOOLS_BY_KIND.values()
        for gate, tool in tools.items()
    })
    "Gate id -> (tool name, tool url), derived from the registry declaration."
    ALLOWED_GATES: ClassVar[frozenset[str]] = frozenset(SARIF_TOOL_INFO)
    "Gate identifiers — derived from SARIF_TOOL_INFO keys (single SSOT)."
    CHECK_REPORT_MARKDOWN_FILENAME: ClassVar[str] = "check-report.md"
    "Human-readable check report written beside the SARIF report."
    CHECK_REPORT_SARIF_FILENAME: ClassVar[str] = "check-report.sarif"
    "SARIF 2.1.0 check report: the machine-readable findings owner of ``check run``."
    RUFF_FORMAT_FILE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*-->\s*(.+?):\d+:\d+\s*$",
    )
    MARKDOWN_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<file>.*?):(?P<line>\d+):(?P<col>\d+):\s+\[(?P<code>MD\d+)\]\s+(?P<msg>.*)$",
    )
    MARKDOWN_FIXED_SUFFIX: ClassVar[str] = "[fixed]"
    "rumdl text-output suffix marking a finding its mutating pass repaired."
    MARKDOWN_FORMAT_DIFF_HEADERS: ClassVar[t.StrPair] = ("--- ", "+++ ")
    MARKDOWN_FORMAT_RE: ClassVar[t.RegexPattern] = re.compile(
        # Prettier applies terminal SGR styling to the warning label in CI.
        r"^\[(?:\x1b\[[0-9;]*m)*warn(?:\x1b\[[0-9;]*m)*\]"
        r"\s+(?P<file>\S+\.md)\s*$",
        re.MULTILINE,
    )
    (
        "``rumdl fmt --check`` unified-diff header pair naming one file the "
        "formatter would rewrite; consecutive lines carry the same path."
    )
    MARKDOWN_PY_FENCE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^```(?P<info>python\S*(?:\s+notest)?)\s*$\n(?P<code>.*?)^```\s*$",
        re.MULTILINE | re.DOTALL,
    )
    (
        "Canonical fenced-Python-block extractor; "
        "the flext-tests markdown validator consumes the same pattern."
    )
    MARKDOWN_CODE_SOURCE_FORMAT: ClassVar[str] = "{}_b{}.py"
    "Temp-file name for one extracted block: sanitized doc path plus block index."
    MARKDOWN_CODE_SKIP_MARKER: ClassVar[str] = "notest"
    (
        "Existing fence marker (pytest-markdown-docs) "
        "opting a block out of code validation."
    )
    MARKDOWN_CODE_SOURCE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"(?P<file>[^\s/:]+_b\d+\.py)(?::(?P<line>\d+))?",
    )
    "Extracted-source name (``MARKDOWN_CODE_SOURCE_FORMAT``) inside any ruff line."
    VALID_GATE_SEVERITIES: ClassVar[frozenset[str]] = frozenset(GateSeverity)
    "Severity levels accepted by gate output parsers — derived from GateSeverity."
    PYRIGHT_DIAGNOSTICS_KEY: ClassVar[str] = "generalDiagnostics"
    PYRIGHT_PROJECT_ARG: ClassVar[str] = "--project"
    PYRIGHT_PROJECT_CONFIG_TARGET: ClassVar[str] = "."
    BANDIT_RESULTS_KEY: ClassVar[str] = "results"
    PYREFLY_ERRORS_KEY: ClassVar[str] = "errors"
    PYREFLY_ZERO_ERRORS_RECEIPT: ClassVar[str] = "INFO 0 errors"
    "Exact successful stderr receipt emitted by Pyrefly's per-file check."

    SCC_BINARY: ClassVar[str] = "scc"
    CLI_DIRENV: ClassVar[str] = "direnv"
    SCC_PYTHON_LANG: ClassVar[str] = "Python"
    "scc language key the 200-LOC cap enforces; "
    "templates (.j2/.mk), schemas (.json), and config (.yml/.toml) are not modules."

    # --- qlty smells gate (code-smell architecture violations) SSOT ---
    QLTY_BINARY: ClassVar[str] = "qlty"
    QLTY_CONFIG_DIRNAME: ClassVar[str] = ".qlty"
    QLTY_CONFIG_FILENAME: ClassVar[str] = "qlty.toml"
    SMELLS_QLTY_ARGS: ClassVar[t.StrSequence] = (
        "smells",
        "--sarif",
        "--include-tests",
        "--no-snippets",
        "--quiet",
        "--no-upgrade-check",
    )
    "Smells scan arguments; the gate appends explicit targets, scanned in full."
    SMELLS_RULE_PREFIX: ClassVar[str] = "qlty:"
    SMELLS_RULE_TAGS: ClassVar[t.MappingKV[str, str]] = MappingProxyType({
        "boolean-logic": "smell_boolean_logic",
        "file-complexity": "smell_file_complexity",
        "function-complexity": "smell_function_complexity",
        "function-parameters": "smell_function_parameters",
        "identical-code": "smell_identical_code",
        "nested-control-flow": "smell_nested_control_flow",
        "return-statements": "smell_return_statements",
        "similar-code": "smell_similar_code",
    })
    (
        "qlty ruleId suffix -> flext-core enforcement tag "
        "(texts SSOT: core ENFORCEMENT_RULES_TEXT)."
    )

    # --- jscpd duplication gate SSOT (flext-infra owns the
    # jscpd plugin behind one centralized `make check` verb; its config is
    # rendered from this typed SSOT at scan time, never a hand-maintained file).
    JSCPD_BINARY: ClassVar[str] = "jscpd"
    (
        "Provisioned by mise from codegen.toolchain.tools entry 'jscpd'; "
        "never a runner or a version here."
    )

    JSCPD_MODE: ClassVar[str] = "strict"
    JSCPD_MIN_LINES: ClassVar[int] = 10
    "Minimum lines for a clone (R2: 10 lines = 62 tokens per consumption-law.md)."
    JSCPD_MIN_TOKENS: ClassVar[int] = 62
    "Minimum tokens for a clone (R2: 10 lines ≈ 62 tokens)."
    JSCPD_THRESHOLD_PERCENT: ClassVar[int] = 0
    "Zero tolerance — every owned clone is an error."
    JSCPD_SCOPE_DIRNAMES: ClassVar[t.StrSequence] = (
        "src",
        "tests",
        "scripts",
        "examples",
        "templates",
        "config",
    )
    (
        "Canonical scope: source, tests, scripts, examples, "
        "templates, config (R2 consumer+family)."
    )
    JSCPD_REPORT_DIRNAME: ClassVar[str] = ".reports/jscpd"
    JSCPD_CONFIG_FILENAME: ClassVar[str] = ".jscpd.generated.json"
    JSCPD_REPORT_FILENAME: ClassVar[str] = "jscpd-report.json"
    JSCPD_FORMAT_EXTENSIONS: ClassVar[t.MappingKV[str, t.StrSequence]] = (
        MappingProxyType({"django": ("j2",)})
    )
    "Parse Jinja projections in place; never duplicate templates into a scan tree."
    JSCPD_IGNORE_PATTERNS: ClassVar[t.StrSequence] = (
        "**/__snapshots__/**",
        "**/__init__.py",
        "**/api_cases/**",
        "**/_cases/**",
        "**/rules/ast-grep/tests/**",
        "**/_cov.py",
        "**/_parts/**",
    )
    "Generated Python surfaces and structured test-case parameterization files "
    "excluded semantically; Git owns artifact visibility. ast-grep rule "
    "fixtures mirror their rule pattern/fix text by design (the fix output IS "
    "the next stage's valid input), so jscpd would always report the fixture "
    "pair; the corpus is validated by `ast-grep test`, never by clone count."

    # --- Extended duplication gate (R2 consumer+family scope) ---
    JSCPD_CONSUMER_FAMILY_SCOPE: ClassVar[bool] = True
    "When true, extend scan scope to consumer+family via [tool.flext.project] keys."
    JSCPD_STRUCTURAL_BAN_FORMS: ClassVar[bool] = True
    (
        "When true, ban structural forms only for mechanisms "
        "with published canonical owner."
    )

    # --- Manual-command blocker (AGENTS.md `Build & Test`) SSOT ---
    MANUAL_CMD_BLOCKED_TOOLS: ClassVar[frozenset[str]] = frozenset({
        "ruff",
        "pytest",
        "pyrefly",
        "mypy",
        "pyright",
    })
    MANUAL_CMD_BLOCKED_GIT: ClassVar[frozenset[str]] = frozenset({
        "commit",
        "add",
        "push",
        "tag",
    })
    MANUAL_CMD_REWRITE_TOOLS: ClassVar[frozenset[str]] = frozenset({"ast-grep"})
    MANUAL_CMD_RUNNERS: ClassVar[frozenset[str]] = frozenset({"python", "python3"})
    MANUAL_CMD_UV_RUN_VALUE_OPTIONS: ClassVar[frozenset[str]] = frozenset({
        "--default-index",
        "--directory",
        "--env-file",
        "--extra",
        "--find-links",
        "--from",
        "--group",
        "--index",
        "--index-url",
        "--index-strategy",
        "--keyring-provider",
        "--link-mode",
        "--no-extra",
        "--no-group",
        "--only-group",
        "--package",
        "--prerelease",
        "--project",
        "--python",
        "--python-platform",
        "--resolution",
        "--with",
        "--with-editable",
        "--with-requirements",
    })
    "``uv run`` options that consume the following token before the real command."
    MANUAL_CMD_WRAPPERS: ClassVar[frozenset[str]] = frozenset({
        "env",
        "time",
        "nohup",
        "xargs",
        "sudo",
        "command",
        "nice",
        "ionice",
        "stdbuf",
    })
    MANUAL_CMD_REWRITE_FLAGS: ClassVar[frozenset[str]] = frozenset({
        "--rewrite",
        "-U",
        "--update-all",
    })
    MANUAL_CMD_SEGMENT_RE: ClassVar[t.RegexPattern] = re.compile(
        r"&&|\|\||;|\||\n|`|\$\(",
    )

    # --- Net-LOC-delta validator (§3.5) SSOT ---
    REFACTOR_COMMIT_LABELS: ClassVar[frozenset[str]] = frozenset({
        "refactor",
        "deduplicate",
        "cleanup",
        "yagni",
        "simplify",
    })


__all__: list[str] = ["FlextInfraConstantsCheck"]
