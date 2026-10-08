"""Repository-local Beads identity resolution composed into detection.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkspaceBeadsMixin:
    """Load and route the repository-local Beads ledger identity."""

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


__all__: list[str] = ["FlextInfraWorkspaceBeadsMixin"]
