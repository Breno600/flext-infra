"""Topology comes from each repository, never from an internal project registry."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from tests import u


class TestsFlextInfraDetectorOwnsNoProjectRegistry:
    """Prove derivation never consults a flext-infra-owned project catalog."""

    @staticmethod
    def _standalone(root: Path, *, name: str) -> Path:
        """Create a real Git repository that flext-infra has never heard of."""
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            name,
            workspace=f"{name}-workspace",
            database=f"{name}-database",
            issue_prefix=f"{name}-prefix",
        )
        return root

    def test_unknown_project_derives_its_own_identity(self, tmp_path: Path) -> None:
        """A repository absent from any catalog still derives from itself."""
        root = self._standalone(
            tmp_path / "totally-unknown-project", name="totally-unknown"
        )

        spec = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(spec.repository.name, eq="totally-unknown")
        # The workspace identity is the repository's own declared beads
        # projection, never a flext-infra catalog entry.
        tm.that(spec.name, eq=u.Tests.required_beads(spec).workspace)
        tm.that(spec.repository.path, eq=Path())
        tm.that(spec.subprojects, empty=True)
        tm.that(u.Tests.required_beads(spec).workspace, eq="totally-unknown-workspace")
