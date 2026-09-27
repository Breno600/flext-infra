"""Declared profiles and complete CUSTOM requirements survive public generation."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m
from flext_infra.codegen import FlextInfraCodegenConform
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from tests import u


class TestsFlextInfraCodegenRuntimeProfiles:
    @pytest.mark.parametrize(
        "upstream",
        tuple(
            item.upstream
            for item in config.Infra.codegen.scaffold.project.dependency_profiles
            if item.project is None
        ),
    )
    @pytest.mark.parametrize("composed", [False, True])
    def test_declared_profile_restores_runtime_and_preserves_custom_specs(
        self, tmp_path: Path, upstream: str, *, composed: bool
    ) -> None:
        """Real standalone and parent plans consume the same member-owned profile."""
        root = tmp_path / "workspace"
        member = root / "sample-member" if composed else tmp_path / "sample-member"
        if composed:
            u.Tests.WorktreeFixture.initialize_governed_project(
                root,
                "sample-workspace",
                workspace="sample-workspace",
                database="sample_workspace",
                issue_prefix="sample",
            )
        pyproject = u.Tests.WorktreeFixture.initialize_governed_project(
            member,
            "sample-member",
            workspace="sample-workspace",
            database="sample_workspace",
            issue_prefix="sample",
        )
        observed = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(member))
        project = u.Tests.project_spec(observed.repository.name).model_copy(
            update={"upstream": upstream}
        )
        manifest = m.Infra.WorkspaceManifestSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=observed.repository.name,
            repository=observed.repository,
            project=project,
            # A member cannot introduce another parent target through its manifest.
            members=(
                u.Tests.repository_ref(
                    "unselected-project", path=Path("unselected-project")
                ),
            ),
        )
        manifest_path = member / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME
        tm.ok(u.Cli.yaml_dump(manifest_path, manifest.model_dump(mode="json")))
        profile = next(
            item
            for item in config.Infra.codegen.scaffold.project.dependency_profiles
            if item.project is None and item.upstream == upstream
        )
        owned_name = tm.not_none(u.Infra.dep_name(profile.runtime[0]))
        custom = (
            "custom-runtime[feature]>=2; python_version < '3.14'",
            "custom-runtime[feature]>=3; python_version >= '3.14'",
            (
                "custom-artifact[extra] @ https://example.invalid/pkg.whl "
                "; sys_platform == 'linux'"
            ),
        )
        declared = tm.ok(
            u.Cli.json_dumps([
                f"{owned_name.upper().replace('-', '_')}[old]==0",
                *custom,
            ])
        )
        # The governed fixture already declares `dependencies`; replace that
        # declaration instead of adding a second (invalid) key.
        pyproject.write_text(
            "".join(
                f"dependencies = {declared}\n"
                if line.startswith("dependencies = ")
                else line
                for line in pyproject.read_text(encoding="utf-8").splitlines(
                    keepends=True
                )
            ),
            encoding="utf-8",
        )
        if composed:
            u.Tests.WorktreeFixture.attach_submodule(
                root,
                member,
                distribution="sample-member",
                relative_path="sample-member",
            )
        request_root = root if composed else member
        before = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(request_root))
        protected = {
            path: path.read_bytes()
            for path in (
                manifest_path,
                member / "config" / c.Infra.BEADS_CONFIG_FILENAME,
                *((root / c.Infra.GITMODULES,) if composed else ()),
            )
        }
        request = u.Tests.conform_request(
            request_root,
            what=c.Infra.CodegenConformSurface.PYPROJECT,
            scope=(
                c.Infra.CodegenConformScope.DECLARED
                if composed
                else c.Infra.CodegenConformScope.SELF
            ),
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        service = FlextInfraCodegenConform(
            repository_root=request_root, request=request
        )
        first = tm.ok(service.plan(request))
        rendered = u.Tests.codegen_file_text(
            next(item for item in first.files if item.path == pyproject)
        )
        rendered_dependencies = set(
            u.Tests.toml_strings_at(rendered, "project", "dependencies")
        )
        owned = rendered_dependencies - set(custom)
        tm.that(rendered_dependencies, has=list(custom))
        # The profile owns which runtime requirements are restored; the
        # dependency conform owner (6086621bd) owns their canonical form, so the
        # restored set must be names of the profile and a conform fixed point.
        tm.that(
            {u.Infra.dep_name(item) for item in owned},
            eq={u.Infra.dep_name(item) for item in profile.runtime},
        )
        expected = tm.ok(
            u.Infra.pyproject_dependencies_conform(
                '[project]\nname = "sample-member"\ndependencies = '
                + u.Cli.toml_array(sorted(owned)).as_string()
                + "\n",
                workspace=tm.ok(
                    FlextInfraWorkspaceDetector.load_workspace_spec(member)
                ),
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
            )
        )
        tm.that(
            set(u.Tests.toml_strings_at(expected, "project", "dependencies")), eq=owned
        )
        tm.that(first.workspace.repository, eq=before.repository)
        tm.that(first.workspace.subprojects, eq=before.subprojects)
        tm.that(first.workspace.beads, eq=before.beads)
        tm.that({item.path for item in first.files}, eq={pyproject})
        pyproject.write_text(rendered, encoding="utf-8")
        second = tm.ok(service.plan(request))
        tm.that(
            u.Tests.codegen_file_text(
                next(item for item in second.files if item.path == pyproject)
            ),
            eq=rendered,
        )
        for path, content in protected.items():
            tm.that(path.read_bytes(), eq=content)

    def test_custom_policy_can_be_explicitly_disabled(self) -> None:
        """An empty preservation policy still elects only the rendered requirements."""
        rendered = '[project]\nname = "sample"\ndependencies = ["owned>=2"]\n'
        live = '[project]\nname = "sample"\ndependencies = ["external[extra]>=1"]\n'
        result = tm.ok(
            u.Infra.overlay_preserved(rendered, live, preserve_project_keys=())
        )
        tm.that(
            u.Tests.toml_strings_at(result, "project", "dependencies"), eq=("owned>=2",)
        )

    @pytest.mark.parametrize("invalid", ['["external>=1", 42]', '"external>=1"'])
    def test_invalid_custom_requirements_are_not_discarded(self, invalid: str) -> None:
        """Composition rejects malformed arrays rather than filtering their entries."""
        rendered = '[project]\nname = "sample"\ndependencies = ["owned>=2"]\n'
        live = f'[project]\nname = "sample"\ndependencies = {invalid}\n'
        tm.fail(
            u.Infra.overlay_preserved(rendered, live),
            has="validate runtime dependencies",
        )
