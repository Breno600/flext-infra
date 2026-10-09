"""Workspace and project-layout fixture test utilities for flext-infra.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from flext_tests import tm

from flext_infra import config, infra, u
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_infra.worktree import FlextInfraWorktreeService
from tests import c, m, t
from tests.utilities_codegen import TestsFlextInfraUtilitiesCodegenMixin
from tests.utilities_fixture_project import TestsFlextInfraUtilitiesProjectFixtureMixin
from tests.utilities_fixture_tooling import TestsFlextInfraUtilitiesToolingFixtureMixin
from tests.utilities_git import TestsFlextInfraUtilitiesGitMixin


class TestsFlextInfraUtilitiesWorkspaceFixtureMixin:
    """Typed workspace and project-layout fixture helpers."""

    @staticmethod
    def mk_project(
        root: Path,
        name: str,
        *,
        pyproject: str = "[tool]\n",
        with_src: bool = False,
        with_git: bool = False,
    ) -> Path:
        """Provide the typed test helper `mk_project`.

        Returns:
            The resulting ``Path``.

        """
        project_dir = root / name
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        if with_src:
            package_dir = project_dir / "src" / name.replace("-", "_")
            package_dir.mkdir(parents=True, exist_ok=True)
            # FLEXT: with_src means a discoverable package, not an empty marker.
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
        if with_git:
            (project_dir / ".git").mkdir(exist_ok=True)
        TestsFlextInfraUtilitiesProjectFixtureMixin.write_project_beads_config(
            project_dir,
            name,
        )
        return project_dir

    @staticmethod
    def demo_project(root: Path, *, name: str = "demo-project") -> t.Pair[Path, Path]:
        """Create one minimal buildable project; return its root and package dir.

        Returns:
            The resulting ``t.Pair[Path, Path]``.

        """
        project = root / name
        package_dir = project / "src" / name.replace("-", "_")
        package_dir.mkdir(parents=True)
        (project / "pyproject.toml").write_text(
            f"[project]\nname='{name}'\n",
            encoding="utf-8",
        )
        (project / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        return project, package_dir

    @staticmethod
    def src_package(project_dir: Path, package_name: str, *, pyproject: str) -> Path:
        """Create one ``src``-layout package plus its ``pyproject.toml``.

        The distribution name a scan resolves is part of the fixture's
        contract, so ``pyproject`` is declared by the caller and never
        derived from the directory name.

        Returns:
            The resulting ``Path``.

        """
        package_dir = project_dir / "src" / package_name
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (project_dir / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        return package_dir

    @staticmethod
    def namespace_workspace(
        tmp_path: Path,
        *,
        project_name: str = "sample-proj",
        package_name: str = "sample_pkg",
        pyproject: str = "[project]\nname='sample'\n",
        declare: bool = True,
    ) -> t.Triple[Path, Path, Path]:
        """Materialize the workspace tree the namespace enforcer scans.

        Returns ``(workspace, project, package)``. ``declare`` writes the
        governed ``.gitmodules`` row; a scan that must observe an undeclared
        project sets it to ``False``.

        Returns:
            The resulting ``t.Triple[Path, Path, Path]``.

        """
        workspace = tmp_path / "workspace"
        project = workspace / project_name
        package = TestsFlextInfraUtilitiesWorkspaceFixtureMixin.src_package(
            project,
            package_name,
            pyproject=pyproject,
        )
        (project / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
        if declare:
            TestsFlextInfraUtilitiesProjectFixtureMixin.declare_workspace_projects(
                workspace,
                (project_name,),
            )
        return workspace, project, package

    @staticmethod
    def write_standalone_workspace_manifest(
        project_dir: Path,
        name: str,
        *,
        upstream: str | None = None,
        inherited_facets: t.StrSequence = (),
        root_modules: t.StrSequence = (),
        root_packages: t.StrSequence = (),
        repository_namespace_packages: t.StrSequence = (),
        packaged_data_paths: t.StrSequence = (),
        packaged_data_excludes: t.StrSequence = (),
        extra_verbs: t.VariadicTuple[m.Infra.MakeVerbSpec] = (),
        gascity_enabled: bool | None = None,
        role: c.Infra.MakeProfile = c.Infra.MakeProfile.STANDALONE,
        cli_module: bool | None = None,
    ) -> Path:
        """Write the declared ``config/workspace.yaml`` of one standalone repository.

        The Makefile projection reads declarations only, so this fixture is
        the complete topology input for ``codegen conform --what makefile
        --scope self``. Every value is derived from the same typed SSOT the
        production loader validates against, never frozen by hand.

        ``extra_verbs`` declares the repository-owned public Make verbs the
        managed Makefile renders into its help block, so a caller controls
        real rendered content through the declaration the loader validates.

        ``cli_module`` declares whether an existing package ships its cli entry
        module; ``None`` keeps the project model's own default.

        ``gascity_enabled`` declares the Gas City participation of a repository
        that participates in Beads; ``None`` writes no overlay at all (the fleet
        default). An overlay states every participation explicitly: its Beads
        default is off, and Gas City requires Beads.

        Returns:
            The resulting ``Path``.

        """
        repository = TestsFlextInfraUtilitiesProjectFixtureMixin.repository_ref(
            name,
            role=role,
        )
        if extra_verbs:
            repository = repository.model_copy(update={"extra_verbs": extra_verbs})
        project = TestsFlextInfraUtilitiesProjectFixtureMixin.project_spec(name)
        if upstream is not None:
            project = project.model_copy(update={"upstream": upstream})
        if inherited_facets:
            project = project.model_copy(
                update={"inherited_facets": tuple(inherited_facets)},
            )
        if cli_module is not None:
            project = project.model_copy(update={"cli_module": cli_module})
        if root_modules or root_packages:
            project = project.model_copy(
                update={
                    "root_modules": tuple(root_modules),
                    "root_packages": tuple(root_packages),
                },
            )
        if repository_namespace_packages:
            project = project.model_copy(
                update={
                    "repository_namespace_packages": tuple(
                        repository_namespace_packages,
                    ),
                },
            )
        if packaged_data_paths:
            project = project.model_copy(
                update={"packaged_data_paths": tuple(packaged_data_paths)},
            )
        if packaged_data_excludes:
            project = project.model_copy(
                update={"packaged_data_excludes": tuple(packaged_data_excludes)},
            )
        manifest = m.Infra.WorkspaceManifestSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=name,
            repository=repository,
            project=project,
        )
        if gascity_enabled is not None:
            manifest = manifest.model_copy(
                update={
                    "repository_policy_overlays": (
                        m.Infra.RepositoryPolicyOverlaySpec(
                            project=name,
                            beads_enabled=True,
                            gascity_enabled=gascity_enabled,
                        ),
                    ),
                },
            )
        config_dir = project_dir / c.CONFIG_DIR_NAME
        config_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = config_dir / c.Infra.WORKSPACE_MANIFEST_FILENAME
        tm.ok(u.Cli.yaml_dump(manifest_path, manifest.model_dump(mode="json")))
        return manifest_path

    @staticmethod
    def declared_requirements(distribution: str) -> t.StrSequence:
        """Declare the governed tooling suppliers a fixture project depends on.

        The set derives from the scaffold dev group and the declared infra
        repository, each pinned to its fixture provider URL and line; the
        project itself is never its own supplier.

        Returns:
            The resulting ``t.StrSequence``.

        """
        fixture = TestsFlextInfraUtilitiesProjectFixtureMixin
        names = {
            config.Infra.codegen.infra_repository.distribution,
            *(
                name
                for requirement in config.Infra.codegen.scaffold.project.dev
                if (name := u.Infra.dep_name(requirement)) is not None
                and name.startswith("flext-")
            ),
        } - {distribution}
        return tuple(
            f"{name} @ git+{fixture.repository_ref(name).url}@"
            f"{fixture.provider_branch()}"
            for name in sorted(names)
        )

    @staticmethod
    def standalone_workspace(
        project_dir: Path,
        name: str = "flext-demo",
    ) -> m.Infra.WorkspaceSpec:
        """Materialize and load the canonical minimal standalone fixture.

        Returns:
            The resulting ``m.Infra.WorkspaceSpec``.

        """
        fixture = TestsFlextInfraUtilitiesWorkspaceFixtureMixin
        dev = ", ".join(f'"{item}"' for item in fixture.declared_requirements(name))
        # The governed notice names the manifest's first author, so the
        # minimal project declares the fixture's own scaffold identity.
        spec = TestsFlextInfraUtilitiesProjectFixtureMixin.project_spec(name)
        python_required = config.Infra.codegen.toolchain.python_required_version
        upstream_source = TestsFlextInfraUtilitiesProjectFixtureMixin.flext_source(
            spec.upstream,
        )
        package_root = project_dir / "src" / name.replace("-", "_")
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text("", encoding="utf-8")
        (project_dir / "pyproject.toml").write_text(
            "[project]\n"
            f'name = "{name}"\n'
            f'authors = [{{name = "{TestsFlextInfraUtilitiesProjectFixtureMixin.project_spec(name).author_name}", email = "{TestsFlextInfraUtilitiesProjectFixtureMixin.project_spec(name).author_email}"}}]\n'
            'version = "0.1.0"\n'
            f'authors = [{{name = "{spec.author_name}", '
            f'email = "{spec.author_email}"}}]\n'
            f'requires-python = "{python_required}"\n'
            f'dependencies = ["{upstream_source}"]\n'
            "[dependency-groups]\n"
            f"dev = [{dev}]\n",
            encoding="utf-8",
        )
        TestsFlextInfraUtilitiesProjectFixtureMixin.write_project_beads_config(
            project_dir,
            name,
        )
        # Provider identity is declared, never a checkout path: the governed
        # HTTPS URL is the origin the manifest carries, so the workspace the
        # detector loads satisfies the canonical-HTTPS provider gate (a bare
        # ``str(root)`` origin reads as a path, not an identity).
        TestsFlextInfraUtilitiesGitMixin.initialize_git_repo(
            project_dir,
            origin_url=(
                f"{TestsFlextInfraUtilitiesProjectFixtureMixin.provider().base_url.rstrip('/')}/"
                f"{name}.git"
            ),
        )
        origin = tm.ok(
            u.Infra.git_remote_url(
                m.Infra.GitRemoteUrlRequest(
                    repo_root=project_dir,
                    remote=c.Infra.GIT_ORIGIN,
                ),
            ),
        )
        TestsFlextInfraUtilitiesProjectFixtureMixin.write_workspace_manifest(
            project_dir,
            name,
            url=origin.text.strip(),
        )
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(project_dir))
        return workspace.model_copy(
            update={
                "project": TestsFlextInfraUtilitiesProjectFixtureMixin.project_spec(
                    name,
                ),
            },
        )

    @staticmethod
    def required_beads(workspace: m.Infra.WorkspaceSpec) -> m.Infra.BeadsProjectSpec:
        """Return the ledger identity the observed loader must always resolve.

        Callers use this only for fixtures that explicitly enable Beads.

        Returns:
            The ledger identity the observed loader must always resolve.

        Raises:
            ValueError: If test fixture requires Beads participation.

        """
        if workspace.beads is None:
            msg = "test fixture requires Beads participation"
            raise ValueError(msg)
        return workspace.beads

    @staticmethod
    def to_pascal(snake: str) -> str:
        """Convert a snake-case fixture name to PascalCase.

        Returns:
            The resulting ``str``.

        """
        return "".join(part.title() for part in snake.split("_"))

    @staticmethod
    def src_module_files() -> t.StrSequence:
        """Return canonical FLEXT source-facade filenames.

        Returns:
            Canonical FLEXT source-facade filenames.

        """
        return (
            "constants.py",
            "typings.py",
            "protocols.py",
            "models.py",
            "utilities.py",
        )

    @staticmethod
    def create_codegen_project(
        *,
        tmp_path: Path,
        name: str,
        pkg_name: str,
        files: t.StrMapping,
    ) -> Path:
        """Provide the typed test helper `create_codegen_project`.

        Returns:
            The resulting ``Path``.

        """
        project = tmp_path / name
        project.mkdir()
        (project / "Makefile").touch()
        (project / "pyproject.toml").write_text(
            (
                f"[project]\nname='{name}'\nversion='0.1.0'\n"
                'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
                "dependencies=['flext-core>=0.1.0']\n"
            ),
            encoding="utf-8",
        )
        TestsFlextInfraUtilitiesProjectFixtureMixin.write_project_beads_config(
            project,
            name,
        )
        pkg = project / "src" / pkg_name
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        pascal_name = TestsFlextInfraUtilitiesWorkspaceFixtureMixin.to_pascal(pkg_name)
        (pkg / "typings.py").write_text(
            "from __future__ import annotations\n\n"
            "from flext_core import FlextTypes\n\n"
            f"class {pascal_name}Types(FlextTypes):\n    pass\n\n"
            f"t = {pascal_name}Types\n\n"
            f'__all__: list[str] = ["{pascal_name}Types", "t"]\n',
            encoding="utf-8",
        )
        (pkg / "constants.py").write_text(
            "from __future__ import annotations\n\n"
            "from flext_core import FlextConstants\n\n"
            f"class {pascal_name}Constants(FlextConstants):\n    pass\n\n"
            f"c = {pascal_name}Constants\n\n"
            f'__all__: list[str] = ["{pascal_name}Constants", "c"]\n',
            encoding="utf-8",
        )
        for filename, content in files.items():
            (pkg / filename).write_text(content, encoding="utf-8")
        TestsFlextInfraUtilitiesGitMixin.initialize_git_repo(project)
        return project

    @staticmethod
    def create_scaffolder_test_project(
        *,
        tmp_path: Path,
        with_all_modules: bool,
    ) -> Path:
        """Create a project fixture for scaffolder tests.

        Returns:
            The resulting ``Path``.

        """
        project = tmp_path / "test-project"
        project.mkdir()
        (project / "Makefile").touch()
        (project / "pyproject.toml").write_text(
            ("[project]\nname='test-project'\ndependencies=['flext-core>=0.1.0']\n"),
            encoding="utf-8",
        )
        (project / ".git").mkdir()
        TestsFlextInfraUtilitiesProjectFixtureMixin.write_project_beads_config(
            project,
            "test-project",
        )
        pkg = project / "src" / "test_project"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").touch()
        if with_all_modules:
            for mod in TestsFlextInfraUtilitiesWorkspaceFixtureMixin.src_module_files():
                (pkg / mod).write_text(
                    f"class TestProject{mod.split('.')[0].title()}:\n    pass\n",
                    encoding="utf-8",
                )
        return project

    class WorktreeFixture:
        """Provide one repository and lane-path contract without collecting tests."""

        @staticmethod
        def add_worktree(repository: Path, branch: str, *, base: str = "HEAD") -> str:
            """Create one applied worktree and return Git's canonical lane path.

            Returns:
                The resulting ``str``.

            """
            return tm.ok(
                FlextInfraWorktreeService(
                    repository_root=repository,
                    operation=c.Infra.WorktreeOperation.ADD,
                    branch=branch,
                    base=base,
                    apply_changes=True,
                ).execute(),
            )

        @staticmethod
        def override_repository_manifest(
            repository: Path,
            updates: Mapping[str, t.JsonValue],
        ) -> m.Infra.RepositoryRef:
            """Re-select the observed repository, apply overrides, rewrite its manifest.

            Returns:
                The resulting ``m.Infra.RepositoryRef``.

            """
            observed = tm.ok(
                FlextInfraWorkspaceDetector.load_workspace_spec(repository),
            )
            declared = observed.repository.model_copy(update=dict(updates))
            tm.ok(
                u.Cli.yaml_dump(
                    repository / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME,
                    {
                        "version": 3,
                        "name": declared.name,
                        "repository": declared.model_dump(mode="json"),
                    },
                ),
            )
            return declared

        @classmethod
        def attach_member_child(cls, root: Path) -> Path:
            """Initialize the standard child member and link it to the root ledger.

            Returns:
                The resulting ``Path``.

            """
            child = root / "fixture-child"
            cls.initialize_governed_project(
                child,
                "fixture-child",
                workspace="fixture-child",
                database="fixture_child",
                issue_prefix="fixture-child",
                beads_owner=False,
            )
            cls.link_member_beads(
                child,
                root,
                workspace_name="fixture-workspace",
                database="fixture_workspace",
                issue_prefix="fixture-workspace",
            )
            return child

        @staticmethod
        def _lane(primary_root: Path, outermost_project: Path, branch: str) -> Path:
            """Resolve the lane through the production topology owner.

            Returns:
                The resulting ``Path``.

            """
            _ = outermost_project
            return tm.ok(
                FlextInfraWorktreeService.canonical_lane_path(primary_root, branch),
            )

        @staticmethod
        def _repository(tmp_path: Path) -> Path:
            repository = tmp_path / "repository"
            repository.mkdir()
            (repository / "README.md").write_text("fixture\n", encoding="utf-8")
            (repository / "pyproject.toml").write_text(
                '[project]\nname = "fixture"\nversion = "0.1.0"\n'
                'description = "A standard PEP 621 description string"\n',
                encoding="utf-8",
            )
            (repository / "Makefile").write_text(
                ".PHONY: setup\n"
                "setup:\n"
                '\t@test "$(WORKSPACE)" = "$(CURDIR)"\n'
                '\t@grep -q "^\\[project\\]" "$(WORKSPACE)/pyproject.toml"\n'
                '\t@printf "setting up %s\\n" "$(WORKSPACE)"\n',
                encoding="utf-8",
            )
            TestsFlextInfraUtilitiesGitMixin.initialize_git_repo(repository)
            return repository

        @staticmethod
        def _commit_fixture(repository: Path, message: str) -> None:
            """Commit one deliberate fixture mutation."""
            tm.ok(
                u.Cli.run_checked(
                    [c.Infra.GIT, "add", "Makefile", "pyproject.toml"],
                    cwd=repository,
                ),
            )
            tm.ok(
                u.Cli.run_checked(
                    [c.Infra.GIT, "commit", "-m", message],
                    cwd=repository,
                ),
            )

        @classmethod
        def conformed_root(cls, tmp_path: Path) -> Path:
            """Materialize one governed project and conform it to a fixed point.

            Returns:
                The resulting ``Path``.

            """
            root = tmp_path / "repo"
            cls.initialize_governed_project(
                root,
                "fixture-project",
                workspace="fixture-workspace",
                database="fixture-database",
                issue_prefix="fixture-prefix",
            )
            TestsFlextInfraUtilitiesGitMixin.commit_git_changes(
                root,
                "Declare project identity",
            )
            tm.ok(
                infra.codegen_conform(
                    TestsFlextInfraUtilitiesCodegenMixin.conform_request(
                        root,
                        scope=c.Infra.CodegenConformScope.SELF,
                        mode=c.Infra.CodegenConformMode.APPLY,
                    ),
                ),
            )
            return root

        @classmethod
        def write_python_project(cls, root: Path, distribution: str) -> Path:
            """Write the minimum typed project used by real Git fixtures.

            The internal dependency declares its own direct Git source: the
            requirement line is the authority conform canonicalizes, and a
            source-less internal dependency fails loudly.

            Returns:
                The resulting ``Path``.

            """
            root.mkdir(parents=True, exist_ok=True)
            pyproject = root / "pyproject.toml"
            repository_url = cls.governed_repository_url(distribution)
            provider = TestsFlextInfraUtilitiesProjectFixtureMixin.provider()
            internal_source = (
                f"git+{provider.base_url.rstrip('/')}/flext-core.git@"
                f"{TestsFlextInfraUtilitiesProjectFixtureMixin.provider_branch()}"
            )
            workspace_fixture = TestsFlextInfraUtilitiesWorkspaceFixtureMixin
            tooling_requirements = ", ".join(
                f'"{item}"'
                for item in workspace_fixture.declared_requirements(distribution)
            )
            tooling = f"\n[dependency-groups]\ndev = [{tooling_requirements}]\n"
            # A governed project always declares its description: the derived
            # render identity reads it and rejects an empty one, exactly as it
            # does for a real checkout.
            # Why: conform's existing-checkout ProjectSpec now derives authors and
            # upstream from live PEP 621 metadata (no fabricated spec) — every
            # governed fixture must declare both.
            python_required = config.Infra.codegen.toolchain.python_required_version
            pyproject.write_text(
                f'[project]\nname = "{distribution}"\nversion = "0.12.0.dev0"\n'
                f'description = "{distribution} governed fixture"\n'
                f'requires-python = "{python_required}"\n'
                'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
                f'dependencies = ["flext-core @ {internal_source}"]\n'
                f'[project.urls]\nRepository = "{repository_url}"\n{tooling}',
                encoding="utf-8",
            )
            package = root / "src" / distribution.replace("-", "_")
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("", encoding="utf-8")
            return pyproject

        @staticmethod
        def governed_repository_url(distribution: str) -> str:
            """Build a fixture repository URL from the declared fixture provider.

            Returns:
                The resulting ``str``.

            """
            provider = TestsFlextInfraUtilitiesProjectFixtureMixin.provider()
            return f"{provider.base_url.rstrip('/')}/{distribution}.git"

        @classmethod
        def link_member_beads(
            cls,
            member: Path,
            workspace: Path,
            *,
            workspace_name: str,
            database: str,
            issue_prefix: str,
        ) -> Path:
            """Create the checked-in member route to the workspace-owned ledger.

            Returns:
                The resulting ``Path``.

            """
            member.mkdir(parents=True, exist_ok=True)
            route = member / ".beads"
            route.symlink_to(os.path.relpath(workspace / ".beads", member))
            cls.write_beads_project(
                member,
                workspace=workspace_name,
                database=database,
                issue_prefix=issue_prefix,
            )
            return route

        @staticmethod
        def write_beads_project(
            root: Path,
            *,
            workspace: str,
            database: str,
            issue_prefix: str,
            custom_issue_types: t.VariadicTuple[str] = (),
        ) -> Path:
            """Write one repository-local Beads identity input.

            Returns:
                The resulting ``Path``.

            """
            path = root / "config" / "beads.yaml"
            payload: t.MutableMappingKV[str, t.JsonValue] = {
                "version": 1,
                "workspace": workspace,
                "database": database,
                "issue_prefix": issue_prefix,
            }
            if custom_issue_types:
                custom_types: list[t.JsonValue] = [*custom_issue_types]
                payload["custom_issue_types"] = custom_types
            tm.ok(u.Cli.yaml_dump(path, payload))
            return path

        @classmethod
        def attach_submodule(
            cls,
            parent: Path,
            member: Path,
            *,
            distribution: str,
            relative_path: str,
        ) -> None:
            """Declare and commit ``member`` as a real gitlink of ``parent``."""
            _ = TestsFlextInfraUtilitiesProjectFixtureMixin.provider()
            (parent / c.Infra.GITMODULES).write_text(
                f'[submodule "{distribution}"]\n'
                f"\tpath = {relative_path}\n"
                f"\turl = {cls.governed_repository_url(distribution)}\n"
                "\tbranch = "
                f"{TestsFlextInfraUtilitiesProjectFixtureMixin.provider_branch()}\n",
                encoding="utf-8",
            )
            # A workspace parent declares its own role as workspace: the
            # manifest must agree with the topology the detector observes.
            TestsFlextInfraUtilitiesProjectFixtureMixin.write_workspace_manifest(
                parent,
                cls.declared_manifest_name(parent),
                role=c.Infra.MakeProfile.WORKSPACE,
            )
            member_head = TestsFlextInfraUtilitiesGitMixin.git_capture(
                member,
                "rev-parse",
                c.Infra.GIT_HEAD,
            )
            _ = TestsFlextInfraUtilitiesGitMixin.git_run(
                parent,
                "add",
                c.Infra.GITMODULES,
            )
            _ = TestsFlextInfraUtilitiesGitMixin.git_run(
                parent,
                "update-index",
                "--add",
                "--cacheinfo",
                f"160000,{member_head.strip()},{relative_path}",
            )
            _ = TestsFlextInfraUtilitiesGitMixin.git_run(
                parent,
                "commit",
                "--quiet",
                "-m",
                "attach member",
            )

        @classmethod
        def governed_workspace(
            cls,
            parent: Path,
            directory: str,
            *,
            distribution: str = "fixture-workspace",
            workspace: str = "fixture-workspace",
            database: str = "fixture_workspace",
            issue_prefix: str = "fixture-workspace",
        ) -> Path:
            """Initialize one governed checkout at ``parent/directory`` and return it.

            Returns:
                The resulting ``Path``.

            """
            root = parent / directory
            _ = cls.initialize_governed_project(
                root,
                distribution,
                workspace=workspace,
                database=database,
                issue_prefix=issue_prefix,
            )
            return root

        @classmethod
        def governed_workspace_with_member(
            cls,
            root: Path,
            *,
            workspace: str = "sample-workspace",
            member: str = "sample-member",
            database: str = "sample_workspace",
            issue_prefix: str = "sample",
        ) -> Path:
            """Compose one governed workspace root with one attached member.

            The root declares its own project with the workspace role, exactly
            as the real composed root does, and the member is a real gitlink
            declared in the root's ``.gitmodules``.

            Returns:
                The attached member checkout path.

            """
            for checkout, distribution in ((root, workspace), (root / member, member)):
                _ = cls.initialize_governed_project(
                    checkout,
                    distribution,
                    workspace=workspace,
                    database=database,
                    issue_prefix=issue_prefix,
                )
            cls.attach_submodule(
                root,
                root / member,
                distribution=member,
                relative_path=member,
            )
            fixture = TestsFlextInfraUtilitiesWorkspaceFixtureMixin
            _ = fixture.write_standalone_workspace_manifest(
                root,
                workspace,
                role=c.Infra.MakeProfile.WORKSPACE,
            )
            return root / member

        @classmethod
        def initialize_governed_project(
            cls,
            root: Path,
            distribution: str,
            *,
            workspace: str,
            database: str,
            issue_prefix: str,
            custom_issue_types: t.VariadicTuple[str] = (),
            beads_owner: bool = True,
        ) -> Path:
            """Create one self-identifying governed project with a real Git origin.

            Every governed repository commits its own checksum-verified Mise seeds;
            ``codegen conform`` validates them and never mints them, so the fixture
            carries them exactly as a real checkout does.

            Returns:
                The resulting ``Path``.

            """
            pyproject = cls.write_python_project(root, distribution)
            TestsFlextInfraUtilitiesToolingFixtureMixin.copy_tracked_mise_seeds(root)
            if beads_owner:
                cls.write_beads_project(
                    root,
                    workspace=workspace,
                    database=database,
                    issue_prefix=issue_prefix,
                    custom_issue_types=custom_issue_types,
                )
            TestsFlextInfraUtilitiesProjectFixtureMixin.write_workspace_manifest(
                root,
                distribution,
            )
            TestsFlextInfraUtilitiesGitMixin.initialize_git_repo(
                root,
                origin_url=cls.governed_repository_url(distribution),
            )
            baseline = tm.ok(
                u.Cli.capture([c.Infra.GIT, "rev-parse", "HEAD"], cwd=root),
            )
            tm.ok(
                u.Cli.run_checked(
                    [c.Infra.GIT, "config", "remote.origin.skipDefaultUpdate", "true"],
                    cwd=root,
                ),
            )
            tm.ok(
                u.Cli.run_checked(
                    [
                        c.Infra.GIT,
                        "update-ref",
                        (
                            "refs/remotes/origin/"
                            f"{TestsFlextInfraUtilitiesProjectFixtureMixin.provider_branch()}"
                        ),
                        baseline,
                    ],
                    cwd=root,
                ),
            )
            return pyproject

        @staticmethod
        def declared_manifest_name(root: Path) -> str:
            """Return the name the root's manifest already declares.

            The Git origin was minted from that distribution; the checkout
            directory name is arbitrary in tmp fixtures and never the identity.

            Returns:
                The name the root's manifest already declares.

            """
            existing = root / "config" / "workspace.yaml"
            if not existing.is_file():
                return root.name
            loaded = tm.ok(u.Cli.config_load(existing, expand_env=False))
            loaded_name = loaded.data.get("name")
            if isinstance(loaded_name, str) and loaded_name:
                return loaded_name
            return root.name

        @classmethod
        def write_gitmodules(cls, root: Path, projects: t.VariadicTuple[str]) -> Path:
            """Declare governed subprojects with the declared fixture contract.

            Returns:
                The resulting ``Path``.

            """
            _ = TestsFlextInfraUtilitiesProjectFixtureMixin.provider()
            path = root / c.Infra.GITMODULES
            path.write_text(
                "".join(
                    (
                        f'[submodule "{project}"]\n'
                        f"\tpath = {project}\n"
                        f"\turl = {cls.governed_repository_url(project)}\n"
                        "\tbranch = "
                        f"{TestsFlextInfraUtilitiesProjectFixtureMixin.provider_branch()}\n"
                    )
                    for project in projects
                ),
                encoding="utf-8",
            )
            # Declaring members makes this root a workspace: its own manifest
            # must declare the same role or the detector rejects the drift. The
            # rewrite keeps the distribution the root already declared (its Git
            # origin was minted from it); the checkout directory name is
            # arbitrary in tmp fixtures and must never become the identity. A
            # .gitmodules without members declares no topology change, so the
            # root stays standalone.
            declared = cls.declared_manifest_name(root)
            role = (
                c.Infra.MakeProfile.WORKSPACE
                if projects
                else c.Infra.MakeProfile.STANDALONE
            )
            TestsFlextInfraUtilitiesProjectFixtureMixin.write_workspace_manifest(
                root,
                declared,
                role=role,
            )
            return path

        @staticmethod
        def repository_snapshot(
            root: Path,
        ) -> t.Pair[t.VariadicTuple[t.Pair[str, bytes]], str]:
            """Capture all repository bytes and porcelain status.

            Git metadata is excluded; every runtime-state owner lives outside the
            repository checkout by construction.

            Returns:
                The resulting ``t.Pair[t.VariadicTuple[t.Pair[str, bytes]], str]``.

            """
            excluded_roots = frozenset({c.Infra.GIT_DIR})
            tree = tuple(
                sorted(
                    (path.relative_to(root).as_posix(), path.read_bytes())
                    for path in root.rglob("*")
                    if path.is_file()
                    and not excluded_roots.intersection(path.relative_to(root).parts)
                ),
            )
            status = tm.ok(
                u.Cli.capture(
                    [c.Infra.GIT, "status", "--porcelain=v1", "--untracked-files=all"],
                    cwd=root,
                ),
            )
            return tree, status

    __all__: t.VariadicTuple[str] = ("WorktreeFixture",)


__all__: list[str] = ["TestsFlextInfraUtilitiesWorkspaceFixtureMixin"]
