"""Single owner of the workspace manifest: its path, its load, its role.

Every consumer that needs the workspace manifest, or whether a checkout
declares itself a fleet umbrella, asks here. The workspace detector service
consumes this owner; no utility reaches back into the service.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from flext_cli import u

from flext_infra import c, m, r, t

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesWorkspaceManifest:
    """Resolve, load and classify a checkout by its workspace manifest."""

    @staticmethod
    def workspace_manifest_path(repository_root: Path) -> Path:
        """Return where the workspace manifest lives for one checkout.

        Returns:
            Where the workspace manifest lives for one checkout.

        """
        return repository_root / c.CONFIG_DIR_NAME / c.Infra.WORKSPACE_MANIFEST_FILENAME

    @classmethod
    def load_workspace_manifest(
        cls,
        repository_root: Path,
    ) -> p.Result[t.SequenceOf[m.Infra.WorkspaceManifestSpec]]:
        """Load the checkout's own workspace manifest as a 0-or-1 sequence.

        Absence is an EMPTY sequence — success payloads are never ``None``.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.WorkspaceManifestSpec]]``.

        """
        manifest_path = cls.workspace_manifest_path(repository_root)
        if not manifest_path.is_file():
            return r[t.SequenceOf[m.Infra.WorkspaceManifestSpec]].ok(())
        text = u.Cli.files_read_text(manifest_path)
        if text.failure:
            return r[t.SequenceOf[m.Infra.WorkspaceManifestSpec]].fail(
                f"invalid workspace manifest ({manifest_path}): {text.error}",
            )
        return cls._parsed_workspace_manifest(text.value, str(manifest_path))

    @staticmethod
    @lru_cache(maxsize=c.Infra.CONTENT_CACHE_MAXSIZE)
    def _parsed_workspace_manifest(
        text: str,
        manifest_path: str,
    ) -> p.Result[t.SequenceOf[m.Infra.WorkspaceManifestSpec]]:
        """Parse and validate one manifest text once per exact content.

        The key is the exact file text, so an edited manifest is a new key,
        never a stale spec.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.WorkspaceManifestSpec]]``.

        """
        loaded = u.Cli.yaml_parse(text)
        if loaded.failure:
            return r[t.SequenceOf[m.Infra.WorkspaceManifestSpec]].fail(
                f"invalid workspace manifest ({manifest_path}): {loaded.error}",
            )
        validated: p.Result[m.Infra.WorkspaceManifestSpec] = u.validate_value(
            m.Infra.WorkspaceManifestSpec,
            loaded.value,
        )
        if validated.failure:
            return r[t.SequenceOf[m.Infra.WorkspaceManifestSpec]].fail_op(
                f"workspace manifest model validation ({manifest_path})",
                validated.error,
            )
        return r[t.SequenceOf[m.Infra.WorkspaceManifestSpec]].ok((validated.value,))

    @classmethod
    def fleet_umbrella(cls, repository_root: Path) -> bool:
        """Whether this checkout declares itself a fleet umbrella.

        The typed role in the handwritten workspace manifest is the only signal.
        Every governed standalone project also carries this manifest, so file
        existence alone would collapse its docs scope onto an aggregate root.

        Returns:
            The resulting ``bool``.

        """
        manifests = cls.load_workspace_manifest(repository_root).unwrap()
        return any(
            manifest.repository.role is c.Infra.MakeProfile.WORKSPACE
            for manifest in manifests
        )


__all__: list[str] = ["FlextInfraUtilitiesWorkspaceManifest"]
