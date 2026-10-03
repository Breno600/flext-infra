"""Base typings for flext-infra project.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast as _ast
from collections.abc import Callable, Container as _Container, MutableMapping
from datetime import date, datetime
from pathlib import Path as _Path
from typing import Annotated, Literal

# Why: flext_cli owns the pipeline models/result contract; flext_core's m/p
# have no nested Cli namespace, so the pipeline handler alias below needs
# flext_cli's own m/p under a distinct name. The import stays at runtime on
# purpose: flext-cli's lazy __init__ keeps it cheap, flext-cli never imports
# flext-infra (no cycle), and the runtime census gate evaluates every alias's
# __value__, so a TYPE_CHECKING-only import would explode as NameError.
from flext_cli import m, m as _cli_m, p as _cli_p, t
from jinja2.environment import (
    Environment as _JinjaEnvironment,
    Template as _JinjaTemplate,
)


class FlextInfraTypesBase:
    """Base typings for flext-infra project."""

    @staticmethod
    def _reject_blanket_mask(rule: str) -> str:
        """Return the bare Ruff rule name, rejecting ``ALL``, padding and codes.

        Normalizing here keeps the rendered TOML free of accidental padding: a
        padded name would otherwise reach a generated pyproject verbatim and no
        longer match the rule Ruff knows. Ruff identifies a rule by its
        kebab-case name (``line-too-long``), so a code (``E501``) is refused.

        Returns:
            The bare rule name.

        Raises:
            ValueError: If the value is blank padding, ``ALL``, or not a
                kebab-case Ruff rule name.

        """
        normalized = rule.strip()
        if not normalized:
            message = "a Ruff exemption must name a rule, not blank padding."
            raise ValueError(message)
        if normalized.upper() == "ALL":
            message = (
                "ALL is not a Ruff exemption: it masks every rule, present and "
                "future. Name each suppressed rule instead."
            )
            raise ValueError(message)
        if not (normalized.islower() and normalized.replace("-", "").isalnum()):
            message = (
                f"{normalized!r} is not a Ruff rule name: name the rule in "
                "kebab-case (line-too-long), never by its code (E501)."
            )
            raise ValueError(message)
        return normalized

    type PlanSourceTimestamp = str | date | datetime | None
    "Native YAML timestamp ingress; dates retain their original precision."
    type DocsRenderedArtifactTuple = t.Triple[_Path, _Path, str | None]
    "Rendered document destination, source, and optional project owner."

    type RegexPattern = t.RegexPattern
    "Compiled regex pattern for string matching."
    type RegexMatch = t.RegexMatch
    "Regex match object for string patterns."
    type JinjaEnvironment = _JinjaEnvironment
    "Jinja2 template rendering environment."
    type JinjaTemplate = _JinjaTemplate
    "Jinja2 template object."

    type ModelFieldSpec = m.FieldInfo
    "Field metadata a model-field factory returns, from the m facade."

    type InfraValue = t.JsonValue
    "Canonical infrastructure payload contract from flext-cli JSON typing."
    type FacadeFamily = str
    "Facade family identifier for FLEXT chain resolution."
    type ExpectedBase = type | str
    "Expected FLEXT base: a class or its qualified name."
    type MetricValue = t.Scalar | _Path | None
    "Output metric value: scalar (str/int/float/bool/datetime), path, or null."
    type ChangeCallback = Callable[[str], None] | None
    "Optional callback invoked on transformer changes."
    # Why: upstream flext_core.FlextTypingContainers is an empty stub (no
    # `Container` alias shipped in the pinned release); flext-infra's own
    # LibCST residue-matching consumer needs a membership-testable generic.
    type Container[ItemT] = _Container[ItemT]
    "Generic membership-testable collection (supports ``in``)."
    type PipelineHandler = Callable[
        [_cli_p.Cli.PipelineStageContext],
        _cli_p.Result[_cli_m.Cli.PipelineStageResult],
    ]
    "Stage handler contract for the flext-infra check/codegen DAG pipelines."
    type PipelineHandlerMap = t.MappingKV[str, PipelineHandler]
    "Stage-id to handler mapping used to build DAG pipeline stage specs."
    type LazyInitProcessResult = tuple[int | None, t.LazyAliasMap]
    "Result for per-directory lazy init processing."
    type LazyInitWriteResult = tuple[int, t.LazyAliasMap]
    "Result for writing generated __init__.py."
    type StrSet = set[str]
    "Mutable string set (supports .update/.intersection/etc)."
    type CanonicalValue = t.Scalar | t.StrSequence
    "Canonical governance value: scalar payload or string sequence."

    type CensusRecord = t.HeaderMapping
    "Single census record: string keys with str|int values (name, type, usages)."

    type InfraMapping = t.JsonMapping
    "Read-only validated infra payload mapping."
    type MutableInfraMapping = MutableMapping[str, InfraValue]
    "Mutable validated infra payload mapping."
    type InfraSequence = t.JsonList
    "Read-only validated infra payload sequence."
    type RuleSelection[KindT] = tuple[KindT, t.JsonMapping]
    "One matched rule kind paired with its validated declarative payload."
    type DomainResult = m.BaseModel | InfraValue
    "Typed service result payload: model or validated JSON value."
    type DomainResultSequence = t.SequenceOf[DomainResult]
    "Read-only sequence of typed service result payloads."
    type StubChainRuntimeState = MutableMapping[str, t.GuardInput | None]
    "Canonical model-construction payload for the stub supply-chain service."

    # ── Transformer / edit result types ──────────────────────────────

    type TransformResult = t.StrSequencePair
    "Canonical (new_source, change_descriptions) from any source transformer."
    type PrivateImportSpec = t.Quint[str, str, str, str, str]
    "(private module, symbol, qualified name, owner package, target reference)."
    type PrivateImportReferences = tuple[
        t.MappingKV[_Path, t.SequenceOf[PrivateImportSpec]],
        t.MappingKV[_Path, t.MappingKV[str, t.StrPair]],
        t.MappingKV[str, t.VariadicTuple[t.Quad[_ast.Module, str, str, str]]],
    ]
    "Resolved private-import specs, declared re-export targets, and facade owners."
    type EditResult = tuple[bool, t.StrSequence]
    "Validated edit outcome: (success, report_lines)."
    type EditResultWithDescs = tuple[bool, t.StrSequence, t.StrSequence]
    "(success, descriptions, report_lines) — includes what was attempted."
    type LintSnapshot = t.MappingKV[str, t.StrSequence]
    "Lint errors per tool: {tool_name: [error_lines]}."

    # ── Lint policy types ────────────────────────────────────────────

    type RuffRule = Annotated[
        str,
        t.StringConstraints(min_length=1),
        m.AfterValidator(_reject_blanket_mask),
    ]
    """One named Ruff rule exempted for a path.

    ``ALL`` is excluded by construction. It suppresses every rule, present and
    future, so it masks real defects and cannot be reviewed: the set it hides
    is unbounded and grows with each Ruff release. UNIVERSAL_CORE r19 requires
    an exemption to name its rule and carry its justification, which a mask
    cannot do. Rendering one into a generated pyproject would push it onto
    every consumer, so the boundary refuses it instead of a gate reporting it
    after the fact.
    """
    type PerFileIgnores = t.MappingKV[str, t.SequenceOf[RuffRule]]
    "Ruff per-file exemptions: {path_glob: [named_rule]}, never a blanket mask."

    type DocsPhase = Literal["audit", "build", "fix", "generate", "validate"]
    "Closed string set selecting which docs orchestrator phase to execute."
    type LayoutRule = Literal["move", "archive", "gitignore", "review"]
    "Closed layout decision kinds produced by the layout engine."
    type LayoutStatus = Literal["planned", "applied", "skipped", "noop"]
    "Closed layout finding execution statuses."
    type ReleaseArtifactKind = Literal["sdist", "wheel"]
    "Closed artifact kind emitted by a release build."
    type ReleaseAbsolutePath = Annotated[
        str,
        t.StringConstraints(min_length=1, pattern=r"^(?:/|[A-Za-z]:[\\/])"),
    ]
    "Absolute POSIX or Windows path serialized in a release report."
    type ReleaseArtifactSha256 = Annotated[
        str,
        t.StringConstraints(pattern=r"^[0-9a-f]{64}$"),
    ]
    "Lowercase SHA-256 digest serialized in a release report."
    type ReleaseCommitOid = Annotated[
        str,
        t.StringConstraints(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$"),
    ]
    "Lowercase Git SHA-1 or SHA-256 commit object identifier."
    # ── Git type aliases ────────────────────────────────────────────

    type GitOid = str
    "Canonical hex Git object identifier."
    type GitRef = str
    "Fully-qualified or short Git ref name."
    type GitPathSpec = str
    "Git pathspec string (e.g. ``:(exclude)dir``)."


__all__: list[str] = ["FlextInfraTypesBase"]
