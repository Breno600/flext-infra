"""Public behavior tests for topology-aware pyproject conformance."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, u
from tests import t, u as test_u


class TestsFlextInfraCodegenPyprojectConform:
    def _repository(
        self, distribution: str, *, role: c.Infra.MakeProfile, path: str
    ) -> m.Infra.RepositoryRef:
        provider = test_u.Tests.provider()
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

    def _workspace(self) -> m.Infra.WorkspaceSpec:
        return test_u.Tests.workspace_spec(
            self._repository("workspace", role=c.Infra.MakeProfile.WORKSPACE, path="."),
            subprojects=(
                self._repository(
                    "flext-core", role=c.Infra.MakeProfile.STANDALONE, path="flext-core"
                ),
            ),
        )

    @staticmethod
    def _detached_dev_floors() -> t.StrSequence:
        """SSOT dev floors seeded for a project outside the workspace overlay.

        A source-less internal dependency is legal only for the workspace
        context root; every other project must carry its declared direct Git
        source (the scaffold seeds exactly this line), so the same SSOT floor
        set is rendered the way a real detached checkout declares it.
        """
        branch = test_u.Tests.provider_branch()
        return tuple(
            (
                f"{floor} @ git+{test_u.Tests.WorktreeFixture.governed_repository_url(name)}"
                f"@{branch}"
                if (name := u.Infra.dep_name(floor))
                and name.startswith("flext-")
                and "@" not in floor
                else floor
            )
            for floor in config.Infra.codegen.scaffold.project.dev
        )

    def test_leaf_conformance_preserves_parent_workspace_execution(
        self, tmp_path: Path
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
        workspace = test_u.Tests.workspace_spec(
            self._repository("member", role=c.Infra.MakeProfile.STANDALONE, path=".")
        )
        rendered = tm.ok(
            u.Infra.pyproject_conform(
                '[project]\nname = "member"\nversion = "1.0"\n'
                'requires-python = ">=3.13"\ndependencies = []\n',
                workspace=workspace,
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
                toolchain=config.Infra.codegen.toolchain,
                required_dev_dependencies=(),
            )
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
            )
        )
        tm.that((root / "uv.lock").exists(), eq=False)
        tm.that((parent / "uv.lock").exists(), eq=False)

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_global_constraints_apply_without_direct_runtime_requirements(
        self, profile: c.Infra.MakeProfile
    ) -> None:
        """Every profile receives SSOT constraints even for indirect dependencies."""
        content = (
            '[project]\nname = "workspace"\nversion = "1.2.3"\ndependencies = []\n'
        )
        first = tm.ok(
            u.Infra.pyproject_conform(
                content,
                workspace=self._workspace(),
                workspace_mode=profile,
                toolchain=config.Infra.codegen.toolchain,
                required_dev_dependencies=self._detached_dev_floors(),
            )
        )
        uv_config = test_u.Tests.toml_table_at(first, "tool", "uv")
        expected = [
            requirement
            for requirement in config.Infra.codegen.toolchain.uv_constraint_dependencies
            if u.Infra.dep_name(requirement) != "uv"
        ]
        tm.that(uv_config.get("constraint-dependencies", []), eq=expected)
        tm.that(test_u.Tests.toml_strings_at(first, "project", "dependencies"), eq=())
        second = tm.ok(
            u.Infra.pyproject_conform(
                first,
                workspace=self._workspace(),
                workspace_mode=profile,
                toolchain=config.Infra.codegen.toolchain,
                required_dev_dependencies=self._detached_dev_floors(),
            )
        )
        tm.that(second, eq=first)

    def test_custom_entry_point_groups_survive_conformance(self) -> None:
        """Plugin registrations remain owned by their declaring distribution."""
        rendered = '[project]\nname = "sample"\n'
        live = (
            '[project]\nname = "sample"\n'
            '[project.entry-points."example.plugins"]\n'
            'sample = "sample.plugin:main"\n'
        )

        overlaid = tm.ok(u.Infra.overlay_preserved(rendered, live))

        tm.that(
            test_u.Tests.toml_table_at(
                overlaid, "project", "entry-points", "example.plugins"
            )["sample"],
            eq="sample.plugin:main",
        )

    def test_overlay_defaults_only_the_omitted_policy(self) -> None:
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
            u.Infra.overlay_preserved(rendered, live, preserve_project_keys=())
        )
        tm.that(
            test_u.Tests.toml_table_at(project_override, "project")[project_key],
            eq="rendered",
        )
        tm.that(
            test_u.Tests.toml_table_at(project_override, "tool", tool_table)["value"],
            eq="rendered",
        )
        tool_override = tm.ok(
            u.Infra.overlay_preserved(rendered, live, managed_tool_tables=())
        )
        tm.that(
            test_u.Tests.toml_table_at(tool_override, "project")[project_key], eq="live"
        )
        tm.that(
            test_u.Tests.toml_table_at(tool_override, "tool", tool_table)["value"],
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
                workspace_mode=c.Infra.MakeProfile.WORKSPACE,
                toolchain=config.Infra.codegen.toolchain,
                required_dev_dependencies=self._detached_dev_floors(),
            )
        )
        original = test_u.Tests.toml_mapping(test_u.Tests.toml_payload(live)["project"])
        project = test_u.Tests.toml_mapping(
            test_u.Tests.toml_payload(conformed)["project"]
        )
        tm.that(project["optional-dependencies"], eq=original["optional-dependencies"])
        tm.that(project["version"], eq=original["version"])
        tm.that(project["description"], eq=original["description"])
        repeated = tm.ok(u.Infra.overlay_preserved(rendered, conformed))
        tm.that(
            test_u.Tests.toml_mapping(test_u.Tests.toml_payload(repeated)["project"])[
                "optional-dependencies"
            ],
            eq=original["optional-dependencies"],
        )

    def test_repository_root_uses_workspace_provenance(self) -> None:
        workspace = self._workspace()
        result = u.Infra.pyproject_dependencies_conform(
            """[project]
