"""Public functional contract for new and existing project conformance.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

import pytest
from flext_infra import config, main
from flext_infra.codegen import FlextInfraCodegenConform, FlextInfraCodegenProjectNew
from flext_infra.deps import FlextInfraPyprojectModernizer
from flext_infra.services.cli_routes_codegen import CodegenRoutes
from flext_infra.workspace import FlextInfraWorkspaceDetector
from flext_tests import tm

from tests import c, m, p, r, u


def _conform_target(
    root: Path, repository: m.Infra.RepositoryRef, *, make_profile: c.Infra.MakeProfile
) -> m.Infra.RepositoryConformTarget:
    """Build a typed rendering target from the same provider SSOT as production."""
    provider = tm.ok(
        u.Infra.repository_provider(repository, config.Infra.codegen.providers)
    )
    return m.Infra.RepositoryConformTarget(
        repository=repository,
        root=root,
        make_profile=make_profile,
        beads_enabled=make_profile is c.Infra.MakeProfile.WORKSPACE_ROOT,
        canonical_project_name=repository.distribution,
        baseline_branch=provider.branch,
        ci_enabled=True,
        technical_branch_patterns=(
            config.Infra.codegen.branch_policy.technical_branch_patterns
        ),
        governed_branch_patterns=(
            config.Infra.codegen.branch_policy.governed_branch_patterns
        ),
    )


def _standalone_workspace(root: Path) -> m.Infra.WorkspaceSpec:
    """Load the smallest owner-written standalone manifest for conform tests."""
    u.Tests.write_standalone_workspace_manifest(
        root, "flext-demo", upstream="flext_cli"
    )
    package_root = root / "src" / "flext_demo"
    tm.ok(u.Cli.ensure_dir(package_root))
    tm.ok(u.Cli.atomic_write_text_file(package_root / "__init__.py", ""))
    tm.ok(
        u.Cli.atomic_write_text_file(
            root / "pyproject.toml",
            (
                "[project]\n"
                'name = "flext-demo"\n'
                'version = "0.1.0"\n'
                'requires-python = ">=3.13,<3.14"\n'
                "dependencies = []\n"
            ),
        )
    )
    return tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))


def _apply_conform_surface(
    root: Path, workspace: m.Infra.WorkspaceSpec, surface: c.Infra.CodegenConformSurface
) -> None:
    """Materialize one exact public conform surface for a focused test."""
    tm.ok(
        FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                what=surface,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )
    )


def _project_tree(root: Path) -> tuple[tuple[str, bytes], ...]:
    """Return the versionable project tree independently of Git test fixtures."""
    return tuple(
        sorted(
            (path.relative_to(root).as_posix(), path.read_bytes())
            for path in root.rglob("*")
            if path.is_file()
            and ".git" not in path.relative_to(root).parts
            and ".infra-baseline" not in path.relative_to(root).parts
        )
    )


def _seed_infra_package_tree(root: Path) -> None:
    """Seed the minimal flext-infra tree (pyproject, src package, tests package).

    The conform templates materialize tests/fixtures/ci/docker/*, and the
    existing-tree tooling render discovers python roots from directories that
    exist on disk (env_dirs). Seeding tests/ makes the first render match the
    post-apply fixed point.
    """
    dist = u.Tests.repository_ref(config.Infra.name).distribution
    tm.ok(
        u.Cli.atomic_write_text_file(
            root / "pyproject.toml",
            f'[project]\nname = "{dist}"\nversion = "0.12.0.dev0"\n'
            'requires-python = ">=3.13,<3.14"\n',
        )
    )
    package_init = root / "src" / "flext_infra" / "__init__.py"
    package_init.parent.mkdir(parents=True, exist_ok=True)
    tm.ok(u.Cli.atomic_write_text_file(package_init, ""))
    tests_init = root / "tests" / "__init__.py"
    tests_init.parent.mkdir(parents=True, exist_ok=True)
    tm.ok(u.Cli.atomic_write_text_file(tests_init, ""))


class TestCodegenConform:
    """Prove one SSOT for project creation and existing-tree conformance."""

    def _conform_with_rendered_makefile(
        self, root: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
    ) -> p.Result[m.Infra.CodegenResult]:
        """Apply conform with ``suffix`` appended to the rendered Makefile."""
        distribution = u.Tests.repository_ref(config.Infra.name).distribution
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "{distribution}"\nversion = "0.12.0.dev0"\n'
            'requires-python = ">=3.13,<3.14"\n',
            encoding="utf-8",
        )
        package_init = root / "src" / distribution.replace("-", "_") / "__init__.py"
        package_init.parent.mkdir(parents=True, exist_ok=True)
        package_init.write_text("", encoding="utf-8")
        original_render = u.Cli.template_render

        def _render(path: Path, context: p.Model) -> p.Result[str]:
            rendered = original_render(path, context)
            if rendered.failure or path.name != f"{c.Infra.MAKEFILE_FILENAME}.j2":
                return rendered
            return r[str].ok(f"{rendered.value}{suffix}")

        monkeypatch.setattr(u.Cli, "template_render", _render)
        return FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )

    @pytest.mark.slow
    def test_rendered_conflict_marker_is_rejected_before_target_changes(
        self, infra_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = infra_git_repo
        target = root / c.Infra.MAKEFILE_FILENAME
        original = "existing generated makefile\n"
        target.write_text(original, encoding="utf-8")

        rejected = self._conform_with_rendered_makefile(
            root, monkeypatch, "\n<<<<<<< incoming\n"
        )

        tm.fail(rejected)
        tm.that(rejected.error, has="base/Makefile.j2")
        tm.that(rejected.error, has=str(target))
        tm.that(rejected.error, has=str(root))
        tm.that(target.read_text(encoding="utf-8"), eq=original)

        monkeypatch.undo()
        request = m.Infra.CodegenConformRequest(
            root=root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
        )
        applied = FlextInfraCodegenConform.execute_request(request)
        tm.ok(applied)
        tm.that(target.read_text(encoding="utf-8"), lacks="<<<<<<< ")
        fixed_point = FlextInfraCodegenConform.execute_request(
            request.model_copy(update={"mode": c.Infra.CodegenConformMode.CHECK})
        )
        tm.ok(fixed_point)
        tm.that(fixed_point.value.written_files, eq=())

    @pytest.mark.slow
    def test_setext_underline_is_accepted_as_ordinary_content(
        self, infra_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A Markdown Setext underline is content, so conform must not reject it."""
        applied = self._conform_with_rendered_makefile(
            infra_git_repo, monkeypatch, "\n# Title\n=======\n"
        )

        tm.ok(applied)

    def test_diff3_ancestor_fence_is_rejected_before_target_changes(
        self, infra_git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A diff3 merge leaves an ancestor fence that must stop the plan."""
        target = infra_git_repo / c.Infra.MAKEFILE_FILENAME
        original = "existing generated makefile\n"
        target.write_text(original, encoding="utf-8")

        rejected = self._conform_with_rendered_makefile(
            infra_git_repo, monkeypatch, "\n||||||| base\nancestor\n"
        )

        tm.fail(rejected)
        tm.that(rejected.error, has="||||||| base")
        tm.that(target.read_text(encoding="utf-8"), eq=original)

    @pytest.mark.slow
    def test_apply_recovers_declared_managed_pyproject_conflict(
        self, infra_git_repo: Path
    ) -> None:
        """Repair a committed managed block through the normal apply plan."""
        root = infra_git_repo
        distribution = u.Tests.repository_ref(config.Infra.name).distribution
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "{distribution}"\nversion = "0.12.0.dev0"\n'
            'requires-python = ">=3.13,<3.14"\n'
            "\n"
            "[tool.pytest.ini_options]\n"
            'addopts = ["--timeout=10"]\n',
            encoding="utf-8",
        )
        package_init = root / "src" / distribution.replace("-", "_") / "__init__.py"
        package_init.parent.mkdir(parents=True, exist_ok=True)
        package_init.write_text("", encoding="utf-8")

        applied = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                what=c.Infra.CodegenConformSurface.PYPROJECT,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )

        tm.ok(applied)
        rendered = (root / "pyproject.toml").read_text(encoding="utf-8")
        tm.that(rendered, lacks="<<<<<<<")
        payload = tomllib.loads(rendered)
        addopts = payload["tool"]["pytest"]["ini_options"]["addopts"]
        tm.that(
            addopts,
            has=f"--timeout={config.Infra.tooling.tools.pytest.case_timeout_seconds}",
        )

    @pytest.mark.slow
    def test_branch_ancestry_accepts_active_merge_parent(self, tmp_path: Path) -> None:
        root = tmp_path / "repository"
        root.mkdir()
        u.Tests.initialize_git_repo(root)
        baseline = tm.ok(u.Cli.capture(["git", "rev-parse", "HEAD"], cwd=root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "update-ref", "refs/remotes/origin/0.12.0-dev", baseline],
                cwd=root,
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "remote", "set-url", "origin", str(tmp_path / "missing")],
                cwd=root,
            )
        )
        empty_tree = tm.ok(u.Cli.capture(["git", "mktree"], cwd=root))
        divergent = tm.ok(
            u.Cli.capture(
                ["git", "commit-tree", empty_tree, "-m", "Create divergent local line"],
                cwd=root,
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "checkout", "-B", "0.12.0-dev", divergent], cwd=root
            )
        )
        divergent_check = tm.ok(
            u.Cli.run_raw(
                ["git", "merge-base", "--is-ancestor", baseline, divergent], cwd=root
            )
        )
        tm.that(divergent_check.exit_code, eq=1)
        repository = u.Tests.repository_ref("flext-infra").model_copy(
            update={"path": Path(), "profile": c.Infra.MakeProfile.STANDALONE}
        )
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=repository.name,
            repository=repository,
        )
        tm.ok(
            u.Cli.yaml_dump(
                root / "config" / "workspace.yaml",
                workspace.model_dump(mode="json", exclude_none=True),
            )
        )
        (root / "pyproject.toml").write_text(
            f"[project]\nname = '{repository.distribution}'\nversion = '0.1.0'\n",
            encoding="utf-8",
        )
        package = root / "src" / repository.distribution.replace("-", "_")
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        service = FlextInfraCodegenConform(workspace_root=root, request=request)

        before_merge = tm.ok(service.plan(request)).branch_ancestry[0]
        divergent_current = next(
            reference
            for reference in before_merge.references
            if reference.reference == "refs/heads/0.12.0-dev"
        )
        tm.that(divergent_current.ancestor, eq=False)

        merge_head = tm.ok(
            u.Cli.capture(["git", "rev-parse", "--git-path", "MERGE_HEAD"], cwd=root)
        )
        (root / merge_head).write_text(f"{baseline}\n", encoding="utf-8")
        during_merge = tm.ok(service.plan(request)).branch_ancestry[0]
        merging_current = next(
            reference
            for reference in during_merge.references
            if reference.reference == "refs/heads/0.12.0-dev"
        )

        tm.that(merging_current.ancestor, eq=True)

    # This end-to-end scenario scaffolds a project and runs its console entry
    # point in a fresh interpreter. The slow marker opts into the single
    # config-owned slow-item budget; tests must not restate that policy locally.
    @pytest.mark.slow
    @pytest.mark.parametrize(
        ("kind", "name"),
        [
            (c.Infra.ProjectKind.EXTERNAL, "flext-demo"),
            (c.Infra.ProjectKind.INTERNAL, "flext-member"),
        ],
    )
    def test_new_project_is_complete_and_idempotent(
        self, tmp_path: Path, kind: c.Infra.ProjectKind, name: str
    ) -> None:
        root = tmp_path / kind.value
        service = FlextInfraCodegenProjectNew(
            name=name,
            kind=kind,
            output_root=root,
            provider="flext-sh",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            year=2026,
            apply_changes=True,
        )
        first = service.execute()
        first_result = tm.ok(first)
        tm.that(bool(first_result.written_files), eq=True)
        tm.that(
            tuple(file.path for file in first_result.plan.files if file.changed), eq=()
        )
        makefile_plan = next(
            item
            for item in first_result.plan.files
            if item.path.name == c.Infra.MAKEFILE_FILENAME
        )
        tm.that(
            makefile_plan.rendered,
            has=f"MAKE_PROFILE := {c.Infra.MakeProfile.STANDALONE.value}",
        )
        tm.that(first_result.plan.request.root, eq=root.resolve())
        tm.that((root / "config" / "workspace.yaml").is_file(), eq=True)
        tm.that((root / "pyproject.toml").is_file(), eq=True)
        tm.that((root / ".env.example").is_file(), eq=True)
        package_name = name.replace("-", "_")
        pythonpath = os.pathsep.join(
            part
            for part in (str(root / "src"), os.environ.get("PYTHONPATH", ""))
            if part
        )
        process = u.Cli.capture(
            [sys.executable, "-m", package_name, "ping"],
            cwd=root,
            env={**os.environ, "PYTHONPATH": pythonpath},
            timeout=c.Infra.TIMEOUT_DEFAULT,
        )
        tm.ok(process)
        tm.that(process.value, eq="✅ pong")

    @pytest.mark.slow
    def test_generated_make_uses_unpinned_environment_uv(
        self, infra_git_repo: Path
    ) -> None:
        """Generated Make delegates uv selection to the caller environment."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        selected = u.Cli.run_raw(
            ["make", "-C", str(root), "--dry-run", "_builtin_status_diagnostics"],
            remove_env_keys=("MAKEFLAGS",),
        )

        selected_process = tm.ok(selected)
        selected_output = selected_process.stdout + selected_process.stderr
        tm.that(selected_process.exit_code, eq=0)
        tm.that(selected_output, has="uv --version")
        tm.that(selected_output, lacks="uv@")
        tm.that(selected_output, lacks="UV_VERSION")
        makefile = (root / "Makefile").read_text(encoding="utf-8")
        tm.that(makefile, has="UV ?= uv")
        tm.that(makefile, lacks="UV_VERSION")
        tm.that(makefile, lacks="uv@")
        tm.that(makefile, lacks="mise exec")

    @pytest.mark.slow
    def test_existing_manifest_converges_to_identical_tree(
        self, infra_git_repo: Path
    ) -> None:
        existing_root = infra_git_repo
        created = FlextInfraCodegenProjectNew(
            name="flext-demo",
            kind=c.Infra.ProjectKind.EXTERNAL,
            output_root=existing_root,
            provider="flext-sh",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            year=2026,
            apply_changes=True,
        ).execute()
        tm.ok(created)
        expected_tree = _project_tree(existing_root)
        tm.ok(
            u.Cli.atomic_write_text_file(
                existing_root / ".gitignore", "# committed managed drift\n"
            )
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                existing_root / "Makefile", "# committed managed drift\n"
            )
        )
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=existing_root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "--no-verify", "-m", "Seed committed drift"],
                cwd=existing_root,
            )
        )
        migrated = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=existing_root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )
        tm.ok(migrated)
        tm.that(_project_tree(existing_root), eq=expected_tree)

    @pytest.mark.slow
    def test_python_root_outside_env_dirs_still_reaches_a_fixed_point(
        self, infra_git_repo: Path
    ) -> None:
        """The gen verb converges for a Python root beyond declarative env_dirs.

        Two derivations used to select the pyright execution environments: the
        dependency command discovered roots ON DISK, while conform planned them
        from declarative ``env_dirs``. A project owning a Python directory
        outside that list therefore oscillated between two writers. Conform is
        the sole generation owner, so it must discover and preserve the extra
        root by itself and immediately reach a fixed point.
        """
        root = infra_git_repo
        _seed_infra_package_tree(root)
        # The defect needs a Python root the declarative env_dirs never lists.
        extra_root = "tools"
        module = root / extra_root / "maintenance.py"
        module.parent.mkdir(parents=True, exist_ok=True)
        tm.ok(u.Cli.atomic_write_text_file(module, "VALUE = 1\n"))
        tm.that(extra_root in u.Infra.discover_python_dirs(root), eq=True)
        tm.that(
            extra_root in config.Infra.tooling.tools.pyright.path_rules.env_dirs,
            eq=False,
        )
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Seed python root beyond env_dirs"],
                cwd=root,
            )
        )

        applied = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )
        tm.ok(applied)

        fixed_point = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            )
        )
        tm.ok(fixed_point)
        tm.that(fixed_point.value.written_files, eq=())

    @pytest.mark.slow
    def test_empty_rendered_directory_is_not_a_python_root(
        self, infra_git_repo: Path
    ) -> None:
        root = infra_git_repo
        _seed_infra_package_tree(root)
        (root / "scripts").mkdir()

        result = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )

        tm.ok(result)
        payload = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        tm.that(
            payload["tool"]["pyrefly"]["project-includes"], lacks="scripts/**/*.py*"
        )
        tm.that(payload["tool"]["pyright"]["include"], lacks="scripts")

    # Why (suite budget): two conform apply cycles plus a check over a full
    # managed tree on a real git repo; the per-case wall only holds idle.
    @pytest.mark.slow
    def test_manifestless_existing_root_plans_artifacts_without_project_spec(
        self, infra_git_repo: Path
    ) -> None:
        root = infra_git_repo
        repository = u.Tests.repository_ref(config.Infra.name)
        local_repository = repository.model_copy(update={"path": Path()})
        create_only = {
            "LICENSE": "existing license\n",
            "README.md": "# Existing repository\n",
            "custom.mk": "_custom_status_diagnostics:\n\t@true\n",
        }
        _seed_infra_package_tree(root)
        for relative, content in create_only.items():
            tm.ok(u.Cli.atomic_write_text_file(root / relative, content))
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "--no-verify", "-m", "Seed manifest-less tree"],
                cwd=root,
            )
        )

        derived = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        tm.that(derived.repository, eq=local_repository)
        tm.that(derived.project, eq=None)

        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
        )
        initial_plan = tm.ok(
            FlextInfraCodegenConform(workspace_root=root).plan(request)
        )
        plans = {
            file.path.relative_to(root).as_posix(): file for file in initial_plan.files
        }
        env_plan = plans[".env.example"]
        tm.that(env_plan.owner, eq="codegen")
        tm.that(env_plan.policy, eq="create-only")
        tm.that(env_plan.changed, eq=False)
        tm.that(env_plan.blocked, eq=False)
        tm.that(env_plan.current_sha256, eq="")
        tm.that((root / ".env.example").exists(), eq=False)
        for required in ("Makefile", ".mise.toml", ".python-version", ".gitignore"):
            tm.that(plans[required].changed, eq=True)

        applied = FlextInfraCodegenConform.execute_request(request)
        tm.ok(applied)
        for relative, content in create_only.items():
            tm.that((root / relative).read_text(encoding="utf-8"), eq=content)
        tm.that((root / "Makefile").is_file(), eq=True)
        tm.that((root / ".mise.toml").is_file(), eq=True)
        tm.that((root / ".python-version").is_file(), eq=True)
        tm.that((root / ".gitignore").is_file(), eq=True)
        tm.that((root / ".env.example").exists(), eq=False)
        tm.that(root / ".env.example" in applied.value.written_files, eq=False)

        fixed_point = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            )
        )
        tm.ok(fixed_point)
        tm.that(fixed_point.value.written_files, eq=())

    def test_workspace_uv_plan_owns_root_lock_and_editable_repositories(
        self, tmp_path: Path
    ) -> None:
        """Keep workspace setup data complete without Make-side re-derivation."""
        root_repository = u.Tests.repository_ref("flext")
        member = u.Tests.repository_ref(
            "flext-core", role=c.Infra.RepositoryRole.WORKSPACE_MEMBER
        )
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name="flext",
            repository=root_repository,
            project=m.Infra.ProjectSpec(
                package_name="flext",
                class_stem="Flext",
                namespace="Flext",
                constant_name="flext",
                namespace_attribute="flext",
                alias="flext",
                environment_prefix="FLEXT_",
                description="FLEXT workspace",
                version="0.12.0.dev0",
                license="MIT",
                author_name="FLEXT Team",
                author_email="team@flext.dev",
                upstream="flext_cli",
                homepage="https://github.com/flext-sh/flext",
                documentation="https://github.com/flext-sh/flext",
                workspace_root_rel=".",
                year=2026,
            ),
            members=(member,),
        )
        root = tmp_path / "flext"
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(
            workspace_root=root, request=request, initial_workspace=workspace
        ).plan(request)
        tm.ok(planned)
        environment = planned.value.uv_environments[0]
        tm.that(environment.environment_root, eq=root.resolve())
        tm.that(environment.lock_path, eq=root.resolve() / "uv.lock")
        tm.that(environment.groups, eq=("dev", "codegen", "workspace"))
        tm.that(
            tuple(item.name for item in environment.editable_repositories),
            eq=("flext-core",),
        )

    @pytest.mark.slow
    def test_workspace_root_catalog_profile_preserves_platform_coverage(
        self, tmp_path: Path
    ) -> None:
        """Route an arbitrary workspace root through its typed catalog profile."""
        provider = config.Infra.codegen.providers[0]
        repository = u.Tests.repository_ref("arbitrary-root").model_copy(
            update={
                "name": "arbitrary-root",
                "distribution": "arbitrary-root",
                "url": f"{provider.base_url}/arbitrary-root.git",
                "path": Path(),
                "role": c.Infra.RepositoryRole.WORKSPACE_ROOT,
                "profile": c.Infra.MakeProfile.WORKSPACE_ROOT,
                "package": False,
                "editable": False,
            }
        )
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name="arbitrary-root",
            repository=repository,
            project=m.Infra.ProjectSpec(
                package_name="arbitrary_root",
                class_stem="ArbitraryRoot",
                namespace="ArbitraryRoot",
                constant_name="arbitrary-root",
                namespace_attribute="arbitrary_root",
                alias="arbitrary_root",
                environment_prefix="ARBITRARY_ROOT_",
                description="Arbitrary workspace root",
                version="0.1.0",
                license="MIT",
                author_name="FLEXT Team",
                author_email="team@flext.dev",
                upstream="flext_cli",
                homepage=f"{provider.base_url}/arbitrary-root",
                documentation=f"{provider.base_url}/arbitrary-root",
                workspace_root_rel=".",
                year=2026,
            ),
        )
        root = tmp_path / "arbitrary-root"
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        service = FlextInfraCodegenConform(
            workspace_root=root, request=request, initial_workspace=workspace
        )

        first = tm.ok(service.plan(request))
        second = tm.ok(service.plan(request))
        first_pyproject = next(
            item for item in first.files if item.path.name == c.Infra.PYPROJECT_FILENAME
        )
        second_pyproject = next(
            item
            for item in second.files
            if item.path.name == c.Infra.PYPROJECT_FILENAME
        )
        rendered_tooling = tomllib.loads(first_pyproject.rendered)["tool"]
        report = rendered_tooling["coverage"]["report"]
        addopts = set(rendered_tooling["pytest"]["ini_options"]["addopts"])
        pytest_policy = config.Infra.tooling.tools.pytest

        tm.that(second_pyproject.rendered, eq=first_pyproject.rendered)
        tm.that(addopts, has=f"--timeout={pytest_policy.case_timeout_seconds}")
        tm.that(addopts, lacks="--session-timeout")
        tm.that(addopts >= set(pytest_policy.standard_addopts), eq=True)
        tm.that(
            report["fail_under"],
            eq=config.Infra.tooling.tools.coverage.fail_under.platform,
        )

    @pytest.mark.slow
    def test_project_root_exports_only_declared_upstream_facets(
        self, tmp_path: Path
    ) -> None:
        repository = u.Tests.repository_ref("consumer")
        project = m.Infra.ProjectSpec(
            package_name="consumer",
            class_stem="Consumer",
            namespace="Consumer",
            constant_name="consumer",
            namespace_attribute="consumer",
            alias="consumer",
            environment_prefix="CONSUMER_",
            description="Consumer project",
            version="0.1.0",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            homepage="https://example.invalid/consumer",
            documentation="https://example.invalid/consumer",
            workspace_root_rel=".",
            year=2026,
        )
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name="consumer",
            repository=repository,
            project=project,
        )
        root = tmp_path / "consumer"
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )

        plan = tm.ok(
            FlextInfraCodegenConform(
                workspace_root=root, request=request, initial_workspace=workspace
            ).plan(request)
        )
        package_root = next(
            item
            for item in plan.files
            if item.path == root / "src/consumer/__init__.py"
        )
        tm.that(package_root.rendered, lacks='"r"')

        declared_workspace = workspace.model_copy(
            update={"project": project.model_copy(update={"inherited_facets": ("r",)})}
        )
        declared_plan = tm.ok(
            FlextInfraCodegenConform(
                workspace_root=root,
                request=request,
                initial_workspace=declared_workspace,
            ).plan(request)
        )
        declared_root = next(
            item
            for item in declared_plan.files
            if item.path == root / "src/consumer/__init__.py"
        )
        tm.that(declared_root.rendered, has='"r"')
        tm.that(declared_root.rendered, has="from flext_cli import r as r")

    def test_make_context_accepts_manifest_without_project_metadata(
        self, tmp_path: Path
    ) -> None:
        """Build Make context from repository-owned data alone."""
        repository = u.Tests.repository_ref("consumer")
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name="consumer",
            repository=repository,
        )
        target = _conform_target(
            tmp_path, repository, make_profile=c.Infra.MakeProfile.STANDALONE
        )
        tooling_runtime = tm.ok(
            FlextInfraPyprojectModernizer(
                workspace_root=tmp_path, skip_check=True
            ).resolve_tooling_context(
                project_name=repository.distribution,
                package_name=repository.distribution.replace("-", "_"),
                path=tmp_path / "pyproject.toml",
                declared_python_dirs=("src",),
            )
        )
        context = FlextInfraCodegenConform.make_render_context(
            repository,
            target,
            workspace,
            config.Infra.codegen,
            tooling_runtime=tooling_runtime,
        )
        rendered = tm.ok(context)
        tm.that(isinstance(rendered, m.Infra.MakeRenderContext), eq=True)
        tm.that(isinstance(rendered, m.Infra.ProjectRenderContext), eq=False)
        tm.that(rendered.workspace_root_rel, eq=".")
        # A standalone consumer declares no flext-infra member, so the
        # reference is derived from the provider contract. The generated
        # Makefile consumes exactly the distribution and the URL (the
        # bootstrap requirement), which is what this asserts; the topology
        # role of a derived reference is not part of that contract.
        tm.that(rendered.infra_repository.distribution, eq=config.Infra.name)
        tm.that(
            rendered.infra_repository.url,
            eq=f"{config.Infra.codegen.providers[0].base_url.rstrip('/')}"
            f"/{config.Infra.name}.git",
        )
        tm.that(rendered.infra_source_root_rel, eq=None)

    def test_make_context_resolves_attached_infra_member_from_workspace(
        self, tmp_path: Path
    ) -> None:
        """An attached member bootstraps from its declared local checkout."""
        workspace_repository = u.Tests.repository_ref("workspace-root-fixture")
        infra_repository = u.Tests.repository_ref(config.Infra.name)
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=workspace_repository.name,
            repository=workspace_repository,
            members=(infra_repository,),
        )
        target = _conform_target(
            tmp_path,
            workspace_repository,
            make_profile=c.Infra.MakeProfile.WORKSPACE_ROOT,
        )
        tooling_runtime = tm.ok(
            FlextInfraPyprojectModernizer(
                workspace_root=tmp_path, skip_check=True
            ).resolve_tooling_context(
                project_name=infra_repository.distribution,
                package_name=infra_repository.distribution.replace("-", "_"),
                path=tmp_path / infra_repository.path / "pyproject.toml",
                declared_python_dirs=("src",),
            )
        )

        rendered = tm.ok(
            FlextInfraCodegenConform.make_render_context(
                infra_repository,
                target,
                workspace,
                config.Infra.codegen,
                tooling_runtime=tooling_runtime,
            )
        )

        tm.that(rendered.infra_source_root_rel, eq=infra_repository.path.as_posix())

    # Why (suite budget): parametrized over both conform modes, each running a
    # full plan/apply cycle on a real git repo; 10s only holds on an idle CPU.
    @pytest.mark.slow
    @pytest.mark.parametrize("mode", tuple(c.Infra.CodegenConformMode))
    def test_public_cli_routes_check_and_apply_to_one_handler(
        self, infra_git_repo: Path, mode: c.Infra.CodegenConformMode
    ) -> None:
        """Execute one public mode without changing an already conform tree."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "--no-verify", "-m", "Seed generated project"],
                cwd=root,
            )
        )
        route = next(
            route
            for route in CodegenRoutes.codegen_routes[c.Infra.CLI_GROUP_CODEGEN]
            if route.name == "conform"
        )
        request = m.Infra.CodegenConformRequest(
            root=root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=mode,
        )
        tm.ok(route.handler(request))
        status = tm.ok(u.Cli.capture(["git", "status", "--porcelain"], cwd=root))
        tm.that(status, eq="")

    # Why (suite budget): dependencies-only apply+check runs two full conform
    # cycles on a real git repo; the per-case wall only holds on an idle CPU.
    @pytest.mark.slow
    def test_dependency_surface_excludes_unowned_managed_files(
        self, infra_git_repo: Path
    ) -> None:
        """Plan only dependency metadata when another managed surface is invalid."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(
            root, workspace, c.Infra.CodegenConformSurface.DEPENDENCIES
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk", ".PHONY: public-handler\npublic-handler:\n\t@true\n"
            )
        )
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "--no-verify", "-m", "Seed generated project"],
                cwd=root,
            )
        )
        request = m.Infra.CodegenConformRequest(
            root=root,
            what=c.Infra.CodegenConformSurface.DEPENDENCIES,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(workspace_root=root, request=request).plan(
            request
        )
        tm.ok(planned)
        tm.that(
            tuple(file.path.name for file in planned.value.files),
            eq=("pyproject.toml",),
        )
        exit_code = main([
            "codegen",
            "conform",
            "--root",
            str(root),
            "--what",
            "dependencies",
            "--scope",
            "self",
            "--mode",
            "check",
        ])
        tm.that(exit_code, eq=0)

    # Why (suite budget): full conform cycle plus subprocess make validation;
    # the default case timeout only holds on an idle machine.

    def test_invalid_public_custom_make_fails_without_side_effects(
        self, infra_git_repo: Path
    ) -> None:
        root = infra_git_repo
        custom = root / "custom.mk"
        content = ".PHONY: public-handler\npublic-handler:\n\t@true\n"
        tm.ok(u.Cli.atomic_write_text_file(custom, content))
        policy: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.STANDALONE
            ]
        )
        result = FlextInfraCodegenConform.validate_custom_make(
            tm.ok(u.Cli.files_read_text(custom)), policy
        )
        tm.fail(result)
        rejection = Path(f"{custom}.rej")
        tm.that(
            result.error or "", has="custom.mk line 1 is not a private custom handler"
        )
        tm.that(rejection.exists(), eq=False)
        tm.that(custom.read_text(encoding="utf-8"), eq=content)

    @pytest.mark.slow
    def test_valid_private_custom_make_has_no_rejection(
        self, infra_git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        custom = root / "custom.mk"
        tm.ok(
            u.Cli.atomic_write_text_file(
                custom,
                (
                    ".PHONY: \\\n"
                    "\t_custom_check_demo \\\n"
                    "\t_custom_run_demo\n"
                    "_custom_check_demo:\n\t@true\n"
                    "_custom_run_demo:\n\t@true\n"
                ),
            )
        )
        result = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )
        tm.ok(result)
        tm.that("WARN:" in capsys.readouterr().out, eq=False)
        tm.that(Path(f"{custom}.rej").exists(), eq=False)

    def test_custom_make_rejects_unterminated_phony_continuation(self) -> None:
        """Fail closed when a multiline private-handler declaration is truncated."""
        policy: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.STANDALONE
            ]
        )

        result = FlextInfraCodegenConform.validate_custom_make(
            ".PHONY: \\\n\t_custom_check_demo \\", policy
        )

        tm.fail(result, has="unterminated .PHONY continuation")

    @pytest.mark.slow
    def test_scaffold_make_help_documents_and_lists_custom_hooks(
        self, infra_git_repo: Path
    ) -> None:
        """Scaffold help documents the hook contract and lists custom.mk hooks."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk",
                ".PHONY: pre-check post-test-all _custom_check_myscan\n"
                "pre-check:\n\t@true\n"
                "post-test-all:\n\t@true\n"
                "_custom_check_myscan:\n\t@true\n",
            )
        )
        outcome = u.Cli.run_raw(
            ["make", "-C", str(root), "help"], remove_env_keys=("MAKEFLAGS", "WHAT")
        )
        output = tm.ok(outcome)
        tm.that(output.exit_code, eq=0)
        tm.that(
            output.stdout,
            has=[
                "Custom hooks (custom.mk):",
                "pre-<verb>",
                "pre-check",
                "post-test-all",
                "_custom_check_myscan",
            ],
        )

    @pytest.mark.slow
    def test_scaffold_make_runs_pre_and_post_verb_hooks_in_order(
        self, infra_git_repo: Path
    ) -> None:
        """Generated _dispatch runs pre-<verb>, handler, post-<verb> in order."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk",
                ".PHONY: pre-check post-check _custom_check_probe\n"
                "pre-check:\n\t@echo HOOK_PRE\n"
                "_custom_check_probe:\n\t@echo HANDLER_BODY\n"
                "post-check:\n\t@echo HOOK_POST\n",
            )
        )
        # `check` requires a provisioned interpreter, which `make setup` would
        # build. Stub it so this test stays about hook ordering.
        u.Tests.write_executable(
            root / ".venv" / "bin" / "python", "#!/bin/sh\nexit 0\n"
        )
        outcome = u.Cli.run_raw(["make", "-C", str(root), "check", "WHAT=probe"])
        output = tm.ok(outcome)
        tm.that(output.exit_code, eq=0)
        combined = output.stdout + output.stderr
        pre_at = combined.find("HOOK_PRE")
        body_at = combined.find("HANDLER_BODY")
        post_at = combined.find("HOOK_POST")
        tm.that(pre_at >= 0 and body_at >= 0 and post_at >= 0, eq=True)
        tm.that(pre_at < body_at, eq=True)
        tm.that(body_at < post_at, eq=True)

    def test_custom_make_accepts_pre_post_verb_hooks(
        self, infra_git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """custom.mk may append pre/post verb hooks (verb-wide and WHAT-scoped)."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        custom = root / "custom.mk"
        tm.ok(
            u.Cli.atomic_write_text_file(
                custom,
                ".PHONY: pre-check post-check pre-test-all post-test-all\n"
                "pre-check:\n\t@true\n"
                "post-check:\n\t@true\n"
                "pre-test-all:\n\t@true\n"
                "post-test-all:\n\t@true\n",
            )
        )
        result = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )
        tm.ok(result)
        tm.that("WARN:" in capsys.readouterr().out, eq=False)
        tm.that(Path(f"{custom}.rej").exists(), eq=False)

    @pytest.mark.slow
    def test_non_regular_custom_make_remains_fatal(self, infra_git_repo: Path) -> None:
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        tm.ok(u.Cli.files_delete(root / "custom.mk"))
        (root / "custom.mk").mkdir()
        result = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            ),
            initial_workspace=workspace,
        )
        tm.fail(result)
        tm.that(result.error, has="not a regular file")
        tm.that(result.error, has=str(root / "custom.mk"))


class TestScriptDispatchMakefile:
    """Prove per-repo extra verbs and script-dispatch WHAT normalization."""

    @staticmethod
    def _render_root_makefile(
        tmp_path: Path,
        *,
        extra_verbs: tuple[m.Infra.MakeVerbSpec, ...],
        script_dispatch: m.Infra.ScriptDispatchSpec | None,
    ) -> str:
        # mro-4gbp: the engine is consumer-agnostic, so this fixture models a
        # neutral downstream root and takes its provider from the engine's own
        # configured provider catalog instead of naming a real consumer.
        provider = config.Infra.codegen.providers[0]
        root_repository = m.Infra.RepositoryRef(
            name="demo-root",
            distribution="demo-root",
            url=f"{provider.base_url}/demo-root.git",
            path=Path(),
            # Script dispatch is a generic capability: exercise it on standalone.
            role=c.Infra.RepositoryRole.STANDALONE,
            provider=provider.name,
            checkout=c.Infra.CheckoutKind.ROOT,
            codegen=c.Infra.CodegenKind.CONFORM,
            package=False,
            editable=False,
            read_only=False,
            extra_verbs=extra_verbs,
            script_dispatch=script_dispatch,
        )
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name="demo-root",
            repository=root_repository,
            project=m.Infra.ProjectSpec(
                package_name="demo_root",
                class_stem="DemoRoot",
                namespace="DemoRoot",
                constant_name="demo-root",
                namespace_attribute="demo_root",
                alias="demo_root",
                environment_prefix="DEMO_",
                description="Demo workspace",
                version="0.2.0",
                license="MIT",
                author_name="Demo",
                author_email="devops@example.com",
                upstream="flext_cli",
                homepage=f"{provider.base_url}/demo-root",
                documentation=f"{provider.base_url}/demo-root",
                workspace_root_rel=".",
                year=2026,
            ),
            members=(),
        )
        root = tmp_path / "demo-root"
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(
            workspace_root=root, request=request, initial_workspace=workspace
        ).plan(request)
        plan = tm.ok(planned)
        makefile = next(
            file for file in plan.files if file.path.name == c.Infra.MAKEFILE_FILENAME
        )
        rendered: str = makefile.rendered
        return rendered

    def test_script_dispatch_repo_routes_extra_verbs_and_normalizes_what(
        self, tmp_path: Path
    ) -> None:
        """Extra verbs join PUBLIC_VERBS and WHAT hyphens map to script stems."""
        rendered = self._render_root_makefile(
            tmp_path,
            extra_verbs=(
                m.Infra.MakeVerbSpec(
                    name="incidente",
                    default_what="all",
                    whats=("all",),
                    apply_what="all",
                ),
                m.Infra.MakeVerbSpec(
                    name="charts", default_what="all", whats=("all",), apply_what="all"
                ),
            ),
            script_dispatch=m.Infra.ScriptDispatchSpec(
                dispatcher="scripts/dispatch.py",
                roots=("scripts", "apps/demo-app/scripts"),
            ),
        )
        # Extra verbs are public targets the dispatcher can reach.
        tm.that("incidente" in rendered, eq=True)
        tm.that("charts" in rendered, eq=True)
        # The generated dispatch normalizes hyphenated WHAT to the module stem.
        tm.that("tr '-' '_'" in rendered, eq=True)
        # It forwards to the declared dispatcher through uv, not a raw builtin.
        tm.that("scripts/dispatch.py" in rendered, eq=True)
        # Existence check spans every declared script root.
        tm.that("apps/demo-app/scripts" in rendered, eq=True)
        # REGRESSION (fork-bomb): every line of the single-recipe _dispatch shell
        # command must continue with a trailing backslash. A blank/unterminated
        # line splits the recipe, drops $$what/$$builtin, and recurses into the
        # default goal. Verify continuity across the whole define body.
        body = rendered.split("define _dispatch", 1)[1].split("endef", 1)[0]
        recipe = [ln for ln in body.splitlines() if ln.startswith("\t")]
        broken = [ln for ln in recipe[:-1] if not ln.rstrip().endswith("\\")]
        tm.that(broken, eq=[])

    def test_dispatch_routes_custom_what_before_allowlist(self, tmp_path: Path) -> None:
        """Custom ``_custom_<verb>_<what>`` handlers bypass the builtin allowlist.

        ai-hub and other projects extend ``run`` / ``check`` via custom.mk. The
        continuous Makefile must discover those handlers and dispatch them
        instead of rejecting unknown WHATs as ``allowed:default``.
        """
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        body = rendered.split("define _dispatch", 1)[1].split("endef", 1)[0]
        tm.that("_custom_$(1)_$$what" in body, eq=True)
        tm.that("custom_rc" in body, eq=True)
        tm.that('$(SELF_MAKE) "$$custom"' in body, eq=True)
        recipe = [ln for ln in body.splitlines() if ln.startswith("\t")]
        broken = [ln for ln in recipe[:-1] if not ln.rstrip().endswith("\\")]
        tm.that(broken, eq=[])

    def test_repo_without_script_dispatch_omits_script_routing(
        self, tmp_path: Path
    ) -> None:
        """A repo with no script dispatch omits every script-routing projection."""
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        # No script routing leaks into non-opted-in repositories.
        tm.that("tr '-' '_'" in rendered, eq=False)
        tm.that("scripts/dispatch.py" in rendered, eq=False)

    def test_gen_replaces_codegen_as_the_single_conform_verb(
        self, tmp_path: Path
    ) -> None:
        """``make gen`` is THE conform verb; ``codegen`` no longer exists.

        The convergence spine (mro-e9j0.6 C7) fuses codegen+conform under the
        single short ``gen`` verb: one verb, one meaning. The old ``codegen``
        Make verb is fully replaced across config, rendered handlers, and the
        regeneration header.
        """
        make_config = config.Infra.codegen.make
        verb_names = {verb.name for verb in make_config.verbs}
        tm.that("gen" in verb_names, eq=True)
        tm.that("codegen" in verb_names, eq=False)
        gen = next(verb for verb in make_config.verbs if verb.name == "gen")
        tm.that(gen.default_what, eq="check")
        tm.that(gen.apply_guarded, eq=True)
        tm.that(hasattr(make_config, "serialization"), eq=False)
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        public_line = next(
            line for line in rendered.splitlines() if line.startswith("PUBLIC_VERBS :=")
        )
        tm.that(" gen" in public_line, eq=True)
        tm.that(" codegen" in public_line, eq=False)
        tm.that("_DEFAULT_gen := check" in rendered, eq=True)
        tm.that("_builtin_gen_check:" in rendered, eq=True)
        tm.that("_builtin_gen_apply:" in rendered, eq=True)
        tm.that("_builtin_codegen_check" in rendered, eq=False)
        tm.that("_builtin_codegen_apply" in rendered, eq=False)
        builtin_line = next(
            line
            for line in rendered.splitlines()
            if line.startswith("BUILTIN_VERBS :=")
        )
        tm.that(" gen" in builtin_line, eq=True)
        tm.that(" codegen" in builtin_line, eq=False)
        phony_line = next(
            line
            for line in rendered.splitlines()
            if line.startswith(".PHONY:") and "_builtin_" in line
        )
        tm.that("_builtin_gen_check" in phony_line, eq=True)
        tm.that("_builtin_gen_apply" in phony_line, eq=True)
        # Both handlers drive the conform engine (CLI namespace is unchanged).
        gen_check_body = rendered.split("_builtin_gen_check:", 1)[1].split("\n\n", 1)[0]
        tm.that(gen_check_body.count("codegen conform"), eq=1)
        tm.that("--mode check" in gen_check_body, eq=True)
        tm.that(gen_check_body, lacks=["codegen init", "deps modernize"])
        # The apply semantics live on _builtin_gen_all; _builtin_gen_apply aliases it.
        gen_all_body = rendered.split("_builtin_gen_all:", 1)[1].split("\n\n", 1)[0]
        tm.that(gen_all_body.count("codegen conform"), eq=1)
        tm.that("--mode apply" in gen_all_body, eq=True)
        tm.that(gen_all_body, lacks=["codegen init", "deps modernize"])
        tm.that("_require_apply" in gen_all_body, eq=True)
        gen_apply_body = rendered.split("_builtin_gen_apply:", 1)[1].split("\n\n", 1)[0]
        tm.that("_builtin_gen_all" in gen_apply_body, eq=True)
        # The regeneration contract published on every projection speaks gen.
        tm.that("# @flext-regenerate: make gen WHAT=apply APPLY=Y" in rendered, eq=True)
        # The custom-surface policy names gen (not codegen) for hooks/handlers.
        handler_policies: dict[str, m.Infra.CustomHandlerPolicy] = dict(
            config.Infra.codegen.make.custom_handler_policies
        )
        for policy in handler_policies.values():
            tm.that("|gen|" in policy.target_pattern, eq=True)
            tm.that("|codegen|" in policy.target_pattern, eq=False)

    # NOTE (mro-4gbp): a test asserting a downstream consumer's verbs from this
    # engine's catalog was removed. The engine is consumer-agnostic: a consumer
    # declares extra_verbs/script_dispatch in its OWN config/workspace.yaml. The
    # generic capability stays covered by the fixture-driven cases below.
    def test_script_dispatch_adds_scripts_to_lint_and_type_paths(
        self, tmp_path: Path
    ) -> None:
        """Opted-in repos scan scripts alongside src and tests."""
        rendered = self._render_root_makefile(
            tmp_path,
            extra_verbs=(
                m.Infra.MakeVerbSpec(
                    name="charts", default_what="all", whats=("all",), apply_what="all"
                ),
                m.Infra.MakeVerbSpec(
                    name="chart-release",
                    default_what="all",
                    whats=("all",),
                    apply_what="all",
                ),
                m.Infra.MakeVerbSpec(
                    name="bead", default_what="all", whats=("all",), apply_what="all"
                ),
            ),
            script_dispatch=m.Infra.ScriptDispatchSpec(
                dispatcher="scripts/dispatch.py", roots=("scripts",)
            ),
        )
        tm.that(
            "RUFF_PATHS := $(PROJECT_ROOT)/src $(PROJECT_ROOT)/tests $(PROJECT_ROOT)/scripts"
            in rendered,
            eq=True,
        )
        tm.that(
            "MYPY_PATHS := $(PROJECT_ROOT)/src $(PROJECT_ROOT)/tests $(PROJECT_ROOT)/scripts"
            in rendered,
            eq=True,
        )

    def test_repo_without_script_dispatch_retains_canonical_lint_and_type_paths(
        self, tmp_path: Path
    ) -> None:
        """A repo without script dispatch keeps src/tests paths and excludes scripts."""
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        tm.that(
            "RUFF_PATHS := $(PROJECT_ROOT)/src $(PROJECT_ROOT)/tests" in rendered,
            eq=True,
        )
        tm.that(
            "MYPY_PATHS := $(PROJECT_ROOT)/src $(PROJECT_ROOT)/tests" in rendered,
            eq=True,
        )
        tm.that("$(PROJECT_ROOT)/scripts" in rendered, eq=False)


__all__: list[str] = []
