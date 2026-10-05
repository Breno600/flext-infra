"""Repository identity, project declaration, and conformance target models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath
from typing import Annotated, ClassVar, Literal

from flext_cli import m, t

from flext_infra._constants import FlextInfraConstantsCodegenProject
from flext_infra._models._config.beads import FlextInfraConfigModelsBeads
from flext_infra._models._config.contract import FlextInfraConfigModelsContract
from flext_infra._models._config.make import FlextInfraConfigModelsMake


class FlextInfraConfigModelsRepository:
    """Repository identity, project declaration, and conformance target models."""

    @staticmethod
    def validated_hatch_build_hook_path(value: Path | None) -> Path | None:
        """Return one normalized project-relative Hatch hook declaration.

        Returns:
            One normalized project-relative Hatch hook declaration.

        Raises:
            ValueError: If hatch_build_hook_path must be a safe project-relative path.

        """
        if value is None:
            return None
        raw = str(value)
        not_project_relative = (
            value.is_absolute() or not value.parts or value.as_posix() in {"", "."}
        )
        unsafe_segments = (
            ".." in value.parts or "\\" in raw or bool(PureWindowsPath(raw).drive)
        )
        if not_project_relative or unsafe_segments:
            msg = f"hatch_build_hook_path must be a safe project-relative path: {raw}"
            raise ValueError(msg)
        return value

    class ProjectSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Deterministic project metadata required to materialize a new tree."""

        flext_source: Annotated[
            t.NonEmptyStr | None,
            m.Field(
                description=(
                    "Direct Git infrastructure requirement declared for scaffolding"
                ),
            ),
        ] = None

        # ProjectSpec is the sole declaration
        # owner; absence is meaningful and must never select a conventional hook.
        hatch_build_hook_path: Annotated[
            Path | None,
            m.Field(description="Project-relative Hatch custom build hook module"),
        ] = None
        package_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Import package name"),
        ]
        class_stem: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical public facade class stem"),
        ]
        namespace: Annotated[
            t.NonEmptyStr,
            m.Field(description="Nested c/t/p/m/u namespace"),
        ]
        constant_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured project name exposed through constants"),
        ]
        namespace_attribute: Annotated[
            t.NonEmptyStr,
            m.Field(description="Private module namespace token"),
        ]
        alias: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical public instance alias"),
        ]
        environment_prefix: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project settings environment prefix"),
        ]
        description: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project description"),
        ]
        license: Annotated[t.NonEmptyStr, m.Field(description="SPDX license id")]
        author_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Author display name"),
        ]
        author_email: Annotated[t.NonEmptyStr, m.Field(description="Author email")]
        upstream: Annotated[
            t.NonEmptyStr,
            m.Field(description="Upstream FLEXT facade module"),
        ]
        namespace_scan_dirs: Annotated[
            t.StrSequence,
            m.Field(
                description=(
                    "Production source roots the namespace validator enforces; "
                    "empty keeps every root in scope (previous behavior)"
                ),
            ),
        ] = ()
        inherited_facets: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Upstream facets re-exported by the project root. The lazy-init "
                    "public-root planner reads this to decide which upstream "
                    "namespace names the generated root __init__ may re-export: a "
                    "facet is inherited when declared here or actually imported "
                    "from source. Without the field the planner cannot honour a "
                    "manifest declaration and re-exports only what source imports "
                    "prove -- which silently drops manifest-declared facets."
                ),
            ),
        ] = ()
        root_packages: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Additional top-level packages under the source directory "
                    "that the distribution must ship beyond the primary "
                    "package. Declared per repository because the layout is a "
                    "fact of that repository, not of its upstream profile."
                ),
            ),
        ] = ()
        repository_namespace_packages: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Implicit namespace directories shipped from the repository root"
                ),
            ),
        ] = ()
        root_modules: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Top-level single-file modules under the source directory "
                    "shipped alongside the packages; see the root_packages "
                    "namesake for why the declaration is per repository."
                ),
            ),
        ] = ()
        packaged_data_paths: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Repository-relative data files and directories"
                    " shipped with the package"
                ),
            ),
        ] = ()
        packaged_data_excludes: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Repository-relative files omitted from declared data directories"
                ),
            ),
        ] = ()
        cli_module: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the package ships its cli entry module. A scaffold "
                    "renders the cli seed in the same plan; an existing checkout "
                    "derives the fact from its source tree. The default console "
                    "script is declared only then, because conform loads every "
                    "declared entry point in its fresh-import stage."
                ),
            ),
        ] = True
        runtime_dependency_overlay: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                default=(),
                description=(
                    "Runtime requirements this repository adds ahead of its "
                    "dependency profile's runtime set. The profile states what "
                    "every project on that upstream needs; the overlay states "
                    "what this one additionally needs, so neither owner has to "
                    "encode the other's scope."
                ),
            ),
        ] = ()
        homepage: Annotated[t.NonEmptyStr, m.Field(description="Project homepage")]
        documentation: Annotated[
            t.NonEmptyStr,
            m.Field(description="Project documentation URL"),
        ]
        repository_root_rel: Annotated[
            t.NonEmptyStr,
            m.Field(description="Declared relative path to the workspace root"),
        ]
        year: Annotated[int, m.Field(ge=2025, description="Copyright year")]

        @m.field_validator("hatch_build_hook_path")
        @classmethod
        def _validate_hatch_build_hook_path(cls, value: Path | None) -> Path | None:
            return FlextInfraConfigModelsRepository.validated_hatch_build_hook_path(
                value,
            )

    class WorkspaceIntegrationSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Declared integration provider and branch of one repository."""

        provider: Annotated[
            t.NonEmptyStr,
            m.Field(description="Configured provider key"),
        ]
        branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Workspace integration branch"),
        ]
        organization: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional provider organization override"),
        ] = None
        base_url: Annotated[
            t.NonEmptyStr | None,
            m.Field(description="Optional provider base URL override"),
        ] = None

    class RepositoryRef(FlextInfraConfigModelsContract.ConfigContract):
        """One declared repository and its immutable Git origin contract."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(use_enum_values=False)

        name: Annotated[t.NonEmptyStr, m.Field(description="Catalog key")]
        distribution: Annotated[
            t.NonEmptyStr,
            m.Field(description="Python distribution or repository name"),
        ]
        url: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical GitHub clone URL ending in .git"),
        ]
        path: Annotated[
            Path,
            m.Field(description="POSIX path relative to its workspace root"),
        ]
        role: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Repository role in the declared topology"),
        ]
        state: Annotated[
            FlextInfraConstantsCodegenProject.RepositoryState,
            m.Field(description="Repository lifecycle state"),
        ] = FlextInfraConstantsCodegenProject.RepositoryState.ACTIVE
        checkout: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Physical checkout topology of the declared tree; "
                    "'root' marks the workspace's own primary checkout"
                ),
            ),
        ] = "root"
        provider: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Provider key the declaring repository's own manifest carries"
                ),
            ),
        ]
        kind: Annotated[
            FlextInfraConstantsCodegenProject.ProjectKind,
            m.Field(
                description=(
                    "Governance kind; only internal_flext repositories are "
                    "rewritten by generation. Defaults to internal_flext, which "
                    "is the behaviour every manifest had before this field "
                    "existed: a repository that omits it is one this generator "
                    "already conforms. Requiring it outright made every manifest "
                    "written before the field was added fail validation, so a "
                    "consumer that had not yet updated could not run `make gen` "
                    "at all -- and a consumer is allowed to lag."
                ),
            ),
        ] = FlextInfraConstantsCodegenProject.ProjectKind.INTERNAL_FLEXT
        codegen: Annotated[
            FlextInfraConstantsCodegenProject.CodegenKind,
            m.Field(description="Repository code-generation policy"),
        ]
        package: Annotated[
            bool,
            m.Field(description="Repository publishes a Python package"),
        ]
        publishes_release: Annotated[
            bool,
            m.Field(
                default=False,
                description=(
                    "Whether this distribution explicitly opts into the generated "
                    "release protocol"
                ),
            ),
        ] = False
        editable: Annotated[
            bool,
            m.Field(description="Overlay repository as an editable dependency"),
        ]
        read_only: Annotated[
            bool,
            m.Field(description="Repository rejects generated mutations"),
        ]
        uv_link_mode: Annotated[
            Literal["clone", "copy", "hardlink", "symlink"] | None,
            m.Field(
                description=(
                    "Repository-specific uv installation link mode; absent uses "
                    "the fleet toolchain default"
                ),
            ),
        ] = None
        duplication_trees: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                description=(
                    "Project-relative directory trees the duplication gate "
                    "must scan besides the canonical src/tests scope (e.g. "
                    "declared Helm charts)"
                ),
            ),
        ] = ()
        extra_verbs: Annotated[
            t.VariadicTuple[FlextInfraConfigModelsMake.MakeVerbSpec],
            m.Field(
                description=(
                    "Additional public Make verbs this repository dispatches "
                    "beyond the canonical set (e.g. a script command framework)"
                ),
            ),
        ] = ()
        script_dispatch: Annotated[
            FlextInfraConfigModelsRepository.ScriptDispatchSpec | None,
            m.Field(
                description=(
                    "Opt-in script command-framework routing for non-builtin "
                    "verbs and WHAT selectors; None keeps builtin-only dispatch"
                ),
            ),
        ] = None

    class RepositoryConformTarget(FlextInfraConfigModelsContract.ConfigContract):
        """Runtime-derived conformance identity for one repository."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(use_enum_values=False)

        repository: Annotated[
            FlextInfraConfigModelsRepository.RepositoryRef,
            m.Field(description="Declared immutable repository identity"),
        ]
        root: Annotated[
            Path,
            m.Field(description="Resolved repository root receiving conformance"),
        ]
        make_profile: Annotated[
            FlextInfraConstantsCodegenProject.MakeProfile,
            m.Field(description="Make profile inferred from live Git topology"),
        ]
        beads: Annotated[
            FlextInfraConfigModelsBeads.BeadsProjectSpec | None,
            m.Field(description="Repository-local Beads identity when enabled"),
        ] = None
        project: Annotated[
            FlextInfraConfigModelsRepository.ProjectSpec | None,
            m.Field(
                description=(
                    "Declared project metadata of the manifest, when the "
                    "repository declares one; carries the distribution roots "
                    "the packaging phase must prove present"
                ),
            ),
        ] = None
        canonical_project_name: Annotated[
            t.NonEmptyStr,
            m.Field(description="Canonical PEP 621 project name"),
        ]
        ci_enabled: Annotated[
            bool,
            m.Field(description="Whether conform owns the CI projection"),
        ]
        publishes_release: Annotated[
            bool,
            m.Field(
                default=False,
                description="Whether conform renders release-protocol artifacts",
            ),
        ] = False
        gascity_enabled: Annotated[
            bool,
            m.Field(
                description=(
                    "Whether the repository consumes the Gas City runtime "
                    "contract; gates the gc tool projection and the inherited "
                    "Dolt endpoint keys at render time."
                ),
            ),
        ] = True
        external_dependency_paths: Annotated[
            t.VariadicTuple[Path],
            m.Field(description="Observed external or fork Git submodule paths"),
        ] = ()

    class ManagedGitlinkSpec(FlextInfraConfigModelsContract.ConfigContract):
        """One governed submodule with its provider-owned baseline branch."""

        repository: Annotated[
            FlextInfraConfigModelsRepository.RepositoryRef,
            m.Field(description="Governed repository identity"),
        ]
        branch: Annotated[
            t.NonEmptyStr,
            m.Field(description="Declared gitlink branch (. follows the superproject)"),
        ]

    class ScriptDispatchSpec(FlextInfraConfigModelsContract.ConfigContract):
        """Opt-in routing of non-builtin verbs to a script command framework."""

        dispatcher: Annotated[
            t.NonEmptyStr,
            m.Field(
                description=(
                    "Repository-relative dispatcher entrypoint that resolves "
                    "scripts/<verb>/<what>.{py,sh} commands"
                ),
            ),
        ]
        roots: Annotated[
            t.VariadicTuple[t.NonEmptyStr],
            m.Field(
                min_length=1,
                description=(
                    "Repository-relative script roots scanned for a matching "
                    "<verb>/<what> command before falling back to a builtin"
                ),
            ),
        ]
