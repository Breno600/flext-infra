"""Repository-local workspace detection from immutable Git topology inputs.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import c, m, t, u
from flext_infra.base import s
from flext_infra.workspace._detector_identity import (
    FlextInfraWorkspaceDetectorIdentityMixin,
)
from flext_infra.workspace._detector_subprojects import (
    FlextInfraWorkspaceDetectorSubprojectsMixin,
)
from flext_infra.workspace._governance import FlextInfraWorkspaceGovernanceMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkspaceDetector(
    FlextInfraWorkspaceGovernanceMixin,
    FlextInfraWorkspaceDetectorIdentityMixin,
    FlextInfraWorkspaceDetectorSubprojectsMixin,
    s[c.Infra.MakeProfile],
):
    """Classify a repository only from files and Git facts inside that checkout."""

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
        refs = cls._resolved_workspace_refs(
            resolved_root,
            beads.value,
            composed=identity.is_attached_submodule,
            allow_unprovisioned_members=allow_unprovisioned_members,
        )
        if refs.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(refs)
        (repository_ref, gascity_enabled, declared_project), (subprojects, external) = (
            refs.value
        )
        named = cls._workspace_name(beads.value, manifest)
        if named.failure:
            return r[m.Infra.WorkspaceSpec].from_failure(named)
        return r[m.Infra.WorkspaceSpec].ok(
            m.Infra.WorkspaceSpec(
                name=named.value,
                beads=beads.value,
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
                subprojects=subprojects,
                external_dependency_paths=external,
                superproject_members=superproject_members,
            ),
        )

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
