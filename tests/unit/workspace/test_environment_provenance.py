"""Behavior tests for fail-closed workspace editable provenance.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from json import dumps
from pathlib import Path
from sys import prefix
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import config
from flext_infra.workspace import FlextInfraWorkspaceEnvironmentProvenance
from tests import c, m, u

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests import p, t


class TestsFlextInfraWorkspaceEnvironmentProvenance:
    """Validate real PEP 610 and distribution file metadata."""

    @pytest.fixture
    def ci_mode(self) -> bool:
        """Read the same typed CI-token contract used by the public consumer.

        Returns:
            Whether this test invocation selects locked CI provenance.

        """
        ci = config.Infra.codegen.make.ci
        return u.Infra.env_value(ci.variable).strip() == ci.value

    @pytest.fixture
    def site_packages(self) -> Iterator[Path]:
        """Isolate metadata beneath the owned prefix without installing packages.

        Yields:
            The metadata directory within the active environment's prefix.

        """
        with TemporaryDirectory(dir=prefix) as temporary:
            yield Path(temporary) / "site-packages"

    @staticmethod
    def _workspace(root: Path, distribution: str = "sample-member") -> Path:
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "sample",
            beads=u.Tests.BeadsIdentity(
                workspace="sample-workspace",
                database="sample-database",
                issue_prefix="sample-prefix",
            ),
        )
        member = root / distribution
        u.Tests.WorktreeFixture.initialize_governed_project(
            member,
            distribution,
            beads=u.Tests.BeadsIdentity(
                workspace=f"{distribution}-workspace",
                database=f"{distribution}-database",
                issue_prefix=f"{distribution}-prefix",
            ),
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
        site_packages: Path,
        distribution: str,
        *,
        direct_root: Path,
        source_root: Path,
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
        """Create the governed workspace, its member, and one stale checkout tree.

        Returns:
            The resulting ``t.Triple[Path, Path, Path]``.

        """
        workspace = self._locked_workspace(tmp_path)
        member = workspace / "sample-member"
        stale = tmp_path / "stale" / "sample-member"
        (stale / "src").mkdir(parents=True)
        return workspace, member, stale

    @staticmethod
    def _provenance_failure(workspace: Path, site_packages: Path) -> str:
        """Validate provenance once and return its typed failure message.

        Returns:
            The resulting ``str``.

        """
        result = FlextInfraWorkspaceEnvironmentProvenance.validate(
            workspace,
            metadata_paths=(str(site_packages),),
        )
        return tm.fail(result)

    def test_accepts_exact_live_editable(
        self,
        tmp_path: Path,
        site_packages: Path,
        *,
        ci_mode: bool,
    ) -> None:
        """Accept one exact PEP 610 editable installed from the live member."""
        workspace = self._locked_workspace(tmp_path)
        member = workspace / "sample-member"
        self._installed_editable(
            site_packages,
            "sample-member",
            direct_root=member,
            source_root=member / "src",
        )

        result = FlextInfraWorkspaceEnvironmentProvenance.validate(
            workspace,
            metadata_paths=(str(site_packages),),
        )

        if ci_mode:
            tm.that(tm.fail(result), has="CI dependency is editable")
        else:
            tm.ok(result, eq=1)

    def test_rejects_stale_direct_url(
        self,
        tmp_path: Path,
        site_packages: Path,
        *,
        ci_mode: bool,
    ) -> None:
        """Reject an editable whose direct URL targets an obsolete checkout."""
        workspace, member, stale = self._stale_checkout(tmp_path)
        self._installed_editable(
            site_packages,
            "sample-member",
            direct_root=stale,
            source_root=member / "src",
        )
        error = self._provenance_failure(workspace, site_packages)
        if ci_mode:
            tm.that(error, has="CI dependency is editable")
        else:
            tm.that(error, has="direct_url mismatch")
            tm.that(error, has=f"expected={member}")
            tm.that(error, has=f"actual={stale}")

    def test_rejects_stale_pth_source(
        self,
        tmp_path: Path,
        site_packages: Path,
        *,
        ci_mode: bool,
    ) -> None:
        """Reject an editable path file that exposes an obsolete source tree."""
        workspace, member, stale = self._stale_checkout(tmp_path)
        self._installed_editable(
            site_packages,
            "sample-member",
            direct_root=member,
            source_root=stale / "src",
        )
        error = self._provenance_failure(workspace, site_packages)
        if ci_mode:
            tm.that(error, has="CI dependency is editable")
        else:
            tm.that(error, has="pth mismatch")
            tm.that(error, has=f"expected_root={member}")
            tm.that(error, has=f"actual={stale / 'src'}")

    def test_rejects_missing_distribution(
        self,
        tmp_path: Path,
        site_packages: Path,
    ) -> None:
        """Fail loud when a declared editable distribution is not installed."""
        workspace = self._locked_workspace(tmp_path)
        site_packages.mkdir()

        error = self._provenance_failure(workspace, site_packages)
        tm.that(error, has="distribution")
        tm.that(error, has="sample-member")

    def _locked_workspace(self, tmp_path: Path) -> Path:
        """Declare a virtual root and commit its member's exact native gitlink.

        Returns:
            The governed workspace root.

        """
        workspace = self._workspace(tmp_path / "workspace")
        member = workspace / "sample-member"
        u.Tests.commit_git_changes(member, "declare member ledger route")
        u.Tests.WorktreeFixture.attach_submodule(
            workspace,
            member,
            distribution="sample-member",
            relative_path="sample-member",
        )
        manifest = tm.ok(u.Infra.load_workspace_manifest(workspace))[0]
        repository = u.Tests.repository_ref(
            "sample-member",
            path=Path("sample-member"),
        ).model_copy(update={"checkout": c.Infra.CheckoutKind.SUBMODULE.value})
        declared = manifest.model_copy(
            update={
                "repository": manifest.repository.model_copy(update={"package": False}),
                "members": (repository,),
            },
        )
        tm.ok(
            u.Cli.yaml_dump(
                u.Infra.workspace_manifest_path(workspace),
                declared.model_dump(mode="json"),
            ),
        )
        (workspace / "uv.lock").write_text(
            '[[package]]\nname = "sample-member"\nversion = "1.0"\n'
            'source = { editable = "sample-member" }\n',
            encoding="utf-8",
        )
        u.Tests.commit_git_changes(workspace, "declare locked workspace")
        return workspace

    def _locked_verdict(
        self,
        workspace: Path,
        *,
        direct_root: Path | None = None,
        source_root: Path | None = None,
        receipt: m.Infra.DirectUrlReceipt | None = None,
    ) -> p.Result[int]:
        """Read real distribution metadata without changing the active environment.

        Returns:
            The public locked-provenance verdict.

        """
        member = workspace / "sample-member"
        with TemporaryDirectory(dir=prefix) as temporary:
            site_packages = Path(temporary) / "site-packages"
            self._installed_editable(
                site_packages,
                "sample-member",
                direct_root=member if direct_root is None else direct_root,
                source_root=Path(prefix) if source_root is None else source_root,
            )
            build_origin = (
                m.Infra.DirectUrlReceipt(
                    url=(member if direct_root is None else direct_root).as_uri(),
                    dir_info=m.Infra.DirectUrlDirectoryInfo(),
                )
                if receipt is None
                else receipt
            )
            direct_url = (
                site_packages / "sample_member-1.0.dist-info" / "direct_url.json"
            )
            direct_url.write_text(
                build_origin.model_dump_json(),
                encoding="utf-8",
            )
            return FlextInfraWorkspaceEnvironmentProvenance.validate_locked(
                workspace,
                metadata_paths=(str(site_packages),),
            )

    @pytest.mark.parametrize(
        ("root_name", "branch"),
        [("candidate one", "integration/alpha"), ("candidate-two", "release/beta")],
    )
    def test_locked_accepts_declared_workspace_gitlink(
        self,
        tmp_path: Path,
        root_name: str,
        branch: str,
    ) -> None:
        """A noneditable local build retains its declared immutable gitlink proof."""
        workspace = self._locked_workspace(tmp_path / root_name)
        u.Tests.git_run(workspace / "sample-member", "checkout", "-b", branch)
        tm.ok(self._locked_verdict(workspace), eq=1)

    @pytest.mark.parametrize("surface", ["direct_url", "pth"])
    def test_locked_rejects_stale_build_identity(
        self,
        tmp_path: Path,
        surface: str,
    ) -> None:
        """The locked-local build retains origin and environment path confinement."""
        workspace = self._locked_workspace(tmp_path)
        stale = tmp_path / "stale"
        stale.mkdir()
        result = self._locked_verdict(
            workspace,
            direct_root=stale if surface == "direct_url" else None,
            source_root=stale if surface == "pth" else None,
        )
        diagnostic = (
            "direct_url mismatch"
            if surface == "direct_url"
            else "CI artifact exposes an external source path"
        )
        tm.that(tm.fail(result), has=diagnostic)

    @pytest.mark.parametrize(
        "defect",
        ["editable", "missing_directory", "vcs", "remote", "relative"],
    )
    def test_locked_rejects_invalid_workspace_build_receipt(
        self,
        tmp_path: Path,
        defect: str,
    ) -> None:
        """A declared member cannot authorize editable or fabricated build metadata."""
        workspace = self._locked_workspace(tmp_path)
        member = workspace / "sample-member"
        identity = tm.ok(
            u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=member)),
        )
        receipt = m.Infra.DirectUrlReceipt(
            url=(
                u.Tests.WorktreeFixture.governed_repository_url("sample-member")
                if defect == "remote"
                else "file:sample-member"
                if defect == "relative"
                else member.as_uri()
            ),
            dir_info=(
                None
                if defect == "missing_directory"
                else m.Infra.DirectUrlDirectoryInfo(editable=defect == "editable")
            ),
            vcs_info=(
                m.Infra.DirectUrlVcsInfo(vcs="git", commit_id=identity.head_oid)
                if defect == "vcs"
                else None
            ),
        )
        result = self._locked_verdict(workspace, receipt=receipt)
        tm.that(
            tm.fail(result),
            has=(
                "CI dependency is editable"
                if defect == "editable"
                else "direct_url mismatch"
            ),
        )

    def test_locked_accepts_declared_noneditable_directory(
        self,
        tmp_path: Path,
    ) -> None:
        """Directory locks require the same declaration and committed Git identity."""
        workspace = self._locked_workspace(tmp_path)
        manifest = tm.ok(u.Infra.load_workspace_manifest(workspace))[0]
        declared = manifest.model_copy(
            update={
                "members": (
                    manifest.members[0].model_copy(update={"editable": False}),
                ),
            },
        )
        tm.ok(
            u.Cli.yaml_dump(
                u.Infra.workspace_manifest_path(workspace),
                declared.model_dump(mode="json"),
            ),
        )
        lock = workspace / "uv.lock"
        lock.write_text(
            lock.read_text(encoding="utf-8").replace("editable =", "directory ="),
            encoding="utf-8",
        )
        u.Tests.commit_git_changes(workspace, "declare noneditable local source")
        tm.ok(self._locked_verdict(workspace), eq=len(declared.members))

    def test_locked_accepts_standalone_root_build(
        self,
        tmp_path: Path,
    ) -> None:
        """A standalone root authenticates its own noneditable build of the checkout."""
        root = tmp_path / "standalone"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "sample-root",
            beads=u.Tests.BeadsIdentity(
                workspace="sample-root-workspace",
                database="sample-root-database",
                issue_prefix="sample-root-prefix",
            ),
        )
        manifest = tm.ok(u.Infra.load_workspace_manifest(root))[0]
        tm.ok(
            u.Cli.yaml_dump(
                u.Infra.workspace_manifest_path(root),
                manifest.model_copy(
                    update={
                        "repository": manifest.repository.model_copy(
                            update={"editable": True},
                        ),
                    },
                ).model_dump(mode="json"),
            ),
        )
        (root / "uv.lock").write_text(
            '[[package]]\nname = "sample-root"\nversion = "1.0"\n'
            'source = { editable = "." }\n',
            encoding="utf-8",
        )
        u.Tests.commit_git_changes(root, "declare standalone root lock")
        with TemporaryDirectory(dir=prefix) as temporary:
            site_packages = Path(temporary) / "site-packages"
            self._installed_editable(
                site_packages,
                "sample-root",
                direct_root=root,
                source_root=Path(prefix),
            )
            (
                site_packages / "sample_root-1.0.dist-info" / "direct_url.json"
            ).write_text(
                m.Infra.DirectUrlReceipt(
                    url=root.as_uri(),
                    dir_info=m.Infra.DirectUrlDirectoryInfo(),
                ).model_dump_json(),
                encoding="utf-8",
            )
            tm.ok(
                FlextInfraWorkspaceEnvironmentProvenance.validate_locked(
                    root,
                    metadata_paths=(str(site_packages),),
                ),
                eq=1,
            )

    @pytest.mark.parametrize(
        ("defect", "diagnostic"),
        [
            ("lock_path", "locked workspace source differs"),
            ("origin", "workspace checkout identity differs"),
            ("dirty", "workspace checkout identity differs"),
            ("head", "workspace checkout differs from locked gitlink"),
            ("gitlink", "governed gitlink is absent"),
            ("staged_gitlink", "workspace checkout differs from locked gitlink"),
            ("checkout", "workspace member has no declared gitlink checkout"),
            ("editable_policy", "locked workspace source differs"),
            ("undeclared", "CI member needs a locked artifact source"),
            ("standalone", "CI member needs a locked artifact source"),
        ],
    )
    def test_locked_rejects_unproven_local_source(
        self,
        tmp_path: Path,
        defect: str,
        diagnostic: str,
    ) -> None:
        """A local source cannot replace declared checkout and revision provenance."""
        workspace = self._locked_workspace(tmp_path)
        member = workspace / "sample-member"
        if defect == "lock_path":
            lock = workspace / "uv.lock"
            lock.write_text(
                lock.read_text(encoding="utf-8").replace(
                    'editable = "sample-member"',
                    'editable = "elsewhere"',
                ),
                encoding="utf-8",
            )
        elif defect == "origin":
            u.Tests.git_run(
                member,
                "remote",
                "set-url",
                "origin",
                u.Tests.WorktreeFixture.governed_repository_url("different-provider"),
            )
        elif defect in {"dirty", "head"}:
            (member / "changed.txt").write_text("changed\n", encoding="utf-8")
            if defect == "head":
                u.Tests.commit_git_changes(member, "advance member without gitlink")
        elif defect == "gitlink":
            u.Tests.git_run(
                workspace,
                "update-index",
                "--force-remove",
                "sample-member",
            )
        elif defect == "staged_gitlink":
            root_identity = tm.ok(
                u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=workspace)),
            )
            tm.ok(
                u.Infra.git_update_index_gitlink(
                    m.Infra.GitUpdateIndexGitlinkRequest(
                        repo_root=workspace,
                        oid=root_identity.head_oid,
                        relative_path="sample-member",
                    ),
                ),
            )
        else:
            manifest = tm.ok(u.Infra.load_workspace_manifest(workspace))[0]
            if defect == "standalone":
                manifest = manifest.model_copy(
                    update={
                        "repository": manifest.repository.model_copy(
                            update={"role": c.Infra.MakeProfile.STANDALONE},
                        ),
                    },
                )
            elif defect in {"checkout", "editable_policy"}:
                manifest = manifest.model_copy(
                    update={
                        "members": (
                            manifest.members[0].model_copy(
                                update=(
                                    {"checkout": c.Infra.CheckoutKind.INDEPENDENT.value}
                                    if defect == "checkout"
                                    else {"editable": False}
                                ),
                            ),
                        ),
                    },
                )
            else:
                manifest = manifest.model_copy(update={"members": ()})
            tm.ok(
                u.Cli.yaml_dump(
                    u.Infra.workspace_manifest_path(workspace),
                    manifest.model_dump(mode="json"),
                ),
            )
        tm.that(tm.fail(self._locked_verdict(workspace)), has=diagnostic)

    @pytest.mark.parametrize(
        "defect",
        ["none", "revision", "remote", "vcs", "editable", "missing"],
    )
    def test_locked_external_git_keeps_exact_revision(
        self,
        tmp_path: Path,
        defect: str,
    ) -> None:
        """An external noneditable provider still requires its locked Git receipt."""
        workspace = self._locked_workspace(tmp_path)
        manifest = tm.ok(u.Infra.load_workspace_manifest(workspace))[0]
        tm.ok(
            u.Cli.yaml_dump(
                u.Infra.workspace_manifest_path(workspace),
                manifest.model_copy(update={"members": ()}).model_dump(mode="json"),
            ),
        )
        identity = tm.ok(
            u.Infra.git_identity(
                m.Infra.GitRepoRequest(repo_root=workspace / "sample-member"),
            ),
        )
        url = u.Tests.WorktreeFixture.governed_repository_url("sample-member")
        (workspace / "uv.lock").write_text(
            '[[package]]\nname = "sample-member"\nversion = "1.0"\n'
            f'source = {{ git = "{url}#{identity.head_oid}" }}\n',
            encoding="utf-8",
        )
        with TemporaryDirectory(dir=prefix) as temporary:
            site_packages = Path(temporary) / "site-packages"
            self._installed_editable(
                site_packages,
                "sample-member",
                direct_root=workspace / "sample-member",
                source_root=Path(prefix),
            )
            receipt = m.Infra.DirectUrlReceipt(
                url=(
                    u.Tests.WorktreeFixture.governed_repository_url(
                        "different-provider",
                    )
                    if defect == "remote"
                    else url
                ),
                dir_info=(
                    m.Infra.DirectUrlDirectoryInfo(editable=True)
                    if defect == "editable"
                    else None
                ),
                vcs_info=m.Infra.DirectUrlVcsInfo(
                    vcs="hg" if defect == "vcs" else "git",
                    commit_id=(
                        "0" * len(identity.head_oid)
                        if defect == "revision"
                        else identity.head_oid
                    ),
                ),
            )
            direct_url = (
                site_packages / "sample_member-1.0.dist-info" / "direct_url.json"
            )
            if defect == "missing":
                direct_url.unlink()
            else:
                direct_url.write_text(
                    dumps(receipt.model_dump(mode="json")),
                    encoding="utf-8",
                )
            result = FlextInfraWorkspaceEnvironmentProvenance.validate_locked(
                workspace,
                metadata_paths=(str(site_packages),),
            )
        if defect == "none":
            tm.ok(result, eq=1)
        else:
            diagnostic = (
                "CI dependency is editable"
                if defect == "editable"
                else "lacks PEP 610 provenance"
                if defect == "missing"
                else "origin differs from committed lock"
            )
            tm.that(tm.fail(result), has=diagnostic)
