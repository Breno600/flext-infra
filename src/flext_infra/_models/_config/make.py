"""Make workflow, verb, CI, and cache specification models."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Literal, Self

from flext_cli import m, u

from ... import t
from ..._constants import (
    FlextInfraConstantsCheck,
    FlextInfraConstantsCodegenProject,
    FlextInfraConstantsDocs,
    FlextInfraConstantsMake,
)
from .._defaults import FlextInfraModelsDefaults
from .contract import FlextInfraConfigModelsContract


class FlextInfraConfigModelsMake:
    """Make workflow, verb, CI, and cache specification models."""

    class MakeGateSuspensionSpec(FlextInfraConfigModelsContract.ConfigContract):
        """An explicitly authorized policy gate excluded from default execution."""

        gate: Annotated[t.NonEmptyStr, m.Field(description="Suspended gate id")]
        authority: Annotated[
            t.NonEmptyStr,
            m.Field(description="Bead and operator decision authorizing suspension"),
        ]
        reason: Annotated[
            t.NonEmptyStr, m.Field(description="Reason recorded in gate receipts")
        ]

        @u.model_validator(mode="after")
        def _validate_evidence(self) -> Self:
            """Whitespace cannot stand in for an authority or a rationale."""
            if not self.authority.strip() or not self.reason.strip():
                msg = "make gate suspension requires authority and reason"
                raise ValueError(msg)
            return self

    class MakeCiSpec(FlextInfraConfigModelsContract.ConfigContract):
        """The only permitted environment delta between local and CI execution."""

        variable: Annotated[t.NonEmptyStr, m.Field(description="CI environment key")]
        value: Annotated[t.NonEmptyStr, m.Field(description="CI environment value")]
        local_value: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Local form of the CI ternary. Check runs the active local "
                    "partition; other pre-push verbs declare this value to "
                    "preserve their local behavior. Pre-push check unsets CI."
                )
            ),
        ] = "N"
        local_check_gates: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Gate ids run by make check under the local CI token: the "
                    "slow whole-program type checkers. This is the ONLY "
                    "declared set; the CI token runs its strict complement and "
                    "an unset token runs every active default gate."
                )
            ),
        ]

        @u.model_validator(mode="after")
        def _validate_local_check_gates(self) -> Self:
            """Every locally owned gate must be in the allowed check vocabulary."""
            allowed = set(FlextInfraConstantsMake.CANONICAL_GATE_IDS)
            unknown = sorted(set(self.local_check_gates) - allowed)
            if unknown:
                msg = (
                    "make.ci.local_check_gates contains unknown gates: "
                    f"{', '.join(unknown)}"
                )
                raise ValueError(msg)
            return self

    class MakeVerbSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One selector-free public Make operation."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Public Make verb")]
        description: Annotated[
            t.NonEmptyStr, m.Field(description="Operator-facing help text")
        ]
        produces_activation: Annotated[
            bool,
            m.Field(
                description=(
                    "Run the producer in the provisioned physical environment, "
                    "then activate its generated environment before post hooks"
                )
            ),
        ] = False
        profiles: Annotated[
            t.VariadicTuple[FlextInfraConstantsCodegenProject.MakeProfile],
            m.Field(
                min_length=1,
                description=(
                    "Make profiles whose generated Makefile declares the verb; "
                    "a verb exists only where its operation applies"
                ),
            ),
        ] = tuple(FlextInfraConstantsCodegenProject.MakeProfile)

    class MakeWorkflowStepSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One canonical workflow step."""

        verb: Annotated[t.NonEmptyStr, m.Field(description="Declared public verb")]
        contexts: Annotated[
            t.VariadicTuple[Literal["local", "ci", "pre_commit", "pre_push"]],
            m.Field(
                min_length=1,
                description="Execution contexts consuming this single workflow row",
            ),
        ]
        gates_skip: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Gate ids this step omits when it runs from a hook context "
                    "(pre_commit/pre_push). Local and CI invocations of the "
                    "same verb keep the full default set."
                ),
            ),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_contexts(self) -> Self:
            """Require unique contexts and retain every step in the local workflow."""
            if len(set(self.contexts)) != len(self.contexts):
                msg = f"make workflow contexts must be unique for {self.verb}"
                raise ValueError(msg)
            if "local" not in self.contexts:
                msg = f"make workflow step {self.verb} must run locally"
                raise ValueError(msg)
            allowed = set(FlextInfraConstantsMake.CANONICAL_GATE_IDS)
            unknown = sorted(set(self.gates_skip) - allowed)
            if unknown:
                msg = (
                    f"make workflow step {self.verb} gates_skip contains "
                    f"unknown gates: {', '.join(unknown)}"
                )
                raise ValueError(msg)
            return self

    class MakeCleanSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Disposable artifacts the generated clean verb removes.

        Stale caches and traces cause FALSE DIAGNOSES, so the disposable set is
        declared data rather than a literal buried in a recipe: every project
        cleans exactly the same things and a new artifact kind is one config row.
        """

        cache_dirs: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Cache directory names removed anywhere in the tree"),
        ]
        root_dirs: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Directories removed at the project root only"),
        ]
        root_files: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Files removed at the project root only"),
        ]
        trace_globs: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Trace/profile globs removed anywhere in the tree"),
        ]

    class MakeDocsSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Generated Makefile docs verb lifecycle and audit policy."""

        actions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Docs verb lifecycle actions in execution order; every "
                    "entry must be a registered docs CLI action"
                ),
            ),
        ]
        api_modules: Annotated[
            Mapping[t.NonEmptyStr, t.VariadicTuple[t.NonEmptyStr]],
            m.Field(
                min_length=1,
                description=(
                    "Public API modules generated per distribution; absent "
                    "distributions own no module pages"
                ),
            ),
        ]
        mutable_actions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Docs actions that mutate"),
        ]
        warning_actions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Docs actions whose findings are reported as warnings "
                    "instead of failing the phase"
                ),
            ),
        ] = ()
        reports_dir: Annotated[
            Path, m.Field(description="Repository-relative docs reports directory")
        ]
        cross_project_relative_link_pattern: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="Regex rejecting cross-project relative Markdown links"
            ),
        ]
        stale_github_organizations: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=("organization",),
                description="Placeholder GitHub orgs that must be rewritten",
            ),
        ] = ("organization",)
        github_repos: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMake.DocsGithubRepoSpec],
            m.Field(
                default=(),
                description="Governed org/repo/branch map for cross-repo doc URLs",
            ),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_api_modules(self) -> Self:
            """Reject duplicate or non-importable API module declarations."""
            for distribution, modules in self.api_modules.items():
                if not modules:
                    msg = f"docs api_modules must not be empty: {distribution}"
                    raise ValueError(msg)
                if len(set(modules)) != len(modules):
                    msg = f"docs api_modules must be unique: {distribution}"
                    raise ValueError(msg)
                invalid = next(
                    (
                        module
                        for module in modules
                        if not all(part.isidentifier() for part in module.split("."))
                    ),
                    None,
                )
                if invalid is not None:
                    msg = f"docs api module is not importable: {invalid}"
                    raise ValueError(msg)
            return self

        @u.model_validator(mode="after")
        def _validate_actions(self) -> Self:
            """Reject unknown, duplicated, or out-of-lifecycle docs actions."""
            if len(set(self.actions)) != len(self.actions):
                msg = "docs actions must be unique"
                raise ValueError(msg)
            unknown = next(
                (
                    action
                    for action in self.actions
                    if action not in FlextInfraConstantsDocs.DOCS_ACTION_IDS
                ),
                None,
            )
            if unknown is not None:
                msg = f"docs action is not a registered CLI action: {unknown}"
                raise ValueError(msg)
            for label, selected in (
                ("mutable_actions", self.mutable_actions),
                ("warning_actions", self.warning_actions),
            ):
                outside = next(
                    (action for action in selected if action not in self.actions), None
                )
                if outside is not None:
                    msg = f"{label} entry is not part of the docs lifecycle: {outside}"
                    raise ValueError(msg)
            return self

    class TestmonCacheSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Adaptive pytest-testmon GitHub Actions cache policy."""

        schema_version: Annotated[
            int, m.Field(ge=1, description="Cache key schema version")
        ]
        namespace: Annotated[
            t.NonEmptyStr, m.Field(description="Persistent state namespace")
        ]
        invocation_namespace: Annotated[
            t.NonEmptyStr, m.Field(description="Pytest invocation namespace")
        ]
        database_filename: Annotated[
            t.NonEmptyStr, m.Field(description="pytest-testmon database filename")
        ]
        target_directory: Annotated[
            Path, m.Field(description="Repository-relative pytest target")
        ]
        reports_directory: Annotated[
            Path, m.Field(description="Repository-relative pytest reports root")
        ]
        mode: Annotated[
            Literal["bootstrap", "stable"], m.Field(description="Cache renewal phase")
        ]
        save_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether CI may upload a new testmon generation. False while "
                    "quota/HTTP 402 blocks fleet-wide saves (QUOTA_HOLD)."
                )
            ),
        ]
        max_bootstrap_generations: Annotated[
            int, m.Field(ge=1, le=10, description="Max retained bootstrap generations")
        ]
        max_stable_generations: Annotated[
            int, m.Field(ge=1, le=10, description="Max retained stable generations")
        ]
        per_repo_budget_bytes: Annotated[
            int, m.Field(ge=1, description="Per-repo testmon namespace budget in bytes")
        ]
        warning_threshold_percent: Annotated[
            int, m.Field(ge=1, le=100, description="Quota warning threshold percent")
        ]
        maintenance_threshold_percent: Annotated[
            int,
            m.Field(ge=1, le=100, description="Quota maintenance threshold percent"),
        ]
        block_threshold_percent: Annotated[
            int, m.Field(ge=1, le=100, description="Quota block-save threshold percent")
        ]
        allowed_save_refs: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Refs allowed to save cache generations"),
        ]
        key_prefix: Annotated[
            t.NonEmptyStr, m.Field(description="Immutable cache key prefix")
        ]

        @u.model_validator(mode="after")
        def _validate_thresholds(self) -> Self:
            """Require warning < maintenance < block."""
            if not (
                self.warning_threshold_percent
                < self.maintenance_threshold_percent
                < self.block_threshold_percent
            ):
                msg = "testmon cache thresholds must satisfy warning < maintenance < block"
                raise ValueError(msg)
            return self

    class MakeWorkInProgressSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Predicate for work-in-progress branches and draft-PR gate behavior.

        A hook that runs the full gate matrix on every push turns an
        in-progress branch into a stop-and-wait loop, so contributors start
        bypassing the hook entirely -- which costs more than it saves. The
        predicate is DATA so the escape is declared and auditable rather than
        improvised per-repository with `--no-verify`.
        """

        draft_pr: Annotated[
            bool, m.Field(description="Treat GitHub draft PRs as work-in-progress")
        ]
        branch_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Regex patterns that mark a branch as work-in-progress",
            ),
        ]
        head_subject_patterns: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Regex patterns that mark a commit subject as work-in-progress; "
                    "matched case-insensitively by the merge guard"
                ),
            ),
        ]
        merge_lock_target_branches: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description="Target branches that are blocked for WIP merges",
            ),
        ]

    class MakeRuffSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Ruff CLI contract for generated Make verbs and quality gates.

        Operator 2026-09-08: ruff is the style and autofix rule. Every
        invocation uses preview. Never weaken ruff to keep a file; change the
        code. Single-pass verb law (operator 2026-09-18): ``make fmt`` runs
        format only and ``make fix`` owns lint repair through the lint gate —
        there is deliberately no ``lint_apply`` key, because a lint pass
        inside fmt would repeat the lint gate's fix.
        """

        format_check: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Flags for ruff format --check (read-only fmt)"),
        ]
        format_apply: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Flags for ruff format APPLY"),
        ]
        lint_check: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(description="Flags for ruff check without mutation"),
        ]
        lint_fix: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Flags for ruff check --fix including unsafe-fixes; the lint "
                    "gate's apply mode (make fix), which reports leftovers"
                )
            ),
        ]

    class MakeSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Complete generated Makefile public and extension contract."""

        ruff: Annotated[
            FlextInfraConfigModelsMake.MakeRuffSpec,
            m.Field(description="Ruff CLI flags for fmt/fix/check Make verbs"),
        ]
        fmt_gates: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=("markdown-format",),
                description=(
                    "Gates whose mutating side `make fmt` drives (formatters). "
                    "The read-only side runs in `make check`; `make fix` never "
                    "repeats them (single-pass verb law)."
                ),
            ),
        ]
        work_in_progress: Annotated[
            FlextInfraConfigModelsMake.MakeWorkInProgressSpec,
            m.Field(description="WIP branch and draft PR gate predicate"),
        ]
        # Why (operator law 2026-08-24): git-hook stages are OFF by default and
        # re-enabled case by case via these config gates. The workflow keeps
        # owning WHICH steps belong to each stage; the booleans only govern
        # whether the stage is generated and installed at all.
        pre_commit: Annotated[
            bool,
            m.Field(
                default=False,
                description="Generate and install the pre-commit git-hook stage",
            ),
        ] = False
        pre_push: Annotated[
            bool,
            m.Field(
                default=False,
                description="Generate and install the pre-push git-hook stage",
            ),
        ] = False
        workflow: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMake.MakeWorkflowStepSpec],
            m.Field(min_length=1, description="Ordered canonical validation workflow"),
        ]
        ci: Annotated[
            FlextInfraConfigModelsMake.MakeCiSpec,
            m.Field(description="Config-owned CI-only environment delta"),
        ]
        testmon_cache: Annotated[
            FlextInfraConfigModelsMake.TestmonCacheSpec,
            m.Field(description="Adaptive testmon Actions cache policy"),
        ]
        verbs: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMake.MakeVerbSpec],
            m.Field(description="Ordered canonical public verbs"),
        ]
        clean: Annotated[
            FlextInfraConfigModelsMake.MakeCleanSpec,
            m.Field(description="Disposable artifacts removed by the clean verb"),
        ]
        docs: Annotated[
            FlextInfraConfigModelsMake.MakeDocsSpec,
            m.Field(description="Public documentation lifecycle policy"),
        ]
        custom_handler_policy: Annotated[
            FlextInfraConfigModelsMake.CustomHandlerPolicy,
            m.Field(description="Private custom target policy"),
        ]
        custom_handler_profile_overrides: Annotated[
            Mapping[
                t.NonEmptyStr, FlextInfraConfigModelsMake.CustomHandlerPolicyOverride
            ],
            m.Field(
                default_factory=FlextInfraModelsDefaults.immutable_empty_mapping,
                description="Per-profile overrides of the custom handler policy",
            ),
        ]
        project_check_gates: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Check gates this project implements itself, unioned into "
                    "the built-in vocabulary. Without this seam the vocabulary "
                    "is a closed Final tuple, so a project that ships a working "
                    "`_custom_check_<gate>` handler still cannot reach it "
                    "through `make check`: the gate is rejected as unknown. A "
                    "gate that can never run is not a gate, which is how "
                    "references, agents, census and waza ended up outside the "
                    "gate matrix in consuming repositories. Each id must have a "
                    "`_custom_check_<id>` handler in the project's "
                    f"{FlextInfraConstantsCodegenProject.CUSTOM_MAKE_FILENAME}."
                ),
            ),
        ] = ()
        check_gate_suspensions: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMake.MakeGateSuspensionSpec],
            m.Field(
                description="Explicitly authorized suspensions shared by local, CI, and hooks"
            ),
        ] = ()

        @u.model_validator(mode="after")
        def _validate_check_gate_suspensions(self) -> Self:
            """Suspensions name unique gates in this project's complete vocabulary."""
            gates = tuple(item.gate for item in self.check_gate_suspensions)
            if len(gates) != len(set(gates)):
                msg = "make check_gate_suspensions must name unique gates"
                raise ValueError(msg)
            unknown = sorted(set(gates) - set(self.check_gates_allowed))
            if unknown:
                msg = f"make check_gate_suspensions contains unknown gates: {', '.join(unknown)}"
                raise ValueError(msg)
            return self

        @u.model_validator(mode="after")
        def _validate_project_check_gates(self) -> Self:
            """Project gates must be unique and must not shadow a built-in."""
            if len(set(self.project_check_gates)) != len(self.project_check_gates):
                msg = "make project_check_gates must be unique"
                raise ValueError(msg)
            builtin = set(FlextInfraConstantsMake.CANONICAL_GATE_IDS)
            shadowed = sorted(set(self.project_check_gates) & builtin)
            if shadowed:
                msg = (
                    "make project_check_gates shadow built-in gates: "
                    f"{', '.join(shadowed)}"
                )
                raise ValueError(msg)
            return self

        @u.model_validator(mode="after")
        def _validate_verbs(self) -> Self:
            """Validate declared public verbs against workflow and contract.

            Why there is no `"setup" in declared` rejection here (flext-lq86m):
            the message it carried -- "make setup cannot require the managed
            validation environment" -- is a statement about a verb's
            ENVIRONMENT DEPENDENCY, not about the name `setup`. Testing the
            name was the wrong predicate, and it contradicted
            `config/codegen.yaml`, which declares `setup` as a public verb; the
            config singleton builds eagerly at import, so every entrypoint died
            on that contradiction. The real invariant is enforced structurally
            in the template, which excludes `setup` from
            `_builtin_require_environment` (`$(filter-out setup,$(PUBLIC_VERBS))`
            and `{% raw %}{% for verb in make.verbs if verb.name != "setup" %}{% endraw %}`),
            so `setup` never depends on the environment it exists to create.
            """
            declared = {verb.name for verb in self.verbs}
            if len(declared) != len(self.verbs):
                msg = "make public verb names must be unique"
                raise ValueError(msg)
            # Why (hq-36xk, flext-lq86m): the guard that lived here read
            # `if "setup" in serialized` and protected `make setup` from being
            # placed in the serialized mutation set, so it could never require
            # the managed validation environment it is supposed to CREATE.
            # 3e5fbc747 exterminated the serialize-make lifecycle and deleted
            # `self.serialization`, but rebound this condition to `declared`
            # instead of removing it with the concept it guarded. `setup` is a
            # mandatory canonical verb, so the inverted check rejected every
            # valid configuration and `flext_infra.config` could not be built at
            # all. The serialized set no longer exists; the guard has no object.
            workflow_verbs = tuple(step.verb for step in self.workflow)
            if len(set(workflow_verbs)) != len(workflow_verbs):
                msg = "make workflow verbs must be unique"
                raise ValueError(msg)
            unknown_workflow = set(workflow_verbs) - declared
            if unknown_workflow:
                msg = (
                    "make workflow verbs are not declared public verbs: "
                    f"{', '.join(sorted(unknown_workflow))}"
                )
                raise ValueError(msg)
            # Every profile renders the workflow, so a workflow verb must exist
            # in every profile's Makefile.
            partial_workflow = sorted(
                verb.name
                for verb in self.verbs
                if verb.name in workflow_verbs
                and set(verb.profiles)
                != set(FlextInfraConstantsCodegenProject.MakeProfile)
            )
            if partial_workflow:
                msg = (
                    "make workflow verbs must exist in every profile: "
                    f"{', '.join(partial_workflow)}"
                )
                raise ValueError(msg)
            unknown_fmt_gates = set(self.fmt_gates) - set(
                FlextInfraConstantsCheck.SARIF_TOOL_INFO
            )
            if unknown_fmt_gates:
                msg = (
                    "make fmt gates are not declared gate vocabulary: "
                    f"{', '.join(sorted(unknown_fmt_gates))}"
                )
                raise ValueError(msg)
            if "docs" not in declared:
                msg = "make docs verb must be declared"
                raise ValueError(msg)
            if (
                self.docs.reports_dir.is_absolute()
                or ".." in self.docs.reports_dir.parts
            ):
                msg = "make docs reports_dir must be repository-relative"
                raise ValueError(msg)
            return self

        @m.computed_field
        @property
        def check_gates_allowed(self) -> t.VariadicTuple[str]:
            """Canonical generated Make check-gate vocabulary.

            The built-in gates this package implements, plus the gates the
            project declares for itself. The built-in tuple is the BASE, never
            the whole vocabulary: a consuming repository owns gates this
            package knows nothing about, and rejecting them as unknown is what
            kept working handlers unreachable from `make check`.
            """
            return (
                *FlextInfraConstantsMake.CANONICAL_GATE_IDS,
                *self.project_check_gates,
            )

        @m.computed_field
        @property
        def check_gates_default(self) -> t.VariadicTuple[str]:
            """Active default gates, shared by local, CI, hooks, and project gates."""
            suspended = frozenset(item.gate for item in self.check_gate_suspensions)
            declared = (
                *FlextInfraConstantsMake.CANONICAL_DEFAULT_GATE_IDS,
                *self.project_check_gates,
            )
            return tuple(gate for gate in declared if gate not in suspended)

        @m.computed_field
        @property
        def check_gates_local(self) -> t.VariadicTuple[str]:
            """Intersect the local partition with the same active default universe."""
            local = frozenset(self.ci.local_check_gates)
            return tuple(gate for gate in self.check_gates_default if gate in local)

        @m.computed_field
        @property
        def check_gates_ci(self) -> t.VariadicTuple[str]:
            """Preserve the CI partition within the same active default universe."""
            local = frozenset(self.check_gates_local)
            return tuple(gate for gate in self.check_gates_default if gate not in local)

        @m.computed_field
        @property
        def check_gates_fixable(self) -> t.VariadicTuple[str]:
            """Gates ``make fix`` can actually repair.

            Asking for a gate that cannot fix anything still pays its full cost;
            a fix pass built from the ALLOWED vocabulary once timed out doing
            exactly that.
            """
            return FlextInfraConstantsMake.CANONICAL_FIXABLE_GATE_IDS

        @m.computed_field
        @property
        def custom_handler_policies(
            self,
        ) -> Mapping[str, FlextInfraConfigModelsMake.CustomHandlerPolicy]:
            """Effective custom-handler policy for every Make profile.

            The base policy states the strictest contract (private handlers
            only). A profile whose custom surface legitimately owns more --
            a workspace root orchestrating its subprojects -- declares only the
            fields it relaxes, so the engine never has to know which project
            it is conforming.
            """
            base = self.custom_handler_policy
            overrides = self.custom_handler_profile_overrides
            # Keys are normalised to the profile's string value: MakeProfile is a
            # StrEnum, so a raw YAML key and its enum subproject must land on the SAME
            # entry. Mixing both would make a lookup silently miss and fall back to
            # the strict base policy.
            return {
                str(profile): (
                    base.model_copy(update=override.model_dump(exclude_none=True))
                    if (override := overrides.get(str(profile)))
                    else base
                )
                for profile in (
                    *overrides,
                    *FlextInfraConstantsCodegenProject.MakeProfile,
                )
            }

    class DocsGithubRepoSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One governed GitHub repository used for cross-repo doc links."""

        organization: Annotated[
            t.NonEmptyStr, m.Field(description="GitHub organization")
        ]
        repository: Annotated[t.NonEmptyStr, m.Field(description="GitHub repository")]
        branch: Annotated[
            t.NonEmptyStr, m.Field(description="Working-line branch for doc links")
        ]
        local_checkout: Annotated[
            str,
            m.Field(
                default="",
                description=(
                    "Optional local checkout path (~ expanded) for existence checks"
                ),
            ),
        ] = ""

    class CustomHandlerPolicy(FlextInfraConfigModelsContract.ConfigContract):
        """Strict schema for the only handwritten Make extension file."""

        filename: Annotated[
            t.NonEmptyStr, m.Field(description="Versioned custom handler filename")
        ]
        target_pattern: Annotated[
            t.NonEmptyStr,
            m.Field(description="Required private target regular expression"),
        ]
        allow_public_targets: bool = m.Field(description="Permit public targets")
        allow_toolchain_declarations: bool = m.Field(
            description="Permit toolchain declarations"
        )

    class CustomHandlerPolicyOverride(FlextInfraConfigModelsContract.ConfigContract):
        """Per-profile relaxation of the strict custom-handler contract.

        Every field is optional: a profile declares ONLY what it relaxes, so a
        new permission added to the base policy propagates automatically
        instead of having to be repeated in each profile.
        """

        allow_public_targets: bool | None = m.Field(
            default=None, description="Permit public targets"
        )
        allow_toolchain_declarations: bool | None = m.Field(
            default=None, description="Permit toolchain declarations"
        )