name = "workspace"
dependencies = ["flext-core"]

[tool.uv.workspace]
members = ["flext-core"]

[tool.uv.sources.flext-core]
workspace = true
""",
            workspace=workspace,
            workspace_mode=c.Infra.MakeProfile.WORKSPACE,
        )
        rendered = tm.ok(result)
        tm.that(
            test_u.Tests.toml_strings_at(rendered, "project", "dependencies"),
            eq=("flext-core",),
        )
        tm.that(
            test_u.Tests.toml_strings_at(rendered, "dependency-groups", "workspace"),
            eq=("flext-core",),
        )

    def test_standalone_requires_declared_git_source(self) -> None:
        """A source-less internal dependency outside the workspace overlay fails."""
        workspace = self._workspace()
        result = u.Infra.pyproject_dependencies_conform(
            '[project]\nname = "external-consumer"\ndependencies = ["flext-core"]\n',
            workspace=workspace,
            workspace_mode=c.Infra.MakeProfile.STANDALONE,
        )
        tm.fail(
            result,
            has="declares no direct git source and is not a workspace dependency",
        )

    def test_standalone_canonicalizes_the_declared_git_source(self) -> None:
        """The declared requirement line is the only URL and branch authority."""
        workspace = self._workspace()
        member = workspace.subprojects[0]
        declared = (
            f"{member.distribution} @ git+{member.url}@{test_u.Tests.provider_branch()}"
        )
        result = u.Infra.pyproject_dependencies_conform(
            f'[project]\nname = "external-consumer"\ndependencies = ["{declared}"]\n',
            workspace=workspace,
            workspace_mode=c.Infra.MakeProfile.STANDALONE,
        )
        rendered = tm.ok(result)
        tm.that(
            test_u.Tests.toml_strings_at(rendered, "project", "dependencies"),
            eq=(declared,),
        )

    def test_dependency_conformance_removes_only_legacy_uv_constraint(self) -> None:
        workspace = self._workspace()
        source = """[project]
name = "external-consumer"
dependencies = ["requests>=2"]

[tool.uv]
constraint-dependencies = ["uv>=0", "requests<3"]
"""
        first = tm.ok(
            u.Infra.pyproject_dependencies_conform(
                source,
                workspace=workspace,
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
            )
        )
        second = tm.ok(
            u.Infra.pyproject_dependencies_conform(
                first,
                workspace=workspace,
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
            )
        )

        tm.that(second, eq=first)
        tm.that(
            test_u.Tests.toml_strings_at(
                first, "tool", "uv", "constraint-dependencies"
            ),
            eq=("requests<3",),
        )

    def test_dependency_conformance_deletes_empty_uv_constraint_key(self) -> None:
        workspace = self._workspace()
        source = """[project]
name = "external-consumer"
dependencies = ["requests>=2"]

