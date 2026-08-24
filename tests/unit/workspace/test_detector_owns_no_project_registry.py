"""Topology comes from the project, never from a registry inside flext-infra.

Operator law: flext-infra owns generic conform behaviour only. It must not
carry a registry of the projects it serves, so a repository's identity and its
governed members are derived from that repository's own
``config/workspace.yaml`` plus live Git, and from nothing else.

A standalone repository that ships no manifest is still derivable: its identity
comes from its own ``pyproject.toml`` metadata and its members from the Git
submodule contract it actually declares.
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, u
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_tests import tm
from tests import u as test_u


def _standalone(root: Path, *, name: str) -> Path:
    """Create a real Git repository that flext-infra has never heard of."""
    (root / "src" / name.replace("-", "_")).mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        f"[project]\nname = '{name}'\nversion = '0.1.0'\n"
        "requires-python = '>=3.13,<3.14'\n",
        encoding="utf-8",
    )
    test_u.Tests.initialize_git_repo(root)
    return root


class TestsDetectorOwnsNoProjectRegistry:
    """Prove derivation never consults a flext-infra-owned project catalog."""

    def test_codegen_config_declares_no_project_registry(self) -> None:
        """flext-infra config carries generic policy, never a project list."""
        tm.that(
            hasattr(config.Infra.codegen, "repositories"),
            eq=False,
            msg="codegen config must not own a registry of served projects",
        )

    def test_unknown_project_derives_its_own_identity(self, tmp_path: Path) -> None:
        """A repository absent from any catalog still derives from itself."""
        root = _standalone(tmp_path / "totally-unknown-project", name="totally-unknown")

        spec = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(spec.name, eq="totally-unknown")
        tm.that(spec.repository.name, eq="totally-unknown")
        tm.that(spec.repository.path, eq=Path())
        tm.that(spec.members, empty=True)

    def test_declared_manifest_remains_the_topology_ssot(self, tmp_path: Path) -> None:
        """When the project ships a manifest, that manifest wins."""
        root = _standalone(tmp_path / "manifested", name="manifested")
        provider = config.Infra.codegen.providers[0]
        (root / "config").mkdir()
        tm.ok(
            u.Cli.yaml_dump(
                root / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME,
                {
                    "version": c.Infra.WORKSPACE_MANIFEST_VERSION,
                    "name": "manifested",
                    "repository": {
                        "name": "manifested",
                        "distribution": "manifested",
                        "provider": provider.name,
                        "url": f"https://github.com/{provider.name}/manifested.git",
                        "path": ".",
                        "role": "workspace-root",
                        "state": "active",
                        "checkout": "root",
                        "codegen": "conform",
                        "package": True,
                        "editable": False,
                        "read_only": False,
                    },
                    "members": [],
                    "exclusions": [],
                },
            )
        )

        spec = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(spec.name, eq="manifested")
        tm.that(spec.repository.distribution, eq="manifested")
