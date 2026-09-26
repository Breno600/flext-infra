"""Repository-local workspace detection from immutable Git topology inputs.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import c, config, m, t, u

from ..base import s
from ._governance import FlextInfraWorkspaceGovernanceMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkspaceDetector(
    FlextInfraWorkspaceGovernanceMixin, s[c.Infra.MakeProfile]
):
    """Classify a repository only from files and Git facts inside that checkout."""

    @staticmethod
    def _beads_path(repository_root: Path) -> Path:
        """Return the mandatory repository-local Beads identity path."""
        return repository_root / c.CONFIG_DIR_NAME / c.Infra.BEADS_CONFIG_FILENAME

    @classmethod
    def _composed_beads_identity_error(
        cls, subproject_root: Path, workspace_beads: m.Infra.BeadsProjectSpec
    ) -> str | None:
        member_identity = (
            subproject_root / c.CONFIG_DIR_NAME / c.Infra.BEADS_CONFIG_FILENAME
        )
        # Detection observes the topology; it does not enforce the ledger-route
        # prohibition. Refusing to load a workspace because one composed project
        # still carries the old cross-project symlink makes the migration
        # impossible to perform — nothing can plan the fix for a repository it
        # cannot describe. `codegen conform` owns the prohibition and rejects
        # the link there, per repository and within the requested scope.
        if not member_identity.is_file():
            return f"missing required member Beads routing identity: {member_identity}"
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
        cls, repository_root: Path
    ) -> p.Result[m.Infra.BeadsProjectSpec]:
        """Load and validate the required local ``config/beads.yaml``."""
        resolved_root = repository_root.expanduser().resolve()
        beads_path = cls._beads_path(resolved_root)
        if not beads_path.is_file():
            return r[m.Infra.BeadsProjectSpec].fail(
                f"missing required repository-local Beads configuration: {beads_path}"
            )
        loaded = u.Cli.config_load(beads_path, expand_env=False)
        if loaded.failure:
            return r[m.Infra.BeadsProjectSpec].fail(
                f"invalid repository-local Beads configuration ({beads_path}): "
                f"{loaded.error or 'configuration load failed'}"
            )
        validated: p.Result[m.Infra.BeadsProjectSpec] = u.validate_value(
            m.Infra.BeadsProjectSpec, loaded.value.data
        )
        if validated.failure:
            return r[m.Infra.BeadsProjectSpec].fail_op(
                f"Beads configuration model validation ({beads_path})", validated.error
            )
        return r[m.Infra.BeadsProjectSpec].ok(validated.value)

    @staticmethod
    def _git_origin_url(repository_root: Path) -> p.Result[str]:
        """Read the repository's required origin without inventing one."""
        result = u.Infra.git_remote_url(
            m.Infra.GitRemoteUrlRequest(repo_root=repository_root, remote="origin")
        )
        if result.failure or not result.value.text.strip():
            return r[str].fail(
                result.error or f"repository origin is required: {repository_root}"
            )
        return r[str].ok(result.value.text.strip())

    @classmethod
    def load_workspace_manifest(
        cls, repository_root: Path
    ) -> p.Result[t.SequenceOf[m.Infra.WorkspaceManifestSpec]]:
        """Load the checkout's own workspace manifest as a 0-or-1 sequence.

        This is the single spec-load owner for ``config/workspace.yaml``: the
        manifest is the authority for a repository's provider identity, and
        every consumer loads it through here so validation cannot diverge.
        Absence is an EMPTY sequence — success payloads are never ``None``.
        """
        manifest_path = u.Infra.workspace_manifest_path(repository_root)
        if not manifest_path.is_file():
            return r[t.SequenceOf[m.Infra.WorkspaceManifestSpec]].ok(())
        loaded = u.Cli.config_load(manifest_path, expand_env=False)
        if loaded.failure:
            error = loaded.error
            if error is None:
                msg = "workspace manifest load failed without an error"
                raise RuntimeError(msg)
            return r[t.SequenceOf[m.Infra.WorkspaceManifestSpec]].fail(
                f"invalid workspace manifest ({manifest_path}): {error}"
            )
        validated: p.Result[m.Infra.WorkspaceManifestSpec] = u.validate_value(
            m.Infra.WorkspaceManifestSpec, loaded.value.data
        )
        if validated.failure:
            return r[t.SequenceOf[m.Infra.WorkspaceManifestSpec]].fail_op(
                f"workspace manifest model validation ({manifest_path})",
                validated.error,
            )
        return r[t.SequenceOf[m.Infra.WorkspaceManifestSpec]].ok((validated.value,))

    @classmethod
    def _declared_provider_name(
        cls, repository_root: Path, *, origin_url: str
    ) -> p.Result[str]:
        """Detect the provider key the repository declares for itself.

        With a workspace manifest, the declaration is real only if the live
        Git origin carries the same organization identity as the declared URL
        (the same discrimination ``git_remote_identity`` gives every remote
        shape). Post-G1, repositories without a manifest take their provider
        identity from the live Git origin organization itself — no catalog,
        no invented rows.
        """
        loaded = cls.load_workspace_manifest(repository_root)
        if loaded.failure:
            return r[str].from_failure(loaded)
        if not loaded.value:
            origin_organization, origin_separator, _ = u.Infra.git_remote_identity(
                origin_url
            ).partition("/")
            if not origin_separator:
                return r[str].fail(
                    "governed repository Git origin must name an owner and "
                    f"repository: {origin_url}"
                )
            return r[str].ok(origin_organization)
        manifest = loaded.value[0]
        manifest_path = u.Infra.workspace_manifest_path(repository_root)
        declared = manifest.repository
        manifest_organization, manifest_separator, _ = u.Infra.git_remote_identity(
            declared.url
        ).partition("/")
        origin_organization, origin_separator, _ = u.Infra.git_remote_identity(
            origin_url
        ).partition("/")
        if (
            not manifest_separator
            or not origin_separator
            or manifest_organization != origin_organization
        ):
            return r[str].fail(
                "workspace manifest url organization differs from the live Git "
                f"origin ({manifest_path}): {declared.url!r} != {origin_url!r}"
            )
        return r[str].ok(declared.provider)

    @staticmethod
    def _manifest_git_contradictions(
        declared: m.Infra.RepositoryRef, observed: m.Infra.RepositoryRef
    ) -> list[str]:
        """Describe every manifest identity or topology conflict with Git."""
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
            observed.url
        ):
            contradictions.append("url identity differs from Git origin")
        # Why (cosmos-d0qn4): a repository-local manifest carries the
        # repository's own coordinates. Whether that repository is currently
        # checked out as a submodule is a fact of the parent's Git tree, not of
        # the manifest, so the same manifest must load both standalone (its own
        # CI observes root) and inside a workspace (the parent's conform
        # observes submodule). Only a manifest that claims to be a submodule
        # while Git shows a standalone checkout contradicts reality.
        if declared.role is not observed.role:
            contradictions.append(
                f"role {declared.role.value!r} contradicts the observed topology"
            )
        return contradictions

    @classmethod
    def _manifest_repository_ref(
        cls,
        repository_root: Path,
        *,
        observed: m.Infra.RepositoryRef,
        beads: m.Infra.BeadsProjectSpec,
    ) -> p.Result[t.Triple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]]:
        """Load a selected repository manifest and reconcile it with Git truth.

        The checkout's own manifest is mandatory for identity: its complete
        typed ``repository`` record is authoritative for repository policy and
        must agree with the immutable identity and topology observed from Git.
        The matched repository policy overlay's Gas City participation rides
        along: ``True`` when the manifest declares no overlay.
        """
        manifest_path = u.Infra.workspace_manifest_path(repository_root)
        loaded = cls.load_workspace_manifest(repository_root)
        if loaded.failure:
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].from_failure(loaded)
        if not loaded.value:
            # A checkout without ``config/workspace.yaml`` remains a valid
            # observed repository (pre-G1 contract, restored): the observed
            # state IS the identity, gascity participates, and no manifest
            # project spec exists. Absence never constructs a None payload.
            return r[tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]].ok((
                observed,
                True,
                None,
            ))
        loaded = u.Cli.config_load(manifest_path, expand_env=False)
        if loaded.failure:
            error = loaded.error
            if error is None:
                msg = "workspace manifest load failed without an error"
                raise RuntimeError(msg)
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].fail(f"invalid workspace manifest ({manifest_path}): {error}")
        validated: p.Result[m.Infra.WorkspaceManifestSpec] = u.validate_value(
            m.Infra.WorkspaceManifestSpec, loaded.value.data
        )
        if validated.failure:
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].fail_op(
                f"workspace manifest model validation ({manifest_path})",
                validated.error,
            )
        manifest = validated.value
        declared = manifest.repository
        contradictions = cls._manifest_git_contradictions(declared, observed)
        if contradictions:
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].fail(
                f"workspace manifest contradicts Git ({manifest_path}): "
                + "; ".join(contradictions)
            )
        # The manifest is the provider-identity authority: its declared URL was
        # just reconciled against the live Git origin above, so the declared
        # provider key rides with it and no catalog lookup may override it.
        if manifest.ledger_id is not None and manifest.ledger_id != beads.database:
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].fail(
                "workspace manifest ledger_id contradicts Beads identity "
                f"({manifest_path}): {manifest.ledger_id!r} != {beads.database!r}"
            )
        if (
            manifest.ledger_prefix is not None
            and manifest.ledger_prefix != beads.issue_prefix
        ):
            return r[
                tuple[m.Infra.RepositoryRef, bool, m.Infra.ProjectSpec | None]
            ].fail(
                "workspace manifest ledger_prefix contradicts Beads identity "
                f"({manifest_path}): {manifest.ledger_prefix!r} != "
                f"{beads.issue_prefix!r}"
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
        repository_root: Path, subproject_path: Path
    ) -> p.Result[t.Pair[str, str]]:
        """Read one exact URL/branch pair from the local ``.gitmodules``."""
        contract = u.Infra.gitmodule_contract(
            m.Infra.GitSubmoduleContractRequest(
                repo_root=repository_root, member_path=subproject_path.as_posix()
            )
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
        """Build repository policy from local metadata and an immutable Git URL."""
        metadata = u.Infra.read_project_metadata_result(repository_root)
        if metadata.failure:
            return r[m.Infra.RepositoryRef].from_failure(metadata)
        origin = cls._git_origin_url(repository_root)
        if origin.failure:
            return r[m.Infra.RepositoryRef].from_failure(origin)
        if declared_url is not None and u.Infra.git_remote_identity(
            origin.value
        ) != u.Infra.git_remote_identity(declared_url):
            return r[m.Infra.RepositoryRef].fail(
                f"subproject origin differs from its .gitmodules URL: {path.as_posix()}"
            )
        effective_url = declared_url or origin.value
        provider_result = cls._declared_provider_name(
            repository_root, origin_url=origin.value
        )
        if provider_result.failure:
            return r[m.Infra.RepositoryRef].from_failure(provider_result)
        role = (
            c.Infra.MakeProfile.WORKSPACE
            if (repository_root / c.Infra.GITMODULES).is_file()
            else c.Infra.MakeProfile.STANDALONE
        )
        project_name = metadata.value.project.name
        # The manifest is the identity authority: the provider key is the one
        # the repository itself declares and the declared URL organization was
        # just reconciled against the live origin, so no catalog may override
        # either.
        return r[m.Infra.RepositoryRef].ok(
            m.Infra.RepositoryRef(
                name=project_name,
                distribution=project_name,
                url=effective_url,
                path=path,
                role=role,
                provider=provider_result.value,
                kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
                codegen=c.Infra.CodegenKind.CONFORM,
                package=True,
                editable=composed,
                read_only=False,
            )
        )

    @classmethod
    def _load_subprojects(
        cls, repository_root: Path, *, workspace_beads: m.Infra.BeadsProjectSpec
    ) -> p.Result[
        t.Pair[t.VariadicTuple[m.Infra.RepositoryRef], t.VariadicTuple[Path]]
    ]:
        """Validate every direct governed .gitmodules entry before planning writes."""
        declared = u.Infra.git_declared_submodule_paths(repository_root)
        result_type = r[tuple[tuple[m.Infra.RepositoryRef, ...], t.VariadicTuple[Path]]]
        if declared.failure:
            return result_type.from_failure(declared)
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
        integration_branch = baseline.value if baseline.success else None
        for path in declared.value:
            if path in seen:
                return result_type.fail(
                    f"duplicate .gitmodules path: {path.as_posix()}"
                )
            seen.add(path)
            loaded = cls._load_subproject(
                repository_root,
                path,
                integration_branch=integration_branch,
                workspace_beads=workspace_beads,
            )
            if loaded.failure:
                return result_type.from_failure(loaded)
            if isinstance(loaded.value, Path):
                external.append(loaded.value)
                continue
            subprojects.append(loaded.value)
        return result_type.ok((tuple(subprojects), tuple(external)))

    @classmethod
    def _load_subproject(
        cls,
        repository_root: Path,
        path: Path,
        *,
        integration_branch: str | None = None,
        workspace_beads: m.Infra.BeadsProjectSpec,
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
        """
        result_type = r[m.Infra.RepositoryRef | Path]
        if path.is_absolute() or not path.parts or ".." in path.parts:
            return result_type.fail(f"invalid .gitmodules path: {path.as_posix()}")
        contract = cls._gitmodule_contract(repository_root, path)
        if contract.failure:
            return result_type.from_failure(contract)
        declared_url, declared_branch = contract.value
        sections = u.Infra.git_submodule_sections(
            m.Infra.GitRepoRequest(repo_root=repository_root)
        )
        if sections.failure:
            return result_type.from_failure(sections)
        section = sections.value.get(path.as_posix())
        if section is not None:
            managed = u.Infra.git_submodule_config_value(
                m.Infra.GitSubmoduleConfigRequest(
                    repo_root=repository_root, section=section, key="flext-managed"
                )
            )
            if managed.failure:
                return result_type.from_failure(managed)
            if managed.value.text and managed.value.text.lower() != "true":
                return result_type.ok(path)
        if not u.Infra.gitmodule_branch_is_governed(
            declared_branch, integration_branch=integration_branch
        ):
            return result_type.fail(
                "governed subproject branch differs from the workspace "
                f"integration line: {path.as_posix()}"
            )
        subproject_root = (repository_root / path).resolve()
        if not subproject_root.is_relative_to(repository_root):
            return result_type.fail(
                f"subproject escapes workspace root: {path.as_posix()}"
            )
        if not subproject_root.is_dir():
            # An indexed gitlink whose checkout was never initialized is an
            # intentionally absent working tree: Git already records the
            # commit it must materialize, so the entry classifies as an
            # external dependency instead of a missing governed checkout.
            indexed = u.Infra.git_staged_gitlink_oid(
                m.Infra.GitRefRequest(
                    repo_root=repository_root, reference=path.as_posix()
                )
            )
            if indexed.success:
                return result_type.ok(path)
            return result_type.fail(
                f"governed subproject checkout is missing: {path.as_posix()}"
            )
        if not (subproject_root / c.PYPROJECT_FILENAME).is_file():
            return result_type.ok(path)
        route_error = (
            cls._composed_beads_identity_error(subproject_root, workspace_beads)
            if (subproject_root / c.Infra.BEADS_DIRNAME).is_symlink()
            else None
        )
        if (
            route_error is None
            and not (subproject_root / c.Infra.BEADS_DIRNAME).is_symlink()
        ):
            beads = cls.load_beads_spec(subproject_root)
            if beads.failure:
                return result_type.from_failure(beads)
        if route_error is not None:
            return result_type.fail(
                "composed project must follow the workspace Beads ledger: "
                f"{route_error}"
            )
        repository = cls._local_repository_ref(
            subproject_root, path=path, composed=True, declared_url=declared_url
        )
        if repository.failure:
            return result_type.from_failure(repository)
        if not u.Infra.workspace_manifest_path(subproject_root).is_file():
            return result_type.ok(repository.value)
        member_beads = cls.load_beads_spec(subproject_root)
        if member_beads.failure:
            return result_type.from_failure(member_beads)
        manifest = cls._manifest_repository_ref(
            subproject_root,
            observed=repository.value.model_copy(update={"path": Path()}),
            beads=member_beads.value,
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
                }
            )
        )

    @classmethod
    def load_workspace_spec(
        cls, repository_root: Path, *, project_metadata: p.ProjectMetadata | None = None
    ) -> p.Result[m.Infra.WorkspaceSpec]:
        """Load local identity and validate local, read-only Git topology."""
        del project_metadata
        resolved_root = repository_root.expanduser().resolve()
        if not resolved_root.is_dir():
            return r[m.Infra.WorkspaceSpec].fail(
                f"repository root is not a directory: {resolved_root}"
            )
        identity = u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=resolved_root))
        if identity.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(identity)
        beads_result = cls.load_beads_spec(resolved_root)
        member_root = identity.value.primary_root
        member_beads = member_root / c.Infra.BEADS_DIRNAME
        if identity.value.is_attached_submodule and member_beads.is_symlink():
            superproject_root = identity.value.superproject_root
            if superproject_root is None:
                return r[m.Infra.WorkspaceSpec].fail(
                    f"Git submodule has no superproject: {resolved_root}"
                )
            inherited_beads = cls.load_beads_spec(superproject_root)
            if inherited_beads.failure:
                return r[m.Infra.WorkspaceSpec].from_failure(inherited_beads)
            try:
                member_path = member_root.relative_to(superproject_root)
            except ValueError:
                return r[m.Infra.WorkspaceSpec].fail(
                    f"Git submodule escapes its superproject: {member_root}"
                )
            # Same owner as the parent load: the declared preference resolves a
            # versioned integration line the provider fallback names miss.
            baseline = u.Infra.repository_baseline_branch(
                superproject_root,
                preference=(
                    config.Infra.codegen.branch_policy.integration_branch_preference
                ),
            )
            loaded_member = cls._load_subproject(
                superproject_root,
                member_path,
                integration_branch=baseline.value if baseline.success else None,
                workspace_beads=inherited_beads.value,
            )
            if loaded_member.failure or isinstance(loaded_member.value, Path):
                return r[m.Infra.WorkspaceSpec].fail(
                    loaded_member.error
                    or "Git submodule is not a declared governed project: "
                    f"{resolved_root}"
                )
            route_error = cls._composed_beads_identity_error(
                resolved_root, inherited_beads.value
            )
            if route_error is not None:
                return r[m.Infra.WorkspaceSpec].fail(
                    "composed project must follow the workspace Beads ledger: "
                    f"{route_error}"
                )
            beads_result = r[m.Infra.BeadsProjectSpec].ok(inherited_beads.value)
        if beads_result.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(beads_result)
        beads = beads_result
        repository = cls._local_repository_ref(
            resolved_root, composed=identity.value.is_attached_submodule
        )
        if repository.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(repository)
        topology = cls._load_subprojects(resolved_root, workspace_beads=beads.value)
        if topology.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(topology)
        subprojects, external = topology.value
        observed_repository = repository.value.model_copy(
            update={
                "role": (
                    c.Infra.MakeProfile.WORKSPACE
                    if subprojects or external
                    else c.Infra.MakeProfile.STANDALONE
                )
            }
        )
        declared_repository = cls._manifest_repository_ref(
            resolved_root, observed=observed_repository, beads=beads.value
        )
        if declared_repository.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(declared_repository)
        repository_ref, gascity_enabled, declared_project = declared_repository.value
        declared_manifest = cls.load_workspace_manifest(resolved_root)
        if declared_manifest.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(declared_manifest)
        return r[m.Infra.WorkspaceSpec].ok(
            m.Infra.WorkspaceSpec(
                name=beads.value.workspace,
                beads=beads.value,
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
                subprojects=subprojects,
                external_dependency_paths=external,
            )
        )

    @classmethod
    def conform_target(
        cls,
        repository_root: Path,
        workspace_spec: m.Infra.WorkspaceSpec | None = None,
        *,
        project_metadata: p.ProjectMetadata | None = None,
    ) -> p.Result[m.Infra.RepositoryConformTarget]:
        """Resolve a target exclusively from the requested checkout."""
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
                "local workspace repository path must be '.'"
            )
        metadata = u.Infra.read_project_metadata_result(resolved_root)
        if metadata.failure:
            return r[m.Infra.RepositoryConformTarget].from_failure(metadata)
        canonical_project_name = metadata.value.project.name
        if canonical_project_name != workspace.repository.distribution:
            return r[m.Infra.RepositoryConformTarget].fail(
                "project metadata and repository identity differ: "
                f"{canonical_project_name} != {workspace.repository.distribution}"
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
            )
        )

    @staticmethod
    def resolve_repository_root(repository_root: Path) -> p.Result[Path]:
        """Return the requested checkout; parent and primary trees are irrelevant."""
        resolved_root = repository_root.expanduser().resolve()
        if not resolved_root.is_dir():
            return r[Path].fail(f"repository root is not a directory: {resolved_root}")
        return r[Path].ok(resolved_root)

    @staticmethod
    def workspace_analysis_exclusion_paths(
        workspace: m.Infra.WorkspaceSpec,
    ) -> t.VariadicTuple[Path]:
        """Return read-only external Git dependencies excluded from analysis."""
        return workspace.external_dependency_paths

    @classmethod
    def analysis_exclusion_paths(
        cls, repository_root: Path
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Load exclusions for governed repositories; ignore ungoverned trees."""
        resolved_root = repository_root.expanduser().resolve()
        if not cls._beads_path(resolved_root).is_file():
            return r[t.VariadicTuple[Path]].ok(())
        # External analysis exclusions are declared exclusively by this
        # checkout's own .gitmodules. A composed project may follow its Beads
        # ledger from the parent, but that does not make the parent's complete
        # repository graph part of the member's analyzer scope. Loading the
        # inherited workspace here revalidated every sibling once per tooling
        # phase and turned one member conform into thousands of Git processes.
        if not (resolved_root / c.Infra.GITMODULES).is_file():
            return r[t.VariadicTuple[Path]].ok(())
        # Why (flext-gajwa): a governed root owns its own repository. A tree
        # that carries .beads/.gitmodules but no .git (a test sandbox, a
        # scratch copy) is ungoverned; asking Git here would discover an
        # ancestor checkout and validate *its* submodules against *this*
        # .gitmodules (sandbox escape observed under flext/.flext-runtime).
        if not (resolved_root / ".git").exists():
            return r[t.VariadicTuple[Path]].ok(())
        # Governance is declared, not matched: only a checkout that declares
        # its own workspace manifest (provider key plus canonical URL) is a
        # governed repository; anything else is an ungoverned tree whose
        # exclusions are none.
        if not u.Infra.workspace_manifest_path(resolved_root).is_file():
            return r[t.VariadicTuple[Path]].ok(())
        workspace = cls.load_workspace_spec(resolved_root)
        if workspace.failure:
            return r[t.VariadicTuple[Path]].from_failure(workspace)
        return r[t.VariadicTuple[Path]].ok(
            cls.workspace_analysis_exclusion_paths(workspace.value)
        )

    def detect(self, project_root: Path) -> p.Result[c.Infra.MakeProfile]:
        """Classify from governed members, not mere vendored Git topology."""
        try:
            resolved_root = project_root.expanduser().resolve()
        except c.EXC_OS_RUNTIME_TYPE as exc:
            return r[c.Infra.MakeProfile].fail_op("Workspace detection", exc)
        if not resolved_root.is_dir():
            return r[c.Infra.MakeProfile].fail(
                f"project root is not a directory: {resolved_root}"
            )
        workspace = self.load_workspace_spec(resolved_root)
        if workspace.failure:
            return r[c.Infra.MakeProfile].from_failure(workspace)
        return r[c.Infra.MakeProfile].ok(workspace.value.repository.role)

    @override
    def execute(self) -> p.Result[c.Infra.MakeProfile]:
        """Execute workspace detection for the configured root."""
        return self.detect(self.repository_root)


__all__: list[str] = ["FlextInfraWorkspaceDetector"]
