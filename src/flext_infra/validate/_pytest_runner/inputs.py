"""Governed non-Python inputs for the persistent Testmon environment."""

from __future__ import annotations

import hashlib
from pathlib import Path

from flext_infra import u
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraPytestInputs:
    """Fingerprint config and workspace-declared resources without storing secrets."""

    @staticmethod
    def fingerprint(root: Path) -> str:
        """Read current input topology on each command construction."""
        digest = hashlib.sha256()
        for state in u.Infra.snapshot_config_sources(root).unwrap():
            digest.update(state.path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            if state.content is None:
                msg = f"required test configuration disappeared: {state.path}"
                raise ValueError(msg)
            digest.update(hashlib.sha256(state.content).digest())
        manifests = FlextInfraWorkspaceDetector.load_workspace_manifest(root).unwrap()
        for manifest in manifests:
            policy = manifest.test_inputs
            if policy is None:
                continue
            for relative in sorted((*policy.templates, *policy.resources)):
                directory = root / relative
                planned = u.Cli.atomic_plan_directory_chain(directory).unwrap()
                digest.update(relative.as_posix().encode())
                digest.update(b"\0")
                if planned.directories:
                    digest.update(b"absent\0")
                    continue
                inventory = u.Cli.atomic_inventory_physical_tree(directory).unwrap()
                digest.update(b"present\0")
                for entry in inventory.entries:
                    if entry.kind == "symlink":
                        msg = f"declared test input must be physical: {entry.path}"
                        raise ValueError(msg)
                    digest.update(entry.path.relative_to(root).as_posix().encode())
                    digest.update(b"\0")
                    digest.update(f"{entry.kind}:{entry.mode}:{entry.sha256}".encode())
                    digest.update(b"\0")
            for name in sorted(policy.environment):
                digest.update(name.encode())
                digest.update(b"\0")
                value = u.Infra.env_lookup(name)
                digest.update(b"absent\0" if value is None else b"present\0")
                if value is not None:
                    digest.update(hashlib.sha256(value.encode()).digest())
        return digest.hexdigest()


__all__: list[str] = ["FlextInfraPytestInputs"]
