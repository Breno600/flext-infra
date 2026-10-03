"""Domain models for the deps subpackage.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from flext_cli import m

from flext_infra import t
from flext_infra._models.deps_toml import FlextInfraModelsDepsToml
from flext_infra._models.deps_tool_config import FlextInfraModelsDepsToolConfig
from flext_infra._models.mixins import FlextInfraModelsMixins as mm


class FlextInfraModelsDeps(FlextInfraModelsDepsToolConfig, FlextInfraModelsDepsToml):
    """Models for dependency detection and modernization reporting."""

    class DependencyMarkerEnvironment(m.Value):
        """Complete PEP 508 facts reported by the consumer interpreter."""

        prefix: Annotated[
            Path,
            m.Field(
                exclude=True,
                description="Consumer interpreter environment prefix",
            ),
        ]
        implementation_name: Annotated[
            str,
            m.Field(description="PEP 508 implementation name"),
        ]
        implementation_version: Annotated[
            str,
            m.Field(description="PEP 508 implementation version"),
        ]
        os_name: Annotated[str, m.Field(description="PEP 508 operating system name")]
        platform_machine: Annotated[
            str,
            m.Field(description="PEP 508 machine architecture"),
        ]
        platform_release: Annotated[
            str,
            m.Field(description="PEP 508 platform release"),
        ]
        platform_system: Annotated[str, m.Field(description="PEP 508 platform system")]
        platform_version: Annotated[
            str,
            m.Field(description="PEP 508 platform version"),
        ]
        platform_python_implementation: Annotated[
            str,
            m.Field(description="PEP 508 Python implementation"),
        ]
        python_full_version: Annotated[
            str,
            m.Field(description="PEP 508 complete Python version"),
        ]
        python_version: Annotated[
            str,
            m.Field(description="PEP 508 Python major and minor version"),
        ]
        sys_platform: Annotated[
            str,
            m.Field(description="PEP 508 interpreter platform"),
        ]

    class BindingResolution(m.Value):
        """Active consumer declarations preserved during one editable binding."""

        overrides: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Active dependency source overrides"),
        ]
        constraints: Annotated[
            t.VariadicTuple[str],
            m.Field(description="Active consumer resolution constraints"),
        ]

    class DetectCommand(mm.WriteMixin, m.ContractModel):
        """Canonical CLI payload for ``flext-infra deps detect``.

        Inherits ``apply``/``dry_run``, ``repository_root``, ``projects``,
        ``verbose`` from ``WriteMixin``.
        """

        output_format: Annotated[
            str,
            m.Field(alias="format", description="Output format for dependency report"),
        ] = "text"
        output: Annotated[
            str | None,
            m.Field(None, description="Optional output report path"),
        ] = None
        quiet: Annotated[
            bool,
            m.Field(default=False, description="Reduce command output"),
        ] = False
        no_fail: Annotated[
            bool,
            m.Field(
                alias="no-fail",
                description="Exit successfully even when issues are found",
            ),
        ] = False
        typings: Annotated[
            bool,
            m.Field(default=False, description="Detect required typing packages"),
        ] = False
        apply_typings: Annotated[
            bool,
            m.Field(
                alias="apply-typings",
                description=(
                    "Declare project.optional-dependencies.typings "
                    "and install through UV"
                ),
            ),
        ] = False
        no_pip_check: Annotated[
            bool,
            m.Field(alias="no-pip-check", description="Skip workspace pip check"),
        ] = False
        limits: Annotated[
            str | None,
            m.Field(None, description="Path to dependency limits TOML"),
        ] = None

        @property
        def output_path(self) -> Path | None:
            """Resolved explicit output path when provided."""
            if self.output is None:
                return None
            return Path(self.output).expanduser().resolve()

        @property
        def limits_path(self) -> Path | None:
            """Resolved dependency limits path when provided."""
            if self.limits is None:
                return None
            return Path(self.limits).expanduser().resolve()

    class ExtraPathsCommand(mm.WriteMixin, m.ContractModel):
        """Canonical CLI payload for ``flext-infra deps extra-paths``."""

    class ModernizeCommand(mm.WriteMixin, m.ContractModel):
        """Canonical CLI payload for ``flext-infra deps modernize``."""

        check: Annotated[
            bool,
            m.Field(default=False, description="Run in check mode"),
        ] = False
        audit: Annotated[
            bool,
            m.Field(description="Audit pyproject changes without writing"),
        ] = False
        skip_check: Annotated[
            bool,
            m.Field(alias="skip-check", description="Skip post-write validation step"),
        ] = False
        skip_comments: Annotated[
            bool,
            m.Field(
                alias="skip-comments",
                description="Skip modernization of explanatory comments",
            ),
        ] = False
        rewrite_constraints: Annotated[
            bool,
            m.Field(
                alias="rewrite-constraints",
                description=(
                    "Rewrite dependency constraints from the provisioned runtime"
                ),
            ),
        ] = False

    # Codegen consumes the pure pyproject
    # renderer directly, so no deps CLI payload remains for path/workspace modes.

    class PyprojectDocumentState(m.ArbitraryTypesModel):
        """Centralized normalized TOML state reused across deps workflows.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(validate_default=False)

        pyproject_path: Annotated[Path, m.Field(description="Resolved pyproject path")]
        original_rendered: Annotated[
            str,
            m.Field(description="Original TOML source text"),
        ] = ""
        rendered: Annotated[
            str,
            m.Field(description="Canonical rendered TOML source text"),
        ] = ""
        payload: Annotated[
            t.MutableJsonMapping,
            m.Field(description="Validated plain TOML payload"),
        ] = m.Field(default_factory=dict)

    class PackagedDataSelection(m.ContractModel):
        """Validated data inputs separated by Hatch selection semantics."""

        files: Annotated[
            t.StrTuple,
            m.Field(description="Explicit data files included individually"),
        ] = ()
        directories: Annotated[
            t.StrTuple,
            m.Field(description="Data directories selected with VCS filters"),
        ] = ()

    class RuffProjectFacts(m.ContractModel):
        """Measured per-project facts the canonical Ruff phase derives from."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)
        first_party: Annotated[
            t.StrSequence,
            m.Field(description="Detected first-party namespaces"),
        ]
        stale_patterns: Annotated[
            t.StrSequence,
            m.Field(description="Legacy per-file ignore patterns to retire"),
        ]
        per_file_ignores: Annotated[
            t.MappingKV[str, t.StrSequence],
            m.Field(description="Effective managed per-file ignores"),
        ]
        analysis_exclusions: Annotated[
            t.StrSequence | None,
            m.Field(
                default=None,
                description=(
                    "Declared analysis exclusions; None derives workspace globs"
                ),
            ),
        ]
        generated_python_roots: Annotated[
            t.StrSequence,
            m.Field(description="Generated python roots to exclude"),
        ]

    class PyprojectDeclaredTopology(m.ContractModel):
        """Project topology a caller declares instead of discovering it on disk.

        An atomic scaffold knows its shipped roots and analyzer roots before
        they exist; an empty declaration keeps filesystem discovery.
        """

        root_modules: Annotated[
            t.StrTuple,
            m.Field(description="Top-level single-file modules the package ships"),
        ] = ()
        root_packages: Annotated[
            t.StrTuple,
            m.Field(description="Top-level packages shipped beyond the primary one"),
        ] = ()
        repository_namespace_packages: Annotated[
            t.StrTuple,
            m.Field(
                description=(
                    "Implicit namespace directories shipped from the repository root"
                ),
            ),
        ] = ()
        packaged_data_paths: Annotated[
            t.StrTuple,
            m.Field(description="Repository-declared relative data paths to ship"),
        ] = ()
        packaged_data_excludes: Annotated[
            t.StrTuple,
            m.Field(
                description=(
                    "Repository-relative files omitted from declared data directories"
                ),
            ),
        ] = ()
        planned_data_files: Annotated[
            t.StrTuple,
            m.Field(
                description=(
                    "Exact scaffold file destinations planned before publication"
                ),
            ),
        ] = ()
        declared_python_dirs: Annotated[
            t.StrTuple,
            m.Field(description="Python roots declared for the project"),
        ] = ()
        declared_python_dirs_are_complete: Annotated[
            bool,
            m.Field(
                description=(
                    "Declared roots are the full set; discovery must not widen it"
                ),
            ),
        ] = False
        project_kind: Annotated[
            str | None,
            m.Field(description="Declared project kind; absent classifies on demand"),
        ] = None
        analysis_exclusions: Annotated[
            t.StrTuple | None,
            m.Field(
                description=(
                    "Workspace-relative paths excluded from analysis; absent "
                    "derives them from the workspace"
                ),
            ),
        ] = None

    class PyprojectAnalyzerContext(m.ContractModel):
        """Placement and Python roots of one pyproject the analyzer phases conform.

        Paths are absent while an atomic scaffold renders a project that is not
        on disk yet; the declared roots then stand in for discovery.
        """

        is_root: Annotated[
            bool,
            m.Field(description="Whether the pyproject is the repository root"),
        ]
        repository_root: Annotated[
            Path | None,
            m.Field(description="Repository root on disk"),
        ] = None
        project_dir: Annotated[
            Path | None,
            m.Field(description="Project directory on disk"),
        ] = None
        declared_python_dirs: Annotated[
            t.StrTuple,
            m.Field(description="Python roots declared for the project"),
        ] = ()
        declared_python_dirs_are_complete: Annotated[
            bool,
            m.Field(
                description=(
                    "Declared roots are the full set; discovery must not widen it"
                ),
            ),
        ] = False

    class DependencyLimitsInfo(m.ArbitraryTypesModel):
        """Dependency limits configuration metadata."""

        python_version: Annotated[
            str | None,
            m.Field(None, description="Python version"),
        ] = None
        limits_path: Annotated[str, m.Field("", description="Path to limits file")] = ""

    class PipCheckReport(m.ArbitraryTypesModel):
        """Pip check execution report with status and output lines."""

        ok: Annotated[
            bool,
            m.Field(default=True, description="Whether pip check passed"),
        ] = True
        lines: Annotated[
            t.StrSequence,
            m.Field(description="Pip check output lines"),
        ] = m.Field(default_factory=tuple)

    class DeptryIssueGroups(m.ArbitraryTypesModel):
        """Deptry issue grouping model by error code (DEP001-DEP004)."""

        dep001: Annotated[
            t.MutableSequenceOf[t.MappingKV[str, t.Primitives | None]],
            m.Field(description="DEP001 issues"),
        ] = m.Field(default_factory=list[t.MappingKV[str, t.Primitives | None]])
        dep002: Annotated[
            t.MutableSequenceOf[t.MappingKV[str, t.Primitives | None]],
            m.Field(description="DEP002 issues"),
        ] = m.Field(default_factory=list[t.MappingKV[str, t.Primitives | None]])
        dep003: Annotated[
            t.MutableSequenceOf[t.MappingKV[str, t.Primitives | None]],
            m.Field(description="DEP003 issues"),
        ] = m.Field(default_factory=list[t.MappingKV[str, t.Primitives | None]])
        dep004: Annotated[
            t.MutableSequenceOf[t.MappingKV[str, t.Primitives | None]],
            m.Field(description="DEP004 issues"),
        ] = m.Field(default_factory=list[t.MappingKV[str, t.Primitives | None]])

    class DeptryReport(m.ArbitraryTypesModel):
        """Deptry analysis report with categorized issue modules."""

        missing: Annotated[
            t.StrSequence,
            m.Field(description="Missing dependencies"),
        ] = m.Field(default_factory=tuple)
        unused: Annotated[t.StrSequence, m.Field(description="Unused dependencies")] = (
            m.Field(default_factory=tuple)
        )
        transitive: Annotated[
            t.StrSequence,
            m.Field(description="Transitive dependencies"),
        ] = m.Field(default_factory=tuple)
        dev_in_runtime: Annotated[
            t.StrSequence,
            m.Field(description="Dev dependencies in runtime"),
        ] = m.Field(default_factory=tuple)
        raw_count: Annotated[
            t.NonNegativeInt,
            m.Field(0, description="Raw issue count"),
        ] = 0

    class ProjectDependencyReport(mm.ProjectNameMixin, m.ArbitraryTypesModel):
        """Project-level dependency report combining deptry results."""

        deptry: FlextInfraModelsDeps.DeptryReport = m.Field(description="Deptry report")

    class TypingsReport(m.ArbitraryTypesModel):
        """Typing stubs analysis report with required/current/delta packages."""

        required_packages: Annotated[
            t.StrSequence,
            m.Field(description="Required packages"),
        ] = m.Field(default_factory=tuple)
        hinted: Annotated[t.StrSequence, m.Field(description="Hinted packages")] = (
            m.Field(default_factory=tuple)
        )
        missing_modules: Annotated[
            t.StrSequence,
            m.Field(description="Missing modules"),
        ] = m.Field(default_factory=tuple)
        current: Annotated[t.StrSequence, m.Field(description="Current typings")] = (
            m.Field(default_factory=tuple)
        )
        to_add: Annotated[t.StrSequence, m.Field(description="Typings to add")] = (
            m.Field(default_factory=tuple)
        )
        to_remove: Annotated[
            t.StrSequence,
            m.Field(description="Typings to remove"),
        ] = m.Field(default_factory=tuple)
        limits_applied: Annotated[
            bool,
            m.Field(default=False, description="Whether limits were applied"),
        ] = False
        python_version: Annotated[
            str | None,
            m.Field(None, description="Python version"),
        ] = None
        untyped_imports_followed: Annotated[
            bool,
            m.Field(
                description=(
                    "Governed mypy follow_untyped_imports policy; when true, "
                    "missing stubs are not findings"
                ),
            ),
        ]

    class ProjectRuntimeReport(m.ArbitraryTypesModel):
        """Project runtime dependency and typings report."""

        deptry: FlextInfraModelsDeps.DeptryReport = m.Field(description="Deptry report")
        typings: FlextInfraModelsDeps.TypingsReport | None = m.Field(
            None,
            description="Typings report",
            validate_default=True,
        )

    class WorkspaceDependencyReport(m.ArbitraryTypesModel):
        """Workspace-level dependency analysis report aggregating all projects.

        Enforcement exemption: internal tooling model with intentional
        mutable state.
        """

        workspace: Annotated[str, m.Field(description="Workspace name")]
        projects: t.MappingKV[str, FlextInfraModelsDeps.ProjectRuntimeReport] = m.Field(
            description="Per-project reports",
        )
        pip_check: FlextInfraModelsDeps.PipCheckReport | None = m.Field(
            None,
            description="Pip check report",
            validate_default=True,
        )
        dependency_limits: FlextInfraModelsDeps.DependencyLimitsInfo | None = m.Field(
            None,
            description="Dependency limits",
            validate_default=True,
        )


__all__: list[str] = ["FlextInfraModelsDeps"]
