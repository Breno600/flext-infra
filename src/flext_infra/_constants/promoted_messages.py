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
    from flext_infra import t


class FlextInfraConstantsPromotedMessages:
    """Promoted-command message and help vocabularies for ``c.Infra``."""

    @unique
    class PromotedMessage(StrEnum):
        """Registry, discovery, and execution diagnostics."""

        MISSING_HEADER = "{path}: sem header cosmos-command"
        INVALID_HEADER_TOML = "{path}: header TOML invalido"
        REQUIRED_STRING = "{path}: campo obrigatorio ausente: {key}"
        REQUIRED_BOOL = "{path}: campo booleano obrigatorio ausente: {key}"
        INVALID_ALIAS = "{path}: alias invalido {alias!r}; use alias ou alias=WHAT"
        STRING_LIST_TYPE = "{path}: {key} deve ser lista de strings"
        STRING_LIST_ITEM = "{path}: {key} invalido"
        MISSING_PARAM = "{verb} WHAT={what}: parametro obrigatorio ausente: {name}; exemplo: {example}"
        INVALID_CHOICE = (
            "{verb} WHAT={what}: {name}={value!r} invalido; validos: {valid}"
        )
        ALL_CHOICES_DIVERGE = "{path}: choices de WHAT divergem dos comandos promovidos para {verb}: declared={declared} actual={actual}"
        PARAM_MUST_BE_REQUIRED = "{path}: parametro {name} deve ser obrigatorio"
        DUPLICATE_COMMAND = "comando duplicado: {verb} WHAT={what}"
        DUPLICATE_ALIAS = "alias duplicado: {alias} aponta para {previous_verb} WHAT={previous_what} e {verb} WHAT={what}"
        NO_COMMANDS = "nenhum comando promovido encontrado em scripts/<verbo>/<WHAT>"
        VERB_DOMAINS = "verbo '{verb}' declara mais de um domain: {domains}"
        ALIAS_OUTSIDE_ALL = "{path}: aliases devem ser declarados apenas em WHAT=all"
        ALIAS_COLLIDES_VERB = "alias '{alias}' colide com verbo promovido"
        ALIAS_UNKNOWN_VERB = "alias '{alias}' aponta para verbo desconhecido {verb}"
        ALIAS_UNKNOWN_WHAT = (
            "alias '{alias}' aponta para {verb} WHAT={what}, mas a acao nao existe"
        )
        UNKNOWN_VERB = "verbo '{verb}' desconhecido"
        INVALID_WHAT = "WHAT='{what}' invalido para {verb}. Validos: {valid}"
        NO_SCRIPTS_DIR = "nenhum diretorio scripts encontrado"
        INVALID_SCRIPTS_ENTRY = "{path}: entrada invalida em {root}"
        NESTED_DIR = "{path}: diretorio aninhado nao e comando publico"
        INVALID_SUFFIX = "{path}: arquivo publico deve ser .sh ou .py"
        VERB_MISMATCH = "{path}: header verb={verb} differs from directory {expected}"
        WHAT_MISMATCH = "{path}: header what={what} differs from file {expected}"
        PARAMS_NOT_LIST = "{path}: params must be a list of TOML objects"
        PARAMS_NOT_TABLE = "{path}: params must contain TOML objects"
        PARAMS_REQUIRED_TYPE = "{path}: params.required must be a boolean"
        PARAMS_DEFAULT_TYPE = "{path}: params.default must be a string"
        BASH_MISSING = "bash nao encontrado no PATH; comandos .sh exigem bash"
        PROCESS_START_FAILED = "command process could not start"
        WORKSPACE_PYTHON_MISSING = "Workspace Python is missing: {python}; run make setup at the workspace root"
        OWNER_UNKNOWN = "Command owner project is unknown: {path}"
        LOCAL_PYTHON_MISSING = (
            "Python local ausente: {python}; crie/sincronize .venv antes de usar make"
        )
        ACTIVE_PYTHON_MISMATCH = (
            "Python ativo nao e o esperado: {python}; use make com PATH da .venv"
        )
        NOT_DISPATCHED = "ERRO: comandos publicos devem ser executados via make <verbo> WHAT=<acao>\n"

    @unique
    class PromotedHelp(StrEnum):
        """Help line templates rendered from the discovered registry."""

        GLOBAL_HEADER = "cosmos - make <verbo> WHAT=<acao> [PARAM=value ...]"
        GLOBAL_LINE = "  {verb:14} [{domain:12}] {summary}{suffix}"
        ALIAS_SUFFIX = " (alias: {aliases})"
        VERB_HEADER = "make {verb} WHAT=<WHAT>{suffix}"
        VERB_WHATS = "WHAT disponiveis:"
        VERB_LINE = "  {what:20} [{domain:12}] {summary}{marker}"
        MUTATES_MARKER = " [mutates]"
        VERB_OPTIONS = "Opcoes por WHAT:"
        VERB_OPTION_LINE = "  {what:20} {params}"
        VERB_DETAIL = "Detalhe de uma acao:"
        VERB_DETAIL_HELP = "  make help WHAT={verb}/<WHAT>"
        VERB_DETAIL_OPTIONS = "  make {verb} WHAT=<WHAT> OPTIONS=Y"
        RULES = "Regras:"
        RULE_LINE = "  - {item}"
        EXAMPLES = "Exemplos:"
        EXAMPLE = "Exemplo:"
        EXAMPLE_LINE = "  {item}"
        COMMAND_HEADER = "make {verb} WHAT={what}"
        COMMAND_DOMAIN = "Dominio: {domain}"
        COMMAND_MUTATES = "Muta: {mutates}"
        YES = "sim"
        NO = "nao"
        PARAMS = "Parametros:"
        PARAM_LINE = "  {name:24} {help}{required}{default}{choices}"
        PARAM_REQUIRED = " obrigatorio"
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
        "make <verbo> mostra o help do verbo e todos os WHAT.",
        "make help WHAT=<verbo> mostra o mesmo help.",
        "make help WHAT=<verbo>/<acao> ou make <verbo> WHAT=<acao> OPTIONS=Y mostra uma acao.",
        "Mutating commands execute their declared operation directly.",
        "Novos comandos vivem em scripts/<verbo>/<WHAT>.sh|py com header cosmos-command.",
    )


__all__: list[str] = ["FlextInfraConstantsPromotedMessages"]
