"""Centralized constants for the check subpackage."""

from __future__ import annotations

import re
from enum import StrEnum, unique
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsCheck:
    """Check infrastructure constants."""

    PYTEST_SELECTED_COLLECTION_OPTION: ClassVar[str] = "--flext-selected-collection"

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

    AST_GREP_DOCS_URL: ClassVar[str] = "https://ast-grep.github.io/"
    "Canonical ast-grep documentation URL for gate metadata."
    # Quality gate identifiers shared with the tool-name vocabulary.
    LINT: ClassVar[str] = "lint"
    FORMAT: ClassVar[str] = "format"
    MARKDOWN: ClassVar[str] = "markdown"
    MARKDOWN_FORMAT: ClassVar[str] = "markdown-format"
    MARKDOWN_CODE: ClassVar[str] = "markdown-code"
    SILENT_FAILURE: ClassVar[str] = "silent-failure"
    SARIF_TOOL_INFO: ClassVar[t.MappingKV[str, t.StrPair]] = MappingProxyType({
        "lint": ("Ruff Linter", "https://docs.astral.sh/ruff/"),
        "format": ("Ruff Formatter", "https://docs.astral.sh/ruff/formatter/"),
        "pyrefly": ("Pyrefly", "https://github.com/facebook/pyrefly"),
        "mypy": ("Mypy", "https://mypy.readthedocs.io/"),
        "pyright": ("Pyright", "https://github.com/microsoft/pyright"),
        "silent-failure": (
            "Flext Silent Failure Detector",
            "internal://flext-infra/silent-failure",
        ),
        "deferred-self-reference": (
            "Flext Deferred Self Reference Detector",
            "internal://flext-infra/deferred-self-reference",
        ),
        "security": ("Bandit", "https://bandit.readthedocs.io/"),
        "markdown": ("rumdl", "https://rumdl.dev/"),
        "markdown-format": ("Prettier", "https://prettier.io/"),
        "markdown-code": ("Ruff", "https://docs.astral.sh/ruff/"),
        "loc-cap": ("scc", "https://github.com/boyter/scc"),
        "boundary": (
            "Flext Abstraction Boundary Auditor",
            "internal://flext-infra/abstraction-boundary",
        ),
        "runtime-census": (
            "Flext Runtime Enforcement Census",
            "internal://flext-infra/runtime-census",
        ),
        "namespace": ("Flext Namespace Rule Gate", "internal://flext-infra/namespace"),
        "tier-whitelist": (
            "Flext Tier Whitelist Gate",
            "internal://flext-infra/tier-whitelist",
        ),
        "index-declarations": (
            "Flext Index Declarations Gate",
            "internal://flext-infra/index-declarations",
        ),
        "smells": ("Flext Code Smell Detector", "internal://flext-infra/smells"),
        "codemod": ("ast-grep", AST_GREP_DOCS_URL),
        "layout": ("Flext Project Layout Gate", "internal://flext-infra/layout"),
        "canonical-alias": (
            "Flext Canonical Alias Detector",
            "internal://flext-infra/canonical-alias",
        ),
        "direnv": (
            "Flext Direnv Environment Contract Gate",
            "internal://flext-infra/direnv",
        ),
        "duplication": ("jscpd", "https://github.com/kucherenko/jscpd"),
    })
    ALLOWED_GATES: ClassVar[frozenset[str]] = frozenset(SARIF_TOOL_INFO)
    "Gate identifiers — derived from SARIF_TOOL_INFO keys (single SSOT)."
    CHECK_REPORT_MARKDOWN_FILENAME: ClassVar[str] = "check-report.md"
    "Human-readable check report written beside the SARIF report."
    CHECK_REPORT_SARIF_FILENAME: ClassVar[str] = "check-report.sarif"
    "SARIF 2.1.0 check report: the machine-readable findings owner of ``check run``."
    MUTATING_GATES: ClassVar[frozenset[str]] = frozenset({FORMAT})
    "Gates that rewrite files: owned by `fmt`/`fix`, never a read-only `check` vocabulary."

    RUFF_FORMAT_FILE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*-->\s*(.+?):\d+:\d+\s*$"
    )
    MARKDOWN_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<file>.*?):(?P<line>\d+):(?P<col>\d+):\s+\[(?P<code>MD\d+)\]\s+(?P<msg>.*)$"
    )
    MARKDOWN_FORMAT_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\[warn\]\s+(?P<file>\S+\.md)\s*$", re.MULTILINE
    )
    "Prettier ``--check`` unformatted-file line (``[warn] <file.md>``); config warns never match."
    MARKDOWN_PY_FENCE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^```(?P<info>python\S*(?:\s+notest)?)\s*$\n(?P<code>.*?)^```\s*$",
        re.MULTILINE | re.DOTALL,
    )
    "Canonical fenced-Python-block extractor; the flext-tests markdown validator consumes the same pattern."
    MARKDOWN_CODE_SOURCE_FORMAT: ClassVar[str] = "{}_b{}.py"
    "Temp-file name for one extracted block: sanitized doc path plus block index."
    MARKDOWN_CODE_SKIP_MARKER: ClassVar[str] = "notest"
    "Existing fence marker (pytest-markdown-docs) opting a block out of code validation."
    MARKDOWN_CODE_FORMAT_FILE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<file>\S+):\d+:\d+:\s+unformatted:\s+"
    )
    "Ruff format ``--check`` concise verdict line over extracted sources."
    MARKDOWN_CODE_FORMAT_ERROR_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^error: Failed to format (?P<file>\S+):", re.MULTILINE
    )
    "Ruff format hard-failure line over extracted sources (parse errors)."
    VALID_GATE_SEVERITIES: ClassVar[frozenset[str]] = frozenset(GateSeverity)
    "Severity levels accepted by gate output parsers — derived from GateSeverity."
    PYRIGHT_DIAGNOSTICS_KEY: ClassVar[str] = "generalDiagnostics"
    PYRIGHT_PROJECT_ARG: ClassVar[str] = "--project"
    PYRIGHT_PROJECT_CONFIG_TARGET: ClassVar[str] = "."
    BANDIT_RESULTS_KEY: ClassVar[str] = "results"
    PYREFLY_ERRORS_KEY: ClassVar[str] = "errors"
    PYREFLY_ZERO_ERRORS_RECEIPT: ClassVar[str] = "INFO 0 errors"
    "Exact successful stderr receipt emitted by Pyrefly's per-file check."
    # --- Abstraction-boundary gate (§2.7) detection SSOT ---
    BOUNDARY_SKIP_PROJECTS: ClassVar[frozenset[str]] = frozenset({
        "flext-cli",
        "flext-core",
    })
    BOUNDARY_TOML_ALLOWED: ClassVar[frozenset[str]] = frozenset({"flext-infra"})
    BOUNDARY_CLICK_FILES: ClassVar[t.StrSequence] = (
        "/flext-tap-",
        "/flext-target-",
        "/flext-meltano/src/flext_meltano/services/executor_base.py",
        "/flext-meltano/src/flext_meltano/_protocols/singer.py",
        "/flext-meltano/tests/unit/test_singer_sdk_adapter.py",
    )
    BOUNDARY_EXTENSION_FILES: ClassVar[frozenset[str]] = frozenset({
        "constants.py",
        "models.py",
        "protocols.py",
        "typings.py",
        "utilities.py",
        "config.py",
        "settings.py",
        "_config.py",
        "_settings.py",
    })
    # ADR-0018 stdlib island: the native hook client runs as `python3 -I -S`
    # and is excluded from the facade-boundary rules; the fragment matches the
    # real posix path segments (src/ai_hub/hook_client.py).
    BOUNDARY_SKIP_PATH_FRAGMENTS: ClassVar[t.StrSequence] = (
        "/ai_hub/hook_client",
        # Vendored standalone workspace tooling (cosmos-command dispatcher):
        # it must stay importable by a bare `python3` outside any project
        # venv, so the facade imports the boundary rules mandate are
        # impossible by design; its stdlib usage belongs to the distributor.
        "/scripts/lib/cosmos_command",
    )
    BOUNDARY_BANNED_LIBS: ClassVar[t.MappingKV[str, str]] = MappingProxyType({
        "typer": "cli.create_app_with_common_params / cli.register_command",
        "click": "flext_cli.cli application, registration, execution, and invocation methods",
        "argparse": "cli.register_result_command + Pydantic model",
        "rich": "cli.print / cli.display_message / cli.render_panel / cli.render_table",
        "tabulate": "cli.format_table / cli.show_table",
        "colorama": "cli.print with c.Cli.MessageStyles",
        "prompt_toolkit": "cli.prompt / cli.confirm / cli.prompt_password",
        "tqdm": "cli.display_progress",
        "getpass": "cli.prompt_password",
        "orjson": "cli.read_json_file / cli.write_json_file / u.Cli.json_dumps",
        "ujson": "cli.read_json_file / cli.write_json_file / u.Cli.json_dumps",
        "simplejson": "cli.read_json_file / cli.write_json_file / u.Cli.json_dumps",
    })
    # Precompiled (lib, regex, replacement) rows — click is exempted at the call
    # site for Singer-SDK boundary files.
    BOUNDARY_BANNED_RULES: ClassVar[
        t.VariadicTuple[t.Triple[str, t.RegexPattern, str]]
    ] = tuple(
        (lib, re.compile(rf"^\s*(import|from)\s+{lib}(\s|$|\.)", re.MULTILINE), repl)
        for lib, repl in BOUNDARY_BANNED_LIBS.items()
    )
    # Unconditional (regex, message) catalog — one data-driven loop in the gate.
    BOUNDARY_SIMPLE_RULES: ClassVar[t.VariadicTuple[t.Pair[t.RegexPattern, str]]] = (
        (
            re.compile(
                rf"^\s*(import|from)\s+{'sub' + 'process'}(\s|$|\.)", re.MULTILINE
            ),
            "imports subprocess — use cli.run / cli.capture",
        ),
        (
            re.compile(r"^\s*sys\.exit\(", re.MULTILINE),
            "uses sys.exit() — use cli.exit()",
        ),
    )
    # The boundary gate's own rule-definition source files legitimately contain the
    # forbidden-pattern strings as DETECTION RULES (not as usage); exempt them from
    # self-scanning so the detector does not flag its own catalog.
    BOUNDARY_SELF_FILES: ClassVar[frozenset[str]] = frozenset({
        "flext_infra/_constants/check.py",
        "flext_infra/gates/abstraction_boundary.py",
        # Why: the Darwin supervisor is a std-lib-only bootstrap executable that
        # must own its process group BEFORE the fleet stack (and its CLI
        # facade) is importable; subprocess with constant argv is its core
        # mechanism, not an untrusted-input boundary.
        "flext_infra/_utilities/_mypy_supervisor.py",
    })
    BOUNDARY_JSON_ATTRS: ClassVar[frozenset[str]] = frozenset({
        "dump",
        "dumps",
        "load",
        "loads",
    })
    BOUNDARY_YAML_ATTRS: ClassVar[frozenset[str]] = frozenset({
        "dump",
        "load",
        "safe_load",
    })
    BOUNDARY_CSV_ATTRS: ClassVar[frozenset[str]] = frozenset({
        "DictReader",
        "DictWriter",
        "reader",
        "writer",
    })
    BOUNDARY_ATTR_RULES: ClassVar[
        t.VariadicTuple[t.Triple[str, frozenset[str], str]]
    ] = (
        (
            "json",
            BOUNDARY_JSON_ATTRS,
            "uses json serialization — use u.Cli.json_* / cli.json_*",
        ),
        (
            "yaml",
            BOUNDARY_YAML_ATTRS,
            "uses yaml serialization — use u.Cli.yaml_* / cli.yaml_*",
        ),
        (
            "csv",
            BOUNDARY_CSV_ATTRS,
            "uses csv serialization — use u.Cli.csv_* / cli.csv_*",
        ),
    )
    BOUNDARY_TOML_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*(import|from)\s+(tomllib|tomlkit)(\s|$|\.)", re.MULTILINE
    )
    BOUNDARY_FLEXT_CLI_CONCRETE_RE: ClassVar[t.RegexPattern] = re.compile(
        r"\bFlextCli[A-Z]\w*"
    )

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
        "--all",
        "--sarif",
        "--include-tests",
        "--no-snippets",
        "--quiet",
        "--no-upgrade-check",
    )
    "Full-workspace scan: default qlty scope is changed-files-only; --all overrides."
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
    "qlty ruleId suffix -> flext-core enforcement tag (texts SSOT: core ENFORCEMENT_RULES_TEXT)."

    # --- jscpd duplication gate SSOT (operator 2026-09-04: flext-infra owns the
    # jscpd plugin behind one centralized `make check` verb; its config is
    # rendered from this typed SSOT at scan time, never a hand-maintained file).
    JSCPD_BINARY: ClassVar[str] = "jscpd"
    "Provisioned by mise from codegen.toolchain.jscpd_version; never a runner or a version here."

    # --- markdown-format gate SSOT (operator 2026-09-18: prettier is the
    # markdown formatter owned by `make fmt`; rumdl stays the linter owned by
    # `make fix`. The binary is mise-provisioned, never a runner or version).
    PRETTIER_BINARY: ClassVar[str] = "prettier"
    "Provisioned by mise from codegen.toolchain.prettier_version; never a runner or a version here."
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
    "Canonical scope: source, tests, scripts, examples, templates, config (R2 consumer+family)."
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
        "**/codemod/tests/**",
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
    "When true, ban structural forms only for mechanisms with published canonical owner."

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
        r"&&|\|\||;|\||\n|`|\$\("
    )

    # --- Net-LOC-delta validator (§3.5) SSOT ---
    REFACTOR_COMMIT_LABELS: ClassVar[frozenset[str]] = frozenset({
        "refactor",
        "deduplicate",
        "cleanup",
        "yagni",
        "simplify",
    })

    # Canonical .pre-commit-config.yaml (SSOT; was templates/pre_commit_config.yaml.j2).
    # Static — no Jinja vars; hooks route through the workspace uv environment.
    PRE_COMMIT_CONFIG: ClassVar[str] = """\
# @generated by flext_infra — DO NOT EDIT. Run `make gen` / `make sync` to regenerate.
#
# Every hook routes through the canonical `uv run --all-packages python -m flext_infra`
# workspace monopoly; no standalone scripts and no bare tool invocations
# (AGENTS.md `Build & Test`).
# Enable locally with `pre-commit install` from the repository root.
repos:
  - repo: local
    hooks:
      - id: flext-abstraction-boundary
        name: Abstraction boundary (§2.7) — CLI-domain libs + concrete FlextCli imports
        entry: uv run --all-packages python scripts/hooks/check_changed_projects.py boundary
        language: system
        pass_filenames: true
        always_run: false
        types: [python]
      - id: flext-loc-cap
        name: MODULE-LOC SUPREME LAW (§3.1) — module cap via scc
        entry: uv run --all-packages python scripts/hooks/check_changed_projects.py loc-cap
        language: system
        pass_filenames: true
        always_run: false
        types: [python]
      - id: flext-manual-command
        name: Manual-command blocker (§5) — no bare tool calls in automation
        entry: uv run --all-packages python -m flext_infra validate --what manual-cmd
        language: system
        pass_filenames: false
        always_run: true
        types: [python]
"""


__all__: list[str] = ["FlextInfraConstantsCheck"]
