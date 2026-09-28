"""``codegen new`` — create a project through the canonical conform pipeline.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, override

from flext_core import r

from .. import c, m, u
from ._execution import FlextInfraCodegenExecutionBase
from .conform import FlextInfraCodegenConform

# New file per operator live
# order (ULW). ctx via u.derive_class_stem (no parallel detection, ADR-005 §9);
# accessor typing/config+settings symmetry fixed in templates in the same lane.

if TYPE_CHECKING:
    from .. import p


class FlextInfraCodegenProjectNew(
    FlextInfraCodegenExecutionBase[m.Infra.CodegenResult]
):
    """Scaffold one new repository of a declared governance kind."""

    name: Annotated[
        str,
        m.Field(
            min_length=1,
            description="Distribution name in kebab-case (e.g. flext-demo / acme-demo).",
        ),
    ]
    kind: Annotated[
        c.Infra.ProjectKind,
        m.Field(
            description=(
                "Governance kind: internal_flext, internal, or third_party_fork."
            )
        ),
    ]
    output_root: Annotated[
        Path, m.Field(description="Directory that becomes the generated project root.")
    ]
    package_name: Annotated[
        str, m.Field(description="Python package name (default: name with '-'→'_').")
    ] = ""
    # Field renamed
    # ``namespace``→``project_namespace`` to avoid colliding with the inherited
    # base field ``target_namespace`` (alias ``namespace``); CLI flag stays ``--ns``.
    project_namespace: Annotated[
        str,
        m.Field(
            alias="ns",
            description="Facade namespace slot (default: class stem minus 'Flext').",
        ),
    ] = ""
    description: Annotated[
        str, m.Field(default="", description="Project description (default: derived).")
    ] = ""
    provider: Annotated[
        str,
        m.Field(
            min_length=1,
            description=(
                "Provider key written into the new repository's own manifest; "
                "flext-infra keeps no provider catalog to resolve it from."
            ),
        ),
    ]
    repository_url: Annotated[
        str,
        m.Field(
            description=(
                "Canonical HTTPS Git clone URL for the new repository. There is "
                "nothing to detect for a repository that does not exist yet, so "
                "the caller must declare it."
            )
        ),
    ]
    repository_branch: Annotated[
        str,
        m.Field(
            description=(
                "Integration branch the new repository initializes on. Git owns "
                "no answer for an unborn repository, so the caller must declare "
                "it."
            )
        ),
    ]
    license: Annotated[
        str, m.Field(min_length=1, description="SPDX project license identifier.")
    ]
    flext_repository_url: Annotated[
        str,
        m.Field(
            min_length=1, description="Git URL of the FLEXT infrastructure source."
        ),
    ]
    flext_repository_ref: Annotated[
        str,
        m.Field(min_length=1, description="Git ref consumed from the FLEXT source."),
    ]
    author_name: Annotated[
        str, m.Field(min_length=1, description="Author/maintainer display name.")
    ]
    author_email: Annotated[
        str, m.Field(min_length=3, description="Author/maintainer email.")
    ]
    upstream: Annotated[str, m.Field(description="Upstream facade module (flext_cli).")]
    flext_source: Annotated[
        str,
        m.Field(
            min_length=1,
            description="Direct Git infrastructure requirement used by the new project",
        ),
    ]
    year: Annotated[int, m.Field(ge=2025, description="Deterministic copyright year.")]

    @override
    def execute(self) -> p.Result[m.Infra.CodegenResult]:
        """Build one typed manifest and delegate all output to conform."""
        if self.effective_dry_run:
            return r[m.Infra.CodegenResult].fail("codegen new requires apply mode")
        # Every identity fact is an explicit caller declaration: for a
        # repository that does not exist yet there is nothing to detect and no
        # catalog to consult.
        repository_url = self.repository_url.strip()
        if not repository_url:
            return r[m.Infra.CodegenResult].fail(
                "repository URL is required: declare --repository-url"
            )
        repository_branch = self.repository_branch.strip()
        if not repository_branch:
            return r[m.Infra.CodegenResult].fail(
                "repository branch is required: declare --repository-branch"
            )
        # Declared remotes are the only provenance a repository that does not
        # exist yet can carry, so both URLs and the FLEXT ref are validated to
        # a usable shape here — before any model, directory, or Git effect.
        origin_url = u.Infra.validate_git_remote_url(repository_url)
        if origin_url.failure:
            return r[m.Infra.CodegenResult].from_failure(origin_url)
        flext_url = u.Infra.validate_git_remote_url(self.flext_repository_url)
        if flext_url.failure:
            return r[m.Infra.CodegenResult].from_failure(flext_url)
        flext_ref = self.flext_repository_ref.strip()
        if not flext_ref:
            return r[m.Infra.CodegenResult].fail(
                "flext repository ref is required: declare --flext-repository-ref"
            )
        package_name = self.package_name or self.name.replace("-", "_")
        class_stem = u.derive_class_stem(self.name)
        derived_namespace = class_stem.removeprefix("Flext")
        project_namespace = self.project_namespace or derived_namespace or class_stem
        alias = u.Infra.package_alias(package_name=package_name)
        repository_page = origin_url.value.removesuffix(".git")
        repository = m.Infra.RepositoryRef(
            name=self.name,
            distribution=self.name,
            provider=self.provider,
            url=origin_url.value,
            path=Path(),
            role=c.Infra.MakeProfile.STANDALONE,
            state=c.Infra.RepositoryState.ACTIVE,
            kind=self.kind,
            codegen=c.Infra.CodegenKind.CONFORM,
            package=True,
            editable=False,
            read_only=False,
        )
        workspace = m.Infra.WorkspaceSpec(
            name=self.name,
            flext_source=m.Infra.CodegenBootstrapSource(
                url=flext_url.value, ref=flext_ref
            ),
            beads=m.Infra.BeadsProjectSpec(
                version=c.Infra.BEADS_CONFIG_VERSION,
                workspace=self.name,
                database=self.name.replace("-", "_"),
                issue_prefix=self.name,
            ),
            repository=repository,
            # The integration branch of a repository that has published nothing
            # yet is a declaration, never a Git guess (ADR-018 p.10). The
            # declaration carries the full line (organization and base URL
            # derived from the explicit repository URL): a fresh checkout has
            # nothing to detect from, and the caller's explicit facts are the
            # line the whole family renders from.
            integration=m.Infra.WorkspaceIntegrationSpec(
                provider=self.provider,
                branch=repository_branch,
                organization=u.Infra.git_remote_identity(repository_url).partition("/")[
                    0
                ],
                base_url=repository_page.rsplit("/", maxsplit=1)[0],
            ),
            project=m.Infra.ProjectSpec(
                package_name=package_name,
                class_stem=class_stem,
                namespace=project_namespace,
                constant_name=self.name,
                namespace_attribute=alias,
                alias=alias,
                environment_prefix=f"{package_name.upper()}_",
                description=(
                    self.description
                    or f"{class_stem} — FLEXT typed integration package"
                ),
                license=self.license,
                author_name=self.author_name,
                author_email=self.author_email,
                upstream=self.upstream,
                flext_source=self.flext_source,
                homepage=repository_page,
                documentation=repository_page,
                repository_root_rel=".",
                year=self.year,
            ),
        )
        request = m.Infra.CodegenConformRequest(
            root=self.output_root.expanduser().resolve(),
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
        )
        return FlextInfraCodegenConform.execute_request(
            request, initial_workspace=workspace
        )


__all__: list[str] = ["FlextInfraCodegenProjectNew"]
