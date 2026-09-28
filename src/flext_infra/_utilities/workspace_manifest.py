"""Single owner of the workspace manifest path and the fleet-umbrella question.

Every consumer that needs to know where the workspace manifest lives, or
whether a checkout declares itself a fleet umbrella, asks here. The expression
existed in five places before this module, and the sixth copy asked the wrong
file: it tested the Beads override, which every project carries, so every
standalone project was classified as an umbrella. That misrouting silently
dropped each new project's README and project docs.

One owner exists so a seventh copy cannot be written.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_cli import u

from .. import c, m

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraUtilitiesWorkspaceManifest:
    """Resolve the workspace manifest and classify a checkout by it."""

    @staticmethod
    def workspace_manifest_path(repository_root: Path) -> Path:
        """Return where the workspace manifest lives for one checkout."""
        return repository_root / c.CONFIG_DIR_NAME / c.Infra.WORKSPACE_MANIFEST_FILENAME

    @classmethod
    def fleet_umbrella(cls, repository_root: Path) -> bool:
        """Whether this checkout declares itself a fleet umbrella.

        The typed role in the handwritten workspace manifest is the only signal.
        Every governed standalone project also carries this manifest, so file
        existence alone would collapse its docs scope onto an aggregate root.
        """
        manifest_path = cls.workspace_manifest_path(repository_root)
        if not manifest_path.is_file():
            return False
        loaded = u.Cli.config_load(manifest_path, expand_env=False).unwrap()
        manifest = m.Infra.WorkspaceManifestSpec.model_validate(loaded.data)
        return manifest.repository.role is c.Infra.MakeProfile.WORKSPACE


__all__: list[str] = ["FlextInfraUtilitiesWorkspaceManifest"]
