"""Public render contract: a packaged data dir ships through exactly one route."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, config, main as infra_main
from tests import t, u

if TYPE_CHECKING:
    from pathlib import Path


FIXTURE_DISTRIBUTION = "flext-packaging-fixture"
FIXTURE_DISTRIBUTION_DATA_DIR = "config"


class TestsFlextInfraCodegenPackagedDataWheel:
    """Rendered wheel and sdist targets never declare one data dir twice."""

    @staticmethod
    def _package_config_path(root: Path) -> Path:
        """Resolve the in-package data dir of the governed fixture project."""
        package_name = u.Tests.project_spec(FIXTURE_DISTRIBUTION).package_name
        return (
            root
            / c.Infra.DEFAULT_SRC_DIR
            / package_name
            / FIXTURE_DISTRIBUTION_DATA_DIR
        )

    @staticmethod
    def _prepare_project(root: Path, *, package_config: bool) -> None:
        """Materialize one governed project, optionally shipping in-package data."""
        _ = u.Tests.standalone_workspace(root, FIXTURE_DISTRIBUTION)
        if package_config:
            tm.ok(
                u.Cli.atomic_write_text_file(
                    TestsFlextInfraCodegenPackagedDataWheel._package_config_path(root)
                    / "meltano.yaml",
                    "value: fixture\n",
                )
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
            f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
            f'dependencies = ["{declared_source}"]\n',
            encoding="utf-8",
        )
        _ = u.Tests.write_standalone_workspace_manifest(root, FIXTURE_DISTRIBUTION)
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
        """Run codegen conform self-apply through the public CLI entrypoint."""
        return infra_main([
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
        """Read the rendered wheel target of the conformed project."""
        manifest = (root / c.PYPROJECT_FILENAME).read_text(encoding="utf-8")
        return u.Tests.toml_table_at(
            manifest, c.Infra.TOOL, "hatch", "build", "targets", "wheel"
        )

    @staticmethod
    def _wheel_force_include(root: Path) -> t.JsonMapping:
        """Read the rendered force-include map, empty when the table is absent."""
        wheel = TestsFlextInfraCodegenPackagedDataWheel._wheel_target(root)
        return (
            u.Tests.toml_mapping(wheel["force-include"])
            if "force-include" in wheel
            else {}
        )

    @staticmethod
    def _sdist_only_include(root: Path) -> t.JsonList:
        """Read the rendered sdist only-include list of the conformed project."""
        manifest = (root / c.PYPROJECT_FILENAME).read_text(encoding="utf-8")
        sdist = u.Tests.toml_table_at(
            manifest, c.Infra.TOOL, "hatch", "build", "targets", "sdist"
        )
        return u.Tests.toml_list(sdist["only-include"])

    @pytest.mark.slow
    def test_root_only_data_dir_stays_force_included(
        self, infra_git_repo: Path
    ) -> None:
        """A root data dir the package does not carry still reaches the wheel."""
        self._prepare_project(infra_git_repo, package_config=False)

        applied = self._conform_self(infra_git_repo)

        tm.that(applied, eq=0)
        package_name = u.Tests.project_spec(FIXTURE_DISTRIBUTION).package_name
        force_include = self._wheel_force_include(infra_git_repo)
        tm.that(
            force_include.get(FIXTURE_DISTRIBUTION_DATA_DIR),
            eq=f"{package_name}/{FIXTURE_DISTRIBUTION_DATA_DIR}",
        )

    @pytest.mark.slow
    def test_in_package_data_dir_is_never_force_included(
        self, infra_git_repo: Path
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
            FIXTURE_DISTRIBUTION_DATA_DIR in self._sdist_only_include(infra_git_repo),
            eq=False,
        )
        # The package copy still ships through the packages entry.
        package_name = u.Tests.project_spec(FIXTURE_DISTRIBUTION).package_name
        wheel = self._wheel_target(infra_git_repo)
        tm.that(
            f"{c.Infra.DEFAULT_SRC_DIR}/{package_name}"
            in u.Tests.toml_list(wheel["packages"]),
            eq=True,
        )
