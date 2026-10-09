"""Public behavior tests for topology-aware pyproject conformance.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_core import e
from flext_infra import c, config, m, p
from tests import t, u


class TestsFlextInfraCodegenPyprojectConform:
    """Tests for ``FlextInfraCodegenPyprojectConform``."""

    @staticmethod
    def _repository(
        distribution: str,
        *,
        role: c.Infra.MakeProfile,
        path: str,
    ) -> m.Infra.RepositoryRef:
        provider = u.Tests.provider()
        return m.Infra.RepositoryRef(
            name=distribution,
            distribution=distribution,
            url=f"{provider.base_url}/{distribution}.git",
            path=Path(path),
            role=role,
            provider=provider.name,
            kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
            codegen=c.Infra.CodegenKind.CONFORM,
            package=role is not c.Infra.MakeProfile.WORKSPACE,
            editable=role is not c.Infra.MakeProfile.WORKSPACE,
            read_only=False,
        )

    def _workspace(
        self,
        *,
        role: c.Infra.MakeProfile = c.Infra.MakeProfile.WORKSPACE,
    ) -> m.Infra.WorkspaceSpec:
        return u.Tests.workspace_spec(
            self._repository("workspace", role=role, path="."),
            subprojects=(
                self._repository(
                    "flext-core",
                    role=c.Infra.MakeProfile.STANDALONE,
                    path="flext-core",
                ),
            ),
        )

    @staticmethod
    def _uv_resolution(
        toolchain: p.Infra.ToolchainSpec,
        exclusions: t.VariadicTuple[m.Infra.UvScopedDependencyExclusionSpec] = (),
    ) -> m.Infra.UvResolutionSpec:
        """Route the toolchain's uv resolver keys the way conform declares them.

        Returns:
            The resulting ``m.Infra.UvResolutionSpec``.

        """
        return m.Infra.UvResolutionSpec(
            link_mode=toolchain.uv_link_mode,
            constraint_dependencies=tuple(toolchain.uv_constraint_dependencies),
            exclude_dependencies=exclusions,
            environments=tuple(toolchain.uv_environments),
        )

    @staticmethod
    def _detached_dev_floors() -> t.StrSequence:
        """SSOT dev floors seeded for a project outside the workspace overlay.

        A source-less internal dependency is legal only for the workspace
        context root; every other project must carry its declared direct Git
        source (the scaffold seeds exactly this line), so the same SSOT floor
        set is rendered the way a real detached checkout declares it.

        Returns:
            The resulting ``t.StrSequence``.

        """
        branch = u.Tests.provider_branch()
        return tuple(
            (
                f"{floor} @ git+{u.Tests.WorktreeFixture.governed_repository_url(name)}"
                f"@{branch}"
                if (name := u.Infra.dep_name(floor))
                and name.startswith("flext-")
                and "@" not in floor
                else floor
            )
            for floor in config.Infra.codegen.scaffold.project.dev
        )

    def test_leaf_conformance_preserves_parent_workspace_execution(
        self,
        tmp_path: Path,
    ) -> None:
        """A generated leaf remains usable from its declared parent workspace."""
        parent = tmp_path / "parent"
        root = parent / "member"
        root.mkdir(parents=True)
        (parent / "pyproject.toml").write_text(
            '[project]\nname = "parent"\nversion = "1.0"\n'
            "dependencies = []\n"
            '[tool.uv.workspace]\nmembers = ["member"]\n',
            encoding="utf-8",
        )
        workspace = u.Tests.workspace_spec(
            self._repository("member", role=c.Infra.MakeProfile.STANDALONE, path="."),
        )
        rendered = tm.ok(
            u.Infra.pyproject_conform(
                '[project]\nname = "member"\nversion = "1.0"\n'
                'requires-python = ">=3.13"\ndependencies = []\n',
                workspace=workspace,
                required_dev_dependencies=(),
                uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
            ),
        )
        (root / "pyproject.toml").write_text(rendered, encoding="utf-8")
        tm.ok(
            u.Cli.run_checked(
                [
                    "uv",
                    "pip",
                    "install",
                    "--dry-run",
                    "--offline",
                    "--python",
                    sys.executable,
                    "-r",
                    str(root / "pyproject.toml"),
                ],
                cwd=parent,
            ),
        )
        tm.that((root / "uv.lock").exists(), eq=False)
        tm.that((parent / "uv.lock").exists(), eq=False)

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_global_constraints_apply_without_direct_runtime_requirements(
        self,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """Every profile receives SSOT constraints even for indirect dependencies."""
        content = (
            '[project]\nname = "workspace"\nversion = "1.2.3"\ndependencies = []\n'
        )
        first = tm.ok(
            u.Infra.pyproject_conform(
                content,
                workspace=self._workspace(role=profile),
                required_dev_dependencies=self._detached_dev_floors(),
                uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
            ),
        )
        uv_config = u.Tests.toml_table_at(first, "tool", "uv")
        expected = [
            requirement
            for requirement in config.Infra.codegen.toolchain.uv_constraint_dependencies
            if u.Infra.dep_name(requirement) != "uv"
        ]
        tm.that(uv_config.get("constraint-dependencies", []), eq=expected)
        tm.that(u.Tests.toml_strings_at(first, "project", "dependencies"), eq=())
        second = tm.ok(
            u.Infra.pyproject_conform(
                first,
                workspace=self._workspace(role=profile),
                required_dev_dependencies=self._detached_dev_floors(),
                uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
            ),
        )
        tm.that(second, eq=first)

    @staticmethod
    def test_custom_entry_point_groups_survive_conformance() -> None:
        """Plugin registrations remain owned by their declaring distribution."""
        rendered = '[project]\nname = "sample"\n'
        live = (
            '[project]\nname = "sample"\n'
            '[project.entry-points."example.plugins"]\n'
            'sample = "sample.plugin:main"\n'
        )

        overlaid = tm.ok(u.Infra.overlay_preserved(rendered, live))

        tm.that(
            u.Tests.toml_table_at(
                overlaid,
                "project",
                "entry-points",
                "example.plugins",
            )["sample"],
            eq="sample.plugin:main",
        )

    @pytest.mark.parametrize("invalid_surface", ["rendered", "live"])
    def test_overlay_retains_native_toml_failure_context(
        self,
        invalid_surface: str,
    ) -> None:
        """A parse failure identifies its input and retains the native cause."""
        valid = "[project]\n"
        invalid = "[project]\nkey =\n"
        result = u.Infra.overlay_preserved(
            invalid if invalid_surface == "rendered" else valid,
            invalid if invalid_surface == "live" else valid,
        )
        tm.fail(result, has=f"{invalid_surface} pyproject is not valid TOML")
        native = tm.not_none(result.exception)
        tm.that(type(native).__name__, eq="TOMLDecodeError")
        tm.that(result.error, has=str(native))
        tm.that(result.error, has=f"line {len(invalid.splitlines())}")

    @staticmethod
    def test_overlay_defaults_only_the_omitted_policy() -> None:
        """Explicit empty policies survive default resolution of the other policy."""
        spec = next(
            item
            for item in config.Infra.codegen.managed_files
            if item.path.as_posix() == c.PYPROJECT_FILENAME
        )
        project_key = spec.preserve_project_keys[0]
        tool_table = spec.managed_tool_tables[0]
        rendered = (
            f'[project]\n{project_key} = "rendered"\n'
            f'[tool.{tool_table}]\nvalue = "rendered"\n'
        )
        live = (
            f'[project]\n{project_key} = "live"\n[tool.{tool_table}]\nvalue = "live"\n'
        )
        project_override = tm.ok(
            u.Infra.overlay_preserved(rendered, live, preserve_project_keys=()),
        )
        tm.that(
            u.Tests.toml_table_at(project_override, "project")[project_key],
            eq="rendered",
        )
        tm.that(
            u.Tests.toml_table_at(project_override, "tool", tool_table)["value"],
            eq="rendered",
        )
        tool_override = tm.ok(
            u.Infra.overlay_preserved(rendered, live, managed_tool_tables=()),
        )
        tm.that(
            u.Tests.toml_table_at(tool_override, "project")[project_key],
            eq="live",
        )
        tm.that(
            u.Tests.toml_table_at(tool_override, "tool", tool_table)["value"],
            eq="live",
        )

    def test_custom_typing_and_feature_extras_survive_conformance(self) -> None:
        """CUSTOM PEP 621 extras survive projection and dependency normalization."""
        live = (
            '[project]\nname = "workspace"\nversion = "1.2.3"\n'
            'description = "custom project"\ndependencies = []\n'
            "[project.optional-dependencies]\n"
            'typings = ["types-requests>=2.0"]\nfeature = ["requests"]\n'
        )
        rendered = '[project]\nname = "workspace"\nversion = "0.0.0"\n'
        overlaid = tm.ok(u.Infra.overlay_preserved(rendered, live))
        conformed = tm.ok(
            u.Infra.pyproject_conform(
                overlaid,
                workspace=self._workspace(),
                required_dev_dependencies=self._detached_dev_floors(),
                uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
            ),
        )
        original = u.Tests.toml_mapping(u.Tests.toml_payload(live)["project"])
        project = u.Tests.toml_mapping(
            u.Tests.toml_payload(conformed)["project"],
        )
        tm.that(project["optional-dependencies"], eq=original["optional-dependencies"])
        tm.that(project["version"], eq=original["version"])
        tm.that(project["description"], eq=original["description"])
        repeated = tm.ok(u.Infra.overlay_preserved(rendered, conformed))
        tm.that(
            u.Tests.toml_mapping(u.Tests.toml_payload(repeated)["project"])[
                "optional-dependencies"
            ],
            eq=original["optional-dependencies"],
        )

    @pytest.mark.parametrize(
        ("role", "attached"),
        [
            (c.Infra.MakeProfile.STANDALONE, False),
            (c.Infra.MakeProfile.STANDALONE, True),
            (c.Infra.MakeProfile.WORKSPACE, False),
        ],
    )
    def test_generated_dev_floors_follow_publication_topology(
        self,
        role: c.Infra.MakeProfile,
        *,
        attached: bool,
    ) -> None:
        """Members publish inline sources; only the root keeps bare local floors."""
        provider = u.Tests.provider()
        branch = u.Tests.provider_branch()
        floors = tuple(config.Infra.codegen.scaffold.project.dev)
        internal = tuple(
            name
            for floor in floors
            if (name := u.Infra.dep_name(floor))
            and name.startswith("flext-")
            and floor.strip() == name
        )
        is_root = role is c.Infra.MakeProfile.WORKSPACE
        workspace = u.Tests.workspace_spec(
            self._repository("consumer", role=role, path="."),
            subprojects=(
                tuple(
                    self._repository(
                        name,
                        role=c.Infra.MakeProfile.STANDALONE,
                        path=name,
                    )
                    for name in internal
                )
                if is_root
                else ()
            ),
        ).model_copy(update={"superproject_members": internal if attached else ()})
        dependency_source = m.Infra.WorkspaceIntegrationSpec(
            provider=provider.name,
            branch=branch,
            base_url=provider.base_url,
        )
        first = tm.ok(
            u.Infra.pyproject_conform(
                '[project]\nname = "consumer"\ndependencies = []\n',
                workspace=workspace,
                required_dev_dependencies=floors,
                uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
                options=u.Infra.PyprojectConformOptions(
                    flext_line=dependency_source,
                ),
            ),
        )
        dev = u.Tests.toml_strings_at(first, "dependency-groups", "dev")
        sources = u.Tests.toml_mapping(
            u.Tests.toml_table_at(first, "tool", "uv").get("sources", {}),
        )
        # A member render is context-independent: attached to a superproject
        # or standalone, it carries git-sourced floors and no fleet source, so
        # it installs from a clone. Only the workspace root redirects members.
        for name in internal:
            expected = (
                name
                if is_root
                else (
                    f"{name} @ git+{dependency_source.base_url}/{name}.git"
                    f"@{dependency_source.branch}"
                )
            )
            tm.that(expected in dev, eq=True)
            tm.that(name in sources, eq=is_root)
            if is_root:
                tm.that(sources[name], eq={"workspace": True})
        second = tm.ok(
            u.Infra.pyproject_conform(
                first,
                workspace=workspace,
                required_dev_dependencies=floors,
                uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
                options=u.Infra.PyprojectConformOptions(
                    flext_line=dependency_source,
                ),
            ),
        )
        tm.that(second, eq=first)

    def test_generated_floor_source_does_not_source_custom_dependencies(self) -> None:
        """Provider facts apply only to generated floors, not arbitrary bare deps."""
        provider = u.Tests.provider()
        unattached = config.Infra.codegen.infra_repository.distribution
        result = u.Infra.pyproject_conform(
            f'[project]\nname = "consumer"\ndependencies = ["{unattached}"]\n',
            workspace=u.Tests.workspace_spec(
                self._repository(
                    "consumer",
                    role=c.Infra.MakeProfile.STANDALONE,
                    path=".",
                ),
            ),
            required_dev_dependencies=(),
            options=u.Infra.PyprojectConformOptions(
                flext_line=m.Infra.WorkspaceIntegrationSpec(
                    provider=provider.name,
                    branch=u.Tests.provider_branch(),
                    base_url=provider.base_url,
                ),
            ),
            uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
        )
        tm.fail(result, has="internal dependency declares no direct git source")

    def test_generated_floor_preserves_existing_inline_source(self) -> None:
        """A bare floor cannot replace the live dependency's declared Git source."""
        provider = u.Tests.provider()
        floor = config.Infra.codegen.infra_repository.distribution
        declared = (
            f"{floor} @ git+{provider.base_url}/custom-{floor}.git"
            f"@{u.Tests.provider_branch()}-custom"
        )
        rendered = tm.ok(
            u.Infra.pyproject_conform(
                '[project]\nname = "consumer"\ndependencies = []\n'
                f'[dependency-groups]\ndev = ["{declared}"]\n',
                workspace=u.Tests.workspace_spec(
                    self._repository(
                        "consumer",
                        role=c.Infra.MakeProfile.STANDALONE,
                        path=".",
                    ),
                ),
                required_dev_dependencies=(floor,),
                options=u.Infra.PyprojectConformOptions(
                    flext_line=m.Infra.WorkspaceIntegrationSpec(
                        provider=provider.name,
                        branch=u.Tests.provider_branch(),
                        base_url=provider.base_url,
                    ),
                ),
                uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
            ),
        )
        tm.that(
            u.Tests.toml_strings_at(rendered, "dependency-groups", "dev"),
            eq=(declared,),
        )

    def test_standalone_requires_declared_git_source(self) -> None:
        """A source-less internal dependency outside the workspace overlay fails.

        The workspace attaches only flext-core, whose declaration supplies the
        source; the infrastructure distribution is internal and unattached.
        """
        unattached = config.Infra.codegen.infra_repository.distribution
        result = u.Infra.pyproject_conform(
            f'[project]\nname = "external-consumer"\ndependencies = ["{unattached}"]\n',
            workspace=self._workspace(role=c.Infra.MakeProfile.STANDALONE),
            required_dev_dependencies=(),
            uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
        )
        tm.fail(result, has="internal dependency declares no direct git source")

    def test_standalone_canonicalizes_the_declared_git_source(self) -> None:
        """The declared requirement line is the only URL and branch authority."""
        workspace = self._workspace(role=c.Infra.MakeProfile.STANDALONE)
        member = workspace.subprojects[0]
        declared = (
            f"{member.distribution} @ git+{member.url}@{u.Tests.provider_branch()}"
        )
        result = u.Infra.pyproject_conform(
            f'[project]\nname = "external-consumer"\ndependencies = ["{declared}"]\n',
            workspace=workspace,
            required_dev_dependencies=(),
            uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
        )
        rendered = tm.ok(result)
        tm.that(
            u.Tests.toml_strings_at(rendered, "project", "dependencies"),
            eq=(declared,),
        )

    def test_conformance_deletes_empty_uv_constraint_key(self) -> None:
        """A constraint set holding only the uv pin removes the key entirely."""
        toolchain = config.Infra.codegen.toolchain.model_copy(
            update={"uv_link_mode": "copy", "uv_constraint_dependencies": ("uv>=0",)},
        )
        source = """[project]
name = "external-consumer"
dependencies = ["requests>=2"]

[tool.uv]
constraint-dependencies = ["uv>=0"]
"""
        conformed = tm.ok(
            u.Infra.pyproject_conform(
                source,
                workspace=self._workspace(),
                required_dev_dependencies=(),
                uv_resolution=self._uv_resolution(toolchain),
            ),
        )

        uv_config = u.Tests.toml_table_at(conformed, "tool", "uv")
        tm.that(uv_config["link-mode"], eq=toolchain.uv_link_mode)
        tm.that("constraint-dependencies" not in uv_config, eq=True)

    def test_standalone_rejects_non_https_manifest_provenance(self) -> None:
        """Test standalone rejects non https manifest provenance."""
        workspace = self._workspace(role=c.Infra.MakeProfile.STANDALONE)
        member = workspace.subprojects[0]
        declared = (
            f"{member.distribution} @ git+{member.url}@{u.Tests.provider_branch()}"
        )
        invalid_workspace = workspace.model_copy(
            update={
                "subprojects": (
                    member.model_copy(
                        update={"url": "git@github.com:flext-sh/flext-core.git"},
                    ),
                ),
            },
        )
        result = u.Infra.pyproject_conform(
            f'[project]\nname = "external-consumer"\ndependencies = ["{declared}"]\n',
            workspace=invalid_workspace,
            required_dev_dependencies=(),
            uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
        )
        tm.fail(result, has="internal dependency manifest provenance must be HTTPS")

    def test_full_conformance_is_idempotent_without_uv_version_pin(self) -> None:
        """Test full conformance is idempotent without uv version pin."""
        workspace = self._workspace(role=c.Infra.MakeProfile.STANDALONE)
        toolchain = config.Infra.codegen.toolchain.model_copy(
            update={"uv_link_mode": "copy"},
        )
        required_dev = self._detached_dev_floors()
        declared_member_source = (
            f"flext-core @ git+{workspace.subprojects[0].url}@"
            f"{u.Tests.provider_branch()}"
        )
        source = f"""[project]
name = "external-consumer"
dependencies = ["{declared_member_source}", "requests>=2"]

[dependency-groups]
dev = ["custom-tool>=1"]

[tool.uv]
required-version = ">=0"
exclude-newer = "7 days"
exclude-newer-package = {{ cryptography = false }}
[tool.pyrefly]
python-interpreter-path = "../.venv/bin/python"
"""
        first = tm.ok(
            u.Infra.pyproject_conform(
                source,
                workspace=workspace,
                required_dev_dependencies=required_dev,
                uv_resolution=self._uv_resolution(toolchain),
            ),
        )
        second = tm.ok(
            u.Infra.pyproject_conform(
                first,
                workspace=workspace,
                required_dev_dependencies=required_dev,
                uv_resolution=self._uv_resolution(toolchain),
            ),
        )
        uv = u.Tests.toml_table_at(first, "tool", "uv")
        tm.that(second, eq=first)
        tm.that(uv["link-mode"], eq=toolchain.uv_link_mode)
        # The supply-chain cooldown is exterminated fleet-wide (flext-fphyv):
        # uv resolves every version published up to now, and a removed
        # declaration exterminates the keys everywhere (flext-gzfd2 class), so
        # pre-existing projections carrying the old cap converge to no keys.
        tm.that("exclude-newer" not in uv, eq=True)
        tm.that("exclude-newer-package" not in uv, eq=True)
        tm.that("required-version" not in uv, eq=True)
        tm.that(
            "python-interpreter-path"
            not in u.Tests.toml_table_at(first, "tool", "pyrefly"),
            eq=True,
        )
        dev_group = u.Tests.toml_strings_at(first, "dependency-groups", "dev")
        tm.that("custom-tool>=1" in dev_group, eq=True)
        # Why (CodeRabbit 3742335224): assert the exact requirement the typed
        # SSOT declares, not merely the package name. A name-only assertion
        # stays green even if the generated floor drifts away from the owner.
        # Why (hq-36xk): the requirement was selected by hardcoding the
        # "pre-commit" package name, which 30b4a37f5 removed from the SSOT when
        # it retired the legacy work lifecycle. `next()` then raised
        # StopIteration and the test failed for a reason unrelated to what it
        # measures. The expectation now derives from the same SSOT sequence
        # production reads, so it survives any legitimate change to that set.
        # A declared floor reaches the rendered group verbatim UNLESS it names a
        # workspace project, which dependency provenance rewrites to its tracked
        # integration-branch source. Asserting by package name keeps both shapes
        # in scope without re-encoding either.
        rendered_names = {u.Infra.dep_name(requirement) for requirement in dev_group}
        for requirement in required_dev:
            tm.that(u.Infra.dep_name(requirement) in rendered_names, eq=True)
        tm.that(
            u.Tests.toml_strings_at(first, "project", "dependencies")[0],
            eq=(
                f"{workspace.subprojects[0].distribution} @ "
                f"git+{workspace.subprojects[0].url}@{u.Tests.provider_branch()}"
            ),
        )

    def test_conformance_never_writes_the_project_version(self) -> None:
        """The release protocol is the only version writer; conform reads only."""
        workspace = self._workspace().model_copy(
            update={"project": u.Tests.project_spec("external-consumer")},
        )
        conformed = tm.ok(
            u.Infra.pyproject_conform(
                '[project]\nname = "external-consumer"\n'
                'version = "0.0.1"\ndependencies = []\n',
                workspace=workspace,
                required_dev_dependencies=self._detached_dev_floors(),
                uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
            ),
        )
        tm.that(u.Tests.toml_table_at(conformed, "project")["version"], eq="0.0.1")

    def test_ssot_required_dev_floor_replaces_stale_same_name_pin(self) -> None:
        """Toolchain required_dev floors win over older same-package member pins."""
        workspace = self._workspace()
        toolchain = config.Infra.codegen.toolchain
        source = """[project]
name = "external-consumer"
dependencies = []

[dependency-groups]
dev = ["rumdl>=0.2.46", "custom-tool>=1"]
"""
        conformed = tm.ok(
            u.Infra.pyproject_conform(
                source,
                workspace=workspace,
                required_dev_dependencies=("rumdl>=0.2.45",),
                uv_resolution=self._uv_resolution(toolchain),
            ),
        )
        dev_group = u.Tests.toml_strings_at(conformed, "dependency-groups", "dev")
        tm.that("rumdl>=0.2.45" in dev_group, eq=True)
        tm.that("rumdl>=0.2.46" not in dev_group, eq=True)
        tm.that("custom-tool>=1" in dev_group, eq=True)

    def test_exclude_dependencies_emit_for_standalone_without_project_key(self) -> None:
        """Standalone member CI needs scoped excludes without the routing key."""
        workspace = self._workspace(role=c.Infra.MakeProfile.STANDALONE)
        exclusion = m.Infra.UvScopedDependencyExclusionSpec(
            project="flext-infra",
            package=m.Infra.UvPackageSelectorSpec(name="flext-tests"),
            dependencies=("flext-infra",),
        )
        source = """[project]
name = "flext-infra"
dependencies = []
"""
        conformed = tm.ok(
            u.Infra.pyproject_conform(
                source,
                workspace=workspace,
                required_dev_dependencies=self._detached_dev_floors(),
                uv_resolution=self._uv_resolution(
                    config.Infra.codegen.toolchain,
                    (exclusion,),
                ),
            ),
        )
        uv = u.Tests.toml_table_at(conformed, "tool", "uv")
        excludes = u.Tests.toml_list(uv["exclude-dependencies"])
        tm.that(
            excludes,
            eq=[{"package": {"name": "flext-tests"}, "dependencies": ["flext-infra"]}],
        )
        tm.that("project" not in u.Tests.toml_mapping(excludes[0]), eq=True)

    @staticmethod
    def test_workspace_root_routes_only_exclusions_of_local_projects(
        tmp_path: Path,
    ) -> None:
        """An exclusion for an absent project would drop its only install edge."""
        configured = config.Infra.codegen.uv_exclude_dependencies
        member = configured[0].project
        rendered = u.Tests.scaffold_text(
            tmp_path / "fixture-project",
            c.PYPROJECT_FILENAME,
            members=(member,),
        )
        uv = u.Tests.toml_table_at(rendered, "tool", "uv")
        local = {"fixture-project", member}
        tm.that(
            u.Tests.toml_list(uv["exclude-dependencies"]),
            eq=[
                {
                    key: value
                    for key, value in item.model_dump(
                        mode="json",
                        exclude_none=True,
                    ).items()
                    if key != "project"
                }
                for item in configured
                if item.project in local
            ],
        )

    @staticmethod
    def test_scaffold_mypy_policy_matches_ssot_and_converges(tmp_path: Path) -> None:
        """The actual Jinja scaffold preserves typed policy on repeated rendering."""
        root = tmp_path / "fixture-project"
        surface = c.Infra.CodegenConformSurface.PYPROJECT
        first = u.Tests.scaffold_text(root, c.PYPROJECT_FILENAME, what=surface)
        mypy = u.Tests.toml_table_at(first, "tool", "mypy")
        policy = config.Infra.tooling.tools.mypy
        tm.that(
            tuple(u.Tests.toml_strings(mypy["plugins"])),
            eq=tuple(policy.plugins),
        )
        tm.that(
            tuple(u.Tests.toml_strings(mypy["disable_error_code"])),
            eq=tuple(policy.disable_error_code),
        )
        for key, value in {**policy.boolean_settings, **policy.string_settings}.items():
            tm.that(mypy[key], eq=value)
        tm.that(
            u.Tests.toml_table_at(first, "tool", "pydantic-mypy"),
            eq=config.Infra.tooling.tools.pydantic_mypy.model_dump(),
        )
        tm.that(
            u.Tests.scaffold_text(root, c.PYPROJECT_FILENAME, what=surface),
            eq=first,
        )

    @staticmethod
    @pytest.mark.parametrize("members", [(), ("fixture-member",)])
    def test_scaffold_pyrefly_policy_matches_ssot_and_converges(
        tmp_path: Path,
        members: t.StrSequence,
    ) -> None:
        """Both repository roles render each declared diagnostic exactly once."""
        root = tmp_path / "fixture-project"
        surface = c.Infra.CodegenConformSurface.PYPROJECT
        first = u.Tests.scaffold_text(
            root,
            c.PYPROJECT_FILENAME,
            members=members,
            what=surface,
        )
        policy = config.Infra.tooling.tools.pyrefly
        tm.that(
            u.Tests.toml_table_at(first, "tool", "pyrefly", "errors"),
            eq=dict.fromkeys(policy.strict_errors, "error"),
        )
        tm.that(
            u.Tests.scaffold_text(
                root,
                c.PYPROJECT_FILENAME,
                members=members,
                what=surface,
            ),
            eq=first,
        )

    @staticmethod
    def test_pyrefly_policy_rejects_duplicate_diagnostic_declarations() -> None:
        """Ambiguous SSOT input fails before the TOML template can emit it."""
        payload = config.Infra.tooling.tools.pyrefly.model_dump(by_alias=True)
        payload["strict-errors"] = ("bad-argument-count", "bad-argument-count")
        with pytest.raises(e.PydanticValidationError, match="duplicate diagnostic"):
            m.Infra.PyreflyConfig.model_validate(payload)

    @staticmethod
    @pytest.mark.parametrize("selection", ["reordered", "subset", "empty"])
    def test_pyrefly_policy_preserves_valid_diagnostic_selections(
        selection: str,
    ) -> None:
        """Validation does not freeze the selected diagnostic set or its order."""
        policy = config.Infra.tooling.tools.pyrefly
        errors = tuple(policy.strict_errors)
        if selection == "reordered":
            selected = tuple(reversed(errors))
        elif selection == "subset":
            selected = errors[::2]
        else:
            selected = ()
        payload = policy.model_dump(by_alias=True)
        payload["strict-errors"] = selected
        validated = m.Infra.PyreflyConfig.model_validate(payload)
        tm.that(tuple(validated.strict_errors), eq=selected)

    @staticmethod
    def _assert_unmanaged_tool_tables_survive(
        live: str,
        rendered: str,
        document: t.JsonMapping,
    ) -> None:
        """`ruff` is managed: the rendered projection wins over the live file.

        `bandit` is unmanaged and live-only, so it survives untouched.
        """
        tool = tm.not_none(u.Cli.toml_mapping_child(document, "tool"))
        ruff = tm.not_none(u.Cli.toml_mapping_child(tool, "ruff"))
        bandit = tm.not_none(u.Cli.toml_mapping_child(tool, "bandit"))
        live_tool = u.Tests.toml_table_at(live, "tool")
        rendered_payload = tm.not_none(u.Cli.toml_mapping_from_text(rendered))
        rendered_tool = tm.not_none(u.Cli.toml_mapping_child(rendered_payload, "tool"))
        rendered_ruff = tm.not_none(u.Cli.toml_mapping_child(rendered_tool, "ruff"))
        tm.that(ruff["line-length"], eq=rendered_ruff["line-length"])
        live_bandit = u.Cli.toml_mapping_child(live_tool, "bandit")
        tm.that(bandit["skips"], eq=(live_bandit or {}).get("skips"))

    def test_overlay_preserves_custom_scripts_and_unmanaged_tools(self) -> None:
        """Package requirements survive without restoring stale profile pins."""
        rendered = """[project]
name = "flext"
dependencies = ["pydantic>=2"]
scripts = {flext = "flext.cli:main"}

[dependency-groups]
codegen = [
    "flext-infra @ git+https://github.com/flext-sh/flext-infra.git@0.12.0-dev",
]
dev = ["rumdl>=0.2.45"]

[tool.ruff]
line-length = 88
"""
        live = """[project]
name = "flext"
dependencies = [
    "pydantic>=1",
    "beartype>=0.22",
    "custom-runtime[feature]>=2; python_version < '3.14'",
    "custom-runtime[feature]>=3; python_version >= '3.14'",
]
scripts = {flext = "flext.workspace:main", flext-dev = "flext.dev:main"}

[dependency-groups]
codegen = ["obsolete-codegen"]
dev = ["rumdl>=0.2.40", "custom-audit>=1"]

[tool.ruff]
line-length = 120

[tool.bandit]
skips = ["B101"]
"""
        first = tm.ok(u.Infra.overlay_preserved(rendered, live))
        document = tm.not_none(u.Cli.toml_mapping_from_text(first))
        project = tm.not_none(u.Cli.toml_mapping_child(document, "project"))
        expected_requirements = frozenset({
            "pydantic>=2",
            "beartype>=0.22",
            "custom-runtime[feature]>=2; python_version < '3.14'",
            "custom-runtime[feature]>=3; python_version >= '3.14'",
        })
        tm.that(
            frozenset(u.Tests.toml_strings_at(first, "project", "dependencies")),
            eq=expected_requirements,
        )
        tm.that(tm.ok(u.Infra.overlay_preserved(rendered, first)), eq=first)
        conformed = tm.ok(
            u.Infra.pyproject_conform(
                first,
                workspace=self._workspace(),
                required_dev_dependencies=("rumdl>=0.2.45",),
                uv_resolution=self._uv_resolution(config.Infra.codegen.toolchain),
            ),
        )
        tm.that(
            frozenset(
                u.Tests.toml_strings_at(conformed, "project", "dependencies"),
            ),
            eq=expected_requirements,
        )
        repeated = tm.ok(u.Infra.overlay_preserved(rendered, conformed))
        tm.that(
            frozenset(
                u.Tests.toml_strings_at(repeated, "project", "dependencies"),
            ),
            eq=expected_requirements,
        )
        # Membership alone hides a required-first / alphabetical oscillation.
        # Exercise both public owners; neither may reorder the other's output.
        canonical_dependencies = u.Tests.toml_strings_at(
            conformed,
            "project",
            "dependencies",
        )
        tm.that(
            u.Tests.toml_strings_at(first, "project", "dependencies"),
            eq=canonical_dependencies,
        )
        tm.that(
            u.Tests.toml_strings_at(repeated, "project", "dependencies"),
            eq=canonical_dependencies,
        )
        dev = u.Tests.toml_strings_at(conformed, "dependency-groups", "dev")
        tm.that("custom-audit>=1" in dev, eq=True)
        tm.that("rumdl>=0.2.45" in dev, eq=True)
        tm.that("rumdl>=0.2.40" not in dev, eq=True)
        tm.that(
            tuple(u.Tests.toml_strings_at(first, "dependency-groups", "codegen")),
            eq=(
                (
                    "flext-infra @ git+https://github.com/flext-sh/flext-infra.git"
                    "@0.12.0-dev"
                ),
            ),
        )
        tm.that("flext-dev" in u.Tests.toml_mapping(project["scripts"]), eq=True)
        self._assert_unmanaged_tool_tables_survive(live, rendered, document)
