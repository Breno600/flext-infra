"""Ruff and Mypy tool configuration models for the deps subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from flext_cli import m

from flext_infra import c, t
from flext_infra._models.deps_tool_config_project import (
    FlextInfraModelsDepsToolConfigProject,
)


class FlextInfraModelsDepsToolConfigLinters(FlextInfraModelsDepsToolConfigProject):
    """Linters tool configuration models."""

    class CodespellConfig(m.ArbitraryTypesModel):
        """Codespell settings loaded from YAML."""

        check_filenames: Annotated[
            bool,
            m.Field(
                alias="check-filenames",
                description="Check filenames in addition to file contents.",
            ),
        ]
        ignore_words_list: Annotated[
            str,
            m.Field(
                alias="ignore-words-list",
                description="Comma-separated allowlist for known project terms.",
            ),
        ] = ""

    class RuffFormatConfig(m.ArbitraryTypesModel):
        """Ruff format settings loaded from YAML."""

        docstring_code_format: Annotated[
            bool,
            m.Field(
                alias="docstring-code-format",
                description="Enable ruff docstring code block formatting.",
            ),
        ]
        indent_style: Annotated[
            str,
            m.Field(
                alias="indent-style",
                description="Indent style for ruff formatter output.",
            ),
        ]
        line_ending: Annotated[
            str,
            m.Field(
                alias="line-ending",
                description="Line ending style for ruff formatter output.",
            ),
        ]
        quote_style: Annotated[
            str,
            m.Field(
                alias="quote-style",
                description="Quote style for ruff formatter output.",
            ),
        ]
        skip_magic_trailing_comma: Annotated[
            bool,
            m.Field(
                alias="skip-magic-trailing-comma",
                description="Collapse short comma-terminated constructs onto one line.",
            ),
        ]

    class RuffIsortConfig(m.ArbitraryTypesModel):
        """Ruff isort settings loaded from YAML."""

        combine_as_imports: Annotated[
            bool,
            m.Field(
                alias="combine-as-imports",
                description="Combine `as` imports in grouped isort blocks.",
            ),
        ]
        force_single_line: Annotated[
            bool,
            m.Field(
                alias="force-single-line",
                description="Force single-line imports in isort output.",
            ),
        ]
        split_on_trailing_comma: Annotated[
            bool,
            m.Field(
                alias="split-on-trailing-comma",
                description="Split imports when a trailing comma exists.",
            ),
        ]

    class RuffPydocstyleConfig(m.ArbitraryTypesModel):
        """Ruff pydocstyle settings loaded from YAML."""

        convention: Annotated[
            Literal["google", "numpy", "pep257"],
            m.Field(
                description=(
                    "Docstring convention; Ruff disables the docstring rules "
                    "it does not use, one of each mutually exclusive pair "
                    "included."
                ),
            ),
        ]

    class RuffPylintConfig(m.ArbitraryTypesModel):
        """Ruff Pylint policy for operator-approved native type descriptors."""

        allow_dunder_method_names: Annotated[
            t.SequenceOf[Literal["__base__", "__bases__"]],
            m.Field(
                alias="allow-dunder-method-names",
                description=(
                    "Only Python type.__base__ and type.__bases__ read-only "
                    "protocol properties are authorized by the operator."
                ),
            ),
        ]

    class RuffTypeCheckingConfig(m.ArbitraryTypesModel):
        """Ruff flake8-type-checking settings loaded from YAML."""

        runtime_evaluated_roots: Annotated[
            t.SequenceOf[t.NonEmptyStr],
            m.Field(
                alias="runtime-evaluated-roots",
                min_length=1,
                description=(
                    "Qualified base classes whose subclasses evaluate their "
                    "annotations at runtime; codegen derives every project "
                    "base inheriting one into runtime-evaluated-base-classes."
                ),
            ),
        ]

    class RuffAuthorizedException(m.ArbitraryTypesModel):
        """One operator-authorized Ruff exception, recorded with its authority.

        An exception exists only together with the operator ruling that
        authorized it and the reason its rules cannot hold for its scope; an
        entry missing either is refused when the config loads.
        """

        rules: Annotated[
            t.SequenceOf[t.Infra.RuffRule],
            m.Field(min_length=1, description="Ruff rules the exception covers."),
        ]
        files: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                description="Glob the exception is scoped to; absent, every file.",
            ),
        ] = None
        authority: Annotated[
            t.NonEmptyStr,
            m.Field(description="Operator ruling that authorized the exception."),
        ]
        reason: Annotated[
            t.NonEmptyStr,
            m.Field(description="Why the rules cannot hold for this scope."),
        ]

    class BanditAuthorizedException(m.ArbitraryTypesModel):
        """One operator-authorized Bandit exception, scoped to owner modules.

        Bandit applies a skip to a whole invocation and reads no per-path
        exception, so the security gate audits the matching files in their own
        invocation that skips only these tests; every other file keeps every
        test. An entry missing its authority or reason is refused at load.
        """

        tests: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(min_length=1, description="Bandit test IDs the owners may raise."),
        ]
        files: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Project-relative globs of the owner modules, matched "
                    "with full-path glob semantics."
                ),
            ),
        ]
        authority: Annotated[
            t.NonEmptyStr,
            m.Field(description="Operator ruling that authorized the exception."),
        ]
        reason: Annotated[
            t.NonEmptyStr,
            m.Field(description="Why the tests cannot hold for these owners."),
        ]

    class BanditConfig(m.ArbitraryTypesModel):
        """Bandit security gate settings loaded from YAML."""

        authorized_exceptions: Annotated[
            tuple[FlextInfraModelsDepsToolConfigLinters.BanditAuthorizedException, ...],
            m.Field(
                alias="authorized-exceptions",
                description=(
                    "Operator-authorized Bandit exceptions, each audited in "
                    "its own invocation that skips only its tests."
                ),
            ),
        ]

    class RuffLintConfig(m.ArbitraryTypesModel):
        """Ruff lint settings loaded from YAML."""

        select: Annotated[
            t.StrSequence,
            m.Field(description="Ruff lint rule selectors."),
        ] = m.Field(default_factory=tuple)
        unfixable: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Rules whose Ruff fixes delete code or diagnostics; reported, "
                    "never auto-fixed."
                ),
            ),
        ]
        extend_safe_fixes: Annotated[
            t.StrSequence,
            m.Field(
                alias="extend-safe-fixes",
                description=(
                    "Rules whose unsafe Ruff fixes are proven to preserve code, "
                    "comments and diagnostics."
                ),
            ),
        ]
        banned_api: Annotated[
            t.StrMapping,
            m.Field(
                alias="banned-api",
                description="Forbidden direct APIs and their canonical alternatives.",
            ),
        ]
        ban_relative_imports: Annotated[
            Literal["all"],
            m.Field(
                alias="ban-relative-imports",
                description="Relative imports are banned; every import is absolute.",
            ),
        ]
        copyright_notice_rgx: Annotated[
            t.NonEmptyStr,
            m.Field(
                alias="copyright-notice-rgx",
                description="Regex every module's copyright notice must match.",
            ),
        ]
        fix_recipes: Annotated[
            t.MappingKV[t.Infra.RuffRule, c.Infra.LintFixRecipe],
            m.Field(
                alias="fix-recipes",
                description=(
                    "Ruff rule name -> repair make fix applies to the findings "
                    "Ruff reports without a fix of its own."
                ),
            ),
        ]
        fix_recipe_phases: Annotated[
            t.VariadicTuple[t.VariadicTuple[c.Infra.LintFixRecipe]],
            m.Field(
                alias="fix-recipe-phases",
                description=(
                    "Recipe phases make fix applies in order; Ruff re-reads "
                    "the tree after each phase so a later phase sees the "
                    "findings an earlier one created or cured."
                ),
            ),
        ]
        fix_recipe_residual: Annotated[
            frozenset[c.Infra.LintFixRecipe],
            m.Field(
                alias="fix-recipe-residual",
                description=(
                    "Recipes whose findings may survive by law: their "
                    "remainder stays a visible check finding for manual "
                    "repair instead of failing make fix."
                ),
            ),
        ]
        isort: FlextInfraModelsDepsToolConfigLinters.RuffIsortConfig = m.Field(
            description="Ruff isort configuration",
        )
        pydocstyle: FlextInfraModelsDepsToolConfigLinters.RuffPydocstyleConfig = (
            m.Field(description="Ruff pydocstyle configuration")
        )
        pylint: FlextInfraModelsDepsToolConfigLinters.RuffPylintConfig = m.Field(
            description="Ruff Pylint native type descriptor policy",
        )
        flake8_type_checking: Annotated[
            FlextInfraModelsDepsToolConfigLinters.RuffTypeCheckingConfig,
            m.Field(
                alias="flake8-type-checking",
                description="Ruff flake8-type-checking configuration",
            ),
        ]
        authorized_exceptions: Annotated[
            tuple[FlextInfraModelsDepsToolConfigLinters.RuffAuthorizedException, ...],
            m.Field(
                alias="authorized-exceptions",
                description=(
                    "Operator-authorized Ruff exceptions: unscoped entries render "
                    "as ignore, scoped entries as per-file-ignores."
                ),
            ),
        ]

        @m.computed_field
        @property
        def ignore(self) -> t.StrSequence:
            """Rules excepted for every file, rendered as Ruff ``ignore``.

            Returns:
                The resulting ``t.StrSequence``.
            """
            return tuple(
                sorted({
                    rule
                    for entry in self.authorized_exceptions
                    if entry.files is None
                    for rule in entry.rules
                }),
            )

        @m.computed_field
        @property
        def per_file_ignores(self) -> t.Infra.PerFileIgnores:
            """Scoped exceptions, rendered as Ruff ``per-file-ignores``.

            Returns:
                The resulting ``t.Infra.PerFileIgnores``.
            """
            return {
                pattern: tuple(
                    sorted({
                        rule
                        for entry in self.authorized_exceptions
                        if entry.files == pattern
                        for rule in entry.rules
                    }),
                )
                for pattern in sorted({
                    entry.files
                    for entry in self.authorized_exceptions
                    if entry.files is not None
                })
            }

        @m.model_validator(mode="after")
        def _reject_repeated_exception(
            self,
        ) -> FlextInfraModelsDepsToolConfigLinters.RuffLintConfig:
            """Refuse a rule excepted twice for the same scope.

            Returns:
                The validated Ruff lint settings.

            Raises:
                ValueError: If two entries except one rule for the same scope.

            """
            scopes = [
                (entry.files, rule)
                for entry in self.authorized_exceptions
                for rule in entry.rules
            ]
            repeated = sorted({
                f"{rule} for {files or 'every file'}"
                for files, rule in scopes
                if scopes.count((files, rule)) > 1
            })
            if repeated:
                msg = "Ruff exceptions declared twice: " + ", ".join(repeated)
                raise ValueError(msg)
            return self

    class RuffConfig(m.ArbitraryTypesModel):
        """Ruff top-level settings loaded from YAML."""

        extend_exclude: Annotated[
            t.StrSequence,
            m.Field(
                alias="extend-exclude",
                description=(
                    "Workspace exclusions added to Ruff's defaults: "
                    "provider-owned tool-home projections stay outside the "
                    "member lint scope."
                ),
            ),
        ] = m.Field(default_factory=tuple)
        namespace_packages: Annotated[
            t.StrSequence,
            m.Field(
                alias="namespace-packages",
                description="Intentional PEP 420 namespace roots checked by Ruff.",
            ),
        ] = m.Field(default_factory=tuple)
        fix: Annotated[bool, m.Field(description="Enable automatic ruff fixes")]
        informative_rules: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                alias="informative-rules",
                description=(
                    "Ruff rule names reported as warnings: their findings "
                    "stay visible in the gate log, the summary, and the SARIF "
                    "reports, but never fail the lint gate (operator ruling "
                    "2026-10-05: rules the operator never authorized as "
                    "blocking are informative only)."
                ),
            ),
        ] = ()
        findings_exit_codes: Annotated[
            t.VariadicTuple[int],
            m.Field(
                alias="findings-exit-codes",
                description="Exit statuses with which Ruff reports its findings.",
            ),
        ]
        line_length: Annotated[
            int,
            m.Field(alias="line-length", description="Maximum line length."),
        ]
        preview: Annotated[bool, m.Field(description="Enable preview ruff behavior.")]
        respect_gitignore: Annotated[
            bool,
            m.Field(
                alias="respect-gitignore",
                description="Respect .gitignore exclusions.",
            ),
        ]
        show_fixes: Annotated[
            bool,
            m.Field(
                alias="show-fixes",
                description="Display fixed violations in ruff output.",
            ),
        ]
        src: Annotated[
            t.StrSequence,
            m.Field(description="Source roots used by ruff import analysis."),
        ] = m.Field(default_factory=tuple)
        target_version: Annotated[
            str,
            m.Field(
                alias="target-version",
                description="Python target version for ruff.",
            ),
        ]
        format: FlextInfraModelsDepsToolConfigLinters.RuffFormatConfig = m.Field(
            description="Ruff format configuration",
        )
        lint: FlextInfraModelsDepsToolConfigLinters.RuffLintConfig = m.Field(
            description="Ruff lint configuration",
        )

    class MypyOverrideConfig(m.ArbitraryTypesModel):
        """Single [[tool.mypy.overrides]] entry."""

        modules: Annotated[
            t.StrSequence,
            m.Field(description="Module patterns for this override."),
        ]
        follow_untyped_imports: Annotated[
            bool,
            m.Field(
                alias="follow-untyped-imports",
                description="Analyze installed source even without typing metadata.",
            ),
        ] = False
        justification: Annotated[
            str,
            m.Field(
                description=(
                    "Required citation (GitHub issue / PEP / mypy docs) justifying "
                    "this override. AGENTS.md:319 forbids suppressions without "
                    "evidence; leave empty only for strictly transitional overrides "
                    "with a TODO in the module comment."
                ),
            ),
        ] = ""

    class MypyConfig(m.ArbitraryTypesModel):
        """Mypy baseline settings loaded from YAML."""

        timeout_seconds: Annotated[
            int,
            m.Field(
                gt=0,
                description=(
                    "Mypy wall-time budget in seconds (SSOT); a project"
                    " overlay may only lower it."
                ),
            ),
        ]
        plugins: Annotated[
            t.StrSequence,
            m.Field(
                description="Mypy plugins, including mandatory Pydantic 2 support.",
            ),
        ]

        @m.field_validator("plugins")
        @classmethod
        def require_pydantic_plugin(cls, plugins: t.StrSequence) -> t.StrSequence:
            """Reject configurations without the mandatory Pydantic 2 plugin.

            Returns:
                The validated plugin declarations.

            Raises:
                ValueError: If Pydantic 2 support is missing or replaced by v1.

            """
            if "pydantic.mypy" not in plugins or "pydantic.v1.mypy" in plugins:
                msg = "Mypy requires pydantic.mypy and forbids pydantic.v1.mypy"
                raise ValueError(msg)
            return plugins

        facade_rebind_error_codes: Annotated[
            t.StrSequence,
            m.Field(
                alias="facade-rebind-error-codes",
                description=(
                    "Mypy error codes the canonical facade rebind raises; codegen "
                    "disables them only in the modules written in that form."
                ),
            ),
        ]
        disable_error_code: Annotated[
            t.StrSequence,
            m.Field(
                alias="disable-error-code",
                description=(
                    "Mypy error codes an operator ruling suspends project-wide; "
                    "rendered as [tool.mypy] disable_error_code. The pydantic "
                    "mypy plugin stays mandatory (Pydantic 2 is the contract)."
                ),
            ),
        ]

        @m.field_validator("disable_error_code")
        @classmethod
        def require_mypy_ruling_codes(cls, codes: t.StrSequence) -> t.StrSequence:
            """Validate the operator's immutable Mypy diagnostic contract.

            Returns:
                The declared policy without adding or replacing configured values.

            Raises:
                ValueError: If a mandatory code is removed or another is suspended.

            """
            if set(codes) != {"prop-decorator", "call-arg"}:
                msg = "Mypy ruling requires only prop-decorator and call-arg"
                raise ValueError(msg)
            return codes

        boolean_settings: Annotated[
            t.BoolMapping,
            m.Field(
                alias="boolean-settings",
                description="Mypy boolean settings keyed by option name.",
            ),
        ]
        string_settings: Annotated[
            t.StrMapping,
            m.Field(
                alias="string-settings",
                description=(
                    "Mypy string-valued settings keyed by option name "
                    "(e.g. follow_imports='normal')."
                ),
            ),
        ]
        overrides: Annotated[
            t.VariadicTuple[FlextInfraModelsDepsToolConfigLinters.MypyOverrideConfig],
            m.Field(
                description=(
                    "Per-module mypy overrides for "
                    "auto-generated files and PEP 695 generics."
                ),
            ),
        ] = m.Field(
            default_factory=tuple,
            description=(
                "Per-module mypy overrides for "
                "auto-generated files and PEP 695 generics."
            ),
        )

        @m.model_validator(mode="after")
        def reject_policy_shadow(self) -> Self:
            """Refuse ambiguous options and re-enabling suspended diagnostics.

            Returns:
                The validated settings without modifying their declared values.

            Raises:
                ValueError: If generic settings bypass a dedicated policy owner.

            """
            boolean_keys = {
                key.strip().replace("-", "_") for key in self.boolean_settings
            }
            strings = {
                key.strip().replace("-", "_"): value
                for key, value in self.string_settings.items()
            }
            reserved = {
                c.Infra.PLUGINS,
                "disable_error_code",
                c.Infra.PYTHON_VERSION_UNDERSCORE,
                "overrides",
                "mypy_path",
            }
            if (boolean_keys | strings.keys()) & reserved:
                msg = "Mypy policy cannot be shadowed by generic options"
                raise ValueError(msg)
            if (
                boolean_keys & strings.keys()
                or len(boolean_keys) != len(self.boolean_settings)
                or len(strings) != len(self.string_settings)
            ):
                msg = "Mypy policy rejects duplicate generic options"
                raise ValueError(msg)
            if "enable_error_code" in boolean_keys:
                msg = "Mypy policy enable_error_code requires a string setting"
                raise ValueError(msg)
            if any(
                not key.isascii() or not key.isidentifier()
                for key in (*self.boolean_settings, *self.string_settings)
            ):
                msg = "Mypy policy requires plain option names, not TOML syntax"
                raise ValueError(msg)
            if self.boolean_settings.get("ignore_errors", False) or (
                "ignore_errors" in strings
            ):
                msg = "Mypy policy cannot ignore unsuspended diagnostics"
                raise ValueError(msg)
            enabled = {
                code.strip()
                for code in strings.get("enable_error_code", "").split(",")
                if code.strip()
            }
            if enabled.intersection(self.disable_error_code):
                msg = "Mypy policy cannot re-enable suspended error codes"
                raise ValueError(msg)
            return self

    class PydanticMypyConfig(m.ArbitraryTypesModel):
        """Pydantic mypy plugin settings loaded from YAML."""

        init_forbid_extra: Annotated[
            bool,
            m.Field(
                description=(
                    "Enable forbid-extra init behavior in pydantic mypy plugin."
                ),
            ),
        ]
        init_typed: Annotated[
            bool,
            m.Field(
                description="Enable typed __init__ signatures in pydantic mypy plugin.",
            ),
        ]
        warn_required_dynamic_aliases: Annotated[
            bool,
            m.Field(
                description="Warn on required dynamic aliases in pydantic mypy plugin.",
            ),
        ]


__all__: list[str] = ["FlextInfraModelsDepsToolConfigLinters"]
