"""Promoted-command framework vocabulary for flext-infra.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from enum import StrEnum, unique
from typing import ClassVar

from flext_core import e

from .validate import FlextInfraConstantsSharedInfra


class FlextInfraConstantsPromoted:
    """``scripts/<verb>/<WHAT>`` command framework vocabulary for ``c.Infra``."""

    class PromotedRegistryError(e.ValidationError):
        """Raised when promoted command metadata or invocation is invalid."""

        _default_error_code: ClassVar[str] = "PROMOTED_REGISTRY_ERROR"

    class PromotedMissingHeaderError(PromotedRegistryError):
        """Raised when a file carries no ``cosmos-command`` header at all.

        A file without a header is not a promoted command; a present but invalid
        header is a defect, so the two never share an exception type.
        """

        _default_error_code: ClassVar[str] = "PROMOTED_MISSING_HEADER"

    @unique
    class PromotedHeader(StrEnum):
        """``cosmos-command`` header markers and TOML keys."""

        START = "/// cosmos-command"
        END = "///"
        COMMENT = "#"
        VERB = "verb"
        WHAT = "what"
        DOMAIN = "domain"
        SUMMARY = "summary"
        DESCRIPTION = "description"
        EXAMPLE = "example"
        MUTATES = "mutates"
        ALIASES = "aliases"
        PARAMS = "params"
        RULES = "rules"
        NAME = "name"
        HELP = "help"
        REQUIRED = "required"
        DEFAULT = "default"
        CHOICES = "choices"
        PARAMS_CHOICES = "params.choices"

    @unique
    class PromotedEnv(StrEnum):
        """Environment variables read or exported by the promoted dispatcher."""

        WHAT = "WHAT"
        HELP = "HELP"
        OPTIONS = "OPTIONS"
        DISPATCHED = "COSMOS_COMMAND_DISPATCHED"
        VERB = "COSMOS_COMMAND_VERB"
        COMMAND_WHAT = "COSMOS_COMMAND_WHAT"
        DOMAIN = "COSMOS_COMMAND_DOMAIN"
        PATH = "COSMOS_COMMAND_PATH"
        SUBMODULE_ROOT = "COSMOS_SUBMODULE_ROOT"
        VIRTUAL_ENV = "VIRTUAL_ENV"
        UV_PROJECT_ENVIRONMENT = "UV_PROJECT_ENVIRONMENT"
        PYTHON = "PYTHON"

    @unique
    class PromotedSelector(StrEnum):
        """Reserved WHAT, argument, and separator tokens of the dispatcher."""

        ALL = "all"
        HELP = "help"
        WHAT = "WHAT"
        VALIDATE = "--validate"
        HELP_PATH = "/"
        ALIAS = "="
        DISPATCHED = "Y"
        DISABLED = "N"
        BASH = "bash"
        PYTHON_SAFE_PATH = "-P"
        VENV_BIN = "bin"
        VENV_PYTHON = "python"
        INCIDENT_DOMAIN = "incident"
        SHELL_SUFFIX = ".sh"

    PROMOTED_HEADER_SCAN_LINES: ClassVar[int] = 160
    PROMOTED_COMMAND_SUFFIXES: ClassVar[frozenset[str]] = frozenset({
        PromotedSelector.SHELL_SUFFIX,
        FlextInfraConstantsSharedInfra.EXT_PYTHON,
    })
    PROMOTED_NON_COMMAND_NAMES: ClassVar[frozenset[str]] = frozenset({
        FlextInfraConstantsSharedInfra.DUNDER_PYCACHE,
        FlextInfraConstantsSharedInfra.INIT_PY,
    })
    PROMOTED_IGNORED_DIRS: ClassVar[frozenset[str]] = frozenset({
        FlextInfraConstantsSharedInfra.DUNDER_PYCACHE,
        "hooks",
        "legado",
        "lib",
    })
    PROMOTED_INCIDENT_MUTATION_REQUIRED_PARAMS: ClassVar[frozenset[str]] = frozenset({
        "EMERGENCY",
        "BREAKING_GLASS_BEAD",
    })
    PROMOTED_VERB_HELP_SELECTORS: ClassVar[frozenset[str]] = frozenset({
        "",
        PromotedSelector.HELP,
    })
    PROMOTED_GLOBAL_HELP_SELECTORS: ClassVar[frozenset[str]] = frozenset({
        *PROMOTED_VERB_HELP_SELECTORS,
        PromotedSelector.ALL,
    })
    PROMOTED_HELP_ARGS: ClassVar[frozenset[str]] = frozenset({
        PromotedSelector.HELP,
        "--help",
        "-h",
    })
    PROMOTED_ENV_ENABLED_VALUES: ClassVar[frozenset[str]] = frozenset({
        "1",
        "Y",
        "YES",
        "TRUE",
    })


__all__: list[str] = ["FlextInfraConstantsPromoted"]
