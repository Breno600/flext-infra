"""Tests for canonical dependency source selection by topology role.

Every project keeps its declared direct Git requirement — the requirement line
is the only URL and ref authority — so the same package metadata resolves
standalone, and conformance drops workspace-scoped ``[tool.uv.sources]``
entries instead of carrying a root overlay.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, config, m
from tests import u


class TestsFlextInfraPyprojectConformTopologySources:
    """Tests for ``FlextInfraPyprojectConformTopologySources``."""

    _ROLE = c.Infra.MakeProfile

    def _member_ref(self, distribution: str, path: str) -> m.Infra.RepositoryRef:
        """Declare one standalone-capable member through the provider contract.

        Returns:
            The resulting ``m.Infra.RepositoryRef``.

        """
        return u.Tests.repository_ref(
            distribution,
            role=self._ROLE.STANDALONE,
            path=Path(path),
        )

    @staticmethod
    def _workspace(*members: m.Infra.RepositoryRef) -> m.Infra.WorkspaceSpec:
        """Compose one workspace fixture from its declared member references.

        Returns:
            The resulting ``m.Infra.WorkspaceSpec``.

        """
        return u.Tests.workspace_spec(
            u.Tests.repository_ref("workspace"),
            subprojects=tuple(members),
        )

    @staticmethod
    def _inline_requirement(ref: m.Infra.RepositoryRef) -> str:
        """Render the direct-source form derived from the declared fixture branch.

        Returns:
            The resulting ``str``.

        """
        return f"{ref.distribution} @ git+{ref.url}@{u.Tests.provider_branch()}"

    @staticmethod
    def _toolchain_resolution() -> m.Infra.UvResolutionSpec:
        """Declare the fleet toolchain's uv resolver keys with no exclusions.

        Returns:
            The resulting ``m.Infra.UvResolutionSpec``.

        """
        toolchain = config.Infra.codegen.toolchain
        return m.Infra.UvResolutionSpec(
            link_mode=toolchain.uv_link_mode,
            constraint_dependencies=tuple(toolchain.uv_constraint_dependencies),
            exclude_dependencies=(),
            environments=tuple(toolchain.uv_environments),
        )

    def test_attached_members_render_on_the_workspace_line_of_any_family(self) -> None:
        """A non-FLEXT member gets its declared source on the workspace line.

        The workspace integrates on its own line (``develop``) while the FLEXT
        family line stays the fixture branch: every attached member, FLEXT or
        not, renders inline on the workspace line; a FLEXT dependency that is
        not a member keeps the FLEXT line.
        """
        workspace_line = "develop"
        flext_member = self._member_ref("flext-core", "flext-core")
        other_member = self._member_ref("acme-charts", "apps/acme-charts")
        workspace = self._workspace(flext_member, other_member).model_copy(
            update={
                "integration": m.Infra.WorkspaceIntegrationSpec(
                    provider=u.Tests.integration().provider,
                    branch=workspace_line,
                ),
            },
        )
        infra = u.Tests.repository_ref("flext-infra")
        infra_requirement = self._inline_requirement(infra)
        source = (
            '[project]\nname = "workspace"\nversion = "0.1.0"\n'
            'dependencies = ["acme-charts", "flext-core", '
            f'"{infra_requirement}"]\n'
        )
        rendered = tm.ok(
            u.Infra.pyproject_conform(
                source,
                workspace=workspace,
                required_dev_dependencies=(),
                uv_resolution=self._toolchain_resolution(),
                family_line=u.Tests.provider_branch(),
            ),
        )
        expected = {
            f"{ref.distribution} @ git+{ref.url}@{workspace_line}"
            for ref in (flext_member, other_member)
        } | {infra_requirement}
        tm.that(
            set(u.Tests.toml_strings_at(rendered, "project", "dependencies")),
            eq=expected,
        )
        workspace_group = u.Tests.toml_strings_at(
            rendered,
            "dependency-groups",
            "workspace",
        )
        tm.that(
            set(workspace_group),
            eq={
                f"{ref.distribution} @ git+{ref.url}@{workspace_line}"
                for ref in (flext_member, other_member)
            },
        )
        second = tm.ok(
            u.Infra.pyproject_conform(
                rendered,
                workspace=workspace,
                required_dev_dependencies=(),
                uv_resolution=self._toolchain_resolution(),
                family_line=u.Tests.provider_branch(),
            ),
        )
        tm.that(second, eq=rendered)

    def test_candidate_commit_is_project_specific_and_reaches_fixed_point(self) -> None:
        """An explicit candidate changes only its declared distribution."""
        cli = self._member_ref("flext-cli", "flext-cli")
        infra = self._member_ref("flext-infra", "flext-infra")
        candidate_commit = "a" * 40
        workspace = self._workspace(cli, infra).model_copy(
            update={
                "candidate_dependencies": (
                    m.Infra.CandidateDependencySourceSpec(
                        distribution=cli.distribution,
                        url=cli.url,
                        commit=candidate_commit,
                    ),
                ),
            },
        )
        source = (
            '[project]\nname = "workspace"\nversion = "0.1.0"\n'
            'dependencies = ["flext-cli", "flext-infra"]\n'
        )
        rendered = tm.ok(
            u.Infra.pyproject_conform(
                source,
                workspace=workspace,
                required_dev_dependencies=(),
                uv_resolution=self._toolchain_resolution(),
                family_line=u.Tests.provider_branch(),
            ),
        )
        dependencies = set(
            u.Tests.toml_strings_at(rendered, "project", "dependencies"),
        )
        tm.that(
            dependencies,
            eq={
                f"{cli.distribution} @ git+{cli.url}@{candidate_commit}",
                (
                    f"{infra.distribution} @ "
                    f"git+{infra.url}@{test_u.Tests.provider_branch()}"
                ),
            },
        )
        tm.that(
            u.Tests.toml_strings_at(rendered, "tool", "uv", "override-dependencies"),
            eq=(f"{cli.distribution} @ git+{cli.url}@{candidate_commit}",),
        )
        tm.that(
            tm.ok(
                u.Infra.pyproject_conform(
                    rendered,
                    workspace=workspace,
                    required_dev_dependencies=(),
                    uv_resolution=self._toolchain_resolution(),
                    family_line=u.Tests.provider_branch(),
                ),
            ),
            eq=rendered,
        )

    def test_candidate_url_must_match_declared_requirement_source(self) -> None:
        """A commit cannot redirect an existing direct requirement to another repo."""
        cli = self._member_ref("flext-cli", "flext-cli")
        foreign = self._member_ref("flext-core", "flext-core")
        workspace = self._workspace(cli).model_copy(
            update={
                "candidate_dependencies": (
                    m.Infra.CandidateDependencySourceSpec(
                        distribution=cli.distribution,
                        url=foreign.url,
                        commit="b" * 40,
                    ),
                ),
            },
        )
        source = (
            '[project]\nname = "workspace"\nversion = "0.1.0"\n'
            f'dependencies = ["{self._inline_requirement(cli)}"]\n'
        )
        result = u.Infra.pyproject_conform(
            source,
            workspace=workspace,
            required_dev_dependencies=(),
            uv_resolution=self._toolchain_resolution(),
            family_line=u.Tests.provider_branch(),
        )
        tm.that(result.failure, eq=True)
        tm.that(result.error or "", contains="candidate dependency Git URL differs")

    def test_candidate_cannot_invent_a_missing_dependency_origin(self) -> None:
        """A candidate pins an owned source; it cannot create provenance."""
        cli = self._member_ref("flext-cli", "flext-cli")
        workspace = self._workspace().model_copy(
            update={
                "candidate_dependencies": (
                    m.Infra.CandidateDependencySourceSpec(
                        distribution=cli.distribution,
                        url=cli.url,
                        commit="c" * 40,
                    ),
                ),
            },
        )
        result = u.Infra.pyproject_conform(
            (
                '[project]\nname = "workspace"\nversion = "0.1.0"\n'
                'dependencies = ["flext-cli"]\n'
            ),
            workspace=workspace,
            required_dev_dependencies=(),
            uv_resolution=self._toolchain_resolution(),
            family_line=u.Tests.provider_branch(),
        )
        tm.that(result.failure, eq=True)
        tm.that(result.error or "", contains="no declared Git provenance")

    def test_candidate_must_be_a_declared_requirement(self) -> None:
        """A stale candidate entry cannot silently leave the resolver unchanged."""
        cli = self._member_ref("flext-cli", "flext-cli")
        workspace = self._workspace().model_copy(
            update={
                "candidate_dependencies": (
                    m.Infra.CandidateDependencySourceSpec(
                        distribution=cli.distribution,
                        url=cli.url,
                        commit="d" * 40,
                    ),
                ),
            },
        )
        result = u.Infra.pyproject_conform(
            '[project]\nname = "workspace"\nversion = "0.1.0"\n',
            workspace=workspace,
            required_dev_dependencies=(),
            uv_resolution=self._toolchain_resolution(),
            family_line=u.Tests.provider_branch(),
        )
        tm.that(result.failure, eq=True)
        tm.that(result.error or "", contains="not declared requirements: flext-cli")

    def test_removing_candidate_removes_global_override(self) -> None:
        """A normal branch resolution leaves no stale candidate override."""
        infra = self._member_ref("flext-infra", "flext-infra")
        stale_commit = "a" * 40
        source = (
            '[project]\nname = "workspace"\nversion = "0.1.0"\n'
            f'dependencies = ["{self._inline_requirement(infra)}"]\n'
            "\n[tool.uv]\noverride-dependencies = "
            f'["{infra.distribution} @ git+{infra.url}@{stale_commit}"]\n'
        )
        rendered = tm.ok(
            u.Infra.pyproject_conform(
                source,
                workspace=self._workspace(infra),
                required_dev_dependencies=(),
                uv_resolution=self._toolchain_resolution(),
                family_line=u.Tests.provider_branch(),
            ),
        )
        parsed = u.Tests.toml_mapping(u.Cli.toml_parse_text(rendered))
        tool = u.Tests.toml_mapping(parsed.get("tool"))
        uv = u.Tests.toml_mapping(tool.get("uv"))
        tm.that("override-dependencies" not in uv, eq=True)

    def _assert_direct_source(self, rendered: str, ref: m.Infra.RepositoryRef) -> None:
        """Assert the canonical standalone output: one direct Git requirement."""
        dependencies = u.Tests.toml_strings_at(rendered, "project", "dependencies")
        tm.that(dependencies, eq=(self._inline_requirement(ref),))
        parsed = u.Tests.toml_mapping(u.Cli.toml_parse_text(rendered))
        tool = parsed.get("tool")
        uv_sources = (
            u.Tests.toml_mapping(u.Tests.toml_mapping(tool).get("uv")).get("sources")
            if tool
            else None
        )
        tm.that(not uv_sources, eq=True)

    def test_external_consumer_keeps_direct_git_requirement(self) -> None:
        """Test external consumer keeps direct git requirement."""
        workspace = self._workspace(self._member_ref("flext-core", "flext-core"))
        core = workspace.subprojects[0]
        external = (
            "[project]\n"
            'name = "acme-platform"\n'
            'version = "0.1.0"\n'
            f'dependencies = ["{self._inline_requirement(core)}"]\n'
        )

        rendered = tm.ok(
            u.Infra.pyproject_conform(
                external,
                workspace=workspace,
                required_dev_dependencies=(),
                uv_resolution=self._toolchain_resolution(),
            ),
        )

        self._assert_direct_source(rendered, core)

    def test_publishable_project_keeps_catalog_git_provenance(self) -> None:
        """Test publishable project keeps catalog git provenance."""
        workspace = self._workspace(
            self._member_ref("flext-core", "flext-core"),
            self._member_ref("flext-api", "flext-api"),
        )
        provider = workspace.subprojects[0]
        publishable_project = (
            f'[project]\nname = "{workspace.subprojects[1].distribution}"\n'
            'version = "0.1.0"\n'
            f'dependencies = ["{self._inline_requirement(provider)}"]\n'
        )

        rendered = tm.ok(
            u.Infra.pyproject_conform(
                publishable_project,
                workspace=workspace,
                required_dev_dependencies=(),
                uv_resolution=self._toolchain_resolution(),
            ),
        )

        self._assert_direct_source(rendered, provider)

    def test_publishable_project_preserves_declared_ref_of_unmapped_source(
        self,
    ) -> None:
        """The declared ref stays authoritative for a dependency no member owns."""
        workspace = self._workspace(
            self._member_ref("flext-core", "flext-core"),
            self._member_ref("flext-api", "flext-api"),
        )
        consumer = workspace.subprojects[1]
        rendered = tm.ok(
            u.Infra.pyproject_conform(
                (
                    f'[project]\nname = "{consumer.distribution}"\n'
                    'version = "0.1.0"\n'
                    'dependencies = ["flext-unmapped @ '
                    'git+https://github.com/flext-sh/flext-unmapped.git@main"]\n'
                ),
                workspace=workspace,
                required_dev_dependencies=(),
                uv_resolution=self._toolchain_resolution(),
            ),
        )

        dependencies = u.Tests.toml_strings_at(rendered, "project", "dependencies")
        tm.that(
            dependencies,
            eq=(
                (
                    "flext-unmapped @ git+https://github.com/flext-sh/"
                    "flext-unmapped.git@main"
                ),
            ),
        )

    def test_standalone_resolves_dependency_groups_with_direct_requirements(
        self,
    ) -> None:
        """Dev-group members resolve standalone through direct Git requirements."""
        workspace = self._workspace(self._member_ref("flext-core", "flext-core"))
        core = workspace.subprojects[0]
        member_source = (
            "[project]\n"
            'name = "flext-tests"\n'
            'version = "0.1.0"\n'
            "\n[dependency-groups]\n"
            f'dev = ["{self._inline_requirement(core)}"]\n'
        )

        rendered = tm.ok(
            u.Infra.pyproject_conform(
                member_source,
                workspace=workspace,
                required_dev_dependencies=(),
                uv_resolution=self._toolchain_resolution(),
            ),
        )

        group = u.Tests.toml_strings_at(rendered, "dependency-groups", "dev")
        parsed = u.Tests.toml_mapping(u.Cli.toml_parse_text(rendered))
        tool = parsed.get("tool")
        uv_sources = (
            u.Tests.toml_mapping(u.Tests.toml_mapping(tool).get("uv")).get("sources")
            if tool
            else None
        )

        tm.that(group, eq=(self._inline_requirement(core),))
        tm.that(not uv_sources, eq=True)

    def test_member_requirement_with_a_foreign_url_fails_provenance(self) -> None:
        """A member dependency cannot point at a URL its manifest does not own."""
        workspace = self._workspace(self._member_ref("flext-core", "flext-core"))
        core = workspace.subprojects[0]
        host = u.Tests.provider().base_url.rstrip("/").rpartition("/")[0]
        foreign = (
            f"{core.distribution} @ git+{host}/foreign-owner/{core.distribution}.git@"
            f"{u.Tests.provider_branch()}"
        )

        result = u.Infra.pyproject_conform(
            (
                '[project]\nname = "acme-platform"\nversion = "0.1.0"\n'
                f'dependencies = ["{foreign}"]\n'
            ),
            workspace=workspace,
            required_dev_dependencies=(),
            uv_resolution=self._toolchain_resolution(),
        )

        tm.fail(result, has="internal dependency Git URL differs from manifest")
