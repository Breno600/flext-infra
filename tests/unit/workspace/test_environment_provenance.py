"""Behavior tests for fail-closed workspace editable provenance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.workspace.environment_provenance import (
    FlextInfraWorkspaceEnvironmentProvenance,
)
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraWorkspaceEnvironmentProvenance:
    """Validate real PEP 610 and distribution file metadata."""

    @staticmethod
    def _workspace(root: Path, distribution: str = "sample-member") -> Path:
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "sample",
            workspace="sample-workspace",
            database="sample-database",
            issue_prefix="sample-prefix",
        )
        member = root / distribution
        u.Tests.WorktreeFixture.initialize_governed_project(
            member,
            distribution,
            workspace=f"{distribution}-workspace",
            database=f"{distribution}-database",
            issue_prefix=f"{distribution}-prefix",
            beads_owner=False,
        )
        u.Tests.WorktreeFixture.link_member_beads(
            member,
            root,
            workspace_name="sample-workspace",
            database="sample-database",
            issue_prefix="sample-prefix",
        )
        u.Tests.WorktreeFixture.write_gitmodules(root, (distribution,))
        return root

    @staticmethod
    def _installed_editable(
        site_packages: Path, distribution: str, *, direct_root: Path, source_root: Path
    ) -> None:
        site_packages.mkdir()
        normalized = distribution.replace("-", "_")
        dist_info = site_packages / f"{normalized}-1.0.dist-info"
        dist_info.mkdir()
        pth_name = f"_editable_impl_{normalized}.pth"
        (site_packages / pth_name).write_text(f"{source_root}\n", encoding="utf-8")
        (dist_info / "METADATA").write_text(
            f"Metadata-Version: 2.4\nName: {distribution}\nVersion: 1.0\n",
            encoding="utf-8",
        )
        (dist_info / "direct_url.json").write_text(
            (f'{{"url":"{direct_root.as_uri()}","dir_info":{{"editable":true}}}}\n'),
            encoding="utf-8",
        )
        (dist_info / "RECORD").write_text(
            (
                f"{pth_name},,\n"
                f"{dist_info.name}/METADATA,,\n"
                f"{dist_info.name}/direct_url.json,,\n"
                f"{dist_info.name}/RECORD,,\n"
            ),
            encoding="utf-8",
        )

    def _stale_checkout(self, tmp_path: Path) -> t.Triple[Path, Path, Path]:
        """Create the governed workspace, its member, and one stale checkout tree."""
        workspace = self._workspace(tmp_path / "workspace")
        member = workspace / "sample-member"
        stale = tmp_path / "stale" / "sample-member"
        (stale / "src").mkdir(parents=True)
        return workspace, member, stale

    @staticmethod
    def _provenance_failure(workspace: Path, site_packages: Path) -> str:
        """Validate provenance once and return its typed failure message."""
        result = FlextInfraWorkspaceEnvironmentProvenance.validate(
            workspace, metadata_paths=(str(site_packages),)
        )
        return tm.fail(result)

    def test_accepts_exact_live_editable(self, tmp_path: Path) -> None:
        """Accept one exact PEP 610 editable installed from the live member."""
        workspace = self._workspace(tmp_path / "workspace")
        member = workspace / "sample-member"
        site_packages = tmp_path / "site-packages"
        self._installed_editable(
            site_packages,
            "sample-member",
            direct_root=member,
            source_root=member / "src",
        )

        result = FlextInfraWorkspaceEnvironmentProvenance.validate(
            workspace, metadata_paths=(str(site_packages),)
        )

        tm.ok(result, eq=1)

    def test_rejects_stale_direct_url(self, tmp_path: Path) -> None:
        """Reject an editable whose direct URL targets an obsolete checkout."""
        workspace, member, stale = self._stale_checkout(tmp_path)
        site_packages = tmp_path / "site-packages"
        self._installed_editable(
            site_packages,
            "sample-member",
            direct_root=stale,
            source_root=member / "src",
        )
        error = self._provenance_failure(workspace, site_packages)
        tm.that(error, has="direct_url mismatch")
        tm.that(error, has=f"expected={member}")
        tm.that(error, has=f"actual={stale}")

    def test_rejects_stale_pth_source(self, tmp_path: Path) -> None:
        """Reject an editable path file that exposes an obsolete source tree."""
        workspace, member, stale = self._stale_checkout(tmp_path)
        site_packages = tmp_path / "site-packages"
        self._installed_editable(
            site_packages,
            "sample-member",
            direct_root=member,
            source_root=stale / "src",
        )
        error = self._provenance_failure(workspace, site_packages)
        tm.that(error, has="pth mismatch")
        tm.that(error, has=f"expected_root={member}")
        tm.that(error, has=f"actual={stale / 'src'}")

    def test_rejects_missing_distribution(self, tmp_path: Path) -> None:
        """Fail loud when a declared editable distribution is not installed."""
        workspace = self._workspace(tmp_path / "workspace")
        site_packages = tmp_path / "site-packages"
        site_packages.mkdir()

        error = self._provenance_failure(workspace, site_packages)
        tm.that(error, has="distribution count mismatch")
        tm.that(error, has="distribution=sample-member")
