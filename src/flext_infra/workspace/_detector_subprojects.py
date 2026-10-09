"""Governed .gitmodules subproject topology composed into detection.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, config, m, t, u
from flext_infra.workspace._detector_beads import FlextInfraWorkspaceBeadsMixin
from flext_infra.workspace._detector_identity import FlextInfraWorkspaceIdentityMixin

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkspaceSubprojectsMixin(
    FlextInfraWorkspaceBeadsMixin,
    FlextInfraWorkspaceIdentityMixin,
):
    """Validate every governed .gitmodules entry before planning writes."""

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
        result_type = r[m.Infra.RepositoryRef | Path]
        gate = cls._governed_entry_gate(
            repository_root,
            path,
            context=context,
        )
        if gate.failure:
            return result_type.from_failure(gate)
        declared_url, external = gate.value
        if external:
            return result_type.ok(path)
        verdict = cls._ci_member_verdict(path, declared_member, declared_url)
        if verdict is None:
            verdict = cls._checkout_verdict(
                repository_root,
                path,
                declared_member=declared_member,
                declared_url=declared_url,
                context=context,
            )
        if verdict is not None:
            return verdict
        subproject_root = (repository_root / path).resolve()
        beads_route = cls._validate_beads_route(
            subproject_root,
            context.workspace_beads,
        )
        if beads_route.failure:
            return result_type.from_failure(beads_route)
        member = cls._composed_member(
            path,
            subproject_root,
            declared_url=declared_url,
            workspace_beads=context.workspace_beads,
        )
        if member.failure:
            return result_type.from_failure(member)
        return result_type.ok(member.value)

    @classmethod
    def _governed_entry_gate(
        cls,
        repository_root: Path,
        path: Path,
        *,
        context: m.Infra.SubprojectLoadContext,
    ) -> p.Result[t.Pair[str, bool]]:
        """Validate the governance gate of one .gitmodules entry.

        Returns:
            The resulting ``(declared_url, is_unmanaged_external)`` pair; an
            external entry classifies as a vendored or fork checkout the
            workspace never governs.

        """
        result_type = r[t.Pair[str, bool]]
        if path.is_absolute() or not path.parts or ".." in path.parts:
            return result_type.fail(f"invalid .gitmodules path: {path.as_posix()}")
        contract = cls._gitmodule_contract(repository_root, path)
        if contract.failure:
            return result_type.from_failure(contract)
        declared_url, declared_branch = contract.value
        unmanaged = u.Infra.git_unmanaged_submodule_paths(
            m.Infra.GitRepoRequest(repo_root=repository_root),
        )
        if unmanaged.failure:
            return result_type.from_failure(unmanaged)
        if path in unmanaged.value:
            return result_type.ok((declared_url, True))
        if not u.Infra.gitmodule_branch_is_governed(
            declared_branch,
            integration_branch=context.integration_branch,
        ):
            return result_type.fail(
                "governed subproject branch differs from the workspace "
                f"integration line: {path.as_posix()}",
            )
        return result_type.ok((declared_url, False))

    @classmethod
    def _ci_member_verdict(
        cls,
        path: Path,
        declared_member: m.Infra.RepositoryRef | None,
        declared_url: str,
    ) -> p.Result[m.Infra.RepositoryRef | Path] | None:
        """Return the CI-mode member identity, or ``None`` outside CI.

        Returns:
            The resulting CI member identity result, or ``None`` when the run
            is not the governed CI environment.

        """
        ci = config.Infra.codegen.make.ci
        if u.Infra.env_value(ci.variable).strip() != ci.value:
            return None
        outcome = r[m.Infra.RepositoryRef | Path]
        if declared_member is None:
            return outcome.fail(
                f"CI requires a root-owned member identity: {path.as_posix()}",
            )
        if u.Infra.git_remote_identity(
            declared_member.url,
        ) != u.Infra.git_remote_identity(declared_url):
            return outcome.fail(
                f"CI member URL differs from root topology: {path.as_posix()}",
            )
        return outcome.ok(declared_member)

    @classmethod
    def _checkout_verdict(
        cls,
        repository_root: Path,
        path: Path,
        *,
        declared_member: m.Infra.RepositoryRef | None,
        declared_url: str,
        context: m.Infra.SubprojectLoadContext,
    ) -> p.Result[m.Infra.RepositoryRef | Path] | None:
        """Classify the checkout state of one governed entry.

        Returns:
            The classification verdict, or ``None`` to continue into the
            composed-member load.

        """
        result_type = r[m.Infra.RepositoryRef | Path]
        subproject_root = (repository_root / path).resolve()
        if not subproject_root.is_relative_to(repository_root):
            return result_type.fail(
                f"subproject escapes workspace root: {path.as_posix()}",
            )
        declared = cls._declared_member_verdict(
            subproject_root,
            path,
            declared_member=declared_member,
            declared_url=declared_url,
            context=context,
        )
        if declared is not None:
            return declared
        if not subproject_root.is_dir():
            return cls._missing_checkout_verdict(repository_root, path)
        if not (subproject_root / c.PYPROJECT_FILENAME).is_file():
            return result_type.ok(path)
        return None

    @classmethod
    def _declared_member_verdict(
        cls,
        subproject_root: Path,
        path: Path,
        *,
        declared_member: m.Infra.RepositoryRef | None,
        declared_url: str,
        context: m.Infra.SubprojectLoadContext,
    ) -> p.Result[m.Infra.RepositoryRef | Path] | None:
        """Classify a manifest-declared member's checkout identity.

        Returns:
            The declared member's verdict, or ``None`` to continue into the
            undeclared-entry classification.

        """
        result_type = r[m.Infra.RepositoryRef | Path]
        if declared_member is None:
            return None
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
        if (subproject_root / c.PYPROJECT_FILENAME).is_file():
            return None
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

    @classmethod
    def _missing_checkout_verdict(
        cls,
        repository_root: Path,
        path: Path,
    ) -> p.Result[m.Infra.RepositoryRef | Path]:
        """Classify an uninitialized governed checkout by its index gitlink.

        Returns:
            The resulting external path for an indexed gitlink, else the
            missing-checkout failure.

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
    def _validate_beads_route(
        cls,
        subproject_root: Path,
        workspace_beads: m.Infra.BeadsProjectSpec | None,
    ) -> p.Result[bool]:
        """Enforce the workspace Beads ledger route for composed members.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        route_error = (
            cls._composed_beads_identity_error(subproject_root, workspace_beads)
            if workspace_beads is not None
            and (subproject_root / c.Infra.BEADS_DIRNAME).is_symlink()
            else None
        )
        if route_error is not None:
            return r[bool].fail(
                "composed project must follow the workspace Beads ledger: "
                f"{route_error}",
            )
        if (
            workspace_beads is not None
            and not (subproject_root / c.Infra.BEADS_DIRNAME).is_symlink()
        ):
            beads = cls.load_beads_spec(subproject_root)
            if beads.failure:
                return r[bool].from_failure(beads)
        return r[bool].ok(value=True)

    @classmethod
    def _composed_member(
        cls,
        path: Path,
        subproject_root: Path,
        *,
        declared_url: str,
        workspace_beads: m.Infra.BeadsProjectSpec | None,
    ) -> p.Result[m.Infra.RepositoryRef]:
        """Load one composed member's repository ref and manifest commands.

        Returns:
            The resulting ``p.Result[m.Infra.RepositoryRef]``.

        """
        repository = cls._local_repository_ref(
            subproject_root,
            path=path,
            composed=True,
            declared_url=declared_url,
        )
        if repository.failure:
            return r[m.Infra.RepositoryRef].from_failure(repository)
        member_manifest = u.Infra.load_workspace_manifest(subproject_root)
        if member_manifest.failure:
            return r[m.Infra.RepositoryRef].from_failure(member_manifest)
        if not member_manifest.value:
            return r[m.Infra.RepositoryRef].ok(repository.value)
        member_beads: m.Infra.BeadsProjectSpec | None = None
        if workspace_beads is not None:
            loaded_member_beads = cls.load_beads_spec(subproject_root)
            if loaded_member_beads.failure:
                return r[m.Infra.RepositoryRef].from_failure(loaded_member_beads)
            member_beads = loaded_member_beads.value
        manifest = cls._manifest_repository_ref(
            subproject_root,
            observed=repository.value.model_copy(update={"path": Path()}),
            beads=member_beads,
        )
        if manifest.failure:
            return r[m.Infra.RepositoryRef].from_failure(manifest)
        # The member owns its commands. Git still owns its composed path,
        # topology and editability; do not import a second member registry.
        commands = manifest.value[0]
        return r[m.Infra.RepositoryRef].ok(
            repository.value.model_copy(
                update={
                    "extra_verbs": commands.extra_verbs,
                    "script_dispatch": commands.script_dispatch,
                },
            ),
        )


__all__: list[str] = ["FlextInfraWorkspaceSubprojectsMixin"]
