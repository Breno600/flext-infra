"""Tool configuration models for the deps subpackage."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Self

from flext_cli import m, u

from flext_infra import t

from . import FlextInfraModelsDefaults
from .deps_tool_config_linters import FlextInfraModelsDepsToolConfigLinters
from .deps_tool_config_type_checkers import FlextInfraModelsDepsToolConfigTypeCheckers


class FlextInfraModelsDepsToolConfig(
    FlextInfraModelsDepsToolConfigLinters, FlextInfraModelsDepsToolConfigTypeCheckers
):
    """Models for tool configuration loaded from YAML."""

    class ModPhasesConfig(m.ArbitraryTypesModel):
        """Component selection for ``make mod`` phases (toggles are data)."""

        import_alignment: Annotated[
            bool,
            m.Field(
                alias="import-alignment",
                default=True,
                description=("Run the rope-native import-alignment phase of make mod."),
            ),
        ] = True

    class ModConfig(m.ArbitraryTypesModel):
        """Declarative policy for the unified modernize verb ``mod``."""

        @staticmethod
        def _default_phases() -> FlextInfraModelsDepsToolConfig.ModPhasesConfig:
            return FlextInfraModelsDepsToolConfig.ModPhasesConfig()

        phases: FlextInfraModelsDepsToolConfig.ModPhasesConfig = m.Field(
            default_factory=_default_phases,
            description="Phase toggles read from config/tooling.yaml.",
        )

    class DeptryConfig(m.ArbitraryTypesModel):
        """Deptry namespace and dependency-group policy."""

        known_first_party: Annotated[
            t.StrTuple,
            m.Field(
                alias="known-first-party",
                description="Base first-party namespaces extended by project metadata.",
            ),
        ]
        pep621_dev_dependency_groups: Annotated[
            t.StrTuple,
            m.Field(
                alias="pep621-dev-dependency-groups",
                description="PEP 735 groups treated as development dependencies.",
            ),
        ]

    class HatchConfig(m.ArbitraryTypesModel):
        """Hatch metadata policy."""

        allow_direct_references: Annotated[
            bool,
            m.Field(
                alias="allow-direct-references",
                description="Allow direct references in project metadata.",
            ),
        ]
        packaged_data_dirs: Annotated[
            t.StrSequence,
            m.Field(
                alias="packaged-data-dirs",
                default_factory=tuple,
                description=(
                    "Root data directories force-included into the wheel when "
                    "present (e.g. config, templates), so they survive install."
                ),
            ),
        ]

    class PytestConfig(m.ArbitraryTypesModel):
        """Pytest baseline settings loaded from YAML."""

        testmon_state_home_variable: Annotated[
            t.NonEmptyStr,
            m.Field(
                alias="testmon-state-home-variable",
                description="Required environment variable owning persistent test state.",
            ),
        ]
        testmon_datafile_variable: Annotated[
            t.NonEmptyStr,
            m.Field(
                alias="testmon-datafile-variable",
                description="pytest-testmon environment variable selecting its database.",
            ),
        ]
        testmon_namespace: Annotated[
            Path,
            m.Field(
                alias="testmon-namespace",
                description="Relative namespace below the persistent state home.",
            ),
        ]
        testmon_database_filename: Annotated[
            t.NonEmptyStr,
            m.Field(
                alias="testmon-database-filename",
                description="pytest-testmon SQLite database filename.",
            ),
        ]
        testmon_lock_filename: Annotated[
            t.NonEmptyStr,
            m.Field(
                alias="testmon-lock-filename",
                description="Exclusive writer lock filename beside the database.",
            ),
        ]

        # flext-j47u (codex): every rendered pytest value is validated config data.
        case_timeout_seconds: Annotated[
            int,
            m.Field(
                alias="case-timeout-seconds",
                gt=0,
                description="Hard maximum runtime for one pytest item.",
            ),
        ]
        slow_timeout_seconds: Annotated[
            int,
            m.Field(
                alias="slow-timeout-seconds",
                gt=0,
                description="Hard maximum runtime for one explicitly slow item.",
            ),
        ]
        run_timeout_seconds: Annotated[
            int,
            m.Field(
                alias="run-timeout-seconds",
                gt=0,
                description="Hard wall-clock maximum for one pytest invocation.",
            ),
        ]
        termination_grace_seconds: Annotated[
            int,
            m.Field(
                alias="termination-grace-seconds",
                gt=0,
                description="Grace period reserved inside the invocation deadline.",
            ),
        ]
        max_failures: Annotated[
            Literal[0],
            m.Field(
                alias="max-failures",
                description="Run every selected test while preserving failure status.",
            ),
        ]
        enforcement_plugin: Annotated[
            t.NonEmptyStr,
            m.Field(
                alias="enforcement-plugin",
                description="Required pytest11 enforcement plugin loaded by Make.",
            ),
        ]
        asyncio_default_fixture_loop_scope: Annotated[
            Literal["function", "class", "module", "package", "session"],
            m.Field(
                alias="asyncio-default-fixture-loop-scope",
                description="Explicit event-loop lifetime for asynchronous pytest fixtures.",
            ),
        ]
        progress_args: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                alias="progress-args",
                min_length=1,
                description="Arguments that expose each pytest item and live progress.",
            ),
        ]
        report_args: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                alias="report-args",
                min_length=1,
                description="Canonical concise pytest reporting arguments.",
            ),
        ]
        diagnostic_args: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                alias="diagnostic-args",
                min_length=1,
                description="Canonical expanded pytest diagnostic arguments.",
            ),
        ]
        parallel_workers: Annotated[
            int,
            m.Field(
                alias="parallel-workers",
                gt=0,
                le=16,
                description="Upper pytest-xdist worker ceiling for full runs.",
            ),
        ]
        parallel_worker_memory_gb: Annotated[
            int,
            m.Field(
                alias="parallel-worker-memory-gb",
                gt=0,
                le=64,
                description=(
                    "Physical-memory reservation per xdist worker; the runner "
                    "also bounds workers by available CPU."
                ),
            ),
        ]
        parallel_distribution: Annotated[
            Literal["load"],
            m.Field(
                alias="parallel-distribution",
                description="Pytest-xdist scheduler for full runs.",
            ),
        ]
        profile_sort: Annotated[
            Literal[
                "calls",
                "cumulative",
                "filename",
                "line",
                "name",
                "nfl",
                "pcalls",
                "stdname",
                "time",
            ],
            m.Field(alias="profile-sort", description="Sort key for cProfile reports."),
        ]
        profile_limit: Annotated[
            int,
            m.Field(
                alias="profile-limit",
                gt=0,
                le=1000,
                description="Maximum cProfile rows rendered.",
            ),
        ]
        min_version: Annotated[
            t.NonEmptyStr,
            m.Field(alias="min-version", description="Minimum pytest version."),
        ]
        python_classes: Annotated[
            t.StrTuple,
            m.Field(
                alias="python-classes",
                description="Canonical pytest test class patterns.",
            ),
        ]
        python_files: Annotated[
            t.StrTuple,
            m.Field(
                alias="python-files",
                description="Canonical pytest test module patterns.",
            ),
        ]
        # flext-wkii.17 (codex): collection roots are validated config, not local state.
        test_paths: Annotated[
            t.StrTuple,
            m.Field(
                alias="test-paths",
                description="Canonical tracked roots collected by pytest.",
            ),
        ]
        filter_warnings: Annotated[
            t.StrTuple,
            m.Field(
                alias="filter-warnings", description="Canonical pytest warning filters."
            ),
        ]

        standard_markers: Annotated[
            t.StrSequence,
            m.Field(
                alias="standard-markers",
                description="Standard pytest markers enforced by modernizer.",
            ),
        ]
        standard_addopts: Annotated[
            t.StrSequence,
            m.Field(
                alias="standard-addopts",
                description="Standard pytest addopts enforced by modernizer.",
            ),
        ]
        external_gate_markers: Annotated[
            t.StrTuple,
            m.Field(
                alias="external-gate-markers",
                description=(
                    "Markers of external-token gates deselected by offline"
                    " verification and reported as NOT EXECUTED; each must be"
                    " declared in standard-markers."
                ),
            ),
        ]

        @property
        def external_gate_deselection(self) -> str:
            """Pytest ``-m`` expression that skips external gates."""
            return f"not ({' or '.join(self.external_gate_markers)})"

        ci_excluded_markers: Annotated[
            t.StrTuple,
            m.Field(
                alias="ci-excluded-markers",
                description="Declared markers deselected in CI and pre-commit only.",
            ),
        ]

        process_timeout_seconds: Annotated[
            int,
            m.Field(
                alias="process-timeout-seconds",
                gt=0,
                description="Hard timeout for the complete pytest process.",
            ),
        ]

        @u.model_validator(mode="after")
        def _validate_execution_limits(self) -> Self:
            """Keep item and termination budgets inside the hard invocation cap."""
            if (
                self.testmon_namespace.is_absolute()
                or self.testmon_namespace == Path()
                or ".." in self.testmon_namespace.parts
            ):
                msg = "pytest testmon namespace must be a non-empty relative path"
                raise ValueError(msg)
            for field_name, filename in (
                ("database", self.testmon_database_filename),
                ("lock", self.testmon_lock_filename),
            ):
                if Path(filename).name != filename or filename in {".", ".."}:
                    msg = f"pytest testmon {field_name} filename must be one basename"
                    raise ValueError(msg)
            if self.testmon_database_filename == self.testmon_lock_filename:
                msg = "pytest testmon database and lock filenames must differ"
                raise ValueError(msg)
            if self.case_timeout_seconds >= self.run_timeout_seconds:
                msg = "pytest case timeout must be less than run timeout"
                raise ValueError(msg)
            if self.termination_grace_seconds >= self.run_timeout_seconds:
                msg = "pytest termination grace must be less than run timeout"
                raise ValueError(msg)
            if (
                self.case_timeout_seconds + self.termination_grace_seconds
                > self.run_timeout_seconds
            ):
                msg = "pytest run timeout must include item and termination budgets"
                raise ValueError(msg)
            if self.slow_timeout_seconds <= self.case_timeout_seconds:
                msg = "pytest slow timeout must exceed the per-case timeout"
                raise ValueError(msg)
            if self.slow_timeout_seconds >= self.run_timeout_seconds:
                msg = "pytest slow timeout must be less than run timeout"
                raise ValueError(msg)
            if self.process_timeout_seconds <= self.run_timeout_seconds:
                msg = (
                    "pytest process timeout must exceed the run timeout: the"
                    " process boundary caps the whole invocation, so a value at"
                    " or below the session budget kills healthy suites"
                )
                raise ValueError(msg)
            if self.process_timeout_seconds <= (
                self.run_timeout_seconds + self.termination_grace_seconds
            ):
                msg = "pytest process timeout must exceed run and termination budgets"
                raise ValueError(msg)
            derived_options = ("--timeout", "--session-timeout")
            if any(
                option in {"-o", "--override-ini"}
                or option.startswith(("-o=", "--override-ini=", *derived_options))
                for option in self.standard_addopts
            ):
                msg = "pytest runtime policy options are derived from typed fields"
                raise ValueError(msg)
            if "--verbose" not in self.progress_args:
                msg = "pytest progress args must expose verbose item progress"
                raise ValueError(msg)
            declared_markers = {
                marker.split(":", 1)[0].strip() for marker in self.standard_markers
            }
            if any(
                marker not in declared_markers for marker in self.ci_excluded_markers
            ):
                msg = "pytest ci-excluded-markers must be declared in standard-markers"
                raise ValueError(msg)
            undeclared = [
                marker
                for marker in self.external_gate_markers
                if marker not in declared_markers
            ]
            if not self.external_gate_markers or undeclared:
                msg = (
                    "pytest external-gate-markers must be a non-empty subset of"
                    f" standard-markers; undeclared: {undeclared}"
                )
                raise ValueError(msg)
            runner_owned_prefixes = (
                "-k",
                "-n",
                "-o",
                "-p",
                "-x",
                "--cov",
                "--dist",
                "--junitxml",
                "--override-ini",
                "--timeout",
            )
            for argument in (
                *self.progress_args,
                *self.report_args,
                *self.diagnostic_args,
            ):
                if (
                    not argument.startswith("-")
                    or any(character in argument for character in "\0\r\n")
                    or argument.startswith(runner_owned_prefixes)
                ):
                    msg = "pytest reporting args must not override runner-owned policy"
                    raise ValueError(msg)
            return self

    class TomlsortConfig(m.ArbitraryTypesModel):
        """tomlsort baseline settings loaded from YAML."""

        all: Annotated[bool, m.Field(description="Sort all TOML tables and entries.")]
        in_place: Annotated[bool, m.Field(description="Apply TOML sorting in place.")]
        process_timeout_seconds: Annotated[
            int,
            m.Field(
                alias="process-timeout-seconds",
                gt=0,
                le=60,
                description="Maximum runtime for Taplo resolution or formatting.",
            ),
        ]
        sort_first: Annotated[
            t.StrSequence, m.Field(description="Top-level TOML sections ordered first.")
        ]

    class YamlfixConfig(m.ArbitraryTypesModel):
        """yamlfix baseline settings loaded from YAML."""

        line_length: Annotated[int, m.Field(description="Maximum YAML line length.")]
        preserve_quotes: Annotated[
            bool, m.Field(description="Preserve quote style in YAML output.")
        ]
        whitelines: Annotated[
            int, m.Field(description="Blank line count between YAML entries.")
        ]
        section_whitelines: Annotated[
            int, m.Field(description="Blank line count between YAML sections.")
        ]
        explicit_start: Annotated[
            bool, m.Field(description="Emit explicit YAML start marker.")
        ]

    class CoverageConfig(m.ArbitraryTypesModel):
        """Coverage baseline settings loaded from YAML."""

        source: Annotated[
            t.StrSequence,
            m.Field(description="Production roots measured by full coverage runs."),
        ]
        show_missing: Annotated[
            bool,
            m.Field(
                alias="show-missing",
                description="Display missing lines in coverage report.",
            ),
        ] = True
        skip_covered: Annotated[
            bool,
            m.Field(
                alias="skip-covered",
                description="Skip covered files in coverage report.",
            ),
        ] = False
        precision: Annotated[
            int, m.Field(description="Decimal precision for coverage percentages.")
        ] = 2
        exclude_also: Annotated[
            t.StrSequence,
            m.Field(
                alias="exclude-also",
                default_factory=tuple,
                description="Coverage report line patterns excluded from runtime coverage.",
            ),
        ]
        omit: Annotated[
            t.StrSequence,
            m.Field(
                default_factory=tuple,
                description="Glob patterns excluded from coverage collection.",
            ),
        ]

    class VultureConfig(m.ArbitraryTypesModel):
        """Vulture production-reachability policy loaded from YAML."""

        # NOTE (multi-agent, flext-j47u): keep dead-code scope fully config-owned.
        exclude: Annotated[
            t.StrTuple,
            m.Field(
                description="Declaration-only path patterns excluded from Vulture."
            ),
        ]
        min_confidence: Annotated[
            int,
            m.Field(
                alias="min-confidence",
                description="Minimum confidence reported as dead production code.",
            ),
        ]
        paths: Annotated[
            t.StrTuple,
            m.Field(description="Production roots scanned for unreachable code."),
        ]
        verbose: bool = m.Field(
            description="Enable Vulture's internal scanner trace when requested."
        )

    class MarkdownPrettierConfig(m.ArbitraryTypesModel):
        """Prettier projection policy: ``make fmt``'s markdown formatter."""

        prose_wrap: Annotated[
            str,
            m.Field(
                default="always",
                alias="prose-wrap",
                description="Prettier proseWrap contract for markdown prose.",
            ),
        ]
        tab_width: Annotated[
            int,
            m.Field(
                default=4,
                alias="tab-width",
                description="Prettier tabWidth for non-markdown targets.",
            ),
        ]
        md_tab_width: Annotated[
            int,
            m.Field(
                default=2,
                alias="md-tab-width",
                description="Prettier tabWidth override for markdown targets.",
            ),
        ]

    class MarkdownConfig(m.ArbitraryTypesModel):
        """Markdown lint rules and excluded non-documentation surfaces."""

        rules: t.JsonMapping = m.Field(description="Rumdl-compatible rule mapping.")
        exclude: t.StrTuple = m.Field(
            description="Glob patterns excluded from Markdown quality checks."
        )

        @staticmethod
        def _default_prettier() -> (
            FlextInfraModelsDepsToolConfig.MarkdownPrettierConfig
        ):
            """Resolve the policy owner after the enclosing model is defined."""
            return FlextInfraModelsDepsToolConfig.MarkdownPrettierConfig()

        prettier: Annotated[
            FlextInfraModelsDepsToolConfig.MarkdownPrettierConfig,
            m.Field(
                default_factory=_default_prettier,
                description="Prettier formatting policy projected into .prettierrc.",
            ),
        ]

    class ToolConfigTools(m.ArbitraryTypesModel):
        """Tool map loaded from YAML."""

        codespell: FlextInfraModelsDepsToolConfig.CodespellConfig = m.Field(
            description="Codespell settings"
        )
        deptry: FlextInfraModelsDepsToolConfig.DeptryConfig = m.Field(
            description="Deptry settings"
        )
        hatch: FlextInfraModelsDepsToolConfig.HatchConfig = m.Field(
            description="Hatch metadata settings"
        )
        markdown: FlextInfraModelsDepsToolConfig.MarkdownConfig = m.Field(
            description="Markdown lint settings"
        )
        ruff: FlextInfraModelsDepsToolConfig.RuffConfig = m.Field(
            description="Ruff settings"
        )
        mypy: FlextInfraModelsDepsToolConfig.MypyConfig = m.Field(
            description="Mypy settings"
        )
        pydantic_mypy: FlextInfraModelsDepsToolConfig.PydanticMypyConfig = m.Field(
            alias="pydantic-mypy", description="Pydantic mypy plugin configuration."
        )
        pyright: FlextInfraModelsDepsToolConfig.PyrightConfig = m.Field(
            description="Pyright settings"
        )
        pyrefly: FlextInfraModelsDepsToolConfig.PyreflyConfig = m.Field(
            description="Pyrefly settings"
        )
        pytest: FlextInfraModelsDepsToolConfig.PytestConfig = m.Field(
            description="Pytest settings"
        )
        tomlsort: FlextInfraModelsDepsToolConfig.TomlsortConfig = m.Field(
            description="Tomlsort settings"
        )
        vulture: FlextInfraModelsDepsToolConfig.VultureConfig = m.Field(
            description="Vulture production-reachability settings"
        )
        yamlfix: FlextInfraModelsDepsToolConfig.YamlfixConfig = m.Field(
            description="Yamlfix settings"
        )
        coverage: FlextInfraModelsDepsToolConfig.CoverageConfig = m.Field(
            description="Coverage configuration with per-project-type thresholds."
        )

    class ProjectTypeOverrideConfig(m.ArbitraryTypesModel):
        """Per-project-type override settings."""

        pyright: Annotated[
            t.StrMapping,
            m.Field(description="Pyright override settings for this project type."),
        ] = m.Field(default_factory=FlextInfraModelsDefaults.ImmutableEmptyMapping)

    class ProjectTypeOverridesConfig(m.ArbitraryTypesModel):
        """Project-type-specific override matrix from ``config/tooling.yaml``."""

        core: FlextInfraModelsDepsToolConfig.ProjectTypeOverrideConfig = m.Field(
            description="Core overrides"
        )
        domain: FlextInfraModelsDepsToolConfig.ProjectTypeOverrideConfig = m.Field(
            description="Domain overrides"
        )
        platform: FlextInfraModelsDepsToolConfig.ProjectTypeOverrideConfig = m.Field(
            description="Platform overrides"
        )
        integration: FlextInfraModelsDepsToolConfig.ProjectTypeOverrideConfig = m.Field(
            description="Integration overrides"
        )
        app: FlextInfraModelsDepsToolConfig.ProjectTypeOverrideConfig = m.Field(
            description="App overrides"
        )

    class LazyInitConfig(m.ArbitraryTypesModel):
        """Declarative policy for ``__init__.py`` lazy export generation."""

        import_layer_order: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                alias="import-layer-order",
                default=(
                    "settings",
                    "config",
                    "c",
                    "t",
                    "p",
                    "m",
                    "u",
                    "base",
                    "services",
                    "api",
                    "cli",
                ),
                description=(
                    "Canonical dependency layer order for project "
                    "imports. Lower index = lower layer. A module may "
                    "runtime-import modules at equal or lower index "
                    "(relative-dot within the same package); importing "
                    "a module at higher index is a reverse dependency "
                    "and the engine emits it under ``if TYPE_CHECKING:`` "
                    "(see ``reverse_import_mode``). Any value not in "
                    "the fleet SSOT is rejected."
                ),
            ),
        ]
        reverse_import_mode: Annotated[
            Literal["type_checking"],
            m.Field(
                alias="reverse-import-mode",
                description=(
                    "How reverse (upward) runtime dependencies are "
                    "emitted. ``type_checking`` moves the import into "
                    "an ``if TYPE_CHECKING:`` block. The engine rejects "
                    "any other value; reverse runtime imports are a "
                    "module defect fixed at the module root cause."
                ),
            ),
        ] = "type_checking"
        forward_import_form: Annotated[
            Literal["relative_dot"],
            m.Field(
                alias="forward-import-form",
                description=(
                    "How forward (downward) intra-project imports are "
                    "emitted. ``relative_dot`` uses relative imports "
                    "within the same package."
                ),
            ),
        ] = "relative_dot"

    class ToolConfigDocument(m.ArbitraryTypesModel):
        """Root schema for canonical ``config/tooling.yaml`` policy data."""

        tools: FlextInfraModelsDepsToolConfig.ToolConfigTools = m.Field(
            description="Tools"
        )
        project_type_overrides: FlextInfraModelsDepsToolConfig.ProjectTypeOverridesConfig = m.Field(
            alias="project-type-overrides",
            description="Per-project-type configuration overrides.",
        )
        lazy_init: FlextInfraModelsDepsToolConfig.LazyInitConfig = m.Field(
            alias="lazy-init", description="Declarative lazy-init generation policy."
        )

        @staticmethod
        def _default_mod() -> FlextInfraModelsDepsToolConfig.ModConfig:
            return FlextInfraModelsDepsToolConfig.ModConfig()

        mod: FlextInfraModelsDepsToolConfig.ModConfig = m.Field(
            default_factory=_default_mod,
            description="Declarative make-mod phase policy.",
        )

    class ToolingScalarSetting(m.ArbitraryTypesModel):
        """One validated scalar setting rendered into an explicit TOML table."""

        name: Annotated[t.NonEmptyStr, m.Field(description="TOML setting name")]
        value: Annotated[
            str, m.Field(description="Validated Pyright diagnostic severity")
        ]

    class ToolingPyrightEnvironment(m.ArbitraryTypesModel):
        """One resolved Pyright execution environment."""

        root: Annotated[t.NonEmptyStr, m.Field(description="Environment root")]
        extra_paths: Annotated[
            t.StrTuple, m.Field(description="Resolved environment import paths")
        ]
        settings: Annotated[
            t.VariadicTuple[FlextInfraModelsDepsToolConfig.ToolingScalarSetting],
            m.Field(description="Resolved environment diagnostics"),
        ]

    class ToolingConformedTools(m.FlexibleModel):
        """Typed view of the ``[tool]`` tables one conformed pyproject carries."""

        deptry: Annotated[t.JsonMapping, m.Field(description="Conformed deptry table")]
        mypy: Annotated[t.JsonMapping, m.Field(description="Conformed mypy table")]
        mypy_path: Annotated[
            t.StrTuple,
            m.Field(
                validation_alias=m.AliasPath("mypy", "mypy_path"),
                description="Synced Mypy search paths, absent before the first sync",
            ),
        ] = ()
        pyrefly: Annotated[
            t.JsonMapping, m.Field(description="Conformed pyrefly table")
        ]
        pyrefly_search_path: Annotated[
            t.StrTuple,
            m.Field(
                validation_alias=m.AliasPath("pyrefly", "search-path"),
                description="Synced Pyrefly search paths, absent before the first sync",
            ),
        ] = ()
        pyright: Annotated[
            t.JsonMapping, m.Field(description="Conformed pyright table")
        ]
        first_party: Annotated[
            t.StrTuple,
            m.Field(
                validation_alias=m.AliasPath(
                    "ruff", "lint", "isort", "known-first-party"
                ),
                description="Conformed first-party namespaces",
            ),
        ]
        ruff_src: Annotated[
            t.StrTuple,
            m.Field(
                validation_alias=m.AliasPath("ruff", "src"),
                description="Conformed Ruff source roots",
            ),
        ]
        ruff_exclude: Annotated[
            t.StrTuple,
            m.Field(
                validation_alias=m.AliasPath("ruff", "exclude"),
                description="Conformed Ruff exclusions",
            ),
        ]
        ruff_ignore: Annotated[
            t.StrTuple,
            m.Field(
                validation_alias=m.AliasPath("ruff", "lint", "ignore"),
                description="Conformed Ruff ignores",
            ),
        ]

    # flext-j47u (codex): explicit runtime-only values keep the Jinja structure full.
    class ToolingRuntimeContext(m.ArbitraryTypesModel):
        """Resolved project/workspace values consumed by the complete template."""

        project_kind: Annotated[
            t.NonEmptyStr, m.Field(description="Resolved project classification")
        ]
        first_party: Annotated[
            t.StrTuple, m.Field(description="Resolved first-party namespaces")
        ]
        mypy_path: Annotated[
            t.StrTuple, m.Field(description="Resolved Mypy search paths")
        ]
        pyrefly_search_path: Annotated[
            t.StrTuple, m.Field(description="Resolved Pyrefly search paths")
        ]
        pyrefly_project_includes: Annotated[
            t.StrTuple, m.Field(description="Resolved Pyrefly production includes")
        ]
        pyright_exclude: Annotated[
            t.StrTuple, m.Field(description="Resolved Pyright exclusions")
        ]
        pyright_ignore: Annotated[
            t.StrTuple, m.Field(description="Resolved Pyright ignored paths")
        ] = ()
        pyright_include: Annotated[
            t.StrTuple, m.Field(description="Resolved Pyright production roots")
        ]
        pyright_extra_paths: Annotated[
            t.StrTuple, m.Field(description="Resolved Pyright import paths")
        ]
        pyright_settings: Annotated[
            t.VariadicTuple[FlextInfraModelsDepsToolConfig.ToolingScalarSetting],
            m.Field(description="Resolved Pyright scalar settings"),
        ]
        pyright_execution_environments: Annotated[
            t.VariadicTuple[FlextInfraModelsDepsToolConfig.ToolingPyrightEnvironment],
            m.Field(description="Resolved Pyright environments"),
        ]
        ruff_src: Annotated[
            t.StrTuple, m.Field(description="Resolved Ruff source roots")
        ]
        ruff_exclude: Annotated[
            t.StrTuple, m.Field(description="Resolved Ruff exclusions")
        ]
        ruff_ignore: Annotated[
            t.StrTuple,
            m.Field(description="Resolved ordinary and justified Ruff ignores"),
        ]


__all__: list[str] = ["FlextInfraModelsDepsToolConfig"]