[tool.uv]
link-mode = "copy"
constraint-dependencies = ["uv>=0"]
"""
        conformed = tm.ok(
            u.Infra.pyproject_dependencies_conform(
                source,
                workspace=workspace,
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
            )
        )

        uv_config = test_u.Tests.toml_table_at(conformed, "tool", "uv")
        tm.that(uv_config["link-mode"], eq="copy")
        tm.that("constraint-dependencies" not in uv_config, eq=True)

    def test_standalone_rejects_non_https_manifest_provenance(self) -> None:
        workspace = self._workspace()
        member = workspace.subprojects[0].model_copy(
            update={"url": "git@github.com:flext-sh/flext-core.git"}
        )
        invalid_workspace = workspace.model_copy(update={"subprojects": (member,)})
        result = u.Infra.pyproject_dependencies_conform(
            '[project]\nname = "external-consumer"\ndependencies = ["flext-core"]\n',
            workspace=invalid_workspace,
            workspace_mode=c.Infra.MakeProfile.STANDALONE,
        )
        tm.that(result.failure, eq=True)

    def test_workspace_rejects_conflicting_direct_source(self) -> None:
        workspace = self._workspace()
        member = workspace.subprojects[0]
        result = u.Infra.pyproject_dependencies_conform(
            (
                '[project]\nname = "workspace"\n'
                f'dependencies = ["{member.distribution} @ git+{member.url}@'
                f'{test_u.Tests.provider_branch()}"]\n'
                "\n[tool.uv.workspace]\n"
                'members = ["flext-core"]\n'
                "\n[tool.uv.sources.flext-core]\n"
                "workspace = true\n"
            ),
            workspace=workspace,
            workspace_mode=c.Infra.MakeProfile.WORKSPACE,
        )
        tm.fail(result, has="workspace dependency declares a conflicting direct source")

    def test_full_conformance_is_idempotent_without_uv_version_pin(self) -> None:
        workspace = self._workspace()
        toolchain = config.Infra.codegen.toolchain.model_copy(
            update={"uv_link_mode": "copy"}
        )
        required_dev = self._detached_dev_floors()
        declared_member_source = (
            f"flext-core @ git+{workspace.subprojects[0].url}@"
            f"{test_u.Tests.provider_branch()}"
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
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
                toolchain=toolchain,
                required_dev_dependencies=required_dev,
            )
        )
        second = tm.ok(
            u.Infra.pyproject_conform(
                first,
                workspace=workspace,
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
                toolchain=toolchain,
                required_dev_dependencies=required_dev,
            )
        )
        uv = test_u.Tests.toml_table_at(first, "tool", "uv")
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
            not in test_u.Tests.toml_table_at(first, "tool", "pyrefly"),
            eq=True,
        )
        dev_group = test_u.Tests.toml_strings_at(first, "dependency-groups", "dev")
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
            test_u.Tests.toml_strings_at(first, "project", "dependencies")[0],
            eq=(
                f"{workspace.subprojects[0].distribution} @ "
                f"git+{workspace.subprojects[0].url}@{test_u.Tests.provider_branch()}"
            ),
        )

    def test_conformance_never_writes_the_project_version(self) -> None:
        """The release protocol is the only version writer; conform reads only."""
        workspace = self._workspace().model_copy(
            update={"project": test_u.Tests.project_spec("external-consumer")}
        )
        conformed = tm.ok(
            u.Infra.pyproject_conform(
                '[project]\nname = "external-consumer"\n'
                'version = "0.0.1"\ndependencies = []\n',
                workspace=workspace,
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
                toolchain=config.Infra.codegen.toolchain,
                required_dev_dependencies=self._detached_dev_floors(),
            )
        )
        tm.that(test_u.Tests.toml_table_at(conformed, "project")["version"], eq="0.0.1")

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
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
                toolchain=toolchain,
                required_dev_dependencies=("rumdl>=0.2.45",),
            )
        )
        dev_group = test_u.Tests.toml_strings_at(conformed, "dependency-groups", "dev")
        tm.that("rumdl>=0.2.45" in dev_group, eq=True)
        tm.that("rumdl>=0.2.46" not in dev_group, eq=True)
        tm.that("custom-tool>=1" in dev_group, eq=True)

    def test_exclude_dependencies_emit_for_standalone_without_project_key(self) -> None:
        """Standalone member CI needs scoped excludes without the routing key."""
        workspace = self._workspace()
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
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
                toolchain=config.Infra.codegen.toolchain,
                required_dev_dependencies=self._detached_dev_floors(),
                uv_exclude_dependencies=(exclusion,),
            )
        )
        uv = test_u.Tests.toml_table_at(conformed, "tool", "uv")
        excludes = test_u.Tests.toml_list(uv["exclude-dependencies"])
        tm.that(
            excludes,
            eq=[{"package": {"name": "flext-tests"}, "dependencies": ["flext-infra"]}],
        )
        tm.that("project" not in test_u.Tests.toml_mapping(excludes[0]), eq=True)

    def test_workspace_root_routes_only_exclusions_of_local_projects(
        self, tmp_path: Path
    ) -> None:
        """An exclusion for an absent project would drop its only install edge."""
        configured = config.Infra.codegen.uv_exclude_dependencies
        member = configured[0].project
        rendered = test_u.Tests.scaffold_text(
            tmp_path / "fixture-project", c.PYPROJECT_FILENAME, members=(member,)
        )
        uv = test_u.Tests.toml_table_at(rendered, "tool", "uv")
        local = {"fixture-project", member}
        tm.that(
            test_u.Tests.toml_list(uv["exclude-dependencies"]),
            eq=[
                {
                    key: value
                    for key, value in item.model_dump(
                        mode="json", exclude_none=True
                    ).items()
                    if key != "project"
                }
                for item in configured
                if item.project in local
            ],
        )

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
        document = u.Cli.toml_mapping_from_text(first)
        tm.that(document, none=False)
        if document is None:
            return
        project = u.Cli.toml_mapping_child(document, "project")
        tm.that(project, none=False)
        if project is None:
            return
        expected_requirements = frozenset({
            "pydantic>=2",
            "beartype>=0.22",
            "custom-runtime[feature]>=2; python_version < '3.14'",
            "custom-runtime[feature]>=3; python_version >= '3.14'",
        })
        tm.that(
            frozenset(test_u.Tests.toml_strings_at(first, "project", "dependencies")),
            eq=expected_requirements,
        )
        tm.that(tm.ok(u.Infra.overlay_preserved(rendered, first)), eq=first)
        conformed = tm.ok(
            u.Infra.pyproject_conform(
                first,
                workspace=self._workspace(),
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
                toolchain=config.Infra.codegen.toolchain,
                required_dev_dependencies=("rumdl>=0.2.45",),
            )
        )
        tm.that(
            frozenset(
                test_u.Tests.toml_strings_at(conformed, "project", "dependencies")
            ),
            eq=expected_requirements,
        )
        repeated = tm.ok(u.Infra.overlay_preserved(rendered, conformed))
        tm.that(
            frozenset(
                test_u.Tests.toml_strings_at(repeated, "project", "dependencies")
            ),
            eq=expected_requirements,
        )
        # Membership alone hides a required-first / alphabetical oscillation.
        # Exercise both public owners; neither may reorder the other's output.
        canonical_dependencies = test_u.Tests.toml_strings_at(
            conformed, "project", "dependencies"
        )
        tm.that(
            test_u.Tests.toml_strings_at(first, "project", "dependencies"),
            eq=canonical_dependencies,
        )
        tm.that(
            test_u.Tests.toml_strings_at(repeated, "project", "dependencies"),
            eq=canonical_dependencies,
        )
        dev = test_u.Tests.toml_strings_at(conformed, "dependency-groups", "dev")
        tm.that("custom-audit>=1" in dev, eq=True)
        tm.that("rumdl>=0.2.45" in dev, eq=True)
        tm.that("rumdl>=0.2.40" not in dev, eq=True)
        tm.that(
            tuple(test_u.Tests.toml_strings_at(first, "dependency-groups", "codegen")),
            eq=(
                (
                    "flext-infra @ git+https://github.com/flext-sh/flext-infra.git"
                    "@0.12.0-dev"
                ),
            ),
        )
        tm.that("flext-dev" in test_u.Tests.toml_mapping(project["scripts"]), eq=True)
        tool = u.Cli.toml_mapping_child(document, "tool")
        tm.that(tool, none=False)
        if tool is None:
            return
        ruff = u.Cli.toml_mapping_child(tool, "ruff")
        bandit = u.Cli.toml_mapping_child(tool, "bandit")
        tm.that(ruff is not None and bandit is not None, eq=True)
        if ruff is None or bandit is None:
            return
        live_tool = test_u.Tests.toml_table_at(live, "tool")
        rendered_payload = u.Cli.toml_mapping_from_text(rendered)
        tm.that(rendered_payload, none=False)
        if rendered_payload is None:
            return
        # `ruff` is a managed tool table: the rendered projection wins over
        # the live file; `bandit` is unmanaged and live-only, so it survives.
        rendered_tool = u.Cli.toml_mapping_child(rendered_payload, "tool")
        tm.that(rendered_tool, none=False)
        if rendered_tool is None:
            return
        rendered_ruff = u.Cli.toml_mapping_child(rendered_tool, "ruff")
        tm.that(rendered_ruff, none=False)
        if rendered_ruff is None:
            return
        tm.that(ruff["line-length"], eq=rendered_ruff["line-length"])
        live_bandit = u.Cli.toml_mapping_child(live_tool, "bandit")
        tm.that(bandit["skips"], eq=(live_bandit or {}).get("skips"))
