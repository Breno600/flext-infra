"""Public render contract: a packaged data dir ships through exactly one route.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import tarfile
import zipfile
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, config, infra, main
from tests import t, u

if TYPE_CHECKING:
    from pathlib import Path


FIXTURE_DISTRIBUTION = "flext-packaging-fixture"
FIXTURE_DISTRIBUTION_DATA_DIR = "config"


class TestsFlextInfraCodegenPackagedDataWheel:
    """Rendered wheel and sdist targets never declare one data dir twice."""

    @staticmethod
    def _package_config_path(root: Path) -> Path:
        """Resolve the in-package data dir of the governed fixture project.

        Returns:
            The resulting ``Path``.

        """
        package_name = u.Tests.project_spec(FIXTURE_DISTRIBUTION).package_name
        return (
            root
            / c.Infra.DEFAULT_SRC_DIR
            / package_name
            / FIXTURE_DISTRIBUTION_DATA_DIR
        )

    @staticmethod
    def _prepare_project(
        root: Path,
        *,
        package_config: bool,
        packaged_data_paths: tuple[str, ...] = (),
        packaged_data_excludes: tuple[str, ...] = (),
        repository_namespace_packages: tuple[str, ...] = (),
    ) -> None:
        """Materialize one governed project, optionally shipping in-package data."""
        _ = u.Tests.standalone_workspace(root, FIXTURE_DISTRIBUTION)
        if package_config:
            tm.ok(
                u.Cli.atomic_write_text_file(
                    TestsFlextInfraCodegenPackagedDataWheel._package_config_path(root)
                    / "meltano.yaml",
                    "value: fixture\n",
                ),
            )
        # The generator detects the FLEXT line from the checkout's declared
        # infrastructure source; the canonical manifest routes never declare
        # one for a leaf fixture, so the pyproject declares the same typed
        # SSOT distribution the production loader resolves.
        infra_distribution = config.Infra.codegen.infra_repository.distribution
        declared_source = (
            f"{infra_distribution} @ git+{u.Tests.provider().base_url}"
            f"/{infra_distribution}.git@{u.Tests.provider_branch()}"
        )
        (root / c.PYPROJECT_FILENAME).write_text(
            "[project]\n"
            f'name = "{FIXTURE_DISTRIBUTION}"\n'
            'version = "0.1.0"\n'
            'requires-python = "'
            f'{config.Infra.codegen.toolchain.python_required_version}"\n'
            f'dependencies = ["{declared_source}"]\n',
            encoding="utf-8",
        )
        # The existing fixture package ships no cli module, so its manifest
        # declares none and conform renders no console script to load.
        _ = u.Tests.write_standalone_workspace_manifest(
            root,
            FIXTURE_DISTRIBUTION,
            declaration=u.Tests.StandaloneManifestDeclaration(
                cli_module=False,
                packaged_data_paths=packaged_data_paths,
                packaged_data_excludes=packaged_data_excludes,
                repository_namespace_packages=repository_namespace_packages,
            ),
        )
        u.Tests.git_bootstrap(
            root,
            (
                "remote",
                "set-url",
                c.Infra.GIT_ORIGIN,
                u.Tests.repository_ref(FIXTURE_DISTRIBUTION).url,
            ),
        )
        u.Tests.copy_tracked_mise_seeds(root)

    @staticmethod
    def _conform_self(root: Path) -> int:
        """Run codegen conform self-apply through the public CLI entrypoint.

        Returns:
            The resulting ``int``.

        """
        return main([
            c.Infra.CLI_GROUP_CODEGEN,
            "conform",
            "--root",
            str(root),
            "--scope",
            c.Infra.CodegenConformScope.SELF.value,
            "--mode",
            c.Infra.CodegenConformMode.APPLY.value,
        ])

    @staticmethod
    def _wheel_target(root: Path) -> t.JsonMapping:
        """Read the rendered wheel target of the conformed project.

        Returns:
            The resulting ``t.JsonMapping``.

        """
        manifest = (root / c.PYPROJECT_FILENAME).read_text(encoding="utf-8")
        return u.Tests.toml_table_at(
            manifest,
            c.Infra.TOOL,
            "hatch",
            "build",
            "targets",
            "wheel",
        )

    @staticmethod
    def _wheel_force_include(root: Path) -> t.JsonMapping:
        """Read the rendered force-include map, empty when the table is absent.

        Returns:
            The resulting ``t.JsonMapping``.

        """
        wheel = TestsFlextInfraCodegenPackagedDataWheel._wheel_target(root)
        return (
            u.Tests.toml_mapping(wheel["force-include"])
            if "force-include" in wheel
            else {}
        )

    @staticmethod
    def _sdist_include(root: Path) -> t.JsonList:
        """Read the rendered sdist source patterns of the conformed project.

        Returns:
            The resulting ``t.JsonList``.

        """
        manifest = (root / c.PYPROJECT_FILENAME).read_text(encoding="utf-8")
        sdist = u.Tests.toml_table_at(
            manifest,
            c.Infra.TOOL,
            "hatch",
            "build",
            "targets",
            "sdist",
        )
        return u.Tests.toml_list(sdist["include"])

    @staticmethod
    def _sdist_force_include(root: Path) -> t.JsonMapping:
        """Read declared source files retained unchanged by the sdist.

        Returns:
            The resulting ``t.JsonMapping``.

        """
        manifest = (root / c.PYPROJECT_FILENAME).read_text(encoding="utf-8")
        sdist = u.Tests.toml_table_at(
            manifest,
            c.Infra.TOOL,
            "hatch",
            "build",
            "targets",
            "sdist",
        )
        return (
            u.Tests.toml_mapping(sdist["force-include"])
            if "force-include" in sdist
            else {}
        )

    @pytest.mark.slow
    def test_declared_root_data_dir_stays_selected(self, infra_git_repo: Path) -> None:
        """A declared root directory reaches the wheel through native selection."""
        self._prepare_project(
            infra_git_repo,
            package_config=False,
            packaged_data_paths=(FIXTURE_DISTRIBUTION_DATA_DIR,),
        )

        applied = self._conform_self(infra_git_repo)

        tm.that(applied, eq=0)
        package_name = u.Tests.project_spec(FIXTURE_DISTRIBUTION).package_name
        sources = u.Tests.toml_mapping(self._wheel_target(infra_git_repo)["sources"])
        tm.that(
            sources.get(FIXTURE_DISTRIBUTION_DATA_DIR),
            eq=f"{package_name}/{FIXTURE_DISTRIBUTION_DATA_DIR}",
        )

    @pytest.mark.slow
    def test_undeclared_governance_config_stays_out_of_archives(
        self,
        infra_git_repo: Path,
    ) -> None:
        """A governance config directory is not implicitly package data."""
        self._prepare_project(infra_git_repo, package_config=False)

        tm.that(self._conform_self(infra_git_repo), eq=0)

        tm.that(
            FIXTURE_DISTRIBUTION_DATA_DIR in self._wheel_force_include(infra_git_repo),
            eq=False,
        )
        tm.that(
            f"/{FIXTURE_DISTRIBUTION_DATA_DIR}/**"
            in self._sdist_include(infra_git_repo),
            eq=False,
        )

    @pytest.mark.slow
    def test_existing_infrastructure_dir_reaches_both_archives(
        self,
        infra_git_repo: Path,
    ) -> None:
        """A project-owned IaC directory ships without a generator template row."""
        self._prepare_project(
            infra_git_repo,
            package_config=False,
            packaged_data_paths=("infra",),
        )
        infrastructure = infra_git_repo / "infra" / "ansible" / "site.yml"
        tm.ok(u.Cli.atomic_write_text_file(infrastructure, "---\n- hosts: all\n"))

        tm.that(self._conform_self(infra_git_repo), eq=0)

        package_name = u.Tests.project_spec(FIXTURE_DISTRIBUTION).package_name
        tm.that(
            u.Tests.toml_mapping(self._wheel_target(infra_git_repo)["sources"]).get(
                "infra",
            ),
            eq=f"{package_name}/infra",
        )
        tm.that("/infra/**" in self._sdist_include(infra_git_repo), eq=True)

    @pytest.mark.slow
    def test_repository_namespace_retains_its_import_path(
        self,
        infra_git_repo: Path,
    ) -> None:
        """A declared root namespace ships at the same import path in both formats."""
        self._prepare_project(
            infra_git_repo,
            package_config=False,
            repository_namespace_packages=("infra",),
        )
        source = infra_git_repo / "infra" / "pulumi" / "__main__.py"
        tm.ok(u.Cli.atomic_write_text_file(source, "VALUE = 'fixture'\n"))

        tm.that(self._conform_self(infra_git_repo), eq=0)

        wheel = self._wheel_target(infra_git_repo)
        tm.that("/infra/**" in u.Tests.toml_list(wheel["include"]), eq=True)
        tm.that(u.Tests.toml_mapping(wheel["sources"]).get("infra"), eq="infra")
        tm.that("/infra/**" in self._sdist_include(infra_git_repo), eq=True)
        output = infra_git_repo.parent / "namespace-artifacts"
        wheel_dir = output / "wheel"
        sdist_dir = output / "sdist"
        tm.ok(
            u.Cli.run_checked(
                ["uv", "build", "--wheel", "--out-dir", str(wheel_dir)],
                cwd=infra_git_repo,
            ),
        )
        tm.ok(
            u.Cli.run_checked(
                ["uv", "build", "--sdist", "--out-dir", str(sdist_dir)],
                cwd=infra_git_repo,
            ),
        )
        with zipfile.ZipFile(next(wheel_dir.glob("*.whl"))) as archive:
            tm.that(archive.read("infra/pulumi/__main__.py"), eq=source.read_bytes())
        with tarfile.open(next(sdist_dir.glob("*.tar.gz"))) as archive:
            member = next(
                item
                for item in archive.getmembers()
                if item.name.endswith("/infra/pulumi/__main__.py")
            )
            stream = archive.extractfile(member)
            assert stream is not None
            with stream:
                tm.that(stream.read(), eq=source.read_bytes())

    @pytest.mark.slow
    def test_undeclared_infrastructure_dir_stays_out_of_archives(
        self,
        infra_git_repo: Path,
    ) -> None:
        """An unrelated root directory cannot enter a package by discovery."""
        self._prepare_project(infra_git_repo, package_config=False)
        infrastructure = infra_git_repo / "infra" / "ansible" / "site.yml"
        tm.ok(u.Cli.atomic_write_text_file(infrastructure, "---\n- hosts: all\n"))

        tm.that(self._conform_self(infra_git_repo), eq=0)

        tm.that("infra" in self._wheel_force_include(infra_git_repo), eq=False)
        tm.that("/infra/**" in self._sdist_include(infra_git_repo), eq=False)

    @pytest.mark.slow
    def test_in_package_data_dir_is_never_force_included(
        self,
        infra_git_repo: Path,
    ) -> None:
        """A data dir already shipped by the package is never force-included again.

        Force-including the root copy maps it onto the same wheel path the
        package entry already archives, and hatchling rejects the duplicate
        with ``ValueError`` at build time.
        """
        self._prepare_project(infra_git_repo, package_config=True)
        tm.that(self._package_config_path(infra_git_repo).is_dir(), eq=True)

        applied = self._conform_self(infra_git_repo)

        tm.that(applied, eq=0)
        force_include = self._wheel_force_include(infra_git_repo)
        tm.that(FIXTURE_DISTRIBUTION_DATA_DIR in force_include, eq=False)
        tm.that(
            f"/{FIXTURE_DISTRIBUTION_DATA_DIR}/**"
            in self._sdist_include(infra_git_repo),
            eq=False,
        )
        # The package copy still ships through the packages entry.
        package_name = u.Tests.project_spec(FIXTURE_DISTRIBUTION).package_name
        wheel = self._wheel_target(infra_git_repo)
        tm.that(
            f"/{c.Infra.DEFAULT_SRC_DIR}/{package_name}/**"
            in u.Tests.toml_list(wheel["include"]),
            eq=True,
        )

    @pytest.mark.slow
    def test_declared_file_keeps_sibling_governance_out(
        self,
        infra_git_repo: Path,
    ) -> None:
        """One catalog file ships without its governance siblings."""
        catalog = "config/deployment.yaml"
        self._prepare_project(
            infra_git_repo,
            package_config=False,
            packaged_data_paths=(catalog,),
        )
        tm.ok(u.Cli.atomic_write_text_file(infra_git_repo / catalog, "profiles: {}\n"))
        tm.that(self._conform_self(infra_git_repo), eq=0)
        package_name = u.Tests.project_spec(FIXTURE_DISTRIBUTION).package_name
        tm.that(
            self._wheel_force_include(infra_git_repo),
            eq={catalog: f"{package_name}/{catalog}"},
        )
        # A declared data file ships through the sdist force-include, never
        # by widening the source include to its whole directory.
        tm.that(
            self._sdist_force_include(infra_git_repo).get(catalog),
            eq=catalog,
        )
        tm.that("/config/**" in self._sdist_include(infra_git_repo), eq=False)

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "declarations",
        [
            ("../outside",),
            ("/absolute",),
            ("config", "config"),
            ("config", "config/workspace.yaml"),
        ],
    )
    def test_invalid_declaration_fails_before_effects(
        self,
        infra_git_repo: Path,
        declarations: tuple[str, ...],
    ) -> None:
        """Escaping and overlapping archive inputs cannot mutate the manifest."""
        self._prepare_project(
            infra_git_repo,
            package_config=False,
            packaged_data_paths=declarations,
        )
        before = (infra_git_repo / c.PYPROJECT_FILENAME).read_bytes()
        with pytest.raises(ValueError, match="packaged data"):
            self._conform_self(infra_git_repo)
        tm.that((infra_git_repo / c.PYPROJECT_FILENAME).read_bytes(), eq=before)

    @pytest.mark.slow
    def test_missing_data_fails_before_effects(self, infra_git_repo: Path) -> None:
        """A missing declared file cannot silently disappear from distributions."""
        self._prepare_project(
            infra_git_repo,
            package_config=False,
            packaged_data_paths=("absent/catalog.yaml",),
        )
        before = (infra_git_repo / c.PYPROJECT_FILENAME).read_bytes()
        with pytest.raises(FileNotFoundError, match="packaged data"):
            self._conform_self(infra_git_repo)
        tm.that((infra_git_repo / c.PYPROJECT_FILENAME).read_bytes(), eq=before)

    @pytest.mark.slow
    def test_declared_collision_fails_before_effects(
        self,
        infra_git_repo: Path,
    ) -> None:
        """Distinct roots cannot claim the same wheel destination."""
        self._prepare_project(
            infra_git_repo,
            package_config=True,
            packaged_data_paths=("config",),
        )
        before = (infra_git_repo / c.PYPROJECT_FILENAME).read_bytes()
        with pytest.raises(ValueError, match="collides"):
            self._conform_self(infra_git_repo)
        tm.that((infra_git_repo / c.PYPROJECT_FILENAME).read_bytes(), eq=before)

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "link_kind",
        ["external", "transitive", "cycle", "dangling"],
    )
    def test_data_links_are_validated_transitively(
        self,
        infra_git_repo: Path,
        link_kind: str,
    ) -> None:
        """Hatch cannot traverse a link the preflight has not authenticated."""
        self._prepare_project(
            infra_git_repo,
            package_config=False,
            packaged_data_paths=("infra",),
        )
        data = infra_git_repo / "infra"
        data.mkdir()
        external = infra_git_repo.parent / "outside-data"
        external.write_text("outside", encoding="utf-8")
        if link_kind == "transitive":
            shared = infra_git_repo / "shared"
            shared.mkdir()
            (shared / "external").symlink_to(external)
            (data / "shared").symlink_to(shared, target_is_directory=True)
        elif link_kind == "cycle":
            (data / "cycle").symlink_to(data, target_is_directory=True)
        elif link_kind == "dangling":
            (data / "missing").symlink_to(infra_git_repo / "absent")
        else:
            (data / "external").symlink_to(external)
        before = (infra_git_repo / c.PYPROJECT_FILENAME).read_bytes()
        with pytest.raises((ValueError, FileNotFoundError)):
            self._conform_self(infra_git_repo)
        tm.that((infra_git_repo / c.PYPROJECT_FILENAME).read_bytes(), eq=before)

    @pytest.mark.slow
    def test_real_archives_preserve_data_selection(self, infra_git_repo: Path) -> None:
        """Direct wheel, sdist and rebuilt wheel carry the same selected bytes."""
        catalog = "config/deployment.yaml"
        asset = "infra/ansible/site.yml"
        self._prepare_project(
            infra_git_repo,
            package_config=False,
            packaged_data_paths=(catalog, "infra"),
        )
        tm.ok(u.Cli.atomic_write_text_file(infra_git_repo / catalog, "profiles: {}\n"))
        tm.ok(
            u.Cli.atomic_write_text_file(infra_git_repo / asset, "---\n- hosts: all\n"),
        )
        tm.that(self._conform_self(infra_git_repo), eq=0)
        ignored = "infra/state.json"
        self._prepare_project(
            infra_git_repo,
            package_config=False,
            packaged_data_paths=(catalog, "infra"),
            packaged_data_excludes=(ignored,),
        )
        tm.ok(u.Cli.atomic_write_text_file(infra_git_repo / catalog, "profiles: {}\n"))
        tm.ok(
            u.Cli.atomic_write_text_file(infra_git_repo / asset, "---\n- hosts: all\n"),
        )
        tm.ok(u.Cli.atomic_write_text_file(infra_git_repo / ignored, "private state\n"))
        tm.that(self._conform_self(infra_git_repo), eq=0)
        with (infra_git_repo / ".gitignore").open("a", encoding="utf-8") as stream:
            stream.write(f"\n/{ignored}\n/{catalog}\n")
        output = infra_git_repo.parent / "artifacts"
        direct = output / "direct"
        source = output / "source"
        rebuilt = output / "rebuilt"
        tm.ok(
            u.Cli.run_checked(
                ["uv", "build", "--wheel", "--out-dir", str(direct)],
                cwd=infra_git_repo,
            ),
        )
        tm.ok(
            u.Cli.run_checked(
                ["uv", "build", "--sdist", "--out-dir", str(source)],
                cwd=infra_git_repo,
            ),
        )
        sdist = next(source.glob("*.tar.gz"))
        tm.ok(
            u.Cli.run_checked(
                ["uv", "build", str(sdist), "--wheel", "--out-dir", str(rebuilt)],
                cwd=infra_git_repo,
            ),
        )
        package_name = u.Tests.project_spec(FIXTURE_DISTRIBUTION).package_name
        expected = {
            catalog: (infra_git_repo / catalog).read_bytes(),
            asset: (infra_git_repo / asset).read_bytes(),
        }
        for directory in (direct, rebuilt):
            with zipfile.ZipFile(next(directory.glob("*.whl"))) as archive:
                for name, content in expected.items():
                    tm.that(archive.read(f"{package_name}/{name}"), eq=content)
                tm.that(f"{package_name}/{ignored}" in archive.namelist(), eq=False)
                tm.that(
                    f"{package_name}/config/workspace.yaml" in archive.namelist(),
                    eq=False,
                )
        with tarfile.open(sdist) as archive:
            members = {
                member.name.partition("/")[2]: member
                for member in archive.getmembers()
                if member.isfile()
            }
            for name, content in expected.items():
                stream = archive.extractfile(members[name])
                assert stream is not None
                with stream:
                    tm.that(stream.read(), eq=content)
            tm.that(ignored in members, eq=False)
            tm.that("config/workspace.yaml" in members, eq=False)

    @pytest.mark.slow
    def test_scaffold_validates_data_against_planned_files(
        self,
        tmp_path: Path,
    ) -> None:
        """A declared generated manifest is accepted before scaffold effects."""
        root = tmp_path / "scaffold-data"
        u.Tests.seed_locked_taplo(tmp_path)
        repository = u.Tests.repository_ref(
            "scaffold-data",
            role=c.Infra.MakeProfile.STANDALONE,
        )
        project = u.Tests.project_spec(repository.name).model_copy(
            update={"packaged_data_paths": ("config/workspace.yaml",)},
        )
        workspace = u.Tests.workspace_spec(repository, project=project)
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
        )
        tm.that(root.exists(), eq=False)
        tm.ok(infra.codegen_conform(request, workspace))
        tm.that((root / "config/workspace.yaml").is_file(), eq=True)
        tm.that(
            self._wheel_force_include(root).get("config/workspace.yaml"),
            eq=f"{project.package_name}/config/workspace.yaml",
        )
