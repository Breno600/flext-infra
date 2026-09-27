"""Session binding of an external consumer onto one flext worktree.

An external project declares flext packages by pinned git URL, so it always
validates PUBLISHED code. A cross-project change therefore could not be reviewed
until it was published, which inverts the order of work.

``FLEXT=<worktree>`` rebinds the consumer's environment onto that checkout for
the session. It is deliberately NOT a declaration: the consumer's
``pyproject.toml`` is never modified, so a local path can never be committed and
running setup without the flag restores the pinned resolution. Persistent,
declared sources remain owned by ``pyproject_conform._sync_uv_sources``; this
service owns only the session override, so the two never overlap.

The rebind set is derived from the intersection of what the consumer declares
and what the worktree actually provides, read from the worktree's own manifest —
never a hardcoded package list.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, t, u

from .detector import FlextInfraWorkspaceDetector

if TYPE_CHECKING:
    from flext_infra import p

logger = u.fetch_logger(__name__)


class FlextInfraFlextBindingService:
    """Resolve and apply one session binding onto a flext worktree."""

    @staticmethod
    def _declared_distributions(consumer_root: Path) -> p.Result[t.VariadicTuple[str]]:
        """Return the distribution names the consumer declares as dependencies."""
        manifest = consumer_root / c.PYPROJECT_FILENAME
        if not manifest.is_file():
            return r[t.VariadicTuple[str]].fail(
                f"consumer has no {c.PYPROJECT_FILENAME}: {consumer_root}"
            )
        payload_result = u.Cli.toml_read_json(manifest)
        payload: t.JsonMapping = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(
            payload_result.unwrap()
        )
        return r[t.VariadicTuple[str]].ok(
            tuple(u.Infra.project_dependency_names_from_payload(payload))
        )

    @classmethod
    def plan_targets(
        cls, *, consumer_root: Path, flext_root: Path
    ) -> p.Result[t.VariadicTuple[str]]:
        """Return the distributions this worktree can supply to the consumer.

        Fails closed when ``flext_root`` is not a flext workspace, so a mistyped
        path can never silently bind nothing and leave the consumer on its pins.
        """
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(flext_root)
        if workspace.failure:
            return r[t.VariadicTuple[str]].fail(
                f"FLEXT is not a flext workspace: {flext_root}: "
                f"{workspace.error or 'manifest unreadable'}"
            )
        available = {
            declared_repository.distribution: declared_repository
            for declared_repository in workspace.value.subprojects
            if declared_repository.package
        }
        declared = cls._declared_distributions(consumer_root)
        if declared.failure:
            return r[t.VariadicTuple[str]].from_failure(declared)
        return r[t.VariadicTuple[str]].ok(
            tuple(sorted(name for name in declared.value if name in available))
        )

    @classmethod
    def apply(
        cls, *, consumer_root: Path, flext_root: Path, python: Path
    ) -> p.Result[int]:
        """Rebind the consumer environment onto the worktree for this session."""
        planned = cls.plan_targets(consumer_root=consumer_root, flext_root=flext_root)
        if planned.failure:
            return r[int].from_failure(planned)
        targets = planned.value
        if not targets:
            u.Cli.info("flext binding: consumer declares no flext packages")
            return r[int].ok(0)
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(flext_root)
        if workspace.failure:
            return r[int].from_failure(workspace)
        paths = {
            declared_repository.distribution: (
                flext_root / declared_repository.path
            ).resolve()
            for declared_repository in workspace.value.subprojects
            if declared_repository.package
        }
        editables: list[str] = []
        for name in targets:
            editables.extend(("--editable", str(paths[name])))
        installed = u.Cli.run_checked(
            (c.Infra.UV, "pip", "install", "--python", str(python), *editables),
            cwd=consumer_root,
        )
        if installed.failure:
            return r[int].from_failure(installed)
        u.Cli.info(
            f"flext binding: {len(targets)} package(s) bound to {flext_root} "
            f"({', '.join(targets)})"
        )
        return r[int].ok(0)


__all__: list[str] = ["FlextInfraFlextBindingService"]
