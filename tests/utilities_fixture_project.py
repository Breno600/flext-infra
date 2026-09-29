"""Project identity and spec fixture test utilities for flext-infra."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config, u
from tests import c, m, t

# Fixture scenario data, declared here and nowhere else: flext-infra ships no
# provider registry, so a test that needs a provider declares the one it means
# instead of reading a catalog. These constants describe the fixture fleet only.
FIXTURE_PROVIDER_NAME = "flext-sh"
FIXTURE_PROVIDER_ORGANIZATION = "flext-sh"
FIXTURE_PROVIDER_BASE_URL = "https://github.com/flext-sh"
FIXTURE_PROVIDER_BRANCH = "0.12.0-dev"
WORKSPACE_MANIFEST_VERSION = 3


class TestsFlextInfraUtilitiesProjectFixtureMixin:
    """Typed project identity, spec, and manifest-seed fixture helpers."""

    @staticmethod
    def create_project_info(
        project_root: Path,
        *,
        name: str = "test-project",
        stack: str = "python",
        has_tests: bool = False,
        has_src: bool = True,
        project_class: str = "FlextTestProject",
        package_name: str = "test_project",
        make_profile: c.Infra.MakeProfile = c.Infra.MakeProfile.STANDALONE,
        declared_subproject: bool = False,
    ) -> m.Infra.ProjectInfo:
        """Provide the typed test helper `create_project_info`."""
        return m.Infra.ProjectInfo(
            name=name,
            path=project_root,
            stack=stack,
            has_tests=has_tests,
            has_src=has_src,
            project_class=project_class,
            package_name=package_name,
            make_profile=make_profile,
            declared_subproject=declared_subproject,
        )

    @staticmethod
    def provider(name: str = FIXTURE_PROVIDER_NAME) -> m.Infra.ProviderIdentitySpec:
        """Return the declared fixture provider identity for one provider key."""
        return m.Infra.ProviderIdentitySpec(
            name=name,
            organization=FIXTURE_PROVIDER_ORGANIZATION,
            base_url=FIXTURE_PROVIDER_BASE_URL,
        )

    @staticmethod
    def provider_branch() -> str:
        """Return the declared fixture integration branch."""
        return FIXTURE_PROVIDER_BRANCH

    @staticmethod
    def flext_source(distribution: str | None = None) -> str:
        """Declare one internal distribution's direct Git source for a fixture.

        Defaults to the infrastructure distribution; every internal flext
        requirement a governed checkout declares carries its own source.
        """
        fixture = TestsFlextInfraUtilitiesProjectFixtureMixin
        if distribution is None:
            distribution = config.Infra.codegen.infra_repository.distribution
        return (
            f"{distribution} @ git+{fixture.provider().base_url.rstrip('/')}/"
            f"{distribution}.git@{fixture.provider_branch()}"
        )

    @staticmethod
    def integration() -> m.Infra.WorkspaceIntegrationSpec:
        """Return the fixture's declared integration line (provider + branch)."""
        provider = TestsFlextInfraUtilitiesProjectFixtureMixin.provider()
        return m.Infra.WorkspaceIntegrationSpec(
            provider=provider.name, branch=FIXTURE_PROVIDER_BRANCH
        )

    @staticmethod
    def workspace_spec(
        repository: m.Infra.RepositoryRef,
        *,
        project: m.Infra.ProjectSpec | None = None,
        subprojects: t.VariadicTuple[m.Infra.RepositoryRef] = (),
    ) -> m.Infra.WorkspaceSpec:
        """Build the workspace one fixture repository declares.

        Identity, Beads and the integration line are all derived from the
        repository reference and the declared fixture provider; a test never
        restates them. ``project`` is the scaffold metadata only a
        materializing test needs.
        """
        fixture = TestsFlextInfraUtilitiesProjectFixtureMixin
        return m.Infra.WorkspaceSpec(
            name=repository.name,
            beads=fixture.beads_project(repository.name),
            repository=repository,
            project=project,
            flext_source=m.Infra.CodegenBootstrapSource(
                url=fixture.repository_ref(config.Infra.name).url,
                ref=fixture.provider_branch(),
            ),
            subprojects=subprojects,
            integration=fixture.integration(),
        )

    @staticmethod
    def repository_ref(
        name: str, *, role: c.Infra.MakeProfile | None = None, path: Path | None = None
    ) -> m.Infra.RepositoryRef:
        """Build a repository reference from the declared fixture provider.

        flext-infra owns no catalog of projects, so a test that needs a
        repository declares the one it means instead of borrowing a row
        from a registry. Only the fixture's own declared provider identity
        is consulted, which keeps the fixture valid for any provider.

        A non-empty path denotes the workspace's view of one composed
        project. That project is standalone in its own right; being composed
        is carried by ``editable``, a fact of the parent's Git tree.
        """
        provider = TestsFlextInfraUtilitiesProjectFixtureMixin.provider()
        resolved_path = Path() if path is None else path
        is_declared_repository = bool(resolved_path.parts)
        resolved_role = role or (
            c.Infra.MakeProfile.STANDALONE
            if is_declared_repository
            else c.Infra.MakeProfile.WORKSPACE
        )
        return m.Infra.RepositoryRef(
            name=name,
            distribution=name,
            url=f"{provider.base_url.rstrip('/')}/{name}.git",
            path=resolved_path,
            role=resolved_role,
            provider=provider.name,
            kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
            codegen=c.Infra.CodegenKind.CONFORM,
            package=True,
            editable=is_declared_repository,
            read_only=False,
        )

    @staticmethod
    def beads_project(name: str) -> m.Infra.BeadsProjectSpec:
        """Build portable Beads identity for one repository fixture."""
        return m.Infra.BeadsProjectSpec(
            version=c.Infra.BEADS_CONFIG_VERSION,
            workspace=name,
            database=name.replace("-", "_"),
            issue_prefix=name,
        )

    @staticmethod
    def project_spec(name: str) -> m.Infra.ProjectSpec:
        """Build deterministic scaffold metadata for one project fixture."""
        package_name = name.replace("-", "_")
        class_stem = u.derive_class_stem(name)
        homepage = (
            f"{TestsFlextInfraUtilitiesProjectFixtureMixin.provider().base_url.rstrip('/')}/"
            f"{name}"
        )
        return m.Infra.ProjectSpec(
            flext_source=TestsFlextInfraUtilitiesProjectFixtureMixin.flext_source(),
            package_name=package_name,
            class_stem=class_stem,
            namespace=class_stem.removeprefix("Flext") or class_stem,
            constant_name=name,
            namespace_attribute=package_name,
            alias=u.Infra.package_alias(package_name=package_name),
            environment_prefix=f"{package_name.upper()}_",
            description=f"{class_stem} test project",
            license=config.Infra.codegen.scaffold.project.supported_licenses[0],
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream=(
                config.Infra.codegen.scaffold.project.dependency_profiles[0].upstream
            ),
            homepage=homepage,
            documentation=homepage,
            repository_root_rel=".",
            year=config.Infra.codegen.scaffold.project.copyright_year,
        )

    @staticmethod
    def write_beads_project(
        repository: Path, *, workspace: str, database: str, issue_prefix: str
    ) -> Path:
        """Write the typed repository-local Beads identity fixture.

        The bytes mirror the managed ``config/beads.yaml.j2`` render for
        the same spec, so a planned regeneration of an existing fixture
        file is never reported as drift.
        """
        path = repository / "config" / "beads.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        spec = m.Infra.BeadsProjectSpec(
            version=c.Infra.BEADS_CONFIG_VERSION,
            workspace=workspace,
            database=database,
            issue_prefix=issue_prefix,
        )
        workspace_dump = u.Cli.json_dumps(spec.workspace)
        database_dump = u.Cli.json_dumps(spec.database)
        prefix_dump = u.Cli.json_dumps(spec.issue_prefix)
        tm.ok(workspace_dump)
        tm.ok(database_dump)
        tm.ok(prefix_dump)
        path.write_text(
            f"version: {spec.version}\n"
            f"workspace: {workspace_dump.value}\n"
            f"database: {database_dump.value}\n"
            f"issue_prefix: {prefix_dump.value}\n\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def write_workspace_manifest(
        repository: Path,
        distribution: str,
        *,
        role: c.Infra.MakeProfile = c.Infra.MakeProfile.STANDALONE,
        url: str | None = None,
    ) -> Path:
        """Declare the repository's own provider identity in its manifest.

        The workspace manifest is the authority a governed repository uses to
        declare its provider key and canonical URL; the detector fails loudly
        without it, so every governed fixture carries one exactly as a real
        checkout does.
        """
        provider = TestsFlextInfraUtilitiesProjectFixtureMixin.provider()
        manifest = repository / "config" / "workspace.yaml"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        resolved_url = url or (f"{provider.base_url.rstrip('/')}/{distribution}.git")
        manifest.write_text(
            f"version: {WORKSPACE_MANIFEST_VERSION}\n"
            f"name: {distribution}\n"
            "repository:\n"
            f"  name: {distribution}\n"
            f"  distribution: {distribution}\n"
            f"  provider: {provider.name}\n"
            f"  url: {resolved_url}\n"
            "  path: .\n"
            f"  role: {role.value}\n"
            "  state: active\n"
            "  kind: internal_flext\n"
            "  codegen: conform\n"
            "  package: true\n"
            "  editable: false\n"
            "  read_only: false\n",
            encoding="utf-8",
        )
        return manifest

    @staticmethod
    def declare_workspace_projects(repository: Path, projects: t.StrSequence) -> Path:
        """Declare the exact governed projects in this root's ``.gitmodules``."""
        provider = TestsFlextInfraUtilitiesProjectFixtureMixin.provider()
        path = repository / c.Infra.GITMODULES
        path.write_text(
            "".join(
                f'[submodule "{project}"]\n'
                f"\tpath = {project}\n"
                f"\turl = {provider.base_url.rstrip('/')}/{Path(project).name}.git\n"
                f"\tbranch = {TestsFlextInfraUtilitiesProjectFixtureMixin.provider_branch()}\n"
                for project in projects
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def write_project_beads_config(project_dir: Path, name: str) -> Path:
        """Write a standalone project's required local topology input."""
        return TestsFlextInfraUtilitiesProjectFixtureMixin.write_beads_project(
            project_dir, workspace=name, database=name, issue_prefix=name
        )

    @staticmethod
    def is_project_valid(project_name: str) -> bool:
        """Validate the lightweight project-name fixture contract."""
        return (
            bool(project_name)
            and project_name.replace("-", "").replace("_", "").isalnum()
        )


__all__: list[str] = ["TestsFlextInfraUtilitiesProjectFixtureMixin"]
