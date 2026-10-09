"""Repository-local workspace detection from immutable Git topology inputs.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import c, config, m, t, u
from flext_infra.base import s
from flext_infra.workspace._governance import FlextInfraWorkspaceGovernanceMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkspaceDetector(
    FlextInfraWorkspaceGovernanceMixin,
    s[c.Infra.MakeProfile],
):
    """Classify a repository only from files and Git facts inside that checkout."""

    @staticmethod
    def _policy_overlay(
        manifest: m.Infra.WorkspaceManifestSpec | None,
    ) -> m.Infra.RepositoryPolicyOverlaySpec | None:
        """Return the repository's own policy overlay, when declared.

        Returns:
            The overlay declared for the repository distribution, else ``None``.

        """
        return (
            next(
                (
                    item
                    for item in manifest.repository_policy_overlays
                    if item.project == manifest.repository.distribution
                ),
                None,
            )
            if manifest is not None
            else None
        )

    @classmethod
    def _resolved_beads(
        cls,
        resolved_root: Path,
        overlay: m.Infra.RepositoryPolicyOverlaySpec | None,
    ) -> p.Result[t.Pair[m.Infra.BeadsProjectSpec | None, bool]]:
        """Resolve the declared Beads ledger under the repository policy.

        Returns:
            The resulting workspace Beads specification with a presence flag
            (False when the repository policy opts out).

        """
        result_type = r[t.Pair[m.Infra.BeadsProjectSpec | None, bool]]
        beads_enabled = overlay is None or overlay.beads_enabled
        if not beads_enabled:
            if overlay is not None and overlay.gascity_enabled:
                return result_type.fail(
                    "Gas City requires Beads participation in the repository policy",
                )
            return result_type.ok((None, False))
        beads_result = cls.load_beads_spec(resolved_root)
        if beads_result.failure:
            return result_type.from_failure(beads_result)
        return result_type.ok((beads_result.value, True))

    @staticmethod
    def _beads_path(repository_root: Path) -> Path:
        """Return the repository-local Beads identity path when enabled.

        Returns:
            The repository-local Beads identity path when enabled.

        """
        return repository_root / c.CONFIG_DIR_NAME / c.Infra.BEADS_CONFIG_FILENAME

    @staticmethod
    def _beads_enabled(manifest: m.Infra.WorkspaceManifestSpec) -> bool:
        """Resolve Beads participation from the manifest's matched policy.

        Returns:
            The resulting ``bool``.

        """
        return next(
            (
                overlay.beads_enabled
                for overlay in manifest.repository_policy_overlays
                if overlay.project == manifest.repository.distribution
            ),
            True,
        )

    @classmethod
    def _composed_beads_identity_error(
        cls,
        subproject_root: Path,
        workspace_beads: m.Infra.BeadsProjectSpec,
    ) -> str | None:
        member_identity_path = (
            subproject_root / c.CONFIG_DIR_NAME / c.Infra.BEADS_CONFIG_FILENAME
        )
        # Detection observes the topology; it does not enforce the ledger-route
        # prohibition. Refusing to load a workspace because one composed project
        # still carries the old cross-project symlink makes the migration
        # impossible to perform — nothing can plan the fix for a repository it
        # cannot describe. `codegen conform` owns the prohibition and rejects
        # the link there, per repository and within the requested scope.
        if not member_identity_path.is_file():
            return (
                "missing required member Beads routing identity: "
                f"{member_identity_path}"
            )
        member_identity_result = cls.load_beads_spec(subproject_root)
        if member_identity_result.failure:
            return member_identity_result.error
        member_identity = member_identity_result.value
        member_key = (
            member_identity.workspace,
            member_identity.database,
            member_identity.issue_prefix,
        )
        workspace_key = (
            workspace_beads.workspace,
            workspace_beads.database,
            workspace_beads.issue_prefix,
        )
        if member_key != workspace_key:
            return (
                "member Beads routing identity differs from the workspace ledger: "
                f"{member_key} != {workspace_key}"
            )
        return None

    @classmethod
    def load_beads_spec(
        cls,
        repository_root: Path,
    ) -> p.Result[m.Infra.BeadsProjectSpec]:
        """Load and validate the required local ``config/beads.yaml``.

        Returns:
            The resulting ``p.Result[m.Infra.BeadsProjectSpec]``.

        """
        resolved_root = repository_root.expanduser().resolve()
        beads_path = cls._beads_path(resolved_root)
        if not beads_path.is_file():
            return r[m.Infra.BeadsProjectSpec].fail(
                f"missing required repository-local Beads configuration: {beads_path}",
            )
        loaded = u.Cli.config_load(beads_path, expand_env=False)
        if loaded.failure:
            return r[m.Infra.BeadsProjectSpec].fail(
                f"invalid repository-local Beads configuration ({beads_path}): "
                f"{loaded.error or 'configuration load failed'}",
            )
        validated: p.Result[m.Infra.BeadsProjectSpec] = u.validate_value(
            m.Infra.BeadsProjectSpec,
            loaded.value.data,
        )
        if validated.failure:
            return r[m.Infra.BeadsProjectSpec].fail_op(
                f"Beads configuration model validation ({beads_path})",
                validated.error,
            )
        return r[m.Infra.BeadsProjectSpec].ok(validated.value)

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

    @classmethod
    def _local_repository_ref(
        cls,
        repository_root: Path,
        *,
        path: Path = Path(),
        composed: bool = False,
        declared_url: str | None = None,
        declared_repository: m.Infra.RepositoryRef | None = None,
    ) -> p.Result[m.Infra.RepositoryRef]:
        """Build identity from declared recovery topology or validated live metadata.

        Returns:
            The resulting ``p.Result[m.Infra.RepositoryRef]``.

        """
        if declared_repository is None:
            metadata = u.Infra.read_project_metadata_result(repository_root)
            if metadata.failure:
                return r[m.Infra.RepositoryRef].from_failure(metadata)
            project_name = metadata.value.project.name
        else:
            project_name = declared_repository.distribution
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
                package=(
                    declared_repository.package
                    if declared_repository is not None
                    else u.Infra.layout(repository_root) is not None
                ),
                editable=composed,
                read_only=False,
            ),
        )

    @classmethod
    def _load_subprojects(
        cls,
        repository_root: Path,
        *,
        workspace_beads: m.Infra.BeadsProjectSpec | None,
        allow_unprovisioned_members: bool = False,
    ) -> p.Result[
        t.Pair[t.VariadicTuple[m.Infra.RepositoryRef], t.VariadicTuple[Path]]
    ]:
        """Validate every direct governed .gitmodules entry before planning writes.

        Returns:
            The resulting ``p.Result[t.Pair[t.VariadicTuple[m.Infra.RepositoryRef],
                t.VariadicTuple[Path]]]``.

        """
        declared = u.Infra.git_submodule_declarations(repository_root)
        result_type = r[tuple[tuple[m.Infra.RepositoryRef, ...], t.VariadicTuple[Path]]]
        if declared.failure:
            return result_type.from_failure(declared)
        members = cls._declared_members(repository_root)
        if members.failure:
            return result_type.from_failure(members)
        subprojects: list[m.Infra.RepositoryRef] = []
        external: list[Path] = []
        # The workspace-declared preference owns the baseline order: a fleet
        # integrating on a versioned release line (0.12.0-dev) is not covered
        # by the provider's conventional fallback names alone.
        baseline = u.Infra.repository_baseline_branch(
            repository_root,
            preference=(
                config.Infra.codegen.branch_policy.integration_branch_preference
            ),
        )
        context = m.Infra.SubprojectLoadContext(
            integration_branch=baseline.value if baseline.success else None,
            workspace_beads=workspace_beads,
            allow_unprovisioned_members=allow_unprovisioned_members,
        )
        for declaration in declared.value:
            loaded = cls._load_subproject(
                repository_root,
                declaration.path,
                declared_member=members.value.get(declaration.path),
                context=context,
            )
            if loaded.failure:
                return result_type.from_failure(loaded)
            if isinstance(loaded.value, Path):
                external.append(loaded.value)
                continue
            subprojects.append(loaded.value)
        return result_type.ok((tuple(subprojects), tuple(external)))

    @classmethod
    def _declared_members(
        cls,
        repository_root: Path,
    ) -> p.Result[t.MappingKV[Path, m.Infra.RepositoryRef]]:
        """Index the manifest's declared member contracts by composed path.

        Returns:
            The resulting ``p.Result[t.MappingKV[Path, m.Infra.RepositoryRef]]``.

        """
        loaded = u.Infra.load_workspace_manifest(repository_root)
        if loaded.failure:
            return r[t.MappingKV[Path, m.Infra.RepositoryRef]].from_failure(loaded)
        return r[t.MappingKV[Path, m.Infra.RepositoryRef]].ok({
            member.path: member
            for manifest in loaded.value
            for member in manifest.members
        })

    @classmethod
    def _load_subproject(
        cls,
        repository_root: Path,
        path: Path,
        *,
        declared_member: m.Infra.RepositoryRef | None,
        context: m.Infra.SubprojectLoadContext,
    ) -> p.Result[m.Infra.RepositoryRef | Path]:
        """Load one governed entry, or its declared path for external entries.

        A submodule whose ``.gitmodules`` section explicitly sets
        ``flext-managed`` to anything other than ``true`` is a vendored or
        fork checkout the workspace never governs: it classifies as an
        external dependency without provider or branch policy validation,
        the same contract lane provisioning already applies. Governed
        subprojects must declare their own identity (manifest) and integrate
        on the workspace's detected integration line or follow the
        superproject.

        Returns:
            The resulting ``p.Result[m.Infra.RepositoryRef | Path]``.

        """
        workspace_beads = context.workspace_beads
        result_type = r[m.Infra.RepositoryRef | Path]
        contract = u.Infra.git_submodule_declaration(
            m.Infra.GitSubmoduleContractRequest(
                repo_root=repository_root,
                member_path=path.as_posix(),
            ),
        )
        if contract.failure:
            return result_type.from_failure(contract)
        declared_url = contract.value.url
        if contract.value.managed is False:
            return result_type.ok(path)
        if not u.Infra.gitmodule_branch_is_governed(
            contract.value.branch,
            integration_branch=context.integration_branch,
        ):
            return result_type.fail(
                "governed subproject branch differs from the workspace "
                f"integration line: {path.as_posix()}",
            )
        subproject_root = (repository_root / path).resolve()
        if not subproject_root.is_relative_to(repository_root):
            return result_type.fail(
                f"subproject escapes workspace root: {path.as_posix()}",
            )
        if declared_member is not None:
            if u.Infra.git_remote_identity(
                declared_member.url,
            ) != u.Infra.git_remote_identity(declared_url):
                return result_type.fail(
                    "declared workspace member URL differs from its .gitmodules "
                    f"URL: {path.as_posix()}",
                )
            # Content-only members have no pyproject by contract. Their
            # manifest identity still governs an uninitialized Git link.
            if not declared_member.package:
                return result_type.ok(declared_member)
            if not (subproject_root / c.PYPROJECT_FILENAME).is_file():
                if (
                    subproject_root / c.Infra.GIT_DIR
                ).exists() and not context.allow_unprovisioned_members:
                    return result_type.fail(
                        "declared Python member checkout has no "
                        f"{c.PYPROJECT_FILENAME}: {path.as_posix()}",
                    )
                # The manifest owns a declared member's identity, so topology
                # stays identical when CI deliberately omits member checkouts.
                return result_type.ok(declared_member)
        if not subproject_root.is_dir():
            # An undeclared indexed gitlink whose checkout was never
            # initialized remains external. Manifest-declared members above
            # retain their governed identity for setup materialization.
            indexed = u.Infra.git_index_gitlink_paths(repository_root)
            if indexed.failure:
                return result_type.from_failure(indexed)
            if path.as_posix() in indexed.value:
                return result_type.ok(path)
            return result_type.fail(
                f"governed subproject checkout is missing: {path.as_posix()}",
            )
        if not (subproject_root / c.PYPROJECT_FILENAME).is_file():
            return result_type.ok(path)
        route_error = (
            cls._composed_beads_identity_error(subproject_root, workspace_beads)
            if workspace_beads is not None
            and (subproject_root / c.Infra.BEADS_DIRNAME).is_symlink()
            else None
        )
        if (
            workspace_beads is not None
            and route_error is None
            and not (subproject_root / c.Infra.BEADS_DIRNAME).is_symlink()
        ):
            beads = cls.load_beads_spec(subproject_root)
            if beads.failure:
                return result_type.from_failure(beads)
        if route_error is not None:
            return result_type.fail(
                "composed project must follow the workspace Beads ledger: "
                f"{route_error}",
            )
        repository = cls._local_repository_ref(
            subproject_root,
            path=path,
            composed=True,
            declared_url=declared_url,
        )
        if repository.failure:
            return result_type.from_failure(repository)
        member_manifest = u.Infra.load_workspace_manifest(subproject_root)
        if member_manifest.failure:
            return result_type.from_failure(member_manifest)
        if not member_manifest.value:
            return result_type.ok(repository.value)
        member_beads: m.Infra.BeadsProjectSpec | None = None
        if workspace_beads is not None:
            loaded_member_beads = cls.load_beads_spec(subproject_root)
            if loaded_member_beads.failure:
                return result_type.from_failure(loaded_member_beads)
            member_beads = loaded_member_beads.value
        manifest = cls._manifest_repository_ref(
            subproject_root,
            observed=repository.value.model_copy(update={"path": Path()}),
            beads=member_beads,
        )
        if manifest.failure:
            return result_type.from_failure(manifest)
        # The member owns its commands. Git still owns its composed path,
        # topology and editability; do not import a second member registry.
        commands = manifest.value[0]
        return result_type.ok(
            repository.value.model_copy(
                update={
                    "extra_verbs": commands.extra_verbs,
                    "script_dispatch": commands.script_dispatch,
                },
            ),
        )

    @classmethod
    def load_workspace_spec(
        cls,
        repository_root: Path,
        *,
        project_metadata: p.ProjectMetadata | None = None,
        allow_unprovisioned_members: bool = False,
    ) -> p.Result[m.Infra.WorkspaceSpec]:
        """Load local identity and validate local, read-only Git topology.

        Returns:
            The resulting ``p.Result[m.Infra.WorkspaceSpec]``.

        """
        del project_metadata
        resolved_root = repository_root.expanduser().resolve()
        authenticated = cls._authenticated_identity(resolved_root)
        if authenticated.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(authenticated)
        identity, declared_manifest = authenticated.value
        manifest = declared_manifest[0] if declared_manifest else None
        superproject_members = cls._superproject_workspace_members(
            identity.superproject_root,
        )
        beads = cls._effective_workspace_beads(resolved_root, identity, manifest)
        if beads.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(beads)
        workspace_beads = beads.value[0] if beads.value else None
        refs = cls._resolved_workspace_refs(
            resolved_root,
            workspace_beads,
            composed=identity.is_attached_submodule,
            allow_unprovisioned_members=allow_unprovisioned_members,
        )
        if refs.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(refs)
        (repository_ref, gascity_enabled, declared_project), (subprojects, external) = (
            refs.value
        )
        named = cls._workspace_name(workspace_beads, manifest)
        if named.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(named)
        return r[m.Infra.WorkspaceSpec].ok(
            m.Infra.WorkspaceSpec(
                name=named.value,
                beads=workspace_beads,
                gascity_enabled=gascity_enabled,
                repository=repository_ref,
                project=declared_project,
                namespace_scan_dirs=(
                    declared_manifest[0].namespace_scan_dirs
                    if declared_manifest
                    else ()
                ),
                integration=(
                    declared_manifest[0].integration if declared_manifest else None
                ),
                candidate_dependencies=(
                    declared_manifest[0].candidate_dependencies
                    if declared_manifest
                    else ()
                ),
                candidate_bootstrap_targets=(
                    declared_manifest[0].candidate_bootstrap_targets
                    if declared_manifest
                    else ()
                ),
                external_consumers=(
                    declared_manifest[0].external_consumers if declared_manifest else ()
                ),
                subprojects=tuple(subprojects),
                external_dependency_paths=tuple(external),
                superproject_members=superproject_members,
            ),
        )

    @classmethod
    def _superproject_workspace_members(
        cls,
        superproject_root: Path | None,
    ) -> tuple[str, ...]:
        """Read the sibling member names a superproject's uv workspace declares.

        Single source of truth: the superproject's own committed pyproject
        ``[tool.uv.workspace]``. Member paths map to distribution names by
        reading each member's ``[project] name`` (this fleet keeps them equal,
        and the read never assumes it). Any absence — no superproject, no
        workspace table, no member manifest — resolves to an empty tuple, the
        standalone shape.

        Returns:
            The resulting ``tuple[str, ...]``.

        """
        if superproject_root is None:
            return ()
        workspace_pyproject = superproject_root / c.PYPROJECT_FILENAME
        if not workspace_pyproject.is_file():
            return ()
        document = u.Cli.toml_read_document(workspace_pyproject)
        if document.failure:
            return ()
        payload = u.Cli.toml_as_mapping(document.value)
        if payload is None:
            return ()
        tool = payload.get(c.Infra.TOOL)
        uv_table = tool.get("uv") if isinstance(tool, Mapping) else None
        workspace_table = (
            uv_table.get("workspace") if isinstance(uv_table, Mapping) else None
        )
        raw_members = (
            workspace_table.get("members")
            if isinstance(workspace_table, Mapping)
            else None
        )
        if not isinstance(raw_members, list):
            return ()
        members: list[str] = []
        for raw_member in raw_members:
            member_path = superproject_root / str(raw_member)
            member_pyproject = member_path / c.PYPROJECT_FILENAME
            if not member_pyproject.is_file():
                continue
            member_document = u.Cli.toml_read_document(member_pyproject)
            if member_document.failure:
                continue
            member_payload = u.Cli.toml_as_mapping(member_document.value)
            project = (
                member_payload.get(c.Infra.PROJECT)
                if isinstance(member_payload, Mapping)
                else None
            )
            name = project.get(c.Infra.NAME) if isinstance(project, Mapping) else None
            if isinstance(name, str) and name.strip():
                members.append(name.strip().strip('"').strip("'").strip())
        return tuple(sorted(set(members)))

    @classmethod
    def _authenticated_identity(
        cls,
        resolved_root: Path,
    ) -> p.Result[
        t.Pair[m.Infra.GitIdentityReport, t.SequenceOf[m.Infra.WorkspaceManifestSpec]]
    ]:
        """Authenticate the repository root, its Git identity, and its manifest.

        Returns:
            The resulting ``(identity, manifest)`` pair.

        """
        result_type = r[
            t.Pair[
                m.Infra.GitIdentityReport,
                t.SequenceOf[m.Infra.WorkspaceManifestSpec],
            ]
        ]
        if not resolved_root.is_dir():
            return result_type.fail(
                f"repository root is not a directory: {resolved_root}",
            )
        identity = u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=resolved_root))
        if identity.failure:
            return result_type.from_failure(identity)
        declared_manifest = u.Infra.load_workspace_manifest(resolved_root)
        if declared_manifest.failure:
            return result_type.from_failure(declared_manifest)
        return result_type.ok((identity.value, declared_manifest.value))

    @classmethod
    def _effective_workspace_beads(
        cls,
        resolved_root: Path,
        identity: m.Infra.GitIdentityReport,
        manifest: m.Infra.WorkspaceManifestSpec | None,
    ) -> p.Result[t.VariadicTuple[m.Infra.BeadsProjectSpec]]:
        """Resolve the effective Beads ledger from the declared policy overlay.

        Returns:
            The effective ledger as a 0-or-1 tuple; a Beads-free repository is
            the empty tuple, never a ``None`` success payload.

        """
        resolved_beads = cls._resolved_beads(
            resolved_root,
            cls._policy_overlay(manifest),
        )
        if resolved_beads.failure:
            return r[t.VariadicTuple[m.Infra.BeadsProjectSpec]].from_failure(
                resolved_beads,
            )
        return cls._effective_beads(
            resolved_root,
            identity,
            resolved_beads.value[0],
        )

    @classmethod
    def _effective_beads(
        cls,
        resolved_root: Path,
        identity: m.Infra.GitIdentityReport,
        beads: m.Infra.BeadsProjectSpec | None,
    ) -> p.Result[t.VariadicTuple[m.Infra.BeadsProjectSpec]]:
        """Resolve the effective Beads ledger, inheriting through submodules.

        Returns:
            The effective workspace Beads specification as a 0-or-1 tuple.

        """
        result_type = r[t.VariadicTuple[m.Infra.BeadsProjectSpec]]
        member_root = identity.primary_root
        member_beads = member_root / c.Infra.BEADS_DIRNAME
        if not (
            beads is not None
            and identity.is_attached_submodule
            and member_beads.is_symlink()
        ):
            return result_type.ok(() if beads is None else (beads,))
        superproject_root = identity.superproject_root
        if superproject_root is None:
            return result_type.fail(
                f"Git submodule has no superproject: {resolved_root}",
            )
        inherited = cls._inherited_member_beads(superproject_root, member_root)
        if inherited.failure:
            return result_type.from_failure(inherited)
        inherited_beads, _loaded_member = inherited.value
        route_error = cls._composed_beads_identity_error(resolved_root, inherited_beads)
        if route_error is not None:
            return result_type.fail(
                "composed project must follow the workspace Beads ledger: "
                f"{route_error}",
            )
        return result_type.ok((inherited_beads,))

    @classmethod
    def _inherited_member_beads(
        cls,
        superproject_root: Path,
        member_root: Path,
    ) -> p.Result[t.Pair[m.Infra.BeadsProjectSpec, m.Infra.RepositoryRef]]:
        """Load the superproject's Beads ledger and the member's governed ref.

        Returns:
            The resulting ``(inherited_beads, loaded_member)`` pair.

        """
        result_type = r[t.Pair[m.Infra.BeadsProjectSpec, m.Infra.RepositoryRef]]
        inherited_beads = cls.load_beads_spec(superproject_root)
        if inherited_beads.failure:
            return result_type.from_failure(inherited_beads)
        if not member_root.is_relative_to(superproject_root):
            return result_type.fail(
                f"Git submodule escapes its superproject: {member_root}",
            )
        member_path = member_root.relative_to(superproject_root)
        # Same owner as the parent load: the declared preference resolves a
        # versioned integration line the provider fallback names miss.
        baseline = u.Infra.repository_baseline_branch(
            superproject_root,
            preference=(
                config.Infra.codegen.branch_policy.integration_branch_preference
            ),
        )
        superproject_members = cls._declared_members(superproject_root)
        if superproject_members.failure:
            return result_type.from_failure(superproject_members)
        loaded_member = cls._load_subproject(
            superproject_root,
            member_path,
            declared_member=superproject_members.value.get(member_path),
            context=m.Infra.SubprojectLoadContext(
                integration_branch=(baseline.value if baseline.success else None),
                workspace_beads=inherited_beads.value,
            ),
        )
        undeclared = f"Git submodule is not a declared governed project: {member_root}"
        if loaded_member.failure:
            return result_type.fail(loaded_member.error or undeclared)
        member_ref = loaded_member.value
        if isinstance(member_ref, Path):
            return result_type.fail(undeclared)
        return result_type.ok((inherited_beads.value, member_ref))

    @classmethod
    def _resolved_workspace_refs(
        cls,
        resolved_root: Path,
        beads: m.Infra.BeadsProjectSpec | None,
        *,
        composed: bool,
        allow_unprovisioned_members: bool,
    ) -> p.Result[
        t.Pair[
            t.Triple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None],
            t.Pair[t.SequenceOf[m.Infra.RepositoryRef], t.SequenceOf[Path]],
        ]
    ]:
        """Resolve the repository ref and the composed subproject topology.

        Returns:
            The resulting ``((repository_ref, gascity_enabled, declared_project),
            (subprojects, external))`` pair pair.

        """
        result_type = r[
            t.Pair[
                t.Triple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None],
                t.Pair[t.SequenceOf[m.Infra.RepositoryRef], t.SequenceOf[Path]],
            ]
        ]
        repository = cls._local_repository_ref(resolved_root, composed=composed)
        if repository.failure:
            return result_type.from_failure(repository)
        topology = cls._load_subprojects(
            resolved_root,
            workspace_beads=beads,
            allow_unprovisioned_members=allow_unprovisioned_members,
        )
        if topology.failure:
            return result_type.from_failure(topology)
        subprojects, external = topology.value
        observed_repository = repository.value.model_copy(
            update={
                "role": (
                    c.Infra.MakeProfile.WORKSPACE
                    if subprojects or external
                    else c.Infra.MakeProfile.STANDALONE
                ),
            },
        )
        declared_repository = cls._manifest_repository_ref(
            resolved_root,
            observed=observed_repository,
            beads=beads,
        )
        if declared_repository.failure:
            return result_type.from_failure(declared_repository)
        return result_type.ok((declared_repository.value, (subprojects, external)))

    @staticmethod
    def _workspace_name(
        beads: m.Infra.BeadsProjectSpec | None,
        manifest: m.Infra.WorkspaceManifestSpec | None,
    ) -> p.Result[str]:
        """Resolve the workspace name from Beads or the declared manifest.

        Returns:
            The resulting workspace name.

        """
        if beads is not None:
            return r[str].ok(beads.workspace)
        if manifest is None:
            return r[str].fail(
                "workspace identity requires a manifest or Beads configuration",
            )
        return r[str].ok(manifest.name)

    @classmethod
    def conform_target(
        cls,
        repository_root: Path,
        workspace_spec: m.Infra.WorkspaceSpec | None = None,
        *,
        project_metadata: p.ProjectMetadata | None = None,
    ) -> p.Result[m.Infra.RepositoryConformTarget]:
        """Resolve a target exclusively from the requested checkout.

        Returns:
            The resulting ``p.Result[m.Infra.RepositoryConformTarget]``.

        """
        del project_metadata
        resolved_root = repository_root.expanduser().resolve()
        workspace = workspace_spec
        if workspace is None:
            loaded = cls.load_workspace_spec(resolved_root)
            if loaded.failure:
                return r[m.Infra.RepositoryConformTarget].from_failure(loaded)
            workspace = loaded.value
        if workspace.repository.path != Path():
            return r[m.Infra.RepositoryConformTarget].fail(
                "local workspace repository path must be '.'",
            )
        metadata = u.Infra.read_project_metadata_result(resolved_root)
        if metadata.failure:
            return r[m.Infra.RepositoryConformTarget].from_failure(metadata)
        canonical_project_name = metadata.value.project.name
        if canonical_project_name != workspace.repository.distribution:
            return r[m.Infra.RepositoryConformTarget].fail(
                "project metadata and repository identity differ: "
                f"{canonical_project_name} != {workspace.repository.distribution}",
            )
        return r[m.Infra.RepositoryConformTarget].ok(
            m.Infra.RepositoryConformTarget(
                repository=workspace.repository,
                root=resolved_root,
                make_profile=workspace.repository.role,
                beads=workspace.beads,
                project=workspace.project,
                canonical_project_name=canonical_project_name,
                ci_enabled=True,
                publishes_release=workspace.repository.publishes_release,
                gascity_enabled=workspace.gascity_enabled,
                external_dependency_paths=workspace.external_dependency_paths,
            ),
        )

    @staticmethod
    def resolve_repository_root(repository_root: Path) -> p.Result[Path]:
        """Return the requested checkout; parent and primary trees are irrelevant.

        Returns:
            The requested checkout; parent and primary trees are irrelevant.

        """
        resolved_root = repository_root.expanduser().resolve()
        if not resolved_root.is_dir():
            return r[Path].fail(f"repository root is not a directory: {resolved_root}")
        return r[Path].ok(resolved_root)

    @staticmethod
    def workspace_analysis_exclusion_paths(
        workspace: m.Infra.WorkspaceSpec,
    ) -> t.VariadicTuple[Path]:
        """Return read-only external Git dependencies excluded from analysis.

        Returns:
            Read-only external Git dependencies excluded from analysis.

        """
        return workspace.external_dependency_paths

    @classmethod
    def analysis_exclusion_paths(
        cls,
        repository_root: Path,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Load exclusions for governed repositories; ignore ungoverned trees.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        resolved_root = repository_root.expanduser().resolve()
        if not u.Infra.workspace_manifest_path(resolved_root).is_file():
            return r[t.VariadicTuple[Path]].ok(())
        # External analysis exclusions are declared exclusively by this
        # checkout's own .gitmodules. A composed project may follow its Beads
        # ledger from the parent, but that does not make the parent's complete
        # repository graph part of the member's analyzer scope. Loading the
        # inherited workspace here revalidated every sibling once per tooling
        # phase and turned one member conform into thousands of Git processes.
        if not (resolved_root / c.Infra.GITMODULES).is_file():
            return r[t.VariadicTuple[Path]].ok(())
        # Why: a governed root owns its own repository. A tree
        # that carries .beads/.gitmodules but no .git (a test sandbox, a
        # scratch copy) is ungoverned; asking Git here would discover an
        # ancestor checkout and validate *its* submodules against *this*
        # .gitmodules (a sandbox nested inside a workspace checkout).
        if not (resolved_root / ".git").exists():
            return r[t.VariadicTuple[Path]].ok(())
        # Governance is declared, not matched: only a checkout that declares
        # its own workspace manifest (provider key plus canonical URL) is a
        # governed repository; anything else is an ungoverned tree whose
        # exclusions are none.
        if not u.Infra.workspace_manifest_path(resolved_root).is_file():
            return r[t.VariadicTuple[Path]].ok(())
        # Analysis scope reads declared topology, so it tolerates members a
        # provisioning surface has not materialized yet (conform renders the
        # setup Makefile before a member's pyproject exists); a strict load
        # here re-imposed governance on a declaration-only read.
        workspace = cls.load_workspace_spec(
            resolved_root,
            allow_unprovisioned_members=True,
        )
        if workspace.failure:
            return r[t.VariadicTuple[Path]].from_failure(workspace)
        return r[t.VariadicTuple[Path]].ok(
            cls.workspace_analysis_exclusion_paths(workspace.value),
        )

    @classmethod
    def analysis_excluded_top_dirs(
        cls,
        repository_root: Path,
    ) -> p.Result[frozenset[str]]:
        """Return the first segments of the read-only external topology paths.

        This is the analysis scope that discovery utilities receive from their
        callers: the topology owner computes it, the utilities only apply it.

        Returns:
            The first segments of the read-only external topology paths.

        """
        return cls.analysis_exclusion_paths(repository_root).map(
            lambda paths: frozenset(path.parts[0] for path in paths if path.parts),
        )

    def detect(self, project_root: Path) -> p.Result[c.Infra.MakeProfile]:
        """Classify from governed members, not mere vendored Git topology.

        Returns:
            The resulting ``p.Result[c.Infra.MakeProfile]``.

        """
        try:
            resolved_root = project_root.expanduser().resolve()
        except c.EXC_OS_RUNTIME_TYPE as exc:
            return r[c.Infra.MakeProfile].fail_op("Workspace detection", exc)
        if not resolved_root.is_dir():
            return r[c.Infra.MakeProfile].fail(
                f"project root is not a directory: {resolved_root}",
            )
        workspace = self.load_workspace_spec(resolved_root)
        if workspace.failure:
            return r[c.Infra.MakeProfile].from_failure(workspace)
        return r[c.Infra.MakeProfile].ok(workspace.value.repository.role)

    @override
    def execute(self) -> p.Result[c.Infra.MakeProfile]:
        """Execute workspace detection for the configured root.

        Returns:
            The resulting ``p.Result[c.Infra.MakeProfile]``.

        """
        return self.detect(self.repository_root)


__all__: list[str] = ["FlextInfraWorkspaceDetector"]
