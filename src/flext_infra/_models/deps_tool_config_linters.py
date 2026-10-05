"""Ruff and Mypy tool configuration models for the deps subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import Annotated, Literal

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
        isort: FlextInfraModelsDepsToolConfigLinters.RuffIsortConfig = m.Field(
            description="Ruff isort configuration",
        )
        pydocstyle: FlextInfraModelsDepsToolConfigLinters.RuffPydocstyleConfig = (
            m.Field(description="Ruff pydocstyle configuration")
        )
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

        namespace_packages: Annotated[
            t.StrSequence,
            m.Field(
                alias="namespace-packages",
                description="Intentional PEP 420 namespace roots checked by Ruff.",
            ),
        ] = m.Field(default_factory=tuple)
        fix: Annotated[bool, m.Field(description="Enable automatic ruff fixes")]
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
        plugins: Annotated[t.StrSequence, m.Field(description="Mypy plugins list.")] = (
            m.Field(default_factory=tuple)
        )
        disable_error_code: Annotated[
            t.StrSequence,
            m.Field(
                alias="disable-error-code",
                description=(
                    "Mypy error codes suspended fleet-wide (operator law "
                    "2026-10-05): false positives the pydantic-2 canonical "
                    "forms generate (call-arg on validators). The pydantic "
                    "plugin stays mandatory"
                ),
            ),
        ] = ()
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
        ruling_disable_error_codes: Annotated[
            t.StrSequence,
            m.Field(
                alias="ruling-disable-error-codes",
                description=(
                    "Mypy error codes an operator ruling disables project-wide; "
                    "codegen renders them as [tool.mypy] disable_error_code. "
                    "Carries the citation in the config comment."
                ),
            ),
        ] = m.Field(default_factory=tuple)
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
