"""Unified, fail-closed conformance for new and existing repositories.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_core import r
from flext_infra.codegen._conform import FlextInfraCodegenConformExecute
from flext_infra.constants
from flext_infra.models
from flext_infra.protocols
from flext_infra.typings
from flext_infra.utilities

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraCodegenConform(FlextInfraCodegenConformExecute):
    """Plan every selected output, then atomically write only a clean plan."""

    @classmethod
    def settle_repository(
        cls,
        root: Path,
        *,
        ports: m.Infra.CodegenConformPorts | None,
        refresh_git_peers: bool = False,
    ) -> p.Result[bool]:
        """Conform every projection of ``root``, then lock it without upgrading.

        ``ports`` are the facade-bound collaborators the complete conform
        crosses into; without them the conform fails before any effect.

        Conform settles ``pyproject.toml`` and every rendered projection first,
        so the lock resolves against them; it upgrades nothing (only ``upg``
        resolves the newest releases). ``refresh_git_peers`` refreshes the
        metadata of the dependencies declared through git only — moving
        sources by declaration — because a peer that moved on the
        integration branch carries stale cached requires-dist a retaining
        lock cannot see through; the propagate caller owns the flag and the
        default stays hermetic. Identical inputs regenerate identical bytes,
        so a rerun changes nothing.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        conformed = cls.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                scope=c.Infra.CodegenConformScope.ALL,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            ports=ports,
        )
        if conformed.failure:
            return r[bool].from_failure(conformed)
        command = [c.Infra.UV, "lock", "--project", str(root)]
        for name in cls._git_dependency_names(root) if refresh_git_peers else ():
            command.extend(("--refresh-package", name))
        return u.Cli.run_checked(command, cwd=root)

    @staticmethod
    def _git_dependency_names(root: Path) -> t.StrSequence:
        """Return the dependency names ``root`` declares through git.

        Branch-tracked git dependencies are moving sources by declaration:
        their cached metadata outlives the peer's tip, so the propagate
        caller refreshes exactly these and nothing else.

        Returns:
            The resulting ``t.StrSequence``.

        """
        payload = u.Infra.pyproject_payload(root / c.PYPROJECT_FILENAME)
        project = payload.get("project")
        if not isinstance(project, dict):
            return ()
        dependencies = project.get("dependencies")
        if not isinstance(dependencies, list):
            return ()
        return tuple(
            spec.split(" @ ", 1)[0].strip()
            for spec in dependencies
            if isinstance(spec, str) and "git+" in spec and " @ " in spec
        )


__all__: list[str] = ["FlextInfraCodegenConform"]
