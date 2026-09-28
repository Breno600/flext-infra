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

from flext_infra import c, config, m, u
from tests import TestsFlextInfraUtilities as tu, u as test_u


class TestsFlextInfraPyprojectConformTopologySources:
    _ROLE = c.Infra.MakeProfile

    def _member_ref(self, distribution: str, path: str) -> m.Infra.RepositoryRef:
        """Declare one standalone-capable member through the provider contract."""
        return test_u.Tests.repository_ref(
            distribution, role=self._ROLE.STANDALONE, path=Path(path)
        )

    def _workspace(self, *members: m.Infra.RepositoryRef) -> m.Infra.WorkspaceSpec:
        """Compose one workspace fixture from its declared member references."""
        return test_u.Tests.workspace_spec(
            test_u.Tests.repository_ref("workspace"), subprojects=tuple(members)
        )

    def _inline_requirement(self, ref: m.Infra.RepositoryRef) -> str:
        """Render the direct-source form derived from the declared fixture branch."""
        return f"{ref.distribution} @ git+{ref.url}@{test_u.Tests.provider_branch()}"

    @staticmethod
    def _toolchain_resolution() -> m.Infra.UvResolutionSpec:
        """Declare the fleet toolchain's uv resolver keys with no exclusions."""
        toolchain = config.Infra.codegen.toolchain
        return m.Infra.UvResolutionSpec(
            link_mode=toolchain.uv_link_mode,
            constraint_dependencies=tuple(toolchain.uv_constraint_dependencies),
            exclude_dependencies=(),
            environments=tuple(toolchain.uv_environments),
        )

    def test_attached_members_render_on_the_workspace_line_of_any_family(
        self,
    ) -> None:
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
                    provider=test_u.Tests.integration().provider,
                    branch=workspace_line,
                ),
            }
        )
        infra = test_u.Tests.repository_ref("flext-infra")
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
                family_line=test_u.Tests.provider_branch(),
            )
        )
        expected = {
            f"{ref.distribution} @ git+{ref.url}@{workspace_line}"
            for ref in (flext_member, other_member)
        } | {infra_requirement}
        tm.that(
            set(tu.Tests.toml_strings_at(rendered, "project", "dependencies")),
            eq=expected,
        )
        workspace_group = tu.Tests.toml_strings_at(
            rendered, "dependency-groups", "workspace"
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
                family_line=test_u.Tests.provider_branch(),
            )
        )
        tm.that(second, eq=rendered)

    def _assert_direct_source(self, rendered: str, ref: m.Infra.RepositoryRef) -> None:
        """Assert the canonical standalone output: one direct Git requirement."""
        dependencies = tu.Tests.toml_strings_at(rendered, "project", "dependencies")
        tm.that(dependencies, eq=(self._inline_requirement(ref),))
        parsed = tu.Tests.toml_mapping(u.Cli.toml_parse_text(rendered))
        tool = parsed.get("tool")
        uv_sources = (
            tu.Tests.toml_mapping(tu.Tests.toml_mapping(tool).get("uv")).get("sources")
            if tool
            else None
        )
        tm.that(not uv_sources, eq=True)

    def test_external_consumer_keeps_direct_git_requirement(self) -> None:
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
            )
        )

        self._assert_direct_source(rendered, core)

    def test_publishable_project_keeps_catalog_git_provenance(self) -> None:
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
            )
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
            )
        )

        dependencies = tu.Tests.toml_strings_at(rendered, "project", "dependencies")
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
            )
        )

        group = tu.Tests.toml_strings_at(rendered, "dependency-groups", "dev")
        parsed = tu.Tests.toml_mapping(u.Cli.toml_parse_text(rendered))
        tool = parsed.get("tool")
        uv_sources = (
            tu.Tests.toml_mapping(tu.Tests.toml_mapping(tool).get("uv")).get("sources")
            if tool
            else None
        )

        tm.that(group, eq=(self._inline_requirement(core),))
        tm.that(not uv_sources, eq=True)
