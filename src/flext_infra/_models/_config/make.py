"""Make workflow, verb, CI, and cache specification models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Self

from flext_cli import m, u

from flext_infra import t
from flext_infra._constants import (
    FlextInfraConstantsCheck,
    FlextInfraConstantsCodegenProject,
    FlextInfraConstantsDocs,
    FlextInfraConstantsMake,
)
from flext_infra._models._config.contract import FlextInfraConfigModelsContract


class ExternalCacheDirectorySpec(FlextInfraConfigModelsContract.ConfigContract):
    """External-cache path pair every tool cache spec owns identically."""

    home_cache_directory: Annotated[
        Path,
        m.Field(description="Standard cache directory below the user home"),
    ]
    external_storage_directory: Annotated[
        Path,
        m.Field(description="FLEXT-owned directory below the cache home"),
    ]

    @u.model_validator(mode="after")
    def require_relative_cache_directories(self) -> Self:
        """Keep both cache directories normalized and repository-relative.

        Returns:
            The resulting ``Self``.

        Raises:
            ValueError: If cache.

        """
        for name, path in (
            ("home_cache_directory", self.home_cache_directory),
            ("external_storage_directory", self.external_storage_directory),
        ):
            if path.is_absolute() or any(
                part in {"", ".", ".."} for part in path.parts
            ):
                msg = f"cache {name} must be normalized and relative"
                raise ValueError(msg)
        return self


def _shared_mypy_cache_spec() -> FlextInfraConfigModelsMake.MypyCacheSpec:
    """Build the declared default shared Mypy analysis cache policy.

    Declared here (module scope) so the field default is one shared policy that
    a member may override, instead of forcing every hand-owned ``codegen.yaml``
    to repeat the same block just to satisfy a required field.

    Returns:
        The resulting ``FlextInfraConfigModelsMake.MypyCacheSpec``.
    """
    return FlextInfraConfigModelsMake.MypyCacheSpec()


def _default_testmon_cache_policy() -> (
    FlextInfraConfigModelsMake.TestmonCachePolicySpec
):
    """Build the declared default testmon cache policy (#1001 delta).

    Returns:
        The resulting ``FlextInfraConfigModelsMake.TestmonCachePolicySpec``.
    """
    return FlextInfraConfigModelsMake.TestmonCachePolicySpec()


class FlextInfraConfigModelsMake:
    """Make workflow, verb, CI, and cache specification models."""

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
                ),
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
                ),
            ),
        ]

        @u.model_validator(mode="after")
        def _validate_local_check_gates(self) -> Self:
            """Every locally owned gate must be in the allowed check vocabulary.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If make.ci.local_check_gates contains unknown gates.
            """
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
            t.NonEmptyStr,
            m.Field(description="Operator-facing help text"),
        ]
        produces_activation: Annotated[
            bool,
            m.Field(
                description=(
                    "Run the producer in the provisioned physical environment, "
                    "then activate its generated environment before post hooks"
                ),
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
            """Require unique contexts and retain every step in the local workflow.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If make workflow contexts must be unique for; or if make
                    workflow step.

            """
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

    class DocsOverviewPreviewLimitsSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Maximum list sizes in the generated public API overview."""

        aliases: Annotated[int, m.Field(gt=0, description="Alias preview limit")]
        public_symbols: Annotated[
            int,
            m.Field(gt=0, description="Public symbol preview limit"),
        ]
        facades: Annotated[int, m.Field(gt=0, description="Facade preview limit")]
        module_exports: Annotated[
            int,
            m.Field(gt=0, description="Module export preview limit"),
        ]
        keywords: Annotated[int, m.Field(gt=0, description="Keyword preview limit")]

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
        mutable_actions: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Docs actions that mutate"),
        ]
        reports_dir: Annotated[
            Path,
            m.Field(description="Repository-relative docs reports directory"),
        ]
        overview_preview_limits: Annotated[
            FlextInfraConfigModelsMake.DocsOverviewPreviewLimitsSpec,
            m.Field(description="Maximum preview sizes for generated API overviews"),
        ]
        cross_project_relative_link_pattern: Annotated[
            t.NonEmptyStr,
            m.Field(
                description="Regex rejecting cross-project relative Markdown links",
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
        def _validate_actions(self) -> Self:
            """Reject unknown, duplicated, or out-of-lifecycle docs actions.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If docs actions must be unique; or if docs action is not a
                    registered CLI action; or if mutable_actions entry is not part of
                    the docs lifecycle.

            """
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
            outside = next(
                (
                    action
                    for action in self.mutable_actions
                    if action not in self.actions
                ),
                None,
            )
            if outside is not None:
                msg = (
                    "mutable_actions entry is not part of the docs lifecycle:"
                    f" {outside}"
                )
                raise ValueError(msg)
            return self

    class TestmonCachePolicySpec(FlextInfraConfigModelsContract.ConfigContract):
        """Declarative Actions-cache policy for the shared testmon database.

        Implements the preserved #1001 delta (bead flext-j0u23): two-phase
        generations with per-mode caps, a per-repository byte budget with a
        three-stage quota ladder, a save-ref allowlist (never save from PRs)
        and a cache-key namespace.
        """

        mode: Annotated[
            Literal["bootstrap", "stable"],
            m.Field(description="Cache phase: bootstrap seeds, stable saves"),
        ] = "stable"
        save_enabled: Annotated[
            bool,
            m.Field(description="Master switch for cache publishes"),
        ] = False
        max_bootstrap_generations: Annotated[
            int,
            m.Field(gt=0, description="Retention cap for bootstrap generations"),
        ] = 3
        max_stable_generations: Annotated[
            int,
            m.Field(gt=0, description="Retention cap for stable generations"),
        ] = 3
        per_repo_budget_bytes: Annotated[
            int,
            m.Field(gt=0, description="Per-repository byte budget"),
        ] = 52_428_800
        warning_threshold_percent: Annotated[
            int,
            m.Field(ge=0, le=100, description="Quota-ladder warning stage"),
        ] = 80
        maintenance_threshold_percent: Annotated[
            int,
            m.Field(ge=0, le=100, description="Quota-ladder maintenance stage"),
        ] = 90
        block_threshold_percent: Annotated[
            int,
            m.Field(ge=0, le=100, description="Quota-ladder block stage"),
        ] = 95
        allowed_save_refs: Annotated[
            tuple[t.NonEmptyStr, ...],
            m.Field(description="Refs whose pushes may publish cache generations"),
        ] = ("main", "0.12.0-dev")
        key_prefix: Annotated[
            t.NonEmptyStr,
            m.Field(description="Actions cache key namespace"),
        ] = "flext-testmon"

        @u.model_validator(mode="after")
        def require_ascending_quota_ladder(self) -> Self:
            """Keep the quota ladder strictly ascending within the percent scale.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If testmon cache quota ladder must ascend warning <
                    maintenance < block <= 100.
            """
            full_scale = 100
            if not (
                self.warning_threshold_percent
                < self.maintenance_threshold_percent
                < self.block_threshold_percent
                <= full_scale
            ):
                msg = "testmon cache quota ladder must ascend warning < maintenance < block <= 100"
                raise ValueError(msg)
            return self

    class MypyCacheSpec(
        ExternalCacheDirectorySpec,
        FlextInfraConfigModelsContract.ConfigContract,
    ):
        """Project-keyed shared Mypy cache: one analysis per project, reused across relocks."""

        cache_environment_variable: Annotated[
            FlextInfraConstantsMake.MypyCacheEnvironment,
            m.Field(
                default=FlextInfraConstantsMake.MypyCacheEnvironment.CACHE_DIR,
                description="Mypy's cache-directory environment variable",
            ),
        ]
        data_home_environment_variable: Annotated[
            FlextInfraConstantsMake.MypyCacheEnvironment,
            m.Field(
                default=FlextInfraConstantsMake.MypyCacheEnvironment.DATA_HOME,
                description="XDG persistent cache-home variable",
            ),
        ]
        user_home_environment_variable: Annotated[
            FlextInfraConstantsMake.MypyCacheEnvironment,
            m.Field(
                default=FlextInfraConstantsMake.MypyCacheEnvironment.USER_HOME,
                description="User home variable for the XDG default",
            ),
        ]
        home_cache_directory: Annotated[
            Path,
            m.Field(
                default=Path(".cache"),
                description="Standard cache directory below the user home",
            ),
        ]
        external_storage_directory: Annotated[
            Path,
            m.Field(
                default=Path("flext/infra/mypy"),
                description="FLEXT-owned directory below the cache home",
            ),
        ]

        @u.model_validator(mode="after")
        def require_external_cache_contract(self) -> Self:
            """Keep the official cache variable and the external path policy exact.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If mypy cache.
            """
            for name, actual, expected in (
                (
                    "cache_environment_variable",
                    self.cache_environment_variable,
                    FlextInfraConstantsMake.MypyCacheEnvironment.CACHE_DIR,
                ),
                (
                    "data_home_environment_variable",
                    self.data_home_environment_variable,
                    FlextInfraConstantsMake.MypyCacheEnvironment.DATA_HOME,
                ),
                (
                    "user_home_environment_variable",
                    self.user_home_environment_variable,
                    FlextInfraConstantsMake.MypyCacheEnvironment.USER_HOME,
                ),
            ):
                if actual != expected:
                    msg = f"mypy cache {name} must be {expected.value}"
                    raise ValueError(msg)
            return self

    class MakeWorkInProgressSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Predicate the generated CI merge guard applies to pull request heads.

        A GitHub Draft selects no job; a promoted PR whose head commit subject
        marks work in progress cannot merge into a protected integration
        branch. The predicate is DATA so the lock is declared and auditable
        rather than improvised per repository.
        """

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

    class MakeGateSuspensionSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One gate temporarily suspended by a declaring authority.

        The suspension is DATA so the active gate default set stays declared
        and auditable: suspended gates leave the active default set without
        leaving the vocabulary, and every suspension records the authority
        that declared it.
        """

        gate: Annotated[
            t.NonEmptyStr,
            m.Field(
                min_length=1,
                description=(
                    "Gate identifier temporarily suspended (the rule name the "
                    "vocabulary knows)"
                ),
            ),
        ]
        authority: Annotated[
            t.NonEmptyStr,
            m.Field(
                min_length=1,
                description=(
                    "Declaring authority for the suspension (operator ruling reference)"
                ),
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

        ``make fix`` never deletes information (flext-itpd1.5): the lint repair
        applies Ruff's safe fixes only, so ``lint_fix`` rejects the unsafe-fix
        flag. Rules whose fixes delete code stay reported through the
        ``unfixable`` list rendered from ``tooling.yaml``.
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
                    "Flags for ruff check --fix applying safe fixes only; the "
                    "lint gate's apply mode (make fix), which reports leftovers"
                ),
            ),
        ]

        @u.model_validator(mode="after")
        def _reject_unsafe_fixes(self) -> Self:
            """Keep the lint repair information-preserving.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If make.ruff.lint_fix must not enable.

            """
            if FlextInfraConstantsMake.RUFF_UNSAFE_FIXES_FLAG in self.lint_fix:
                msg = (
                    "make.ruff.lint_fix must not enable "
                    f"{FlextInfraConstantsMake.RUFF_UNSAFE_FIXES_FLAG}: unsafe "
                    "Ruff fixes delete code, comments and diagnostics"
                )
                raise ValueError(msg)
            return self

    class MakeSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Complete generated Makefile public and extension contract."""

        check_gate_suspensions: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMake.MakeGateSuspensionSpec],
            m.Field(
                description=(
                    "Gates temporarily suspended for this project (the gate "
                    "id plus the declaring authority); suspended gates leave "
                    "the active default set without leaving the vocabulary."
                ),
            ),
        ] = ()

        class TestmonCachePolicySpec(FlextInfraConfigModelsContract.ConfigContract):
            """Declarative Actions-cache policy for the shared testmon database.

            Implements the preserved #1001 delta (bead flext-j0u23): two-phase
            generations with per-mode caps, a per-repository byte budget with a
            three-stage quota ladder, a save-ref allowlist (never save from PRs)
            and a cache-key namespace.
            """

            mode: Annotated[
                Literal["bootstrap", "stable"],
                m.Field(description="Cache phase: bootstrap seeds, stable saves"),
            ] = "stable"
            save_enabled: Annotated[
                bool,
                m.Field(description="Master switch for cache publishes"),
            ] = False
            max_bootstrap_generations: Annotated[
                int,
                m.Field(gt=0, description="Retention cap for bootstrap generations"),
            ] = 3
            max_stable_generations: Annotated[
                int,
                m.Field(gt=0, description="Retention cap for stable generations"),
            ] = 3
            per_repo_budget_bytes: Annotated[
                int,
                m.Field(gt=0, description="Per-repository byte budget"),
            ] = 52_428_800
            warning_threshold_percent: Annotated[
                int,
                m.Field(ge=0, le=100, description="Quota-ladder warning stage"),
            ] = 80
            maintenance_threshold_percent: Annotated[
                int,
                m.Field(ge=0, le=100, description="Quota-ladder maintenance stage"),
            ] = 90
            block_threshold_percent: Annotated[
                int,
                m.Field(ge=0, le=100, description="Quota-ladder block stage"),
            ] = 95
            allowed_save_refs: Annotated[
                tuple[t.NonEmptyStr, ...],
                m.Field(description="Refs whose pushes may publish cache generations"),
            ] = ("main", "0.12.0-dev")
            key_prefix: Annotated[
                t.NonEmptyStr,
                m.Field(description="Actions cache key namespace"),
            ] = "flext-testmon"

            @u.model_validator(mode="after")
            def require_ascending_quota_ladder(self) -> Self:
                """Keep the quota ladder strictly ascending within the percent scale.

                Returns:
                    The resulting ``Self``.

                Raises:
                    ValueError: If testmon cache quota ladder must ascend warning <
                        maintenance < block <= 100.

                """
                full_scale = 100
                if not (
                    self.warning_threshold_percent
                    < self.maintenance_threshold_percent
                    < self.block_threshold_percent
                    <= full_scale
                ):
                    msg = (
                        "testmon cache quota ladder must ascend"
                        " warning < maintenance < block <= 100"
                    )
                    raise ValueError(msg)
                return self

        class TestmonCacheSpec(
            ExternalCacheDirectorySpec,
            FlextInfraConfigModelsContract.ConfigContract,
        ):
            """Persistent pytest-testmon database and runner paths."""

            database_filename: Annotated[
                t.NonEmptyStr,
                m.Field(description="pytest-testmon database filename"),
            ]
            database_environment_variable: Annotated[
                FlextInfraConstantsMake.PytestCacheEnvironment,
                m.Field(
                    description="pytest-testmon's supported database-path variable",
                ),
            ]
            data_home_environment_variable: Annotated[
                FlextInfraConstantsMake.PytestCacheEnvironment,
                m.Field(description="XDG persistent cache-home variable"),
            ]
            user_home_environment_variable: Annotated[
                FlextInfraConstantsMake.PytestCacheEnvironment,
                m.Field(description="User home variable for the XDG default"),
            ]
            target_directory: Annotated[
                Path,
                m.Field(description="Repository-relative pytest target"),
            ]
            reports_directory: Annotated[
                Path,
                m.Field(description="Repository-relative pytest reports root"),
            ]

            @u.model_validator(mode="after")
            def require_external_database_contract(self) -> Self:
                """Keep testmon's official path variable and external path policy exact.

                Returns:
                    The resulting ``Self``.

                Raises:
                    ValueError: If testmon cache database_filename must be a filename;
                        or if testmon cache.

                """
                for name, actual, expected in (
                    (
                        "database_environment_variable",
                        self.database_environment_variable,
                        FlextInfraConstantsMake.PytestCacheEnvironment.DATABASE_FILE,
                    ),
                    (
                        "data_home_environment_variable",
                        self.data_home_environment_variable,
                        FlextInfraConstantsMake.PytestCacheEnvironment.DATA_HOME,
                    ),
                    (
                        "user_home_environment_variable",
                        self.user_home_environment_variable,
                        FlextInfraConstantsMake.PytestCacheEnvironment.USER_HOME,
                    ),
                ):
                    if actual != expected:
                        msg = f"testmon cache {name} must be {expected.value}"
                        raise ValueError(msg)
                if Path(self.database_filename).name != self.database_filename:
                    msg = "testmon cache database_filename must be a filename"
                    raise ValueError(msg)
                return self

        class CodemodRulesCacheSpec(
            ExternalCacheDirectorySpec,
            FlextInfraConfigModelsContract.ConfigContract,
        ):
            """Content-keyed parsed codemod rule catalogs shared by every process."""

            data_home_environment_variable: Annotated[
                t.NonEmptyStr,
                m.Field(description="XDG persistent cache-home variable"),
            ]
            user_home_environment_variable: Annotated[
                t.NonEmptyStr,
                m.Field(description="User home variable for the XDG default"),
            ]

        class MypyCacheSpec(
            ExternalCacheDirectorySpec,
            FlextInfraConfigModelsContract.ConfigContract,
        ):
            """Project-keyed shared Mypy cache: one analysis per project,
            reused across relocks.
            """

            cache_environment_variable: Annotated[
                FlextInfraConstantsMake.MypyCacheEnvironment,
                m.Field(
                    default=FlextInfraConstantsMake.MypyCacheEnvironment.CACHE_DIR,
                    description="Mypy's cache-directory environment variable",
                ),
            ]
            data_home_environment_variable: Annotated[
                FlextInfraConstantsMake.MypyCacheEnvironment,
                m.Field(
                    default=FlextInfraConstantsMake.MypyCacheEnvironment.DATA_HOME,
                    description="XDG persistent cache-home variable",
                ),
            ]
            user_home_environment_variable: Annotated[
                FlextInfraConstantsMake.MypyCacheEnvironment,
                m.Field(
                    default=FlextInfraConstantsMake.MypyCacheEnvironment.USER_HOME,
                    description="User home variable for the XDG default",
                ),
            ]
            home_cache_directory: Annotated[
                Path,
                m.Field(
                    default=Path(".cache"),
                    description="Standard cache directory below the user home",
                ),
            ]
            external_storage_directory: Annotated[
                Path,
                m.Field(
                    default=Path("flext/infra/mypy"),
                    description="FLEXT-owned directory below the cache home",
                ),
            ]

            @u.model_validator(mode="after")
            def require_external_cache_contract(self) -> Self:
                """Keep the official cache variable and the external path policy exact.

                Returns:
                    The resulting ``Self``.

                Raises:
                    ValueError: If mypy cache.

                """
                for name, actual, expected in (
                    (
                        "cache_environment_variable",
                        self.cache_environment_variable,
                        FlextInfraConstantsMake.MypyCacheEnvironment.CACHE_DIR,
                    ),
                    (
                        "data_home_environment_variable",
                        self.data_home_environment_variable,
                        FlextInfraConstantsMake.MypyCacheEnvironment.DATA_HOME,
                    ),
                    (
                        "user_home_environment_variable",
                        self.user_home_environment_variable,
                        FlextInfraConstantsMake.MypyCacheEnvironment.USER_HOME,
                    ),
                ):
                    if actual != expected:
                        msg = f"mypy cache {name} must be {expected.value}"
                        raise ValueError(msg)
                return self

        examples_timeout_seconds: Annotated[
            int,
            m.Field(gt=0, le=120, description="Workspace examples process deadline"),
        ]
        submodule_timeout_seconds: Annotated[
            int,
            m.Field(gt=0, le=600, description="Governed submodule setup deadline"),
        ]
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
            TestmonCacheSpec,
            m.Field(description="Adaptive testmon Actions cache policy"),
        ]
        testmon_cache_policy: Annotated[
            FlextInfraConfigModelsMake.TestmonCachePolicySpec,
            m.Field(
                default_factory=FlextInfraConfigModelsMake.TestmonCachePolicySpec,
                description=(
                    "Declarative save/budget/quota policy for the shared"
                    " testmon cache (#1001 delta)"
                ),
            ),
        ]
        codemod_rules_cache: Annotated[
            FlextInfraConfigModelsMake.MakeSpec.CodemodRulesCacheSpec,
            m.Field(description="Content-keyed parsed codemod rule catalog cache"),
        ]
        mypy_cache: Annotated[
            FlextInfraConfigModelsMake.MypyCacheSpec,
            m.Field(
                default_factory=_shared_mypy_cache_spec,
                description="Project-keyed shared Mypy analysis cache policy",
            ),
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
                t.NonEmptyStr,
                FlextInfraConfigModelsMake.CustomHandlerPolicyOverride,
            ],
            m.Field(description="Per-profile overrides of the custom handler policy"),
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
        standalone_check_gates: Annotated[
            Mapping[t.NonEmptyStr, t.NonEmptyStr],
            m.Field(
                description=(
                    "Public Make verb to checker gate mapping outside make check"
                ),
            ),
        ] = m.Field(default_factory=lambda: MappingProxyType({}))

        @u.model_validator(mode="after")
        def _validate_project_check_gates(self) -> Self:
            """Project gates must be unique and must not shadow a built-in.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If make project_check_gates must be unique; or if make
                    project_check_gates shadow built-in gates.

            """
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
            and
            `{% raw %}{% for verb in make.verbs
            if verb.name != "setup" %}{% endraw %}`),
            so `setup` never depends on the environment it exists to create.

            Returns:
                The resulting ``Self``.

            Raises:
                ValueError: If make public verb names must be unique; or if make
                    standalone_check_gates names undeclared verbs; or if make
                    standalone_check_gates requires verbs in every profile; or if make
                    standalone_check_gates names unknown gates; or if make
                    standalone_check_gates must route each gate once; or if make
                    workflow verbs must be unique; or if make workflow verbs are not
                    declared public verbs; or if make workflow verbs must exist in every
                    profile; or if make fmt gates are not declared gate vocabulary; or
                    if make docs verb must be declared; or if make docs reports_dir must
                    be repository-relative.

            """
            declared = {verb.name for verb in self.verbs}
            if len(declared) != len(self.verbs):
                msg = "make public verb names must be unique"
                raise ValueError(msg)
            unknown_standalone_verbs = sorted(
                set(self.standalone_check_gates) - declared,
            )
            if unknown_standalone_verbs:
                msg = (
                    "make standalone_check_gates names undeclared verbs: "
                    f"{', '.join(unknown_standalone_verbs)}"
                )
                raise ValueError(msg)
            partial_standalone = sorted(
                verb.name
                for verb in self.verbs
                if verb.name in self.standalone_check_gates
                and set(verb.profiles)
                != set(FlextInfraConstantsCodegenProject.MakeProfile)
            )
            if partial_standalone:
                msg = (
                    "make standalone_check_gates requires verbs in every profile: "
                    f"{', '.join(partial_standalone)}"
                )
                raise ValueError(msg)
            unknown_standalone_gates = sorted(
                set(self.standalone_check_gates.values())
                - set(self.check_gates_allowed),
            )
            if unknown_standalone_gates:
                msg = (
                    "make standalone_check_gates names unknown gates: "
                    f"{', '.join(unknown_standalone_gates)}"
                )
                raise ValueError(msg)
            standalone_gates = tuple(self.standalone_check_gates.values())
            if len(standalone_gates) != len(set(standalone_gates)):
                msg = "make standalone_check_gates must route each gate once"
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
                FlextInfraConstantsCheck.SARIF_TOOL_INFO,
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
            standalone = frozenset(self.standalone_check_gates.values())
            declared = (
                *FlextInfraConstantsMake.CANONICAL_DEFAULT_GATE_IDS,
                *self.project_check_gates,
            )
            return tuple(gate for gate in declared if gate not in standalone)

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
            t.NonEmptyStr,
            m.Field(description="GitHub organization"),
        ]
        repository: Annotated[t.NonEmptyStr, m.Field(description="GitHub repository")]
        branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Working-line branch for doc links"),
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
            t.NonEmptyStr,
            m.Field(description="Versioned custom handler filename"),
        ]
        target_pattern: Annotated[
            t.NonEmptyStr,
            m.Field(description="Required private target regular expression"),
        ]
        allow_public_targets: bool = m.Field(description="Permit public targets")
        allow_toolchain_declarations: bool = m.Field(
            description="Permit toolchain declarations",
        )

    class CustomHandlerPolicyOverride(FlextInfraConfigModelsContract.ConfigContract):
        """Per-profile relaxation of the strict custom-handler contract.

        Every field is optional: a profile declares ONLY what it relaxes, so a
        new permission added to the base policy propagates automatically
        instead of having to be repeated in each profile.
        """

        allow_public_targets: bool | None = m.Field(
            default=None,
            description="Permit public targets",
        )
        allow_toolchain_declarations: bool | None = m.Field(
            default=None,
            description="Permit toolchain declarations",
        )
