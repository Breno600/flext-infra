"""Domain models for the transformers subpackage.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from flext_cli import m

from flext_infra import t


class FlextInfraModelsTransformers:
    """Models for source transformers — exposed through the ``m.Infra`` facade."""

    class AliasMigrationContext(m.ContractModel):
        """Resolved ownership and import-root context for one alias migration."""

        policy_owner: Annotated[
            str,
            m.Field(description="Project package that owns the canonical alias policy"),
        ]
        import_root: Annotated[
            str,
            m.Field(description="Public facade root from which consumers import"),
        ]

    class SemanticFilePlan(m.ContractModel):
        """Exact before state and desired state for one semantic migration file."""

        project: Annotated[Path, m.Field(description="Physical owning project root")]
        path: Annotated[Path, m.Field(description="Absolute managed file path")]
        before: Annotated[
            m.Cli.AtomicFileState,
            m.Field(description="Descriptor-authenticated file state before migration"),
        ]
        desired_content: Annotated[
            bytes | None,
            m.Field(
                strict=True,
                description=(
                    "Exact desired bytes after migration, or None for no change"
                ),
            ),
        ]
        desired_mode: Annotated[
            int | None,
            m.Field(
                ge=0,
                le=0o7777,
                strict=True,
                description="Exact desired mode, or None for no change",
            ),
        ]
        changes: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Recorded migration operations"),
        ] = m.Field(default_factory=tuple)
        source_states: Annotated[
            tuple[m.Cli.AtomicFileState, ...],
            m.Field(
                description="Read-only semantic dependency inputs",
            ),
        ] = m.Field(default_factory=tuple)

    class SemanticMigrationEdit(m.ContractModel):
        """One validated in-memory semantic source rewrite."""

        # Why: source bytes must survive validation byte-exact;
        # the strict base strips whitespace, which corrupts CAS comparisons.
        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(str_strip_whitespace=False)

        file_path: Annotated[Path, m.Field(description="Source file to rewrite")]
        original_source: Annotated[
            str,
            m.Field(description="Source bytes before migration"),
        ]
        updated_source: Annotated[
            str,
            m.Field(description="Prospective source bytes after migration"),
        ]
        changes: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Recorded migration operations"),
        ] = ()

    class CompatibilityAliasRewritePlan(m.ArbitraryTypesModel):
        """Binding-proven rewrites planned for one compatibility-alias cutover file."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        local_aliases: Annotated[
            t.StrMapping,
            m.Field(description="Aliases the file declares, mapped to their targets"),
        ]
        import_aliases: Annotated[
            t.MappingKV[str, t.StrMapping],
            m.Field(description="Imported aliases per source module and their targets"),
        ]
        attribute_aliases: Annotated[
            t.MappingKV[t.Pair[str, str], str],
            m.Field(description="Module attribute alias accesses and their targets"),
        ]
        qualified_aliases: Annotated[
            t.StrMapping,
            m.Field(description="Qualified alias identities mapped to their targets"),
        ]
        target_bindings: Annotated[
            frozenset[str],
            m.Field(description="Module-level names the file already binds"),
        ]

    class NestingModuleAliasScan(m.ArbitraryTypesModel):
        """Module bindings one consumer holds on modules whose members nest."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        aliases: Annotated[
            t.StrMapping,
            m.Field(description="Local module binding mapped to its nested module"),
        ]
        residual: Annotated[
            frozenset[str],
            m.Field(description="Bindings still used as the module object"),
        ]
        read: Annotated[
            frozenset[str],
            m.Field(description="Bindings read through a member the owner holds"),
        ]
        owner_imports: Annotated[
            frozenset[str],
            m.Field(description="Nested modules whose owner the file imports"),
        ]

    class PrivateImportRewritePlan(m.ArbitraryTypesModel):
        """Binding-proven import rewrites planned for one private-import file."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        removals: Annotated[
            t.MappingKV[str, frozenset[str]],
            m.Field(description="Private symbols removed per source module"),
        ]
        obsolete_imports: Annotated[
            t.MappingKV[str, frozenset[str]],
            m.Field(description="Public roots superseded by their facade alias"),
        ]
        replacements: Annotated[
            t.StrMapping,
            m.Field(description="Private qualified identities and public references"),
        ]
        public_imports: Annotated[
            t.StrMapping,
            m.Field(description="Facade aliases mapped to their publishing package"),
        ]

    class Tier0ImportAnalysis(m.Value):
        """Detection results for a single Python file self-import patterns."""

        # Why: value contract owned by m.Infra transformers facet, not nested
        # in the fixer service.
        package_name: Annotated[
            str,
            m.Field(description="Resolved package name for the analyzed file"),
        ]
        file_path: Annotated[
            Path,
            m.Field(description="Python file analyzed for Tier 0 import violations"),
        ]
        alias_to_module: Annotated[
            t.StrMapping,
            m.Field(description="Alias names mapped to their source modules"),
        ]
        category_a: Annotated[
            frozenset[str],
            m.Field(description="Top-level aliases that are informational only"),
        ] = m.Field(default_factory=frozenset[str])
        category_b: Annotated[
            frozenset[str],
            m.Field(description="Core aliases to redirect to the core package"),
        ] = m.Field(default_factory=frozenset[str])
        category_c: Annotated[
            frozenset[str],
            m.Field(description="Aliases to move into a TYPE_CHECKING block"),
        ] = m.Field(default_factory=frozenset[str])
        category_d: Annotated[
            frozenset[str],
            m.Field(
                description="Runtime-used aliases requiring direct import handling",
            ),
        ] = m.Field(default_factory=frozenset[str])

        @m.computed_field
        @property
        def has_violations(self) -> bool:
            """True if any imports need redirecting or moving.

            Returns:
                The resulting ``bool``.
            """
            return bool(self.category_b or self.category_c or self.category_d)

    class SourceRewrite(m.ArbitraryTypesModel):
        """One source rewrite: replace ``source[start:end]`` with ``text``."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        start: Annotated[int, m.Field(description="Start byte offset in the source")]
        end: Annotated[int, m.Field(description="End byte offset in the source")]
        text: Annotated[str, m.Field(description="Replacement text")]

    class HeaderSpan(m.ArbitraryTypesModel):
        """Byte offsets for the logical sections of a Python module header.

        Mutable accumulator populated incrementally by the header tokenizer
        (``_utilities/transformer_header_parser.py``); never frozen while a
        parse is open.
        """

        shebang_end: Annotated[
            int,
            m.Field(description="Byte offset just after the shebang line"),
        ] = 0
        encoding_end: Annotated[
            int,
            m.Field(description="Byte offset just after the encoding cookie"),
        ] = 0
        comments_end: Annotated[
            int,
            m.Field(description="Byte offset after the leading comment block"),
        ] = 0
        docstring_end: Annotated[
            int,
            m.Field(description="Byte offset after the module docstring"),
        ] = 0
        last_import_end: Annotated[
            int,
            m.Field(description="Byte offset after the last import statement"),
        ] = 0

    class ClassBlockLayout(m.ArbitraryTypesModel):
        """Measured layout of one wrapper class block to unwrap.

        Line coordinates are Rope's one-based lines; ``indentation`` is the
        body column width to strip, and ``docstring_span`` excludes the
        wrapper's own docstring lines from the strip when present.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        header_start: Annotated[int, m.Field(description="First header line")]
        header_end: Annotated[int, m.Field(description="Last header line")]
        body_end: Annotated[int, m.Field(description="Last body line")]
        indentation: Annotated[
            int,
            m.Field(description="Body indent width stripped per line"),
        ]
        docstring_span: Annotated[
            tuple[int, int] | None,
            m.Field(description="Wrapper docstring line span"),
        ] = None

    class HeaderInfo(m.ArbitraryTypesModel):
        """Structural summary of a module header."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        has_future_annotations: Annotated[
            bool,
            m.Field(description="Whether the module already imports annotations"),
        ]
        aliases: Annotated[
            frozenset[str],
            m.Field(description="Local names bound by from-import statements"),
        ]
        span: Annotated[
            FlextInfraModelsTransformers.HeaderSpan,
            m.Field(description="Byte offsets for the header sections"),
        ]


__all__: list[str] = ["FlextInfraModelsTransformers"]
