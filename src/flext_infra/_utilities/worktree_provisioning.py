"""Worktree provisioning module.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorktreeProvisioning:
    @staticmethod
    def _ensure_gitlink_checkout(lane: Path, member_path: Path) -> p.Result[bool]:
        from flext_infra import u

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
        initialized = u.Infra.git_submodule_init(
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
        from flext_infra import u

        reference = member_path.as_posix()
        identity = u.Infra.git_identity(
            m.Infra.GitRepoRequest(repo_root=lane / member_path),
        )
        if identity.failure:
            return r[bool].from_failure(identity)
        if identity.value.dirty:
            return r[bool].fail(f"governed gitlink is dirty: {reference}")
        origin = identity.value.origin_remote
        if origin is None or u.Infra.git_remote_identity(
            origin,
        ) != u.Infra.git_remote_identity(declared_url):
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
        from flext_infra import u

        reference = member_path.as_posix()
        contract = u.Infra.gitmodule_contract(
            m.Infra.GitSubmoduleContractRequest(repo_root=lane, member_path=reference),
        )
        if contract.failure:
            return r[bool].from_failure(contract)
        recorded = u.Infra.git_staged_gitlink_oid(
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
        from flext_infra import u

        declared = u.Infra.git_declared_submodule_paths(lane)
        if declared.failure:
            return r[bool].from_failure(declared)
        sections = u.Infra.git_submodule_sections(
            m.Infra.GitRepoRequest(repo_root=lane),
        )
        if sections.failure:
            return r[bool].from_failure(sections)
        for member_path in declared.value:
            section = sections.value.get(member_path.as_posix())
            if section is None:
                return r[bool].fail(
                    f"lane gitlink declaration is missing: {member_path}",
                )
            managed = u.Infra.git_submodule_config_value(
                m.Infra.GitSubmoduleConfigRequest(
                    repo_root=lane,
                    section=section,
                    key=c.Infra.GITMODULE_MANAGED_KEY,
                ),
            )
            if managed.failure:
                return r[bool].from_failure(managed)
            if managed.value.text.lower() != "true":
                continue
            validated = cls._validate_governed_gitlink(lane, member_path)
            if validated.failure:
                return validated
        return r[bool].ok(value=True)

    @classmethod
    def setup_lane(cls, lane: Path) -> p.Result[bool]:
        from flext_infra import u

        gitlinks = cls._prepare_governed_gitlinks(lane)
        if gitlinks.failure:
            return gitlinks
        if not (lane / c.PYPROJECT_FILENAME).is_file():
            return r[bool].ok(value=True)
        lane_venv = u.Infra.runtime_environment_dir(lane)
        if lane_venv.is_symlink():
            return r[bool].fail(
                f"lane environment must be physical, not a symlink: {lane_venv}",
            )
        setup = u.Cli.run_live(
            (c.Infra.MAKE, "setup"),
            cwd=lane,
            remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
        )
        if setup.failure:
            return r[bool].from_failure(setup)
        interpreter = u.Infra.runtime_python(lane)
        if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
            return r[bool].fail(
                f"lane setup did not create an interpreter: {interpreter}",
            )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraWorktreeProvisioning"]
