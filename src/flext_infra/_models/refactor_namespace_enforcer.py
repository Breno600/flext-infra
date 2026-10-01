"""Domain models for namespace enforcer violations and reports."""

from __future__ import annotations

from typing import Annotated

from flext_cli import m

from flext_infra import t

from .mixins import FlextInfraModelsMixins as mm


class FlextInfraModelsNamespaceEnforcer:
    """Namespace enforcer violation and report models."""

    class FileLineViolation(mm.FileLineViolationMixin, m.ContractModel):
        """Shared base: file + line for all violation models."""

    class ImportViolationBase(mm.CurrentImportMixin, FileLineViolation):
        """Shared base: file + line + current_import."""

    class FacadeStatus(m.ContractModel):
        """Facade status."""

        family: Annotated[t.NonEmptyStr, m.Field(description="Facade family name")]
        exists: Annotated[bool, m.Field(description="Whether facade exists")]
        class_name: Annotated[str, m.Field(description="Facade class name")] = ""
        file: Annotated[str, m.Field(description="Facade file path")] = ""
        symbol_count: Annotated[
            t.NonNegativeInt, m.Field(description="Symbol count")
        ] = 0

    class LooseObjectViolation(FileLineViolation):
        """Loose object violation."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Symbol name")]
        kind: Annotated[str, m.Field(description="Object kind")]
        suggestion: Annotated[str, m.Field(description="Fix suggestion")] = ""


    class ImportAliasViolation(ImportViolationBase):
        """Import alias violation."""

        suggested_import: Annotated[
            str, m.Field(description="Suggested import statement")
        ]

    class NamespaceSourceViolation(FileLineViolation):
        """Namespace source violation."""

        alias: Annotated[t.NonEmptyStr, m.Field(description="Runtime alias letter")]
        current_source: Annotated[
            t.NonEmptyStr, m.Field(description="Current import source")
        ]
        correct_source: Annotated[
            t.NonEmptyStr, m.Field(description="Correct import source")
        ]
        current_import: Annotated[str, m.Field(description="Current import statement")]
        suggested_import: Annotated[
            str, m.Field(description="Suggested import statement")
        ]

    class ClassPlacementViolation(FileLineViolation):
        """Class placement violation."""

        name: Annotated[t.NonEmptyStr, m.Field(description="Class name")]
        base_class: Annotated[t.NonEmptyStr, m.Field(description="Base class name")]
        suggestion: Annotated[str, m.Field(description="Fix suggestion")]
        action: Annotated[
            str, m.Field(description="Recommended fix action identifier")
        ] = "manual"
        fixable: Annotated[
            bool, m.Field(description="Whether the violation can be auto-fixed")
        ] = False
        target_facade: Annotated[
            str, m.Field(description="Target facade class suggestion")
        ] = ""
        family: Annotated[
            str, m.Field(description="Canonical family letter (c/m/p/t/u)")
        ] = ""

    class InternalImportViolation(mm.ViolationDetailMixin, ImportViolationBase):
        """Internal import violation."""


    class PrivateImportBypassViolation(mm.ViolationDetailMixin, ImportViolationBase):
        """Private-module import that should use the canonical facade."""

        private_module: Annotated[
            t.NonEmptyStr,
            m.Field(description="Fully-qualified private module being imported"),
        ]
        imported_symbol: Annotated[
            t.NonEmptyStr,
            m.Field(description="Symbol imported from the private module"),
        ]
        suggested_facade: Annotated[
            t.NonEmptyStr, m.Field(description="Canonical facade module to import from")
        ]
        symbol_exported: Annotated[
            bool,
            m.Field(description="Whether the symbol is already exported by the facade"),
        ] = False


    class CyclicImportViolation(m.ContractModel):
        """Cyclic import violation."""

        cycle: Annotated[
            t.VariadicTuple[str], m.Field(description="Import cycle chain")
        ]
        files: Annotated[
            t.VariadicTuple[str], m.Field(description="Files in cycle")
        ] = m.Field(default_factory=tuple)

    class RuntimeAliasViolation(
        mm.FilePathMixin,
        mm.NonNegativeLineMixin,
        mm.ViolationDetailMixin,
        m.ContractModel,
    ):
        """Runtime alias violation."""

        kind: Annotated[str, m.Field(description="Violation kind")]
        alias: Annotated[str, m.Field(description="Alias involved")]


    class CompatibilityAliasViolation(FileLineViolation):
        """Compatibility alias violation."""

        alias_name: Annotated[t.NonEmptyStr, m.Field(description="Alias name")]
        target_name: Annotated[t.NonEmptyStr, m.Field(description="Target name")]
        module_name: Annotated[
            str, m.Field(description="Source module for import-kind violations")
        ] = ""

    class ParseFailureViolation(mm.FilePathMixin, mm.ErrorDetailMixin, m.ContractModel):
        """Parse failure violation."""

        stage: Annotated[t.NonEmptyStr, m.Field(description="Parse stage")]
        error_type: Annotated[t.NonEmptyStr, m.Field(description="Error type")]

    class ProjectEnforcementReport(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Project enforcement report."""

        project_root: Annotated[str, m.Field(description="Project root path")]
        facade_statuses: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.FacadeStatus],
            m.Field(
                default_factory=tuple,
                description="Facade status entries collected for the project.",
            ),
        ]
        loose_objects: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.LooseObjectViolation],
            m.Field(
                default_factory=tuple,
                description="Loose object violations collected for the project.",
            ),
        ]
        import_violations: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.ImportAliasViolation],
            m.Field(
                default_factory=tuple,
                description="Import alias violations collected for the project.",
            ),
        ]
        namespace_source_violations: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.NamespaceSourceViolation],
            m.Field(
                default_factory=tuple,
                description="Namespace source violations collected for the project.",
            ),
        ]
        internal_import_violations: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.InternalImportViolation],
            m.Field(
                default_factory=tuple,
                description="Internal import violations collected for the project.",
            ),
        ]
        private_import_bypass_violations: Annotated[
            t.SequenceOf[
                FlextInfraModelsNamespaceEnforcer.PrivateImportBypassViolation
            ],
            m.Field(
                default_factory=tuple,
                description="Private-import bypass violations collected for the project.",
            ),
        ]
        cyclic_imports: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.CyclicImportViolation],
            m.Field(
                default_factory=tuple,
                description="Cyclic import violations collected for the project.",
            ),
        ]
        runtime_alias_violations: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.RuntimeAliasViolation],
            m.Field(
                default_factory=tuple,
                description="Runtime alias violations collected for the project.",
            ),
        ]
        relocation_findings: Annotated[
            t.NonNegativeInt,
            m.Field(
                description=(
                    "Rule-catalog findings whose rule declares a rope relocation "
                    "and that remain after the namespace pass."
                )
            ),
        ] = 0
        compatibility_alias_violations: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.CompatibilityAliasViolation],
            m.Field(
                default_factory=tuple,
                description="Compatibility alias violations collected for the project.",
            ),
        ]
        foreign_canonical_alias_violations: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.CompatibilityAliasViolation],
            m.Field(
                default_factory=tuple,
                description=(
                    "Foreign canonical alias imports collected for the project."
                ),
            ),
        ]
        class_placement_violations: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.ClassPlacementViolation],
            m.Field(
                default_factory=tuple,
                description="Class placement violations collected for the project.",
            ),
        ]
        parse_failures: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.ParseFailureViolation],
            m.Field(
                default_factory=tuple,
                description="Parse failures collected for the project.",
            ),
        ]
        files_scanned: Annotated[
            t.NonNegativeInt, m.Field(description="Files scanned")
        ] = 0

        @m.computed_field
        @property
        def has_violations(self) -> bool:
            """Whether this project has any violations."""
            missing_facades = any(not f.exists for f in self.facade_statuses)
            violation_fields = (
                self.loose_objects,
                self.import_violations,
                self.namespace_source_violations,
                self.internal_import_violations,
                self.private_import_bypass_violations,
                self.cyclic_imports,
                self.runtime_alias_violations,
                self.compatibility_alias_violations,
                self.foreign_canonical_alias_violations,
                self.class_placement_violations,
                self.parse_failures,
            )
            return (
                missing_facades
                or self.relocation_findings > 0
                or any(v for v in violation_fields)
            )

    class WorkspaceEnforcementReport(m.ArbitraryTypesModel):
        """Workspace enforcement report."""

        workspace: Annotated[t.NonEmptyStr, m.Field(description="Repository root path")]
        projects: Annotated[
            t.SequenceOf[FlextInfraModelsNamespaceEnforcer.ProjectEnforcementReport],
            m.Field(
                default_factory=tuple,
                description="Per-project enforcement reports for the workspace.",
            ),
        ]

        @m.computed_field
        @property
        def has_violations(self) -> bool:
            """Whether any project carries a violation."""
            return any(project.has_violations for project in self.projects)


__all__: list[str] = ["FlextInfraModelsNamespaceEnforcer"]
