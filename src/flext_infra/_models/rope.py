"""Domain models for rope refactoring operations.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from flext_cli import m

from flext_infra import c, p, t
from flext_infra._models import FlextInfraModelsMixins
from flext_infra._models._codegen.base import FlextInfraCodegen


class FlextInfraModelsRope:
    """Rope operation result models — accessed via m.Infra.Rope.*."""

    # Callers resolve project
    # selection once; source iteration has one exact, branch-free request shape.
    class SourceScanRequest(m.ContractModel):
        """Exact project roots selected for one production-source scan."""

        project_roots: Annotated[
            t.VariadicTuple[Path],
            m.Field(
                min_length=1,
                description="Non-empty ordered project roots to scan",
            ),
        ]

    class ExportOptions(m.ContractModel):
        """Canonical options for Rope module export discovery."""

        include_dunder: Annotated[
            bool,
            m.Field(description="Whether dunder exports should be returned."),
        ] = False
        allow_main: Annotated[
            bool,
            m.Field(description="Whether a module-level main() may be exported."),
        ] = False
        allow_assignments: Annotated[
            bool,
            m.Field(description="Whether assignment-backed names may be exported."),
        ] = False
        allow_functions: Annotated[
            bool,
            m.Field(description="Whether module functions may be exported."),
        ] = False
        require_explicit_all: Annotated[
            bool,
            m.Field(
                description="Whether __all__ must exist for exports to be returned.",
            ),
        ] = False

    class ClassInfo(FlextInfraModelsMixins.PositiveLineMixin, m.ContractModel):
        """Semantic class info from rope — name, line, bases in one shot."""

        name: Annotated[str, m.Field(description="Class name")]
        bases: Annotated[t.StrSequence, m.Field(description="Base class names")] = ()

    class SourceClassReference(m.ContractModel):
        """A lexical binding and its attribute path, distinct from Ruff's spelling."""

        target: Annotated[str, m.Field(description="Dotted target the binding names")]
        attributes: Annotated[
            t.StrTuple,
            m.Field(description="Attribute path read off the binding target"),
        ] = ()
        qualified_base: Annotated[
            str,
            m.Field(description="Fully qualified base spelling when resolved"),
        ] = ""

    class SourceClassDefinition(m.ContractModel):
        """One source declaration, preserving ordered bases and member shadowing."""

        identity: Annotated[
            str,
            m.Field(description="Qualified identity of the declared class"),
        ]
        bases: Annotated[
            t.VariadicTuple[FlextInfraModelsRope.SourceClassReference],
            m.Field(description="Ordered base references of the declaration"),
        ]
        members: Annotated[
            t.MappingKV[str, FlextInfraModelsRope.SourceClassReference | None],
            m.Field(description="Member name to shadowing reference mapping"),
        ]

    class ScopeDefinition(FlextInfraModelsMixins.PositiveLineMixin, m.ContractModel):
        """One semantic scope (def/class) discovered via rope's scope tree.

        Built from ``PyScope.get_kind()``/``get_scopes()`` and the scope's
        ``pyobject.get_name()`` — no ``ast`` walking. ``is_module_level`` is True
        when the scope is a direct child of the module (global) scope.
        """

        name: Annotated[str, m.Field(description="Definition name")]
        kind: Annotated[
            c.Infra.RopeScopeKind,
            m.Field(description="Rope scope kind (Module/Function/Class/Unknown)"),
        ]
        is_module_level: Annotated[
            bool,
            m.Field(description="Whether the scope is a direct child of the module"),
        ]

    class LogicalStatement(FlextInfraModelsMixins.PositiveLineMixin, m.ContractModel):
        """One logical statement from the rope structure boundary (no ``ast``).

        Built from a rope ``LogicalLineFinder`` region plus an indent stack over
        the rope-owned source; carries the lexical category, indentation, the
        enclosing def/class scope, and the rope source slice for lexical probes.
        """

        indent: Annotated[
            int,
            m.Field(ge=0, description="Leading-whitespace column of the statement"),
        ]
        # Rope owns both boundaries so multiline consumers
        # never reconstruct statement ranges from source text.
        end_line: Annotated[
            int,
            m.Field(ge=1, description="Final line in the Rope logical region"),
        ]
        start_offset: Annotated[
            int,
            m.Field(ge=0, description="Source offset where the region starts"),
        ]
        end_offset: Annotated[
            int,
            m.Field(ge=0, description="Source offset where the region ends"),
        ]
        category: Annotated[
            c.Infra.StatementCategory,
            m.Field(description="Lexical category of the leading token"),
        ]
        enclosing_kind: Annotated[
            c.Infra.RopeScopeKind,
            m.Field(description="Kind of the nearest enclosing def/class scope"),
        ] = c.Infra.RopeScopeKind.MODULE
        enclosing_name: Annotated[
            str,
            m.Field(description="Name of the nearest enclosing def/class, or empty"),
        ] = ""
        # Consumers share this Rope-derived guard fact instead
        # of rebuilding TYPE_CHECKING control flow with stdlib AST visitors.
        type_checking_guarded: Annotated[
            bool,
            m.Field(description="Whether the statement is inside TYPE_CHECKING"),
        ] = False
        text: Annotated[
            str,
            m.Field(description="Rope-owned source slice for the statement"),
        ] = ""

    class FamilyWrapperFlatten(m.ArbitraryTypesModel):
        """Rope identity of one namespace wrapper flattened into its family owner."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        project: Annotated[
            t.Infra.RopeProject,
            m.Field(description="Rope snapshot project resolving every consumer"),
        ]
        owner_name: Annotated[
            str,
            m.Field(description="Family owner class receiving promoted members"),
        ]
        wrapper_name: Annotated[
            str,
            m.Field(description="Declared name of the flattened namespace wrapper"),
        ]
        wrapper: Annotated[
            t.Infra.RopePyName,
            m.Field(description="Rope identity of the flattened namespace wrapper"),
        ]
        names: Annotated[
            t.StrMapping,
            m.Field(description="Wrapper member names mapped to promoted names"),
        ]

    class ConstantInfo(
        FlextInfraModelsMixins.NonNegativeLineMixin,
        FlextInfraModelsMixins.NestedClassPathMixin,
        m.ContractModel,
    ):
        """Final-annotated constant definition from rope semantic analysis."""

        name: Annotated[str, m.Field(description="Constant name")]
        annotation: Annotated[str, m.Field(description="Type annotation text")] = ""
        value: Annotated[str, m.Field(description="Value representation")] = ""

    class SymbolInfo(FlextInfraModelsMixins.NonNegativeLineMixin, m.ContractModel):
        """Top-level symbol metadata from rope semantic analysis."""

        name: Annotated[str, m.Field(description="Symbol name")]
        kind: Annotated[
            str,
            m.Field(description="Symbol kind: class, function, assignment"),
        ]

    class ConsolidatorScannedFile(m.ArbitraryTypesModel):
        """One scanned module whose assignments match canonical constants."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(frozen=True)

        resource: Annotated[
            t.Infra.RopeResource,
            m.Field(description="Rope resource of the scanned module"),
        ]
        source: Annotated[
            str,
            m.Field(description="Source captured at scan; restored on failed gates"),
        ]
        matches: Annotated[
            t.SequenceOf[t.Triple[FlextInfraModelsRope.SymbolInfo, str, str]],
            m.Field(description="Matched symbol, canonical reference, and raw value"),
        ]

    class ModuleSemanticState(m.ContractModel):
        """Unified semantic snapshot for one Rope module analysis pass."""

        class_infos: Annotated[
            t.VariadicTuple[FlextInfraModelsRope.ClassInfo],
            m.Field(description="Local classes discovered in the module"),
        ] = ()
        declared_imports: Annotated[
            t.StrMapping,
            m.Field(description="Declared import targets by name"),
        ]
        semantic_imports: Annotated[
            t.StrMapping,
            m.Field(description="Resolved import targets by name"),
        ]

    class RopeModuleIndexEntry(m.ContractModel):
        """Generic Rope-backed index entry for one Python module resource."""

        file_path: Annotated[Path, m.Field(description="Absolute filesystem path")]
        resource_path: Annotated[
            str,
            m.Field(description="Rope resource path relative to the project root"),
        ]
        module_name: Annotated[
            str,
            m.Field(description="Fully-qualified Rope module name for this file"),
        ]
        package_name: Annotated[
            str,
            m.Field(
                description="Importable package resolved for the containing directory",
            ),
        ]
        package_dir: Annotated[
            Path,
            m.Field(description="Absolute package directory for this module"),
        ]
        project_root: Annotated[
            Path | None,
            m.Field(
                description="Owning project root resolved from the Rope source folder",
            ),
        ] = None
        is_package_init: Annotated[
            bool,
            m.Field(description="Whether this resource is the package __init__.py"),
        ] = False

    class RopePackageIndexEntry(m.ContractModel):
        """Generic Rope-backed package aggregation entry."""

        package_dir: Annotated[
            Path,
            m.Field(description="Absolute package directory represented by this entry"),
        ]
        init_path: Annotated[
            Path,
            m.Field(description="Expected __init__.py path for this package directory"),
        ]
        package_name: Annotated[
            str,
            m.Field(
                description="Importable package name, or empty when non-importable",
            ),
        ]
        project_root: Annotated[
            Path | None,
            m.Field(
                description="Owning project root resolved for this package directory",
            ),
        ] = None
        modules: Annotated[
            t.VariadicTuple[FlextInfraModelsRope.RopeModuleIndexEntry],
            m.Field(
                description=(
                    "Direct Python module resources that belong to this package"
                ),
            ),
        ] = ()
        direct_child_dirs: Annotated[
            t.VariadicTuple[Path],
            m.Field(
                description="Direct child package directories discovered from Rope",
            ),
        ] = ()
        descendant_child_dirs: Annotated[
            t.VariadicTuple[Path],
            m.Field(
                description="All descendant package directories discovered from Rope",
            ),
        ] = ()

    class RopeWorkspaceIndex(m.ContractModel):
        """Generic Rope-backed workspace index for package planning."""

        repository_root: Annotated[
            Path,
            m.Field(
                description="Absolute repository root used to open the Rope project",
            ),
        ]
        package_dirs: Annotated[
            t.VariadicTuple[Path],
            m.Field(
                description="All package directories discovered from Rope resources",
            ),
        ] = ()
        packages_by_dir: Annotated[
            t.MappingKV[str, FlextInfraModelsRope.RopePackageIndexEntry],
            m.Field(description="Package entries keyed by absolute directory path"),
        ]
        modules_by_path: Annotated[
            t.MappingKV[str, FlextInfraModelsRope.RopeModuleIndexEntry],
            m.Field(description="Module entries keyed by absolute file path"),
        ]
        package_dir_by_name: Annotated[
            t.MappingKV[str, Path],
            m.Field(description="Importable package directory keyed by package name"),
        ]
        project_package_by_root: Annotated[
            t.StrMapping,
            m.Field(
                description="Canonical source package name keyed by project root path",
            ),
        ]

    class RopeProjectLayout(m.ContractModel):
        """Canonical project layout derived once for Rope-backed codegen flows."""

        project_root: Annotated[Path, m.Field(description="Resolved project root path")]
        project_name: Annotated[str, m.Field(description="Canonical project name")]
        package_name: Annotated[str, m.Field(description="Primary Python package name")]
        package_alias: Annotated[
            str,
            m.Field(description="Canonical root alias derived from the package"),
        ]
        class_stem: Annotated[
            str,
            m.Field(description="Canonical facade class stem derived from the project"),
        ]
        src_dir: Annotated[
            Path,
            m.Field(description="Resolved source directory for the project"),
        ]
        package_dir: Annotated[
            Path,
            m.Field(description="Resolved package directory for the project"),
        ]
        init_path: Annotated[
            Path,
            m.Field(description="Resolved package __init__.py path"),
        ]
        runtime_aliases: Annotated[
            t.StrSequence,
            m.Field(
                description="Canonical runtime aliases published by the package root",
            ),
        ] = ()

    class RopeModuleConvention(m.ContractModel):
        """Unified module naming and namespace convention for one file."""

        file_path: Annotated[Path, m.Field(description="Resolved Python module path")]
        relative_path: Annotated[
            Path,
            m.Field(description="Module path relative to its package directory"),
        ]
        module_name: Annotated[str, m.Field(description="Fully-qualified module name")]
        package_name: Annotated[
            str,
            m.Field(description="Importable package name for the module"),
        ]
        package_dir: Annotated[
            Path,
            m.Field(description="Resolved package directory containing the module"),
        ]
        package_context: Annotated[
            FlextInfraCodegen.LazyInitPackageContext,
            m.Field(description="Resolved lazy-init package context for the module"),
        ]
        module_policy: Annotated[
            FlextInfraCodegen.NamespaceModulePolicy,
            m.Field(description="Canonical module policy derived for the module"),
        ]
        project_layout: Annotated[
            FlextInfraModelsRope.RopeProjectLayout | None,
            m.Field(
                description="Resolved project layout, when the module belongs to one",
            ),
        ] = None

    class RopeInventoryRecordInput(m.ArbitraryTypesModel):
        """Validated payload for building one rope inventory census object."""

        rope_project: Annotated[
            t.Infra.RopeProject,
            m.Field(description="Rope project used for reference discovery"),
        ]
        resource: Annotated[
            t.Infra.RopeResource,
            m.Field(description="Rope resource containing the symbol definition"),
        ]
        source: Annotated[
            str,
            m.Field(description="Full source text used to compute fingerprints"),
        ]
        name: Annotated[str, m.Field(description="Resolved symbol name being recorded")]
        pyname: Annotated[
            t.Infra.RopePyName,
            m.Field(description="Rope pyname node for the symbol"),
        ]
        module_name: Annotated[
            str,
            m.Field(description="Resolved module name for the symbol"),
        ]
        project_name: Annotated[
            str,
            m.Field(description="Resolved project name for census attribution"),
        ]
        convention: Annotated[
            FlextInfraModelsRope.RopeModuleConvention,
            m.Field(description="Module convention metadata for tier/facade checks"),
        ]
        scope_chain: Annotated[
            t.StrSequence,
            m.Field(description="Nested scope path leading to the symbol"),
        ] = ()
        class_chain: Annotated[
            t.StrSequence,
            m.Field(description="Nested class path leading to the symbol"),
        ] = ()
        child_scope: Annotated[
            p.Infra.RopeScopeDsl | None,
            m.Field(description="Optional child scope object from rope"),
        ] = None
        rope_workspace: Annotated[
            p.Infra.RopeWorkspaceDsl,
            m.Field(description="Shared rope workspace/session owning the resource"),
        ]

    class RopeWorkspaceSession(m.ContractModel):
        """Public Rope workspace snapshot used by the service DSL."""

        repository_root: Annotated[
            Path,
            m.Field(description="Resolved repository root requested by the caller"),
        ]
        rope_repository_root: Annotated[
            Path,
            m.Field(description="Canonical root used to open the shared Rope project"),
        ]
        # Policy stays in config.Infra;
        # this field-only model retains only materialized session state.
        workspace_index: Annotated[
            FlextInfraModelsRope.RopeWorkspaceIndex,
            m.Field(description="Materialized workspace index for the open session"),
        ]


__all__: list[str] = ["FlextInfraModelsRope"]
