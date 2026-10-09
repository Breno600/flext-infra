"""Repository-local workspace detection from immutable Git topology inputs.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_infra import c, config, m, r, t, u
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
        declared = u.Infra.git_declared_submodule_paths(repository_root)
        result_type = r[tuple[tuple[m.Infra.RepositoryRef, ...], t.VariadicTuple[Path]]]
        if declared.failure:
            return result_type.from_failure(declared)
        members = cls._declared_members(repository_root)
        if members.failure:
            return result_type.from_failure(members)
        subprojects: list[m.Infra.RepositoryRef] = []
        external: list[Path] = []
        seen: set[Path] = set()
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
        for path in declared.value:
            if path in seen:
                return result_type.fail(
                    f"duplicate .gitmodules path: {path.as_posix()}",
                )
            seen.add(path)
            loaded = cls._load_subproject(
                repository_root,
                path,
                declared_member=members.value.get(path),
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
        entry = cls._admitted_subproject_entry(
            repository_root,
            path,
            integration_branch=context.integration_branch,
        )
        if entry.failure:
            return result_type.from_failure(entry)
        if isinstance(entry.value, Path):
            return result_type.ok(entry.value)
        subproject_root = cls._validated_subproject_root(repository_root, path)
        if subproject_root.failure:
            return result_type.from_failure(subproject_root)
        if declared_member is not None:
            member = cls._declared_member_result(
                subproject_root.value,
                path,
                declared_member=declared_member,
                declared_url=entry.value[0],
                allow_unprovisioned_members=context.allow_unprovisioned_members,
            )
            if member is not None:
                return member
        if not subproject_root.value.is_dir():
            return cls._indexed_gitlink_result(repository_root, path)
        return cls._governed_member_result(
            subproject_root.value,
            path,
            declared_url=entry.value[0],
            workspace_beads=workspace_beads,
        )

    @classmethod
    def _admitted_subproject_entry(
        cls,
        repository_root: Path,
        path: Path,
        *,
        integration_branch: str | None,
    ) -> p.Result[t.Pair[str, str] | Path]:
        """Admit one ``.gitmodules`` entry or classify it as external.

        Returns:
            The declared URL/branch pair, or the entry path when the checkout
            is an unmanaged external submodule.

        """
        result_type = r[t.Pair[str, str] | Path]
        if path.is_absolute() or not path.parts or ".." in path.parts:
            return result_type.fail(f"invalid .gitmodules path: {path.as_posix()}")
        contract = cls._gitmodule_contract(repository_root, path)
        if contract.failure:
            return result_type.from_failure(contract)
        declared_branch = contract.value[1]
        unmanaged = u.Infra.git_unmanaged_submodule_paths(
            m.Infra.GitRepoRequest(repo_root=repository_root),
        )
        if unmanaged.failure:
            return result_type.from_failure(unmanaged)
        if path in unmanaged.value:
            return result_type.ok(path)
        if not u.Infra.gitmodule_branch_is_governed(
            declared_branch,
            integration_branch=context.integration_branch,
        ):
            return result_type.fail(
                "governed subproject branch differs from the workspace "
                f"integration line: {path.as_posix()}",
            )
        return result_type.ok(contract.value)

    @staticmethod
    def _validated_subproject_root(
        repository_root: Path,
        path: Path,
    ) -> p.Result[Path]:
        """Resolve the subproject checkout and keep it inside the workspace.

        Returns:
            The resolved subproject root inside the workspace root.

        """
        subproject_root = (repository_root / path).resolve()
        if not subproject_root.is_relative_to(repository_root):
            return r[Path].fail(
                f"subproject escapes workspace root: {path.as_posix()}",
            )
        return r[Path].ok(subproject_root)

    @classmethod
    def _declared_member_result(
        cls,
        subproject_root: Path,
        path: Path,
        *,
        declared_member: m.Infra.RepositoryRef,
        declared_url: str,
        allow_unprovisioned_members: bool,
    ) -> p.Result[m.Infra.RepositoryRef | Path] | None:
        """Resolve a manifest-declared member, or continue the governed lane.

        Returns:
            The terminal declared-member result, or ``None`` when the entry
            continues through the governed checkout lanes.

        """
        result_type = r[m.Infra.RepositoryRef | Path]
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
            ).exists() and not allow_unprovisioned_members:
                return result_type.fail(
                    "declared Python member checkout has no "
                    f"{c.PYPROJECT_FILENAME}: {path.as_posix()}",
                )
            # The manifest owns a declared member's identity, so topology
            # stays identical when CI deliberately omits member checkouts.
            return result_type.ok(declared_member)
        return None

    @classmethod
    def _indexed_gitlink_result(
        cls,
        repository_root: Path,
        path: Path,
    ) -> p.Result[m.Infra.RepositoryRef | Path]:
        """Classify an uninitialized checkout by the Git index gitlinks.

        Returns:
            The external entry path when indexed, or the missing-checkout
            refusal.

        """
        result_type = r[m.Infra.RepositoryRef | Path]
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

    @classmethod
    def _governed_member_result(
        cls,
        subproject_root: Path,
        path: Path,
        *,
        declared_url: str,
        workspace_beads: m.Infra.BeadsProjectSpec | None,
    ) -> p.Result[m.Infra.RepositoryRef | Path]:
        """Load one governed checkout and merge its manifest commands.

        Returns:
            The governed repository reference for the subproject.

        """
        result_type = r[m.Infra.RepositoryRef | Path]
        if not (subproject_root / c.PYPROJECT_FILENAME).is_file():
            return result_type.ok(path)
        route = cls._validated_beads_route(subproject_root, workspace_beads)
        if route.failure:
            return result_type.from_failure(route)
        repository = cls._local_repository_ref(
            subproject_root,
            path=path,
            composed=True,
            declared_url=declared_url,
        )
        if repository.failure:
            return result_type.from_failure(repository)
        return cls._manifest_member_result(
            subproject_root,
            repository=repository.value,
            workspace_beads=workspace_beads,
        )

    @classmethod
    def _validated_beads_route(
        cls,
        subproject_root: Path,
        workspace_beads: m.Infra.BeadsProjectSpec | None,
    ) -> p.Result[bool]:
        """Hold the checkout Beads layout against the workspace ledger route.

        Returns:
            Success when the checkout follows the workspace Beads ledger.

        """
        if workspace_beads is None:
            return r[bool].ok(value=True)
        if (subproject_root / c.Infra.BEADS_DIRNAME).is_symlink():
            route_error = cls._composed_beads_identity_error(
                subproject_root,
                workspace_beads,
            )
            if route_error is not None:
                return r[bool].fail(
                    "composed project must follow the workspace Beads ledger: "
                    f"{route_error}",
                )
            return r[bool].ok(value=True)
        beads = cls.load_beads_spec(subproject_root)
        if beads.failure:
            return r[bool].from_failure(beads)
        return r[bool].ok(value=True)

    @classmethod
    def _manifest_member_result(
        cls,
        subproject_root: Path,
        *,
        repository: m.Infra.RepositoryRef,
        workspace_beads: m.Infra.BeadsProjectSpec | None,
    ) -> p.Result[m.Infra.RepositoryRef | Path]:
        """Merge the member manifest identity and commands into the reference.

        Returns:
            The member repository reference carrying its owned commands.

        """
        result_type = r[m.Infra.RepositoryRef | Path]
        member_manifest = u.Infra.load_workspace_manifest(subproject_root)
        if member_manifest.failure:
            return result_type.from_failure(member_manifest)
        if not member_manifest.value:
            return result_type.ok(repository)
        member_beads = cls._member_beads_spec(subproject_root, workspace_beads)
        if member_beads.failure:
            return result_type.from_failure(member_beads)
        manifest = cls._manifest_repository_ref(
            subproject_root,
            observed=repository.model_copy(update={"path": Path()}),
            beads=member_beads.value,
        )
        if manifest.failure:
            return result_type.from_failure(manifest)
        # The member owns its commands. Git still owns its composed path,
        # topology and editability; do not import a second member registry.
        commands = manifest.value[0]
        return result_type.ok(
            repository.model_copy(
                update={
                    "extra_verbs": commands.extra_verbs,
                    "script_dispatch": commands.script_dispatch,
                },
            ),
        )

    @classmethod
    def _member_beads_spec(
        cls,
        subproject_root: Path,
        workspace_beads: m.Infra.BeadsProjectSpec | None,
    ) -> p.Result[m.Infra.BeadsProjectSpec | None]:
        """Load the member Beads spec when the workspace routes one ledger.

        Returns:
            The member Beads spec, or ``None`` when the workspace has none.

        """
        if workspace_beads is None:
            return r[m.Infra.BeadsProjectSpec | None].ok(None)
        loaded_member_beads = cls.load_beads_spec(subproject_root)
        if loaded_member_beads.failure:
            return r[m.Infra.BeadsProjectSpec | None].from_failure(
                loaded_member_beads,
            )
        return r[m.Infra.BeadsProjectSpec | None].ok(loaded_member_beads.value)

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
        if not resolved_root.is_dir():
            return r[m.Infra.WorkspaceSpec].fail(
                f"repository root is not a directory: {resolved_root}",
            )
        identity = u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=resolved_root))
        if identity.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(identity)
        declared_manifest = u.Infra.load_workspace_manifest(resolved_root)
        if declared_manifest.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(declared_manifest)
        manifest = declared_manifest.value[0] if declared_manifest.value else None
        overlay = (
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
        beads_enabled = overlay is None or overlay.beads_enabled
        if not beads_enabled and overlay is not None and overlay.gascity_enabled:
            return r[m.Infra.WorkspaceSpec].fail(
                "Gas City requires Beads participation in the repository policy",
            )
        beads: m.Infra.BeadsProjectSpec | None = None
        if beads_enabled:
            beads_result = cls.load_beads_spec(resolved_root)
            if beads_result.failure:
                return r[m.Infra.WorkspaceSpec].from_failure(beads_result)
            beads = beads_result.value
        member_root = identity.value.primary_root
        member_beads = member_root / c.Infra.BEADS_DIRNAME
        if (
            beads_enabled
            and identity.value.is_attached_submodule
            and member_beads.is_symlink()
        ):
            superproject_root = identity.value.superproject_root
            if superproject_root is None:
                return r[m.Infra.WorkspaceSpec].fail(
                    f"Git submodule has no superproject: {resolved_root}",
                )
            inherited_beads = cls.load_beads_spec(superproject_root)
            if inherited_beads.failure:
                return r[m.Infra.WorkspaceSpec].from_failure(inherited_beads)
            if not member_root.is_relative_to(superproject_root):
                return r[m.Infra.WorkspaceSpec].fail(
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
                return r[m.Infra.WorkspaceSpec].from_failure(superproject_members)
            loaded_member = cls._load_subproject(
                superproject_root,
                member_path,
                declared_member=superproject_members.value.get(member_path),
                context=m.Infra.SubprojectLoadContext(
                    integration_branch=(baseline.value if baseline.success else None),
                    workspace_beads=inherited_beads.value,
                ),
            )
            if loaded_member.failure or isinstance(loaded_member.value, Path):
                return r[m.Infra.WorkspaceSpec].fail(
                    loaded_member.error
                    or "Git submodule is not a declared governed project: "
                    f"{resolved_root}",
                )
            route_error = cls._composed_beads_identity_error(
                resolved_root,
                inherited_beads.value,
            )
            if route_error is not None:
                return r[m.Infra.WorkspaceSpec].fail(
                    "composed project must follow the workspace Beads ledger: "
                    f"{route_error}",
                )
            beads = inherited_beads.value
        repository = cls._local_repository_ref(
            resolved_root,
            composed=identity.value.is_attached_submodule,
        )
        if repository.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(repository)
        topology = cls._load_subprojects(
            resolved_root,
            workspace_beads=beads,
            allow_unprovisioned_members=allow_unprovisioned_members,
        )
        if topology.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(topology)
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
            return r[m.Infra.WorkspaceSpec].from_failure(declared_repository)
        repository_ref, gascity_enabled, declared_project = declared_repository.value
        if beads is not None:
            workspace_name = beads.workspace
        else:
            if manifest is None:
                return r[m.Infra.WorkspaceSpec].fail(
                    "workspace identity requires a manifest or Beads configuration",
                )
            workspace_name = manifest.name
        return r[m.Infra.WorkspaceSpec].ok(
            m.Infra.WorkspaceSpec(
                name=workspace_name,
                beads=beads,
                gascity_enabled=gascity_enabled,
                repository=repository_ref,
                project=declared_project,
                namespace_scan_dirs=(
                    declared_manifest.value[0].namespace_scan_dirs
                    if declared_manifest.value
                    else ()
                ),
                integration=(
                    declared_manifest.value[0].integration
                    if declared_manifest.value
                    else None
                ),
                candidate_dependencies=(
                    declared_manifest.value[0].candidate_dependencies
                    if declared_manifest.value
                    else ()
                ),
                candidate_bootstrap_targets=(
                    declared_manifest.value[0].candidate_bootstrap_targets
                    if declared_manifest.value
                    else ()
                ),
                subprojects=subprojects,
                external_dependency_paths=external,
            ),
        )

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
