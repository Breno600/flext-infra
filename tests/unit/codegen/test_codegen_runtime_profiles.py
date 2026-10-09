"""Declared profiles and complete CUSTOM requirements survive public generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m
from flext_infra.codegen import FlextInfraCodegenConform
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from tests import t, u


class TestsFlextInfraCodegenRuntimeProfiles:
    """Tests for ``FlextInfraCodegenRuntimeProfiles``."""

    @staticmethod
    def _seed_member_workspace(
        tmp_path: Path,
        upstream: str,
        *,
        composed: bool,
    ) -> tuple[Path, Path, Path]:
        """Initialize the governed member (and parent when composed).

        The member manifest carries the one profile under test; a member
        cannot introduce another parent target through its manifest.

        Returns:
            The request root, the member checkout, and the member pyproject.

        """
        fixture = u.Tests.WorktreeFixture
        root = tmp_path / "workspace"
        member = root / "sample-member" if composed else tmp_path / "sample-member"
        if composed:
            fixture.initialize_governed_project(
                root,
                "sample-workspace",
                beads=u.Tests.BeadsIdentity(
                    workspace="sample-workspace",
                    database="sample_workspace",
                    issue_prefix="sample",
                ),
            )
        pyproject = fixture.initialize_governed_project(
            member,
            "sample-member",
            beads=u.Tests.BeadsIdentity(
                workspace="sample-workspace",
                database="sample_workspace",
                issue_prefix="sample",
            ),
        )
        observed = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(member))
        project = u.Tests.project_spec(observed.repository.name).model_copy(
            update={"upstream": upstream},
        )
        manifest = m.Infra.WorkspaceManifestSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=observed.repository.name,
            docs_audit=observed.docs_audit,
            repository=observed.repository,
            project=project,
            members=(
                u.Tests.repository_ref(
                    "unselected-project",
                    path=Path("unselected-project"),
                ),
            ),
        )
        manifest_path = member / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME
        tm.ok(u.Cli.yaml_dump(manifest_path, manifest.model_dump(mode="json")))
        if composed:
            fixture.attach_submodule(
                root,
                member,
                distribution="sample-member",
                relative_path="sample-member",
            )
        return root, member, pyproject

    @staticmethod
    def _declare_custom_dependencies(
        pyproject: Path,
        upstream: str,
    ) -> tuple[m.Infra.ScaffoldDependencyProfileSpec, t.VariadicTuple[str]]:
        """Replace the governed dependencies with the custom requirements.

        The governed fixture already declares `dependencies`; that
        declaration is replaced instead of adding a second (invalid) key.

        Returns:
            The declared profile under test and the custom requirements.

        """
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
            ]),
        )
        pyproject.write_text(
            "".join(
                f"dependencies = {declared}\n"
                if line.startswith("dependencies = ")
                else line
                for line in pyproject.read_text(encoding="utf-8").splitlines(
                    keepends=True,
                )
            ),
            encoding="utf-8",
        )
        return profile, custom

    @staticmethod
    def _protected_state(
        request_root: Path,
        member: Path,
        *,
        composed: bool,
    ) -> tuple[m.Infra.WorkspaceSpec, t.MappingKV[Path, bytes]]:
        """Snapshot the baseline workspace and the bytes conform must preserve.

        Returns:
            The observed workspace and the protected path-to-bytes mapping.

        """
        before = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(request_root))
        protected = {
            path: path.read_bytes()
            for path in (
                member / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME,
                member / "config" / c.Infra.BEADS_CONFIG_FILENAME,
                *((request_root / c.Infra.GITMODULES,) if composed else ()),
            )
        }
        return before, protected

    def _assert_render_restores_profile(
        self,
        rendered: str,
        member: Path,
        profile: m.Infra.ScaffoldDependencyProfileSpec,
        custom: t.VariadicTuple[str],
    ) -> str:
        """The CHECK plan renders one profile-owned conform fixed point.

        Returns:
            The rendered pyproject text the second plan must reproduce.

        """
        rendered_dependencies = set(
            u.Tests.toml_strings_at(rendered, "project", "dependencies"),
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
        tm.that(
            u.Tests.toml_table_at(rendered, "tool", "pyrefly", "errors"),
            eq=dict.fromkeys(
                sorted(set(config.Infra.tooling.tools.pyrefly.strict_errors)), "error"
            ),
        )
        toolchain = config.Infra.codegen.toolchain
        expected = tm.ok(
            u.Infra.pyproject_conform(
                '[project]\nname = "sample-member"\ndependencies = '
                + u.Cli.toml_array(sorted(owned)).as_string()
                + "\n",
                workspace=tm.ok(
                    FlextInfraWorkspaceDetector.load_workspace_spec(member),
                ),
                required_dev_dependencies=(),
                uv_resolution=m.Infra.UvResolutionSpec(
                    link_mode=toolchain.uv_link_mode,
                    constraint_dependencies=tuple(toolchain.uv_constraint_dependencies),
                    exclude_dependencies=(),
                    environments=tuple(toolchain.uv_environments),
                ),
            ),
        )
        tm.that(
            set(u.Tests.toml_strings_at(expected, "project", "dependencies")),
            eq=owned,
        )
        return rendered

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
        self,
        tmp_path: Path,
        upstream: str,
        *,
        composed: bool,
    ) -> None:
        """Real standalone and parent plans consume the same member-owned profile."""
        root, member, pyproject = self._seed_member_workspace(
            tmp_path,
            upstream,
            composed=composed,
        )
        profile, custom = self._declare_custom_dependencies(pyproject, upstream)
        request_root = root if composed else member
        before, protected = self._protected_state(
            request_root,
            member,
            composed=composed,
        )
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
            repository_root=request_root,
            request=request,
        )
        first = tm.ok(service.plan(request))
        rendered = self._assert_render_restores_profile(
            u.Tests.codegen_file_text(
                next(item for item in first.files if item.path == pyproject),
            ),
            member,
            profile,
            custom,
        )
        tm.that(first.workspace.repository, eq=before.repository)
        tm.that(first.workspace.subprojects, eq=before.subprojects)
        tm.that(first.workspace.beads, eq=before.beads)
        tm.that({item.path for item in first.files}, eq={pyproject})
        pyproject.write_text(rendered, encoding="utf-8")
        second = tm.ok(service.plan(request))
        tm.that(
            u.Tests.codegen_file_text(
                next(item for item in second.files if item.path == pyproject),
            ),
            eq=rendered,
        )
        for path, content in protected.items():
            tm.that(path.read_bytes(), eq=content)

    @staticmethod
    def test_custom_policy_can_be_explicitly_disabled() -> None:
        """An empty preservation policy still elects only the rendered requirements."""
        rendered = '[project]\nname = "sample"\ndependencies = ["owned>=2"]\n'
        live = '[project]\nname = "sample"\ndependencies = ["external[extra]>=1"]\n'
        result = tm.ok(
            u.Infra.overlay_preserved(rendered, live, preserve_project_keys=()),
        )
        tm.that(
            u.Tests.toml_strings_at(result, "project", "dependencies"),
            eq=("owned>=2",),
        )

    @staticmethod
    @pytest.mark.parametrize("invalid", ['["external>=1", 42]', '"external>=1"'])
    def test_invalid_custom_requirements_are_not_discarded(invalid: str) -> None:
        """Composition rejects malformed arrays rather than filtering their entries."""
        rendered = '[project]\nname = "sample"\ndependencies = ["owned>=2"]\n'
        live = f'[project]\nname = "sample"\ndependencies = {invalid}\n'
        tm.fail(
            u.Infra.overlay_preserved(rendered, live),
            has="validate runtime dependencies",
        )
