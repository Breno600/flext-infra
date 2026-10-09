"""Constants namespace for flext_infra.refactor.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from enum import StrEnum, unique
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, ClassVar, Literal

from flext_core import c
from flext_infra._constants import FlextInfraConstantsBase

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsRefactor:
    """Shared constants for refactor modules."""

    MOD_SCAN_REPORT_RELATIVE_PATH: ClassVar[Path] = (
        Path(FlextInfraConstantsBase.REPORTS_DIR_NAME) / "refactor" / "mod-findings.json"
    )
    "Canonical single-file evidence snapshot for the latest mod scan."
    MOD_SCAN_REPORT_SCHEMA_VERSION: ClassVar[Literal[1]] = 1
    "Exact structured mod evidence schema version."
    MOD_SCAN_REPORT_MODE: ClassVar[int] = 0o644
    "Canonical permission bits for structured mod evidence."
    ACCESSOR_MIGRATION_REPORT_RELATIVE_PATH: ClassVar[Path] = (
        Path(FlextInfraConstantsBase.REPORTS_DIR_NAME) / "refactor" / "accessor-migration.json"
    )
    "Canonical single-file evidence snapshot for the latest accessor migration."
    NAMESPACE_ENFORCE_REPORT_RELATIVE_PATH: ClassVar[Path] = (
        Path(FlextInfraConstantsBase.REPORTS_DIR_NAME) / "refactor" / "namespace-enforce.json"
    )
    "Canonical single-file evidence snapshot for the latest namespace enforcement."
    VIOLATIONS_SWEEP_ROUTE_NAME: ClassVar[str] = "violations-sweep"
    "Canonical refactor CLI verb that repairs and proves the always-reducing law."
    VIOLATIONS_SWEEP_REPORT_RELATIVE_PATH: ClassVar[Path] = (
        Path(FlextInfraConstantsBase.REPORTS_DIR_NAME) / "refactor" / "violations-sweep.json"
    )
    "Canonical single-file receipt for the latest violations sweep."
    VIOLATIONS_SWEEP_REPORT_SCHEMA_VERSION: ClassVar[Literal[1]] = 1
    "Exact structured violations-sweep report schema version."
    VIOLATIONS_SWEEP_REPAIR_VERBS: ClassVar[t.StrSequence] = ("fix", "fmt", "mod")
    "Canonical repair sequence the sweep runs between its two mod scans."
    LINT_REPORT_COUNT_LINE: ClassVar[t.RegexPattern] = re.compile(
        r"^- lint: (?:PASS|FAIL) \((\d+) issues\)$",
        re.MULTILINE,
    )
    """The check report's generated lint line; its count is the repo's lint column."""
    AST_GREP_ERROR_FINDING_RECEIPT: ClassVar[str] = (
        "Error: {count} error(s) found in code."
    )
    "Exact first stderr line emitted for error-severity JSONL findings."
    AST_GREP_ERROR_FINDING_HELP: ClassVar[str] = (
        "Help: Scan succeeded and found error level diagnostics in the codebase."
    )
    "Exact second stderr line emitted for error-severity JSONL findings."
    IMPORT_NORMALIZATION_MAX_PASSES: ClassVar[int] = 24
    "Fixed-point pass ceiling for import normalization."
    IMPORT_LAW_OTHER_LAYER: ClassVar[str] = "other"
    "Import-layer slot of a module whose path names no declared layer."
    IMPORT_LAW_ROOT_SINGLETONS: ClassVar[frozenset[str]] = frozenset({
        "config",
        "settings",
    })
    "Root singletons and import layers of the config/settings law (ADR-005)."
    IMPORT_LAW_GUARD_ERRORS: ClassVar[frozenset[str]] = frozenset({
        "ImportError",
        "ModuleNotFoundError",
    })
    "Exceptions whose handlers make a ``try`` around imports an import guard."
    IMPORT_LAW_FAMILY_BASE_FILE: ClassVar[str] = "base.py"
    "File name of a private family's leaf base module."

    @unique
    class ImportPlacement(StrEnum):
        """Where the import law places one imported binding."""

        RUNTIME = "runtime"
        "The module import block."
        TYPING = "typing"
        "The module ``if TYPE_CHECKING:`` block (typing-only reverse edge)."
        BOUND = "bound"
        "Nowhere new: an equal module-level import already binds it."
        STAY = "stay"
        "Its current place: a reverse runtime use or a foreign binding."

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
    class CodemodRelocation(StrEnum):
        """Rope relocation a detection-only rule names in its metadata.

        The engine's own capability set: a rule declares which relocation
        repairs its findings, and the namespace phase runs that relocation
        over what the rule captured:

        - ``protocol`` / ``typing-alias``: move the declaration ``$NAME`` to
          its family owner;
        - ``future-annotations``: add the future import to the file;
        - ``module-import``: hoist the matched import statement to the
          module import block;
        - ``package-root-import``: rebind ``$NAME`` from ``$MODULE`` to that
          module's top-level package;
        - ``own-package-import``: rebind ``$NAME`` from ``$MODULE`` to the
          project's own package;
        - ``facade-class``: move class ``$NAME`` to the module of facade
          family ``$FAMILY``.
        """

        PROTOCOL = "protocol"
        TYPING_ALIAS = "typing-alias"
        FUTURE_ANNOTATIONS = "future-annotations"
        MODULE_IMPORT = "module-import"
        PACKAGE_ROOT_IMPORT = "package-root-import"
        OWN_PACKAGE_IMPORT = "own-package-import"
        FACADE_CLASS = "facade-class"

    @unique
    class CodemodContextPredicate(StrEnum):
        """Project-context predicate a rule applies to one captured metavariable.

        ast-grep matches one file's syntax; what a match means can depend on
        the project and file it is in. A rule names the predicate under
        ``metadata.context`` for a captured ``$VAR`` and the engine admits the
        finding only when the predicate holds (``is``) or fails (``not``). Each
        predicate is derived from an existing source of truth:

        - ``stdlib-module``: the captured module's top-level name is in the
          interpreter's ``sys.stdlib_module_names``;
        - ``own-package``: it is the project's own import package (the
          package of its ``pyproject.toml`` project);
        - ``runtime-package``: it is the import package of a distribution in
          the project's runtime dependency closure;
        - ``facade-package``: it is a runtime package that publishes runtime
          aliases through its generated lazy exports;
        - ``runtime-alias``: the captured name is a runtime alias published
          by the package named by the ``of`` capture (the own package when
          ``of`` is absent);
        - ``local-alias``: it is a runtime alias the own package binds in its
          own modules (their ``__all__``);
        - ``module-export``: it is declared in the ``__all__`` of the
          finding's own module;
        - ``package-export``: it is declared in the ``__all__`` of the module
          named by the ``of`` capture;
        - ``file-family``: it is a facade letter (tooling import-layer order)
          of the family the finding's module belongs to: the letters its own
          ``__all__`` declares and those its private family package's facade
          module declares;
        - ``facade-module``: the finding's module declares a facade letter in
          its ``__all__`` (the captured value is not read);
        - ``later-layer``: the captured import (a module of the own package or
          a facade letter) belongs to a later layer of the import-layer order
          than the finding's module;
        - ``import-cycle``: the captured import (module as written, with the
          imported name as ``of``) is an edge of a runtime import cycle of the
          project's import graph;
        - ``composes-family``: the captured class of a facade module reaches,
          through its bases, every class the facade's family package
          declares in ``__all__``;
        - ``class-stem``: the captured class name starts with the project's
          class stem as class nesting derives it (``Tests`` + stem under the
          tests tree; ``Examples``/``Scripts`` + stem or the bare stem under
          those surfaces);
        - ``package-layers``: the finding's package provides every layer the
          rule names in ``arg`` (a declared facade letter, a module, a
          private module or a subpackage of that name);
        - ``family-base``: the private family package holding the finding's
          module begins with ``base.py``.

        ``later-layer`` compares with the layer the rule names in ``arg`` when
        it names one.
        """

        STDLIB_MODULE = "stdlib-module"
        OWN_PACKAGE = "own-package"
        RUNTIME_PACKAGE = "runtime-package"
        FACADE_PACKAGE = "facade-package"
        RUNTIME_ALIAS = "runtime-alias"
        LOCAL_ALIAS = "local-alias"
        MODULE_EXPORT = "module-export"
        PACKAGE_EXPORT = "package-export"
        FILE_FAMILY = "file-family"
        FACADE_MODULE = "facade-module"
        LATER_LAYER = "later-layer"
        IMPORT_CYCLE = "import-cycle"
        COMPOSES_FAMILY = "composes-family"
        CLASS_STEM = "class-stem"
        PACKAGE_LAYERS = "package-layers"
        PACKAGE_ROOT_INIT = "package-root-init"
        FAMILY_BASE = "family-base"
        PAYLOAD_DECLARATION = "payload-declaration"
        RESOLVED_SYMBOL = "resolved-symbol"
        SAME_BINDING = "same-binding"
        EXECUTABLE_OCCURRENCE = "executable-occurrence"
        UNREFERENCED_IMPORT = "unreferenced-import"

    CODEMOD_RUNTIME_CLOSURE_PREDICATES: ClassVar[frozenset[CodemodContextPredicate]] = (
        frozenset({
            CodemodContextPredicate.RUNTIME_PACKAGE,
            CodemodContextPredicate.FACADE_PACKAGE,
        })
    )
    "Predicates evaluated against the project's runtime dependency closure."

    @unique
    class SemanticCutoverPhase(StrEnum):
        """Semantic ``make mod`` cutovers planned by ``u.Infra``."""

        DECLARATION_RELOCATION = "declaration-relocation"
        CLASS_NESTING = "class-nesting"
        COMPAT_ALIAS = "compat-alias"
        PRIVATE_IMPORT = "private-import"
        FACADE_BASE = "facade-base"
        MODEL_FIELDS = "model-fields"
        SELF_FACADE_IMPORT = "self-facade-import"
        DYNAMIC_ENVIRONMENT = "dynamic-environment"
        MODULE_END = "module-end"
        NOTICE_LAST = "notice-last"

    SEMANTIC_CUTOVER_RULE_IDS: ClassVar[t.MappingKV[str, str]] = MappingProxyType({
        SemanticCutoverPhase.DECLARATION_RELOCATION: (
            "ban-nested-payload-outside-models"
        ),
        SemanticCutoverPhase.COMPAT_ALIAS: "ban-compat-alias",
        SemanticCutoverPhase.PRIVATE_IMPORT: "ban-private-import",
        SemanticCutoverPhase.FACADE_BASE: "facade-base-by-class-name",
        SemanticCutoverPhase.MODEL_FIELDS: (
            "rewire-getattr-model-fields-to-direct-access"
        ),
        SemanticCutoverPhase.SELF_FACADE_IMPORT: (
            "ban-infra-utility-module-self-facade-import"
        ),
        SemanticCutoverPhase.DYNAMIC_ENVIRONMENT: "ban-ambient-environ-read",
        SemanticCutoverPhase.MODULE_END: "require-all-last",
        SemanticCutoverPhase.NOTICE_LAST: "require-notice-last",
    })
    "ast-grep rule whose findings select each finding-driven semantic cutover."

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
    CODEMOD_RULE_SUFFIX: ClassVar[str] = ".yml"
    CODEMOD_DOCUMENT_SEPARATOR_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^---\s*$",
        re.MULTILINE,
    )
    CODEMOD_CONFIG_FILENAME: ClassVar[str] = "sgconfig.yml"
    # Static rules are data under the one rule root, config/rules: the
    # ast-grep corpus (sgconfig, rules, utils, tests with snapshots) and the
    # rope phase data. The same relative path names a governed checkout's
    # catalog and the copy a distribution ships as <pkg>/config.
    CODEMOD_RULES_RELPATH: ClassVar[Path] = Path("config") / "rules"
    CODEMOD_CONFIG_RELPATH: ClassVar[Path] = (
        CODEMOD_RULES_RELPATH / "ast-grep" / CODEMOD_CONFIG_FILENAME
    )
    CODEMOD_ROPE_RULES_RELPATH: ClassVar[Path] = CODEMOD_RULES_RELPATH / "rope"
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
        CODEMOD_RULES_RELPATH / "mod" / CODEMOD_TEXT_RULES_FILENAME
    )
    CODEMOD_TEXT_RULES_KEY: ClassVar[str] = "rules"
    CODEMOD_TEXT_KEY_ID: ClassVar[str] = "id"
    CODEMOD_TEXT_KEY_DESCRIPTION: ClassVar[str] = "description"
    CODEMOD_TEXT_KEY_INCLUDE: ClassVar[str] = "include"
    CODEMOD_TEXT_KEY_EXCLUDE: ClassVar[str] = "exclude"
    CODEMOD_TEXT_KEY_DISTRIBUTIONS: ClassVar[str] = "distributions"
    CODEMOD_TEXT_KEY_FIND: ClassVar[str] = "find"
    CODEMOD_TEXT_KEY_REPLACE: ClassVar[str] = "replace"
    CODEMOD_TEXT_KEY_FLAGS: ClassVar[str] = "flags"
    CODEMOD_TEXT_KEY_EXPECTED: ClassVar[str] = "expected"
    CODEMOD_TEXT_KEY_CAPTURE_EQUALS: ClassVar[str] = "capture_equals"
    # ast-grep rejects unknown top-level keys, so an ast-grep rule declares
    # its finding-count receipt under the `metadata` mapping it does accept.
    CODEMOD_RULE_METADATA_KEY: ClassVar[str] = "metadata"
    # A rule scoped to everything but its owning project names that project's
    # distribution under `metadata.owner`; the plan of the owner drops it.
    CODEMOD_RULE_OWNER_KEY: ClassVar[str] = "owner"
    # A rule that binds only the consumers of a facade distribution names it
    # under `metadata.consumers_of`; a plan whose runtime closure lacks that
    # distribution (the owner itself and its own dependencies) drops it.
    CODEMOD_RULE_CONSUMERS_OF_KEY: ClassVar[str] = "consumers_of"
    # A detection-only rule names the rope relocation that repairs it under
    # `metadata.relocation` and captures the relocated symbol as `$NAME`.
    CODEMOD_RULE_RELOCATION_KEY: ClassVar[str] = "relocation"
    # A rule whose meaning depends on the project names, per captured
    # metavariable, the context predicate the engine checks on each finding
    # (`metadata.context: {VAR: {is|not: predicate}}`).
    CODEMOD_RULE_CONTEXT_KEY: ClassVar[str] = "context"
    CODEMOD_CONTEXT_HOLDS_KEY: ClassVar[str] = "is"
    CODEMOD_CONTEXT_FAILS_KEY: ClassVar[str] = "not"
    CODEMOD_CONTEXT_OF_KEY: ClassVar[str] = "of"
    CODEMOD_CONTEXT_ARG_KEY: ClassVar[str] = "arg"
    CODEMOD_CONTEXT_AS_KEY: ClassVar[str] = "as"
    CODEMOD_RULE_NAME_METAVARIABLE: ClassVar[str] = "NAME"
    CODEMOD_RULE_MODULE_METAVARIABLE: ClassVar[str] = "MODULE"
    CODEMOD_RULE_FAMILY_METAVARIABLE: ClassVar[str] = "FAMILY"
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
        FlextInfraConstantsBase.RK_ID,
        FlextInfraConstantsBase.NAME,
        FlextInfraConstantsBase.RK_DESCRIPTION,
        FlextInfraConstantsBase.RK_ENABLED,
        FlextInfraConstantsBase.RK_SEVERITY,
    )
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

    TYPING_FACTORY_ASSIGN_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(\w+)\s*=\s*(?:(?:\w+\.)*)?"
        r"(?:TypeVar|ParamSpec|TypeVarTuple|NewType)\s*\(",
        re.MULTILINE,
    )
    "Matches TypeVar/ParamSpec/TypeVarTuple/NewType assignments."
    ENFORCEMENT_CANONICAL_ALIASES: ClassVar[frozenset[str]] = (
        c.ENFORCEMENT_CANONICAL_ALIASES
    )
    "Canonical short aliases exposed by FLEXT facades (SSOT: flext-core)."
    # Consume core enforcement data through its exact canonical alias.
    ENFORCEMENT_LIBRARY_OWNERS: ClassVar[t.StrMapping] = c.ENFORCEMENT_LIBRARY_OWNERS
    "External library → project that owns its abstraction facade (SSOT: flext-core)."
    "Matches 'from __future__ import annotations' import statement."
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

    NAMESPACE_PRIVATE_BASE_MODULE: ClassVar[str] = "_base.py"
    "Private base module name allowed to host private FLEXT base contracts."
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
    "Public accessor prefixes to rename (drop the prefix or use a canonical name)."

    # --- Symbol/identifier patterns ---
    IDENTIFIER_PATTERN: ClassVar[t.RegexPattern] = re.compile(r"\b[A-Za-z_]\w*\b")
    "Regex: Python identifier word boundary match."


__all__: list[str] = ["FlextInfraConstantsRefactor"]
