"""Release workflow fixture test utilities for flext-infra."""

from __future__ import annotations

from pathlib import Path

from flext_infra import config, main, u
from flext_infra.codegen import FlextInfraCodegenConform
from tests import c, m, t
from tests.utilities_fixture_project import TestsFlextInfraUtilitiesProjectFixtureMixin
from tests.utilities_git import TestsFlextInfraUtilitiesGitMixin


class TestsFlextInfraUtilitiesReleaseMixin:
    """Release protocol workspace and report fixture helpers."""

    @staticmethod
    def release_policy_root() -> Path:
        """Return the packaged template root that owns the Gitleaks policy."""
        return (
            Path(__file__).resolve().parents[1]
            / "src"
            / "flext_infra"
            / "templates"
            / "project"
            / "base"
        )

    @staticmethod
    def create_release_workspace(
        root: Path,
        *,
        project_names: t.StrSequence = (),
        version: str = "0.1.0",
        initialize_root_git: bool = True,
        initialize_project_git: bool = False,
    ) -> Path:
        """Create a release workflow workspace fixture.

        ``version`` seeds the root ``pyproject.toml``, the version SSOT the
        release protocol reads and is the only writer of.
        """
        workspace = root / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        TestsFlextInfraUtilitiesProjectFixtureMixin.write_project_beads_config(
            workspace, "workspace"
        )
        source = TestsFlextInfraUtilitiesProjectFixtureMixin.flext_source
        (workspace / "pyproject.toml").write_text(
            (
                "[project]\n"
                'name = "workspace"\n'
                'description = "Release workflow fixture"\n'
                f'version = "{version}"\n'
                'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
                f'dependencies = ["{source("flext-core")}"]\n'
                # The FLEXT line is detected from the declared infrastructure
                # source, never cataloged: a governed checkout declares every
                # internal requirement (the scaffold dev SSOT includes
                # flext-tests) with its own direct Git source.
                "\n[dependency-groups]\n"
                f'dev = ["{source()}", "{source("flext-tests")}"]\n'
            ),
            encoding="utf-8",
        )
        # The integration baseline uses the same ignore contract as its release
        # lane, so local resolver state never becomes an untracked source file.
        gitignore = FlextInfraCodegenConform.render_project_gitignore(
            config.Infra.codegen,
            profile=c.Infra.MakeProfile.STANDALONE,
            project_name=workspace.name,
        ).unwrap()
        (workspace / ".gitignore").write_text(gitignore, encoding="utf-8")
        # Gitleaks is a codegen projection; build constraints render from the
        # typed config SSOT at release time and have no repository projection.
        gitleaks_source = (
            TestsFlextInfraUtilitiesReleaseMixin.release_policy_root()
            / f"{c.Infra.RELEASE_GITLEAKS_CONFIG_PATH}.j2"
        )
        rendered_gitleaks = u.Cli.template_render(gitleaks_source, config.Infra.release)
        if rendered_gitleaks.failure:
            raise RuntimeError(
                rendered_gitleaks.error or "release policy render failed: gitleaks"
            )
        gitleaks_target = workspace / c.Infra.RELEASE_GITLEAKS_CONFIG_PATH
        gitleaks_target.parent.mkdir(parents=True, exist_ok=True)
        gitleaks_target.write_text(rendered_gitleaks.value, encoding="utf-8")
        if not project_names:
            # A standalone FLEXT repository publishes its own Python package;
            # the release stamp's conform guard probes that layout in a fresh
            # interpreter, so the fixture carries the package it releases.
            root_package = workspace / c.Infra.DEFAULT_SRC_DIR / workspace.name
            root_package.mkdir(parents=True, exist_ok=True)
            (root_package / c.Infra.INIT_PY).write_text("", encoding="utf-8")
        for name in project_names:
            project = workspace / name
            project.mkdir(parents=True, exist_ok=True)
            package_name = name.replace("-", "_")
            (project / "pyproject.toml").write_text(
                (
                    "[build-system]\n"
                    'build-backend = "hatchling.build"\n'
                    'requires = ["hatchling"]\n'
                    "\n"
                    "[dependency-groups]\n"
                    'dev = ["flext-tests @ '
                    'git+https://github.com/flext-sh/flext-tests.git@0.12.0-dev"]\n'
                    "\n"
                    "[project]\n"
                    f'name = "{name}"\n'
                    'description = "Release member fixture"\n'
                    'version = "0.1.0"\n'
                    'license = "MIT"\n'
                    'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
                    'dependencies = ["flext-core @ '
                    'git+https://github.com/flext-sh/flext-core.git@0.12.0-dev"]\n'
                    "\n"
                    "[project.optional-dependencies]\n"
                    'dev = ["flext-tests @ '
                    'git+https://github.com/flext-sh/flext-tests.git@0.12.0-dev"]\n'
                    "\n"
                    "[tool.hatch.build.targets.sdist]\n"
                    'include = ["/LICENSE", "/pyproject.toml", "/src"]\n'
                    "\n"
                    "[tool.hatch.build.targets.wheel]\n"
                    f'packages = ["src/{package_name}"]\n'
                    "\n"
                    "[tool.hatch.metadata]\n"
                    "allow-direct-references = true\n"
                ),
                encoding="utf-8",
            )
            (project / "LICENSE").write_text(
                "MIT License\n\nCopyright (c) FLEXT Tests\n", encoding="utf-8"
            )
            src_dir = project / "src" / package_name
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / "__init__.py").write_text("", encoding="utf-8")
            TestsFlextInfraUtilitiesProjectFixtureMixin.write_project_beads_config(
                project, name
            )
        if project_names:
            TestsFlextInfraUtilitiesProjectFixtureMixin.declare_workspace_projects(
                workspace, project_names
            )
        if initialize_root_git:
            TestsFlextInfraUtilitiesGitMixin.initialize_git_repo(workspace)
        else:
            (workspace / ".git").mkdir(exist_ok=True)
        if initialize_project_git:
            for name in project_names:
                TestsFlextInfraUtilitiesGitMixin.initialize_git_repo(workspace / name)
        return workspace

    @staticmethod
    def run_release_main(repository_root: Path, *arguments: str) -> int:
        """Run the public release CLI against one real test workspace."""
        return main([
            "release",
            "run",
            "--repository-root",
            str(repository_root),
            *arguments,
        ])

    @staticmethod
    def run_release_build(
        repository_root: Path, project_name: str, *, dry_run: bool = False
    ) -> int:
        """Run the release build phase for one project through the public CLI."""
        return TestsFlextInfraUtilitiesReleaseMixin.run_release_main(
            repository_root,
            "--phase",
            c.Tests.RELEASE_PHASE_BUILD,
            "--projects",
            project_name,
            "--dry-run" if dry_run else "--apply",
        )

    @staticmethod
    def release_internal_workspace(
        root: Path, project_name: str, *, initialize_project_git: bool = True
    ) -> Path:
        """Create a release workspace carrying one project and its internal deps."""
        return TestsFlextInfraUtilitiesReleaseMixin.create_release_workspace(
            root,
            project_names=(project_name, *c.Tests.RELEASE_INTERNAL_DEPENDENCIES),
            initialize_project_git=initialize_project_git,
        )

    @staticmethod
    def release_build_report(repository_root: Path) -> m.Infra.BuildReport:
        """Read the strict build report the last build phase wrote."""
        report_path = (
            TestsFlextInfraUtilitiesReleaseMixin.release_report_dir(
                repository_root, c.Tests.RELEASE_VERSION_BASE
            )
            / "build-report.json"
        )
        return m.Infra.BuildReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )

    @staticmethod
    def release_build_log_text(repository_root: Path, project_name: str) -> str:
        """Read one release project's build log at the base release version."""
        return TestsFlextInfraUtilitiesReleaseMixin.release_build_log(
            repository_root, c.Tests.RELEASE_VERSION_BASE, project_name
        ).read_text(encoding="utf-8")

    @staticmethod
    def release_report_dir(repository_root: Path, version: str) -> Path:
        """Return the public release report directory for one version."""
        return repository_root / ".reports" / "release" / f"v{version}"

    @staticmethod
    def release_build_log(
        repository_root: Path, version: str, project_name: str
    ) -> Path:
        """Return one release project's observable build log path."""
        return (
            TestsFlextInfraUtilitiesReleaseMixin.release_report_dir(
                repository_root, version
            )
            / f"build-{project_name}.log"
        )

    @staticmethod
    def release_artifact_dir(
        repository_root: Path, version: str, project_name: str
    ) -> Path:
        """Return one release project's immutable artifact-set directory."""
        return (
            TestsFlextInfraUtilitiesReleaseMixin.release_report_dir(
                repository_root, version
            )
            / "artifacts"
            / project_name
        )


__all__: list[str] = ["TestsFlextInfraUtilitiesReleaseMixin"]
