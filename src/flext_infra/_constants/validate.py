"""Centralized constants for the core subpackage."""

from __future__ import annotations

import re
from enum import IntEnum, StrEnum, unique
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from flext_core import c as core_c

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsSharedInfra:
    """Shared infrastructure constants consumed by flext_infra.constants."""

    PRIMITIVES_TYPES: ClassVar[
        tuple[type[str], type[int], type[float], type[bool]]
    ] = core_c.PRIMITIVES_TYPES
    """Re-export of the flext-core primitives owner (ENFORCE-079)."""

    EnforcementRuleSeverity: ClassVar[type[StrEnum]] = core_c.EnforcementRuleSeverity
    """Re-export of the flext-core enforcement severity owner."""

    @unique
    class ScriptExitCode(IntEnum):
        """Canonical exit codes for infra-owned validation scripts."""

        PASS = 0
        FAIL = 1
        USAGE = 2
        INFRA = 3

    EXEMPT_FILENAMES: ClassVar[frozenset[str]] = frozenset({
        "__init__.py",
        "conftest.py",
        "__main__.py",
    })
    EXEMPT_PREFIXES: ClassVar[frozenset[str]] = frozenset({"test_", "_"})
    FACADE_MODULE_DEPTH: ClassVar[int] = 3
    "Relative path part count for root facade modules (src/<pkg>/<file>.py)."
    FACADE_MINIMUM_BASES: ClassVar[int] = 2
    "Minimum explicit bases required by a canonical nested project facade."
    ALIAS_NAMES: ClassVar[frozenset[str]] = frozenset({
        "c",
        "t",
        "m",
        "p",
        "u",
        "r",
        "d",
        "e",
        "h",
        "s",
        "x",
        "tc",
    })
    DUNDER_ALLOWED: ClassVar[frozenset[str]] = frozenset({"__all__", "__version__"})
    TYPEVAR_CALLABLES: ClassVar[frozenset[str]] = frozenset({
        "TypeVar",
        "ParamSpec",
        "TypeVarTuple",
    })
    ENUM_BASES: ClassVar[frozenset[str]] = frozenset({"StrEnum", "Enum", "IntEnum"})
    CLASSVAR_ANNOTATION_NAMES: ClassVar[frozenset[str]] = frozenset({"ClassVar"})
    "Names treated as class-variable constant annotations."
    COLLECTION_CALLS: ClassVar[frozenset[str]] = frozenset({
        "frozenset",
        "tuple",
        "dict",
        "list",
    })
    SKILLS_DIR: ClassVar[Path] = Path(".agents/skills")
    BASELINE_DEFAULT: ClassVar[str] = ".agents/skills/{skill}/baseline.json"
    SCRIPT_EXIT_CODE_VALUES: ClassVar[frozenset[int]] = frozenset(
        int(item) for item in ScriptExitCode
    )
    SCRIPT_HEADER_MAX_LINES: ClassVar[int] = 10
    SCRIPT_MIN_CODE_LINES: ClassVar[int] = 20
    SKILL_REPORT_VALIDATED_TOP_DIRS: ClassVar[frozenset[str]] = frozenset({"."})
    SKILL_REPORT_SKIPPED_TOP_DIRS: ClassVar[frozenset[str]] = frozenset({
        "evidence",
        "plans",
        "drafts",
        "validation",
        "dependencies",
    })
    SKILL_REPORT_SKIPPED_FILES: ClassVar[frozenset[str]] = frozenset({".gitkeep"})
    PYTHON_IMPORT_NAME_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"
    )
    SKILL_OWNER_MARKER_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^# Owner-Skill:\s+(.agents/skills/([a-z0-9][-a-z0-9]*)/SKILL\.md)\s*$"
    )
    SKILL_REPORT_ARTIFACT_NAME_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^[a-z][-a-z0-9]*--[a-z]+--[a-z][-a-z0-9]*\.[a-z]+$"
    )
    SKILL_REPORT_ARTIFACT_SKILL_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^[a-z][-a-z0-9]*$"
    )
    SKILL_REPORT_ARTIFACT_SLUG_INVALID_RE: ClassVar[t.RegexPattern] = re.compile(
        r"[^a-z0-9-]+"
    )
    SKILL_REPORT_ARTIFACT_MULTI_DASH_RE: ClassVar[t.RegexPattern] = re.compile(r"-+")
    SKILL_REPORTS_PATH_RE: ClassVar[t.RegexPattern] = re.compile(
        r"\.reports/([^\s\"']+)"
    )
    SKILL_BASH_EXIT_RE: ClassVar[t.RegexPattern] = re.compile(r"^\s*exit\s+(\d+)")
    SKILL_INTERACTIVE_PY_RE: ClassVar[t.RegexPattern] = re.compile(r"\binput\s*\(")
    SKILL_INTERACTIVE_SH_RE: ClassVar[t.RegexPattern] = re.compile(
        r"\bread\s+-p\b|\bselect\s+\w+\s+in\b|\bdialog\b|\bwhiptail\b"
    )
    SKILL_INTERACTIVE_GATE_RE: ClassVar[t.RegexPattern] = re.compile(r"--interactive")
    SKILL_VALIDATOR_NAME_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(enforce|check|validate|test|verify|audit|lint|scan)[-_]"
    )
    SKILL_FIXER_NAME_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(fix|autofix|repair|correct|reorder|refactor|standardize)[-_]"
    )
    MISSING_IMPORT_RE: ClassVar[t.RegexPattern] = re.compile(
        r"Cannot find module `([^`]+)` \[missing-import\]"
    )
    MYPY_HINT_RE: ClassVar[t.RegexPattern] = re.compile(
        r'note:\s+(?:hint|note):\s+(?:["`].*?\bpip\s+install\s+|install\s+stub\s+package\s+["`]?)'
        r'([A-Za-z0-9][A-Za-z0-9_.-]*)["`]?',
        re.IGNORECASE,
    )
    MYPY_STUB_RE: ClassVar[t.RegexPattern] = re.compile(
        r"Library stubs not installed for ['\"](\S+?)['\"]"
    )
    INTERNAL_PREFIXES: ClassVar[t.VariadicTuple[str]] = ("flext_", "flext-")
    METADATA_TOMLLIB_MODULES: ClassVar[frozenset[str]] = frozenset({"tomllib"})
    # Package-tree markers matched against "/<path relative to the scanned
    # root>" (X-77): the directory name of the working copy (a lane may be
    # named anything) never takes part in the match.
    METADATA_ALLOWLIST_PATH_MARKERS: ClassVar[t.StrSequence] = (
        "/src/flext_core/_utilities/project_metadata.py",
        "/src/flext_infra/iteration.py",
        "/src/flext_infra/__version__.py",
    )
    METADATA_TARGET_SCOPE_MARKERS: ClassVar[t.StrSequence] = ("/src/flext_infra/",)

    # --- Integration baseline discovery ---
    # Ordered preference used to derive one repository's integration baseline
    # from live Git. A provider default is a fallback ordering, never the
    # answer: repositories under the same provider legitimately integrate on
    # different branches, so the published remote-tracking branch decides.
    #
    # This is the built-in ordering of conventional names only. The governing
    # value is `codegen.branch_policy.integration_branch_preference`, which a
    # workspace declares for itself — a fleet that integrates on a versioned
    # line names it there rather than asking for a constant here. Product- and
    # release-specific names do not belong in this tuple.
    INTEGRATION_BRANCH_PREFERENCE: ClassVar[t.VariadicTuple[str]] = (
        "develop",
        "dev",
        "main",
    )

    # --- File names (was: class Files) ---
    PYPROJECT_FILENAME: ClassVar[str] = "pyproject.toml"
    MAKEFILE_FILENAME: ClassVar[str] = "Makefile"
    GITMODULES: ClassVar[str] = ".gitmodules"
    # Why: conform .gitmodules merge classifies sections via these patterns;
    # they belong beside GITMODULES on c.Infra, not as leaf re.compile copies.
    GITMODULE_SECTION_RE: ClassVar[t.RegexPattern] = re.compile(
        r'(?m)^\[submodule "[^"]+"\]\s*$'
    )
    "``.gitmodules`` submodule section header at line start."
    GITMODULE_PATH_RE: ClassVar[t.RegexPattern] = re.compile(
        r"(?m)^[ \t]*path[ \t]*=[ \t]*(.+?)[ \t]*$"
    )
    "``.gitmodules`` path assignment value inside a submodule section."
    GITMODULE_MANAGED_KEY: ClassVar[str] = "flext-managed"
    "``.gitmodules`` key whose explicit non-``true`` value opts a member out of governance."
    FOLLOW_SUPERPROJECT_BRANCH: ClassVar[str] = "."
    GITIGNORE: ClassVar[str] = ".gitignore"
    PRE_COMMIT_CONFIG_FILENAME: ClassVar[str] = ".pre-commit-config.yaml"
    MARKDOWNLINT_CONFIG_FILENAME: ClassVar[str] = ".markdownlint.json"
    MARKDOWNLINT_IGNORE_FILENAME: ClassVar[str] = ".markdownlintignore"
    PRETTIER_CONFIG_FILENAME: ClassVar[str] = ".prettierrc"
    PRETTIER_IGNORE_FILENAME: ClassVar[str] = ".prettierignore"
    "Generated markdown-formatting projections (SSOT: tooling.tools.markdown)."
    "Hook-config projection whose presence decides whether a checkout runs hooks."
    SONARCLOUD_PROPERTIES_FILENAME: ClassVar[str] = ".sonarcloud.properties"
    "Generated SonarCloud automatic-analysis scope (SSOT: codegen.sonarcloud)."
    SONARCLOUD_ISSUE_IGNORE_KEY: ClassVar[str] = "sonar.issue.ignore.multicriteria"
    "Server-side PROPERTY_SET that automatic analysis honors for issue exclusions."
    SONARCLOUD_API_AUTH_VALIDATE_PATH: ClassVar[str] = "/api/authentication/validate"
    SONARCLOUD_API_SETTINGS_VALUES_PATH: ClassVar[str] = "/api/settings/values"
    SONARCLOUD_API_SETTINGS_SET_PATH: ClassVar[str] = "/api/settings/set"
    SONARCLOUD_API_SETTINGS_RESET_PATH: ClassVar[str] = "/api/settings/reset"
    "SonarCloud web API routes of the proven settings-sync contract."
    SONARCLOUD_PROJECT_KEY_SEPARATOR: ClassVar[str] = "_"
    "Joins organization and repository into the SonarCloud project key."
    BEADS_CONFIG_RELPATH: ClassVar[str] = ".beads/config.yaml"
    BEADS_METADATA_RELPATH: ClassVar[str] = ".beads/metadata.json"
    "Generated project-owned Beads configuration paths."
    GITIGNORE_DERIVED_SECTION_NAME: ClassVar[str] = "Derived build and tool artifacts"
    "Heading of the trailing .gitignore section holding derived artifacts."
    GITIGNORE_MANAGED_SECTION_NAME: ClassVar[str] = "Tracked managed artifacts"
    "Heading of the trailing .gitignore section that re-allows managed files."
    GITIGNORE_LAYOUT_SECTION_NAME: ClassVar[str] = "Project layout exceptions"
    GITIGNORE_PROJECT_SECTION_NAME: ClassVar[str] = (
        "Project ignore patterns (config/*.yaml ManagedArtifacts.Gitignore)"
    )
    "Heading of the trailing .gitignore section holding layout-SSOT additions."
    MANAGED_FILE_POLICY_FULL: ClassVar[str] = "full"
    INIT_PY: ClassVar[str] = "__init__.py"
    API_PY: ClassVar[str] = "api.py"
    CONSTANTS_PY: ClassVar[str] = "constants.py"
    MODELS_PY: ClassVar[str] = "models.py"
    RESULT_PY: ClassVar[str] = "result.py"
    UTILITIES_PY: ClassVar[str] = "utilities.py"
    TYPINGS_PY: ClassVar[str] = "typings.py"
    PROTOCOLS_PY: ClassVar[str] = "protocols.py"
    PY_TYPED: ClassVar[str] = "py.typed"

    # --- Git constants (was: class Git) ---
    GIT_DIR: ClassVar[str] = ".git"
    GIT_ORIGIN: ClassVar[str] = "origin"
    GIT_MAIN: ClassVar[str] = "main"
    GIT_HEAD: ClassVar[str] = "HEAD"

    # --- Package name prefixes (was: class Packages) ---
    PKG_CORE: ClassVar[str] = "flext-core"
    PKG_CORE_UNDERSCORE: ClassVar[str] = "flext_core"
    PKG_TESTS_UNDERSCORE: ClassVar[str] = "flext_tests"
    PKG_INFRA_UNDERSCORE: ClassVar[str] = "flext_infra"
    PKG_ROOT: ClassVar[str] = "flext"
    PKG_PREFIX_HYPHEN: ClassVar[str] = "flext-"
    PKG_PREFIX_UNDERSCORE: ClassVar[str] = "flext_"

    # --- Dunder names (was: class Dunders) ---
    DUNDER_ALL: ClassVar[str] = "__all__"
    DUNDER_VERSION: ClassVar[str] = "__version__"
    DUNDER_INIT: ClassVar[str] = "__init__"
    DUNDER_PYCACHE: ClassVar[str] = "__pycache__"

    # --- File extensions (was: class Extensions) ---
    EXT_PYTHON: ClassVar[str] = ".py"
    EXT_PYTHON_GLOB: ClassVar[str] = "*.py"

    # --- Directory names (was: class Directories) ---
    DIR_TESTS: ClassVar[str] = "tests"
    DIR_EXAMPLES: ClassVar[str] = "examples"
    DIR_SCRIPTS: ClassVar[str] = "scripts"
    # Runtime-exempt surfaces, matched on path parts RELATIVE to the scanned
    # repository root (X-75): an ancestor directory name never grants an
    # exemption. Scope exclusions (state/cache dirs) belong to the source-scan
    # ignore list, not here.
    TIER_WHITELIST_NON_RUNTIME_DIR_PARTS: ClassVar[frozenset[str]] = frozenset({
        DIR_TESTS,
        DIR_EXAMPLES,
        DIR_SCRIPTS,
        "evaluate",
    })
    TIER_WHITELIST_SETTINGS_MODULE_LIBRARIES: ClassVar[frozenset[str]] = frozenset({
        "pydantic_settings"
    })
    TIER_WHITELIST_LEAF_CONFIG_FILES: ClassVar[frozenset[str]] = frozenset({
        "_config.py"
    })
    "Leaf config modules (e.g. ai-hub/_config.py) that own their external-library"
    "imports directly as the bottom of the c/t/p/m/u chain."
    DIR_TYPINGS: ClassVar[str] = "typings"
    DIR_DOCS: ClassVar[str] = "docs"
    DIR_BUILD: ClassVar[str] = "build"
    DIR_SITE: ClassVar[str] = "site"

    # --- Timeout values in seconds (was: class Timeouts) ---
    TIMEOUT_DEFAULT: ClassVar[int] = 300
    TIMEOUT_SHORT: ClassVar[int] = 60
    TIMEOUT_SHORT_POLL: ClassVar[int] = 2
    "Bounded wait proving a child is still blocked on a held owner lock."
    TIMEOUT_MEDIUM: ClassVar[int] = 120
    TIMEOUT_LONG: ClassVar[int] = 600
    TIMEOUT_CI: ClassVar[int] = 900

    # --- Path constants (was: class Paths) ---
    DEFAULT_SRC_DIR: ClassVar[str] = "src"


__all__: list[str] = ["FlextInfraConstantsSharedInfra"]
