"""Worktree provisioning module.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from flext_cli import u

from flext_infra import c, m, r
from flext_infra._utilities import (
    FlextInfraUtilitiesGitSemanticIdentityMixin,
    FlextInfraUtilitiesGitSemanticIndexMixin,
    FlextInfraUtilitiesGitSemanticSubmoduleMixin,
    FlextInfraUtilitiesGitWorktreeDiscoveryMixin,
    FlextInfraUtilitiesProjectDiscovery,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorktreeProvisioning:
    @staticmethod
    def _ensure_gitlink_checkout(lane: Path, member_path: Path) -> p.Result[bool]:

        reference = member_path.as_posix()
        git_marker = lane / member_path / ".git"
        if git_marker.is_symlink() or (
            git_marker.exists() and not git_marker.is_file()
        ):
            return r[bool].fail(
                f"governed gitlink has an invalid .git marker: {reference}",
            )
        if git_marker.exists():
            return r[bool].ok(value=True)
        initialized = FlextInfraUtilitiesGitSemanticSubmoduleMixin.git_submodule_init(
            m.Infra.GitRefRequest(repo_root=lane, reference=reference),
        )
        if initialized.failure:
            return r[bool].from_failure(initialized)
        return r[bool].ok(value=True)

    @staticmethod
    def _verify_gitlink_state(
        lane: Path,
        member_path: Path,
        declared_url: str,
        recorded_oid: str,
    ) -> p.Result[bool]:

        reference = member_path.as_posix()
        identity = FlextInfraUtilitiesGitSemanticIdentityMixin.git_identity(
            m.Infra.GitRepoRequest(repo_root=lane / member_path),
        )
        if identity.failure:
            return r[bool].from_failure(identity)
        if identity.value.dirty:
            return r[bool].fail(f"governed gitlink is dirty: {reference}")
        origin = identity.value.origin_remote
        discovery = FlextInfraUtilitiesGitWorktreeDiscoveryMixin
        if origin is None or discovery.git_remote_identity(
            origin,
        ) != discovery.git_remote_identity(declared_url):
            return r[bool].fail(f"governed gitlink identity mismatch: {reference}")
        if identity.value.head_oid != recorded_oid:
            return r[bool].fail(
                f"governed gitlink {reference} is not at recorded oid {recorded_oid}",
            )
        return r[bool].ok(value=True)

    @classmethod
    def _validate_governed_gitlink(
        cls,
        lane: Path,
        member_path: Path,
    ) -> p.Result[bool]:

        reference = member_path.as_posix()
        submodule = FlextInfraUtilitiesGitSemanticSubmoduleMixin
        contract = submodule.git_submodule_declaration(
            m.Infra.GitSubmoduleContractRequest(repo_root=lane, member_path=reference),
        )
        if contract.failure:
            return r[bool].from_failure(contract)
        recorded = FlextInfraUtilitiesGitSemanticIndexMixin.git_staged_gitlink_oid(
            m.Infra.GitRefRequest(repo_root=lane, reference=reference),
        )
        if recorded.failure:
            return r[bool].from_failure(recorded)
        ensured = cls._ensure_gitlink_checkout(lane, member_path)
        if ensured.failure:
            return ensured
        return cls._verify_gitlink_state(
            lane,
            member_path,
            contract.value.url,
            recorded.value.oid,
        )

    @classmethod
    def _prepare_governed_gitlinks(cls, lane: Path) -> p.Result[bool]:

        discovery = FlextInfraUtilitiesGitWorktreeDiscoveryMixin
        declared = discovery.git_declared_submodule_paths(lane)
        if declared.failure:
            return r[bool].from_failure(declared)
        for declaration in declared.value:
            # Lane provisioning materializes only explicitly managed links.
            if declaration.managed is not True:
                continue
            validated = cls._validate_governed_gitlink(lane, declaration.path)
            if validated.failure:
                return validated
        return r[bool].ok(value=True)

    @classmethod
    def setup_lane(cls, lane: Path) -> p.Result[bool]:

        gitlinks = cls._prepare_governed_gitlinks(lane)
        if gitlinks.failure:
            return gitlinks
        if not (lane / c.PYPROJECT_FILENAME).is_file():
            return r[bool].ok(value=True)
        lane_venv = FlextInfraUtilitiesProjectDiscovery.runtime_environment_dir(lane)
        if lane_venv.is_symlink():
            return r[bool].fail(
                f"lane environment must be physical, not a symlink: {lane_venv}",
            )
        setup = u.Cli.run_live(
            (c.Infra.MAKE, "setup"),
            cwd=lane,
            options=m.Cli.ProcessOptions(
                remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            ),
        )
        if setup.failure:
            return r[bool].from_failure(setup)
        interpreter = FlextInfraUtilitiesProjectDiscovery.runtime_python(lane)
        if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
            return r[bool].fail(
                f"lane setup did not create an interpreter: {interpreter}",
            )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraWorktreeProvisioning"]
