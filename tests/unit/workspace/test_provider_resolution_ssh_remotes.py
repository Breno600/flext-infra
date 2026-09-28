"""CI rewrites private submodule origins to SSH; resolution must still find the provider.

The generated workflow materializes a read-only deploy key per private member and
points that member's ``origin`` at an SSH URL, sometimes through a Host alias so
two keys can coexist on one forge. Provider resolution reads the live ``origin``,
so it has to accept every remote form Git accepts, not only HTTPS.
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from tests import u


class TestsFlextInfraProviderResolutionAcceptsSshRemotes:
    """Every remote form for a governed repository resolves to its provider."""

    @staticmethod
    def _governed_project(root: Path, name: str) -> Path:
        """Create one governed repository owned by the configured provider."""
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            name,
            workspace=f"{name}-workspace",
            database=f"{name}-database",
            issue_prefix=f"{name}-prefix",
        )
        return root

    @staticmethod
    def _repoint_origin(root: Path, url: str) -> None:
        """Rewrite ``origin`` the way the generated CI deploy-key step does."""
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "remote", "set-url", "origin", url], cwd=root
            )
        )

    def test_ssh_origin_resolves(self, tmp_path: Path) -> None:
        """A plain SSH origin is the same repository as its HTTPS form."""
        organization = u.Tests.provider().organization
        root = self._governed_project(tmp_path / "ssh-origin", "ssh-origin")
        self._repoint_origin(root, f"git@github.com:{organization}/ssh-origin.git")

        spec = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(spec.repository.name, eq="ssh-origin")

    def test_ssh_host_alias_origin_resolves(self, tmp_path: Path) -> None:
        """A deploy-key Host alias is not a different owner.

        This is the exact shape the generated workflow writes for a private
        member: the alias exists only so SSH can select a second identity file.
        """
        organization = u.Tests.provider().organization
        root = self._governed_project(tmp_path / "alias-origin", "alias-origin")
        self._repoint_origin(root, f"git@github-alias:{organization}/alias-origin.git")

        spec = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

        tm.that(spec.repository.name, eq="alias-origin")

    def test_foreign_organization_is_still_rejected(self, tmp_path: Path) -> None:
        """Accepting SSH must not make the organization stop discriminating."""
        root = self._governed_project(tmp_path / "foreign-origin", "foreign-origin")
        self._repoint_origin(
            root, "git@github-alias:organization-nobody-declares/foreign-origin.git"
        )

        tm.fail(FlextInfraWorkspaceDetector.load_workspace_spec(root))
