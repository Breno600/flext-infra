"""Beads ledger route reconciliation for composed repositories.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, p, r
from flext_infra.codegen._conform.docs_ownership import (
    FlextInfraCodegenConformDocsOwnership,
)
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraCodegenConformBeadsRoutes(FlextInfraCodegenConformDocsOwnership):
    """Beads ledger route reconciliation for composed repositories."""

    def conform_workspace_beads_routes(
        self,
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[bool]:
        """Reconcile private metadata directories without cross-project links.

        A composed project follows the workspace ledger through its own rendered
        ``.beads`` configuration, which every checkout resolves identically. It
        previously followed the ledger through ``.beads -> ../.beads``, a link
        escaping into another repository: a second owner of a fact the
        configuration already declares, resolvable only on one machine's exact
        layout, and invisible to review because it reads as a directory. This
        method used to create those links and delete the real directory first;
        now it proves none survive and enforces the client's private-directory
        contract after publication, for the root and its composed members.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        root = request.root.expanduser().resolve()
        workspace_result = FlextInfraWorkspaceDetector.load_workspace_spec(root)
        if workspace_result.failure:
            return r[bool].from_failure(workspace_result)
        workspace = workspace_result.value
        owner = root / c.Infra.BEADS_DIRNAME
        if workspace.beads is None:
            if owner.exists() or owner.is_symlink():
                return r[bool].fail(
                    f"Beads-disabled repository still has Beads state: {owner}",
                )
            return r[bool].ok(value=True)
        # The ledger directory is a conform projection: absent before the
        # first render is normal; a link, or a non-directory, is not physical.
        if owner.is_symlink() or (owner.exists() and not owner.is_dir()):
            return r[bool].fail(
                f"workspace Beads ledger owner is not physical: {owner}",
            )
        if owner.is_dir():
            owner.chmod(c.Infra.BEADS_DIRECTORY_MODE)
        for repository in workspace.subprojects:
            state = self.beads_route_state((root / repository.path).resolve())
            if state.failure:
                return state
        return r[bool].ok(value=True)

    @staticmethod
    def beads_route_state(root: Path) -> p.Result[bool]:
        """Prove one repository reaches the ledger through its own directory.

        The route used to be a symlink into the workspace, so the directory
        always existed by the time anything rendered into it. Each repository
        now owns a real ``.beads`` holding its own generated configuration, and
        a generator owns the destination directory of the artifacts it
        declares: without it the first render fails reading a before-state
        whose parent is missing. The directory is created empty;
        ``.beads/config.yaml`` and ``.beads/metadata.json`` are rendered into
        it by generation, never copied and never linked.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        allowed_entries = (
            frozenset({
                Path(c.Infra.BEADS_CONFIG_RELPATH).name,
                Path(c.Infra.BEADS_METADATA_RELPATH).name,
                c.Infra.BEADS_LOCAL_VERSION_FILENAME,
                c.Infra.BEADS_LAST_TOUCHED_FILENAME,
                # Passive bd runtime exports: the bd client rewrites these from
                # the rig's Dolt ledger on every interaction, so they are
                # regenerable projections of ledger truth, never composed output.
                "issues.jsonl",
                "interactions.jsonl",
            })
            | c.Infra.BEADS_RUNTIME_ENTRY_NAMES
        )
        route = root / c.Infra.BEADS_DIRNAME
        if route.is_symlink():
            return r[bool].fail(
                "composed project reaches the workspace ledger through a "
                f"cross-project symbolic link: {route}",
            )
        if not route.exists():
            route.mkdir(mode=c.Infra.BEADS_DIRECTORY_MODE, parents=True)
            return r[bool].ok(value=True)
        if not route.is_dir():
            return r[bool].fail(
                f"composed project Beads route is not a directory: {route}",
            )
        unexpected = sorted(
            entry.name for entry in route.iterdir() if entry.name not in allowed_entries
        )
        if unexpected:
            return r[bool].fail(
                f"composed project has unmerged Beads state at {route}: "
                + ", ".join(unexpected),
            )
        route.chmod(c.Infra.BEADS_DIRECTORY_MODE)
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraCodegenConformBeadsRoutes"]
