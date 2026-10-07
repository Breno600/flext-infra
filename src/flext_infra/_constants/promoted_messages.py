"""Promoted-command diagnostics and help templates for flext-infra.

The rendered help and diagnostics are the operator-facing surface of every
repository dispatching ``make <verb> WHAT=<action>``; the wording is a fleet
contract (consumer gates match the dispatcher guard line), so the templates are
kept verbatim and rendered with ``str.format``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from enum import StrEnum, unique
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra._constants.typings import t


class FlextInfraConstantsPromotedMessages:
    """Promoted-command message and help vocabularies for ``c.Infra``."""

    @unique
    class PromotedMessage(StrEnum):
        """Registry, discovery, and execution diagnostics."""

        MISSING_HEADER = "{path}: missing flext-command header"
        INVALID_HEADER_TOML = "{path}: invalid header TOML"
        REQUIRED_STRING = "{path}: missing required field: {key}"
        REQUIRED_BOOL = "{path}: missing required boolean field: {key}"
        INVALID_ALIAS = "{path}: invalid alias {alias!r}; use alias or alias=WHAT"
        STRING_LIST_TYPE = "{path}: {key} must be a list of strings"
        STRING_LIST_ITEM = "{path}: invalid {key}"
        MISSING_PARAM = (
            "{verb} WHAT={what}: missing required parameter: {name}; example: {example}"
        )
        INVALID_CHOICE = "{verb} WHAT={what}: invalid {name}={value!r}; valid: {valid}"
        ALL_CHOICES_DIVERGE = (
            "{path}: WHAT choices differ from the promoted commands of"
            " {verb}: declared={declared} actual={actual}"
        )
        PARAM_MUST_BE_REQUIRED = "{path}: parameter {name} must be required"
        DUPLICATE_COMMAND = "duplicate command: {verb} WHAT={what}"
        DUPLICATE_ALIAS = (
            "duplicate alias: {alias} points to {previous_verb}"
            " WHAT={previous_what} and {verb} WHAT={what}"
        )
        NO_COMMANDS = "no promoted command found in scripts/<verb>/<WHAT>"
        VERB_DOMAINS = "verb '{verb}' declares more than one domain: {domains}"
        ALIAS_OUTSIDE_ALL = "{path}: aliases may be declared only in WHAT=all"
        ALIAS_COLLIDES_VERB = "alias '{alias}' collides with a promoted verb"
        ALIAS_UNKNOWN_VERB = "alias '{alias}' points to unknown verb {verb}"
        ALIAS_UNKNOWN_WHAT = (
            "alias '{alias}' points to {verb} WHAT={what},"
            " but the action does not exist"
        )
        UNKNOWN_VERB = "unknown verb '{verb}'"
        INVALID_WHAT = "invalid WHAT='{what}' for {verb}. Valid: {valid}"
        NO_SCRIPTS_DIR = "no scripts directory found"
        INVALID_SCRIPTS_ENTRY = "{path}: invalid entry in {root}"
        NESTED_DIR = "{path}: a nested directory is not a public command"
        INVALID_SUFFIX = "{path}: a public file must be .sh or .py"
        VERB_MISMATCH = "{path}: header verb={verb} differs from directory {expected}"
        WHAT_MISMATCH = "{path}: header what={what} differs from file {expected}"
        PARAMS_NOT_LIST = "{path}: params must be a list of TOML objects"
        PARAMS_NOT_TABLE = "{path}: params must contain TOML objects"
        PARAMS_REQUIRED_TYPE = "{path}: params.required must be a boolean"
        PARAMS_DEFAULT_TYPE = "{path}: params.default must be a string"
        BASH_MISSING = "bash not found on PATH; .sh commands require bash"
        PROCESS_START_FAILED = "command process could not start"
        WORKSPACE_PYTHON_MISSING = (
            "Workspace Python is missing: {python};"
            " run make setup at the workspace root"
        )
        OWNER_UNKNOWN = "Command owner project is unknown: {path}"
        LOCAL_PYTHON_MISSING = (
            "Local Python is missing: {python}; create or sync .venv before using make"
        )
        ACTIVE_PYTHON_MISMATCH = (
            "Active Python is not the expected one: {python};"
            " run make with the .venv PATH"
        )
        NOT_DISPATCHED = (
            "ERROR: public commands must run through make <verb> WHAT=<action>\n"
        )

    @unique
    class PromotedHelp(StrEnum):
        """Help line templates rendered from the discovered registry."""

        GLOBAL_HEADER = "make <verb> WHAT=<action> [PARAM=value ...]"
        GLOBAL_LINE = "  {verb:14} [{domain:12}] {summary}{suffix}"
        ALIAS_SUFFIX = " (alias: {aliases})"
        VERB_HEADER = "make {verb} WHAT=<WHAT>{suffix}"
        VERB_WHATS = "Available WHAT:"
        VERB_LINE = "  {what:20} [{domain:12}] {summary}{marker}"
        MUTATES_MARKER = " [mutates]"
        VERB_OPTIONS = "Options per WHAT:"
        VERB_OPTION_LINE = "  {what:20} {params}"
        VERB_DETAIL = "Details of one action:"
        VERB_DETAIL_HELP = "  make help WHAT={verb}/<WHAT>"
        VERB_DETAIL_OPTIONS = "  make {verb} WHAT=<WHAT> OPTIONS=Y"
        RULES = "Rules:"
        RULE_LINE = "  - {item}"
        EXAMPLES = "Examples:"
        EXAMPLE = "Example:"
        EXAMPLE_LINE = "  {item}"
        COMMAND_HEADER = "make {verb} WHAT={what}"
        COMMAND_DOMAIN = "Domain: {domain}"
        COMMAND_MUTATES = "Mutates: {mutates}"
        YES = "yes"
        NO = "no"
        PARAMS = "Parameters:"
        PARAM_LINE = "  {name:24} {help}{required}{default}{choices}"
        PARAM_REQUIRED = " required"
        PARAM_DEFAULT = "default={default}"
        PARAM_CHOICES = "choices={choices}"
        INLINE_REQUIRED = "*"
        INLINE_DETAIL = "{rendered}({detail})"
        MAKE_VERB = "make {verb}"
        CANONICAL_EXAMPLE = "{canonical} WHAT={what}"

    @unique
    class PromotedJoin(StrEnum):
        """Separators joining rendered help and diagnostic values."""

        LIST = ", "
        VALUES = ","
        DETAIL = ";"
        CHOICES = "|"
        WORDS = " "
        LINES = "\n"

    PROMOTED_HELP_GLOBAL_FOOTER: ClassVar[t.VariadicTuple[str]] = (
        "",
        "make <verb> shows the verb help and every WHAT.",
        "make help WHAT=<verb> shows the same help.",
        (
            "make help WHAT=<verb>/<action> or make <verb> WHAT=<action>"
            " OPTIONS=Y shows one action."
        ),
        "Mutating commands execute their declared operation directly.",
        "New commands live in scripts/<verb>/<WHAT>.sh|py with a flext-command header.",
    )


__all__: list[str] = ["FlextInfraConstantsPromotedMessages"]
