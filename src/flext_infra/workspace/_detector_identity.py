"""Repository identity reconciled from the manifest and live Git origin.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkspaceIdentityMixin:
    """Build repository references from local metadata and Git truth."""

    @staticmethod
    def _git_origin_url(repository_root: Path) -> p.Result[str]:
        """Read the repository's required origin without inventing one.

        Returns:
            The resulting ``p.Result[str]``.

        """
        result = u.Infra.git_remote_url(
            m.Infra.GitRemoteUrlRequest(repo_root=repository_root, remote="origin"),
        )
        if result.failure or not result.value.text.strip():
            return r[str].fail(
                result.error or f"repository origin is required: {repository_root}",
            )
        return r[str].ok(result.value.text.strip())

    @classmethod
    def _declared_provider_name(
        cls,
        repository_root: Path,
        *,
        origin_url: str,
    ) -> p.Result[str]:
        """Detect the provider key the repository declares for itself.

        With a workspace manifest, the declaration is real only if the live
        Git origin carries the same organization identity as the declared URL
        (the same discrimination ``git_remote_identity`` gives every remote
        shape). Post-G1, repositories without a manifest take their provider
        identity from the live Git origin organization itself — no catalog,
        no invented rows.

        Returns:
            The resulting ``p.Result[str]``.

        """
        loaded = u.Infra.load_workspace_manifest(repository_root)
        if loaded.failure:
            return r[str].from_failure(loaded)
        if not loaded.value:
            origin_organization, origin_separator, _ = u.Infra.git_remote_identity(
                origin_url,
            ).partition("/")
            if not origin_separator:
                return r[str].fail(
                    "governed repository Git origin must name an owner and "
                    f"repository: {origin_url}",
                )
            return r[str].ok(origin_organization)
        manifest = loaded.value[0]
        manifest_path = u.Infra.workspace_manifest_path(repository_root)
        declared = manifest.repository
        manifest_organization, manifest_separator, _ = u.Infra.git_remote_identity(
            declared.url,
        ).partition("/")
        origin_organization, origin_separator, _ = u.Infra.git_remote_identity(
            origin_url,
        ).partition("/")
        if (
            not manifest_separator
            or not origin_separator
            or manifest_organization != origin_organization
        ):
            return r[str].fail(
                "workspace manifest url organization differs from the live Git "
                f"origin ({manifest_path}): {declared.url!r} != {origin_url!r}",
            )
        return r[str].ok(declared.provider)

    @staticmethod
    def _manifest_git_contradictions(
        declared: m.Infra.RepositoryRef,
        observed: m.Infra.RepositoryRef,
    ) -> list[str]:
        """Describe every manifest identity or topology conflict with Git.

        Returns:
            The resulting ``list[str]``.

        """
        comparisons = (
            (
                declared.name != observed.name,
                f"name {declared.name!r} != {observed.name!r}",
            ),
            (
                declared.distribution != observed.distribution,
                f"distribution {declared.distribution!r} != {observed.distribution!r}",
            ),
            (
                declared.provider != observed.provider,
                f"provider {declared.provider!r} != {observed.provider!r}",
            ),
            (
                declared.path != observed.path,
                f"path {declared.path.as_posix()!r} != {observed.path.as_posix()!r}",
            ),
            (
                declared.role is not observed.role,
                f"role {declared.role.value!r} != {observed.role.value!r}",
            ),
        )
        contradictions = [message for differs, message in comparisons if differs]
        if u.Infra.git_remote_identity(declared.url) != u.Infra.git_remote_identity(
            observed.url,
        ):
            contradictions.append("url identity differs from Git origin")
        # Why: a repository-local manifest carries the
        # repository's own coordinates. Whether that repository is currently
        # checked out as a submodule is a fact of the parent's Git tree, not of
        # the manifest, so the same manifest must load both standalone (its own
        # CI observes root) and inside a workspace (the parent's conform
        # observes submodule). Only a manifest that claims to be a submodule
        # while Git shows a standalone checkout contradicts reality.
        if declared.role is not observed.role:
            contradictions.append(
                f"role {declared.role.value!r} contradicts the observed topology",
            )
        return contradictions

    @classmethod
    def _manifest_repository_ref(
        cls,
        repository_root: Path,
        *,
        observed: m.Infra.RepositoryRef,
        beads: m.Infra.BeadsProjectSpec | None,
    ) -> p.Result[t.Triple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]]:
        """Load a selected repository manifest and reconcile it with Git truth.

        The checkout's own manifest is mandatory for identity: its complete
        typed ``repository`` record is authoritative for repository policy and
        must agree with the immutable identity and topology observed from Git.
        The matched repository policy overlay's Gas City participation rides
        along: ``True`` when the manifest declares no overlay.

        Returns:
            The resulting ``p.Result[t.Triple[m.Infra.RepositoryRef, bool,
                m.Infra.ProjectSpec | None]]``.

        """
        manifest_path = u.Infra.workspace_manifest_path(repository_root)
        loaded = u.Infra.load_workspace_manifest(repository_root)
        if loaded.failure:
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].from_failure(loaded)
        if not loaded.value:
            # A checkout without ``config/workspace.yaml`` remains a valid
            # observed repository (pre-G1 contract, restored): the observed
            # state IS the identity, gascity participates, and no manifest
            # project spec exists. Absence never constructs a None payload.
            outcome = tuple[
                m.Infra.RepositoryRef,
                bool,
                m.Infra.ProjectSpec | None,
            ]
            return r[outcome].ok((
                observed,
                True,
                None,
            ))
        manifest = loaded.value[0]
        declared = manifest.repository
        contradictions = cls._manifest_git_contradictions(declared, observed)
        if contradictions:
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].fail(
                f"workspace manifest contradicts Git ({manifest_path}): "
                + "; ".join(contradictions),
            )
        # The manifest is the provider-identity authority: its declared URL was
        # just reconciled against the live Git origin above, so the declared
        # provider key rides with it and no catalog lookup may override it.
        if manifest.ledger_id is not None and (
            beads is None or manifest.ledger_id != beads.database
        ):
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].fail(
                "workspace manifest ledger_id contradicts Beads identity "
                f"({manifest_path}): {manifest.ledger_id!r} != "
                f"{beads.database if beads is not None else None!r}",
            )
        if manifest.ledger_prefix is not None and (
            beads is None or manifest.ledger_prefix != beads.issue_prefix
        ):
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].fail(
                "workspace manifest ledger_prefix contradicts Beads identity "
                f"({manifest_path}): {manifest.ledger_prefix!r} != "
                f"{beads.issue_prefix if beads is not None else None!r}",
            )
        overlay = next(
            (
                item
                for item in manifest.repository_policy_overlays
                if item.project == declared.distribution
            ),
            None,
        )
        # The manifest owns identity; Git owns editability (a composed checkout
        # is editable), exactly as the subproject load documents.
        return r[tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]].ok((
            declared.model_copy(update={"editable": observed.editable}),
            True if overlay is None else overlay.gascity_enabled,
            manifest.project,
        ))

    @staticmethod
    def _gitmodule_contract(
        repository_root: Path,
        subproject_path: Path,
    ) -> p.Result[t.Pair[str, str]]:
        """Read one exact URL/branch pair from the local ``.gitmodules``.

        Returns:
            The resulting ``p.Result[t.Pair[str, str]]``.

        """
        contract = u.Infra.gitmodule_contract(
            m.Infra.GitSubmoduleContractRequest(
                repo_root=repository_root,
                member_path=subproject_path.as_posix(),
            ),
        )
        if contract.failure:
            return r[tuple[str, str]].from_failure(contract)
        return r[tuple[str, str]].ok((contract.value.url, contract.value.branch))

    @classmethod
    def _local_repository_ref(
        cls,
        repository_root: Path,
        *,
        path: Path = Path(),
        composed: bool = False,
        declared_url: str | None = None,
    ) -> p.Result[m.Infra.RepositoryRef]:
        """Build repository policy from local metadata and an immutable Git URL.

        Returns:
            The resulting ``p.Result[m.Infra.RepositoryRef]``.

        """
        metadata = u.Infra.read_project_metadata_result(repository_root)
        if metadata.failure:
            return r[m.Infra.RepositoryRef].from_failure(metadata)
        origin = cls._git_origin_url(repository_root)
        if origin.failure:
            return r[m.Infra.RepositoryRef].from_failure(origin)
        if declared_url is not None and u.Infra.git_remote_identity(
            origin.value,
        ) != u.Infra.git_remote_identity(declared_url):
            return r[m.Infra.RepositoryRef].fail(
                f"subproject origin differs from its .gitmodules URL: "
                f"{path.as_posix()}",
            )
        effective_url = declared_url or origin.value
        provider_result = cls._declared_provider_name(
            repository_root,
            origin_url=origin.value,
        )
        if provider_result.failure:
            return r[m.Infra.RepositoryRef].from_failure(provider_result)
        role = (
            c.Infra.MakeProfile.WORKSPACE
            if (repository_root / c.Infra.GITMODULES).is_file()
            else c.Infra.MakeProfile.STANDALONE
        )
        project_name = metadata.value.project.name
        _, separator, repository_name = u.Infra.git_remote_identity(
            origin.value,
        ).partition("/")
        if not separator or not repository_name:
            return r[m.Infra.RepositoryRef].fail(
                f"Git origin does not identify a repository: {origin.value}",
            )
        # The manifest is the identity authority: the provider key is the one
        # the repository itself declares and the declared URL organization was
        # just reconciled against the live origin, so no catalog may override
        # either. Package participation stays an observed fact for a
        # manifest-less checkout (the observed state IS the identity): the
        # canonical layout resolution returns the typed "not a Python package
        # project" signal for such roots, and declaring a package there made
        # the fresh-import guard demand an importable layout no repository
        # publishes. A flext-* checkout that cannot resolve its package fails
        # the discovery contract loudly instead of being declared one.
        return r[m.Infra.RepositoryRef].ok(
            m.Infra.RepositoryRef(
                name=repository_name,
                distribution=project_name,
                url=effective_url,
                path=path,
                role=role,
                provider=provider_result.value,
                kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
                codegen=c.Infra.CodegenKind.CONFORM,
                package=u.Infra.layout(repository_root) is not None,
                editable=composed,
                read_only=False,
            ),
        )


__all__: list[str] = ["FlextInfraWorkspaceIdentityMixin"]
