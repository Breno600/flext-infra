"""Constants namespace for flext_infra.refactor."""

from __future__ import annotations

import re
from enum import StrEnum, unique
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Literal

from flext_core import c

from .base import FlextInfraConstantsBase as cb

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsRefactor:
    """Shared constants for refactor modules."""

    MOD_SCAN_REPORT_RELATIVE_PATH: ClassVar[Path] = (
        Path(cb.REPORTS_DIR_NAME) / "refactor" / "mod-findings.json"
    )
    "Canonical single-file evidence snapshot for the latest mod scan."
    MOD_SCAN_REPORT_SCHEMA_VERSION: ClassVar[Literal[1]] = 1
    "Exact structured mod evidence schema version."
    MOD_SCAN_REPORT_MODE: ClassVar[int] = 0o644
    "Canonical permission bits for structured mod evidence."
    AST_GREP_ERROR_FINDING_RECEIPT: ClassVar[str] = (
        "Error: {count} error(s) found in code."
    )
    "Exact first stderr line emitted for error-severity JSONL findings."
    AST_GREP_ERROR_FINDING_HELP: ClassVar[str] = (
        "Help: Scan succeeded and found error level diagnostics in the codebase."
    )
    "Exact second stderr line emitted for error-severity JSONL findings."

    @unique
    class ModScanCommand(StrEnum):
        """Public mod scan modes recorded in structured evidence."""

        SCAN = "scan"
        APPLY = "apply"

    @unique
    class ModScanFindingClass(StrEnum):
        """Mutability class derived from one ast-grep rule contract."""

        ACTIONABLE = "actionable"
        DETECTION_ONLY = "detection_only"
        NON_ACTIONABLE_WITH_FIX = "non_actionable_with_fix"

    @unique
    class SemanticCutoverPhase(StrEnum):
        """Semantic ``make mod`` cutovers planned by ``u.Infra.plan_semantic_cutover``."""

        CLASS_NESTING = "class-nesting"
        COMPAT_ALIAS = "compat-alias"
        PRIVATE_IMPORT = "private-import"
        FACADE_BASE = "facade-base"
        MODEL_FIELDS = "model-fields"
        SELF_FACADE_IMPORT = "self-facade-import"
        DYNAMIC_ENVIRONMENT = "dynamic-environment"

    SEMANTIC_CUTOVER_RULE_IDS: ClassVar[t.MappingKV[str, str]] = MappingProxyType({
        SemanticCutoverPhase.COMPAT_ALIAS: "ban-compat-alias",
        SemanticCutoverPhase.PRIVATE_IMPORT: "ban-private-import",
        SemanticCutoverPhase.FACADE_BASE: "facade-base-by-class-name",
        SemanticCutoverPhase.MODEL_FIELDS: "rewire-getattr-model-fields-to-direct-access",
        SemanticCutoverPhase.SELF_FACADE_IMPORT: "ban-infra-utility-module-self-facade-import",
        SemanticCutoverPhase.DYNAMIC_ENVIRONMENT: "ban-ambient-environ-read",
    })
    "ast-grep rule whose findings select each finding-driven semantic cutover."

    RK_REFACTOR: ClassVar[str] = "refactor"
    RK_PROJECT_SCAN_DIRS: ClassVar[str] = "project_scan_dirs"
    RK_FILE_EXTENSIONS: ClassVar[str] = "file_extensions"
    RK_FORBIDDEN_IMPORTS: ClassVar[str] = "forbidden_imports"
    RK_REDUNDANT_TYPE_TARGETS: ClassVar[str] = "redundant_type_targets"
    RK_TARGET_MODULES: ClassVar[str] = "target_modules"
    RK_MODULE_RENAMES: ClassVar[str] = "module_renames"
    RK_IMPORT_SYMBOL_RENAMES: ClassVar[str] = "import_symbol_renames"
    RK_SIGNATURE_MIGRATIONS: ClassVar[str] = "signature_migrations"
    RK_METHOD_ORDER: ClassVar[str] = "method_order"
    RK_ORDER: ClassVar[str] = "order"
    RK_ALLOW_ALIASES: ClassVar[str] = "allow_aliases"
    RK_ALLOW_TARGET_SUFFIXES: ClassVar[str] = "allow_target_suffixes"
    CODEMOD_RESOURCE_DIRNAME: ClassVar[str] = "codemod"
    CODEMOD_RULE_SUFFIX: ClassVar[str] = ".yml"
    CODEMOD_DOCUMENT_SEPARATOR_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^---\s*$", re.MULTILINE
    )
    CODEMOD_CONFIG_FILENAME: ClassVar[str] = "sgconfig.yml"
    # Why: restored — deleted declaration with consumers left behind in codemod_rules.py
    CODEMOD_CONFIG_RELPATH: ClassVar[Path] = Path(CODEMOD_RESOURCE_DIRNAME) / (
        CODEMOD_CONFIG_FILENAME
    )
    CODEMOD_RULE_DIRS_KEY: ClassVar[str] = "ruleDirs"
    CODEMOD_UTIL_DIRS_KEY: ClassVar[str] = "utilDirs"
    CODEMOD_TEST_CONFIGS_KEY: ClassVar[str] = "testConfigs"
    CODEMOD_TEST_DIR_KEY: ClassVar[str] = "testDir"
    CODEMOD_SCOPE_KEY: ClassVar[str] = "scope"
    CODEMOD_SCOPE_UNIVERSAL: ClassVar[str] = "universal"
    CODEMOD_SCOPE_RUNTIME: ClassVar[str] = "runtime"
    # Declarative sed-by-list rules: one list entry drives one regex rewrite
    # across the governed scan surface with an exact expected-count receipt.
    # The sed-by-list catalogue has one declared owner per governed repository:
    # config/rules/mod/sed.yaml, whose schema the file itself documents. The
    # engine previously looked for a `text_rules.yml` that exists nowhere in
    # the tree, so the phase was wired but inert and the declared catalogue was
    # read by nothing.
    CODEMOD_TEXT_RULES_FILENAME: ClassVar[str] = "sed.yaml"
    # Declarative text-rule path derived from the filename SSOT.
    CODEMOD_TEXT_RULES_RELPATH: ClassVar[Path] = (
        Path("config") / "rules" / "mod" / CODEMOD_TEXT_RULES_FILENAME
    )
    CODEMOD_TEXT_RULES_KEY: ClassVar[str] = "rules"
    CODEMOD_TEXT_KEY_ID: ClassVar[str] = "id"
    CODEMOD_TEXT_KEY_DESCRIPTION: ClassVar[str] = "description"
    CODEMOD_TEXT_KEY_INCLUDE: ClassVar[str] = "include"
    CODEMOD_TEXT_KEY_EXCLUDE: ClassVar[str] = "exclude"
    CODEMOD_TEXT_KEY_FIND: ClassVar[str] = "find"
    CODEMOD_TEXT_KEY_REPLACE: ClassVar[str] = "replace"
    CODEMOD_TEXT_KEY_FLAGS: ClassVar[str] = "flags"
    CODEMOD_TEXT_KEY_EXPECTED: ClassVar[str] = "expected"
    CODEMOD_TEXT_KEY_CAPTURE_EQUALS: ClassVar[str] = "capture_equals"
    # ast-grep rejects unknown top-level keys, so an ast-grep rule declares
    # its finding-count receipt under the `metadata` mapping it does accept.
    CODEMOD_RULE_METADATA_KEY: ClassVar[str] = "metadata"
    # The declarative signature-migration catalogue: one owner per governed
    # repository, read by the propagate-signatures verb.
    REFACTOR_SIGNATURE_RULES_RELPATH: ClassVar[Path] = (
        Path("config") / "rules" / "refactor" / "signature-propagation.yml"
    )
    REFACTOR_SIGNATURE_RULES_KEY: ClassVar[str] = "migrations"
    CODEMOD_TEXT_FLAG_NAMES: ClassVar[t.MappingKV[str, int]] = MappingProxyType({
        "IGNORECASE": re.IGNORECASE,
        "MULTILINE": re.MULTILINE,
        "DOTALL": re.DOTALL,
    })
    CODEMOD_SNAPSHOT_DIRNAME: ClassVar[str] = "__snapshots__"
    CODEMOD_SNAPSHOT_SUFFIX: ClassVar[str] = "-snapshot.yml"
    # ast-grep rule-test protocol keys: a test names its rule and lists the
    # invalid cases; a snapshot file maps each invalid case to its projection.
    CODEMOD_RULE_TEST_ID_KEY: ClassVar[str] = "id"
    CODEMOD_RULE_TEST_INVALID_KEY: ClassVar[str] = "invalid"
    CODEMOD_SNAPSHOTS_KEY: ClassVar[str] = "snapshots"
    # `make mod` only verifies committed snapshots; the regeneration is its own
    # verb so every snapshot change lands as a reviewed commit.
    CODEMOD_SNAPSHOT_REFRESH_HINT: ClassVar[str] = (
        "ast-grep snapshots are projections of the rule tests: run "
        "`make mod-snapshots`, review the snapshot diff and commit it"
    )
    CODEMOD_EPHEMERAL_DIRNAME: ClassVar[str] = "__pycache__"
    REFACTOR_CONFIG_KEYS: ClassVar[t.StrSequence] = (
        RK_PROJECT_SCAN_DIRS,
        RK_FILE_EXTENSIONS,
    )
    """Allowed keys under the ``refactor`` config scope."""

    TYPING_DEFINITION_FILES: ClassVar[frozenset[str]] = frozenset({
        "constants.py",
        "_constants",
        "typings.py",
        "_typings",
        "protocols.py",
        "_protocols",
    })
    """Declaration layers where a runtime ``t`` dependency would invert layering."""
    TYPING_INLINE_UNION_CANONICAL_MAP: ClassVar[t.MappingKV[frozenset[str], str]] = (
        MappingProxyType({
            frozenset({"str", "int", "float", "bool"}): "t.Primitives",
            frozenset({"int", "float"}): "t.Numeric",
            frozenset({"str", "int", "float", "bool", "datetime"}): "t.Scalar",
        })
    )

    RULE_TABLE_HEADERS: ClassVar[t.StrSequence] = (
        cb.RK_ID,
        cb.NAME,
        cb.RK_DESCRIPTION,
        cb.RK_ENABLED,
        cb.RK_SEVERITY,
    )
    FLEXT_CONSTANTS_FILE_NAMES: ClassVar[frozenset[str]] = frozenset({
        "constants.py",
        "_constants.py",
    })
    "Canonical constants module file names."
    FLEXT_CONSTANTS_DIRECTORY: ClassVar[str] = "constants"
    "Canonical constants package directory name."
    FLEXT_TYPINGS_FILE_NAMES: ClassVar[frozenset[str]] = frozenset({
        "typings.py",
        "_typings.py",
    })
    "Canonical typings module file names."
    FLEXT_TYPINGS_DIRECTORY: ClassVar[str] = "typings"
    "Canonical typings package directory name."
    FLEXT_PROTOCOLS_FILE_NAMES: ClassVar[frozenset[str]] = frozenset({
        "protocols.py",
        "_protocols.py",
    })
    "Canonical protocols module file names."
    FLEXT_PROTOCOLS_DIRECTORY: ClassVar[str] = "protocols"
    "Canonical protocols package directory name."
    FLEXT_PROTOCOLS_DIRECTORIES: ClassVar[frozenset[str]] = frozenset({
        FLEXT_PROTOCOLS_DIRECTORY,
        f"_{FLEXT_PROTOCOLS_DIRECTORY}",
    })
    "Sanctioned protocol package directory names (public and private)."
    FLEXT_MODELS_FILE_NAMES: ClassVar[frozenset[str]] = frozenset({"models.py"})
    "Canonical models module file names."
    FLEXT_MODELS_DIRECTORY: ClassVar[str] = "models"
    "Canonical models package directory name."
    FLEXT_MODELS_DIRECTORIES: ClassVar[frozenset[str]] = frozenset({
        FLEXT_MODELS_DIRECTORY,
        f"_{FLEXT_MODELS_DIRECTORY}",
    })
    "Sanctioned model package directory names (public and private)."
    FLEXT_UTILITIES_FILE_NAMES: ClassVar[frozenset[str]] = frozenset({
        "utilities.py",
        "_utilities.py",
    })
    "Canonical utilities module file names."
    FLEXT_UTILITIES_DIRECTORY: ClassVar[str] = "utilities"
    "Canonical utilities package directory name."
    CONSTANTS_CLASS_SUFFIX: ClassVar[str] = "Constants"
    "Class-name suffix used to identify constants facades."
    CONSTANT_PATTERN: ClassVar[t.RegexPattern] = re.compile(r"^_*[A-Z][A-Z0-9_]*$")
    "Compiled naming pattern for module-level constant candidates."
    CLASSVAR_DECLARATION_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^([A-Z][A-Z0-9_]*:\s*)ClassVar\[(.*?)\](\s*=)", re.DOTALL
    )
    "One ``NAME: ClassVar[T] =`` declaration head, capturing name, type and ``=``."
    DOCSTRING_DELIMITER_COUNT: ClassVar[int] = 2
    "Opening plus closing quote delimiters of a one-line docstring."
    FAMILY_SUFFIXES: ClassVar[t.StrMapping] = MappingProxyType({
        "c": "Constants",
        "t": "Types",
        "p": "Protocols",
        "m": "Models",
        "u": "Utilities",
    })
    "Facade family letter → class suffix mapping."
    FAMILY_DIRECTORIES: ClassVar[t.StrMapping] = MappingProxyType({
        "c": "_constants",
        "t": "_typings",
        "p": "_protocols",
        "m": "_models",
        "u": "_utilities",
    })
    "Facade family letter → subdirectory name mapping."
    FAMILY_FILES: ClassVar[t.StrMapping] = MappingProxyType({
        "c": "*constants.py",
        "t": "*typings.py",
        "p": "*protocols.py",
        "m": "*models.py",
        "u": "*utilities.py",
    })
    "Facade family letter → file glob mapping."
    FAMILY_PUBLIC_MODULES: ClassVar[t.StrMapping] = MappingProxyType({
        "c": "constants",
        "m": "models",
        "p": "protocols",
        "t": "typings",
        "u": "utilities",
    })
    "Facade family letter → public facade module suffix mapping."
    NAMESPACE_FILE_TO_FAMILY: ClassVar[t.StrMapping] = MappingProxyType(
        dict.fromkeys(FLEXT_CONSTANTS_FILE_NAMES, "c")
        | dict.fromkeys(FLEXT_TYPINGS_FILE_NAMES, "t")
        | dict.fromkeys(FLEXT_PROTOCOLS_FILE_NAMES, "p")
        | dict.fromkeys(FLEXT_MODELS_FILE_NAMES, "m")
        | dict.fromkeys(FLEXT_UTILITIES_FILE_NAMES, "u")
    )
    "Canonical facade file name → family alias mapping."
    FLEXT_FAMILIES: ClassVar[frozenset[str]] = frozenset({"c", "t", "p", "m", "u"})
    "All FLEXT families."
    DOMAIN_PACKAGES: ClassVar[frozenset[str]] = frozenset({
        "flext-ldap",
        "flext-ldif",
        "flext-db-oracle",
        "flext-oracle-wms",
        "flext-oracle-oic",
    })
    "Known domain-layer packages."
    PLATFORM_PACKAGES: ClassVar[frozenset[str]] = frozenset({
        "flext-cli",
        "flext-meltano",
        "flext-api",
        "flext-auth",
        "flext-web",
        "flext-grpc",
    })
    "Known platform-layer packages."
    INTEGRATION_CLASS_PREFIXES: ClassVar[t.VariadicTuple[str]] = (
        "FlextTap",
        "FlextTarget",
        "FlextDbt",
    )
    "Class name prefixes that identify integration projects."
    MODEL_TOKENS: ClassVar[t.StrSequence] = (
        "model",
        "schema",
        "entity",
        "pydantic",
        "dataclass",
    )
    "Tokens indicating model-related code."
    DECORATOR_TOKENS: ClassVar[t.StrSequence] = ("decorator", "inject", "provide")
    "Tokens indicating decorator-related code."
    DISPATCHER_TOKENS: ClassVar[t.StrSequence] = (
        "dispatcher",
        "dispatch",
        "command",
        "query",
        "event",
    )
    "Tokens indicating dispatcher-related code."
    NAMESPACE_PREFIXES: ClassVar[t.StrMapping] = MappingProxyType({
        "utility": "FlextUtilities",
        "models": "FlextModels",
        "decorators": "d",
        "dispatcher": "FlextDispatcher",
    })
    "Namespace → class prefix mapping for violation classification."
    CLASSIFICATION_PRIORITY: ClassVar[t.StrSequence] = (
        "dispatcher",
        "decorators",
        "models",
        "utility",
    )
    "Priority order for violation classification."
    MIN_PATH_DEPTH: int = 2
    "Minimum relative path depth for module prefix detection."
    NAMESPACE_CONSTANT_PATTERN: ClassVar[t.RegexPattern] = re.compile(
        r"^_?[A-Z][A-Z0-9_]+$"
    )
    "Regex: namespace constant candidate names."
    CLASSVAR_EXEMPT_NAMES: ClassVar[frozenset[str]] = (
        c.ENFORCEMENT_CLASSVAR_EXEMPT_NAMES
    )
    "ClassVar attribute names that are framework idioms and stay in place (SSOT: flext-core)."
    CLASSVAR_ALLOWED_CALLS: ClassVar[frozenset[str]] = frozenset({
        "Path",
        "PurePath",
        "PosixPath",
        "WindowsPath",
        "frozenset",
        "tuple",
        "dict",
        "list",
        "set",
        "MappingProxyType",
    })
    "Canonical factory calls allowed as ClassVar default values."
    NAMESPACE_MIN_ALIAS_LENGTH: ClassVar[int] = 2
    FACADE_ALIAS_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(\w)\b[^=]*=\s*(\w+)", re.MULTILINE
    )
    "Matches ``m = FlextFooModels`` alias assignments in facade files."

    # --- Detector regex constants ---
    ASSIGN_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^([A-Z_]\w*)\s*[:=]", re.MULTILINE
    )
    "Matches top-level UPPER_CASE assignments for loose constant detection."
    LOGGER_ASSIGN_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^([A-Za-z_]\w*)\s*[:=]\s*(?:(?:\w+\.)*)?"
        r"(?:fetch_logger|create_module_logger|get_logger|logging\.getLogger)\s*\(",
        re.IGNORECASE | re.MULTILINE,
    )
    "Matches top-level logger assignments created outside namespace classes."
    PEP695_RE: ClassVar[t.RegexPattern] = re.compile(r"^type\s+(\w+)\s*=", re.MULTILINE)
    "Matches PEP 695 type alias definitions."
    TYPEALIAS_ANNOT_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(\w+)\s*:\s*(?:\w+\.)*TypeAlias\s*=", re.MULTILINE
    )
    "Matches TypeAlias annotation syntax for typing alias detection."
    TYPING_FACTORY_ASSIGN_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(\w+)\s*=\s*(?:(?:\w+\.)*)?"
        r"(?:TypeVar|ParamSpec|TypeVarTuple|NewType)\s*\(",
        re.MULTILINE,
    )
    "Matches TypeVar/ParamSpec/TypeVarTuple/NewType assignments."
    COMPAT_ALIAS_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^([A-Z]\w+)\s*=\s*([A-Z]\w+)\s*$", re.MULTILINE
    )
    "Matches compatibility alias assignments (CapitalName = CapitalName)."
    COMPAT_SKIP_NAMES: ClassVar[frozenset[str]] = frozenset({
        "__all__",
        "__version__",
        "__version_info__",
    })
    "Names to skip during compatibility alias detection."
    ENFORCEMENT_CANONICAL_ALIASES: ClassVar[frozenset[str]] = (
        c.ENFORCEMENT_CANONICAL_ALIASES
    )
    "Canonical short aliases exposed by FLEXT facades (SSOT: flext-core)."
    ENFORCEMENT_PROJECT_ALIAS_OWNERS: ClassVar[t.StrSequenceMapping] = (
        c.ENFORCEMENT_PROJECT_ALIAS_OWNERS
    )
    "Project package → canonical aliases it re-exports locally (SSOT: flext-core)."
    # flext-j47u: consume core enforcement data through its exact canonical alias.
    ENFORCEMENT_LIBRARY_OWNERS: ClassVar[t.StrMapping] = c.ENFORCEMENT_LIBRARY_OWNERS
    "External library → project that owns its abstraction facade (SSOT: flext-core)."
    FUTURE_ANNOTATIONS_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^from\s+__future__\s+import\s+annotations\b", re.MULTILINE
    )
    "Matches 'from __future__ import annotations' import statement."
    ONLY_DOCSTRING_RE: ClassVar[t.RegexPattern] = re.compile(
        r'^("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')\s*$'
    )
    "Matches files that contain only a module docstring."
    MIN_METHODS_FOR_REORDER: ClassVar[int] = 2
    "Minimum method count before class method reordering is attempted."

    # --- Method category StrEnum (was: plain class MethodCategory) ---
    @unique
    class MethodCategory(StrEnum):
        """Canonical method category identifiers for FLEXT reordering."""

        MAGIC = "magic"
        PROPERTY = "property"
        STATIC = "static"
        CLASS = "class"
        PUBLIC = "public"
        PROTECTED = "protected"
        PRIVATE = "private"

    # --- Scan constants (was: class Scan) ---
    SCAN_ALLOWED_TOP_LEVEL: ClassVar[frozenset[str]] = frozenset({
        "__all__",
        "__version__",
        "__version_info__",
    })
    "Top-level names allowed without namespace classification."
    NAMESPACE_PRIVATE_BASE_MODULE: ClassVar[str] = "_base.py"
    "Private base module name allowed to host private FLEXT base contracts."
    NAMESPACE_PRIVATE_BASE_CLASS_SUFFIXES: ClassVar[frozenset[str]] = frozenset({
        "Base",
        "Mixin",
        "Typing",
    })
    "Allowed suffixes for multiple private classes in a private base module."
    NAMESPACE_PYTEST_MODULE_PREFIX: ClassVar[str] = "test_"
    "Pytest module prefix exempt from production loose-object structure checks."
    NAMESPACE_PYTEST_MODULE_SUFFIXES: ClassVar[frozenset[str]] = frozenset({
        "_test.py",
        "_tests.py",
    })
    "Pytest module suffixes exempt from production loose-object structure checks."

    ACCESSOR_WARNING_PREFIXES: ClassVar[frozenset[str]] = frozenset({
        "get_",
        "set_",
        "is_",
    })
    "Public accessor name prefixes that should be renamed (drop the prefix or use a canonical verb)."

    # --- Symbol/identifier patterns ---
    IDENTIFIER_PATTERN: ClassVar[t.RegexPattern] = re.compile(r"\b[A-Za-z_]\w*\b")
    "Regex: Python identifier word boundary match."

    # --- Import bypass pattern (for transformer matching) ---
    IMPORT_BYPASS_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^try:\n"
        r"(    from .+\n)"
        r"except ImportError:\n"
        r"    from .+\n",
        re.MULTILINE,
    )
    "Regex: try/except ImportError import bypass block (strict form)."

    # --- Deprecated class pattern ---
    CLASS_BLOCK_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(class\s+(\w+)\b[^\n]*:\n(?:(?:[ \t]+[^\n]*|[ \t]*)\n)*)", re.MULTILINE
    )
    "Regex: full class block including body lines."
    DEPRECATION_WARN_RE: ClassVar[t.RegexPattern] = re.compile(r"\.warn\s*\(")
    "Regex: deprecation warning call site (.warn())."

    # --- Lazy import fixer ---
    DEF_ASYNC_CLASS_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?:def |async def |class )", re.MULTILINE
    )
    "Regex: top-level def/async def/class keyword (for lazy import detection)."


__all__: list[str] = ["FlextInfraConstantsRefactor"]
