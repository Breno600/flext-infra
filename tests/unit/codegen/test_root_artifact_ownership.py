"""Public contract for governed repository-root artifact ownership.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, infra
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import c, m, u


class TestsFlextInfraRootArtifactOwnership:
    """Prove codegen config is the sole root-artifact ownership catalog."""

    @staticmethod
    def test_envrc_template_covers_every_repository_profile() -> None:
        """Every generated repository owns the same direnv activation contract."""
        entry = next(
            item
            for item in config.Infra.codegen.templates.entries
            if item.destination == c.Infra.ENVRC_FILENAME
        )

        tm.that(set(entry.profiles), eq=set(c.Infra.MakeProfile))

    @staticmethod
    def test_release_workflow_requires_explicit_repository_opt_in() -> None:
        """Package membership alone must never activate release automation."""
        entry = next(
            item
            for item in config.Infra.codegen.templates.entries
            if item.destination == ".github/workflows/release.yml"
        )

        tm.that(entry.requires_release_protocol, eq=True)

    @staticmethod
    def test_governed_artifacts_have_one_explicit_policy() -> None:
        """Test governed artifacts have one explicit policy."""
        configured = config.Infra.codegen.managed_files
        paths = tuple(item.path.as_posix() for item in configured)

        tm.that(len(paths), eq=len(set(paths)))
        github_templates = {
            Path(entry.destination)
            for entry in config.Infra.codegen.templates.entries
            if Path(entry.destination).parts[:1] == (".github",)
        }
        github_managed = {
            item.path: item
            for item in configured
            if item.path.parts[:1] == (".github",)
        }
        tm.that(set(github_managed), eq=github_templates)
        tm.that(github_templates, empty=False)
        for owned in github_managed.values():
            tm.that(owned.policy, eq="full")

    @staticmethod
    def test_every_packaged_github_template_is_declared() -> None:
        """Keep the packaged GitHub tree and typed render manifest bijective."""
        template_root = (
            Path(__file__).parents[3]
            / "src"
            / "flext_infra"
            / "templates"
            / "project"
            / "base"
        )
        physical = {
            path.relative_to(template_root).as_posix().removesuffix(".j2")
            for path in (template_root / ".github").rglob("*.j2")
            if "_fragments" not in path.relative_to(template_root).parts
        }
        declared = {
            entry.destination
            for entry in config.Infra.codegen.templates.entries
            if Path(entry.destination).parts[:1] == (".github",)
        }

        tm.that(physical, eq=declared)

    @staticmethod
    def test_github_template_without_managed_owner_is_rejected() -> None:
        """Reject any config where a GitHub projection escapes full ownership."""
        spec = config.Infra.codegen
        github_managed = tuple(
            item for item in spec.managed_files if item.path.parts[:1] == (".github",)
        )
        target = github_managed[0]
        mutated = spec.model_copy(
            update={
                "managed_files": tuple(
                    item for item in spec.managed_files if item.path != target.path
                ),
            },
        )

        with pytest.raises(ValueError, match="ownership mismatch"):
            type(spec).model_validate(mutated)

    @staticmethod
    def test_github_managed_owner_must_be_full() -> None:
        """Reject weaker policies for every config-declared GitHub artifact."""
        spec = config.Infra.codegen
        target = next(
            item for item in spec.managed_files if item.path.parts[:1] == (".github",)
        )
        mutated = spec.model_copy(
            update={
                "managed_files": tuple(
                    item.model_copy(update={"policy": "merge"})
                    if item.path == target.path
                    else item
                    for item in spec.managed_files
                ),
            },
        )

        with pytest.raises(ValueError, match="must be full-managed"):
            type(spec).model_validate(mutated)

    @staticmethod
    def test_conform_uses_one_fixed_point_plan(infra_git_repo: Path) -> None:
        """Test conform uses one fixed point plan."""
        root = infra_git_repo
        project = u.Tests.project_spec("flext-demo")
        u.Tests.write_project_beads_config(root, "flext-demo")
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
                    f'authors = [{{name = "{project.author_name}", email = "{project.author_email}"}}]\n'
                    f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
                    f'dependencies = ["{u.Tests.flext_source(project.upstream)}"]\n'
                    "[project.urls]\n"
                    'Repository = "https://github.com/flext-sh/flext-demo"\n'
                ),
            ),
        )
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            mode=c.Infra.CodegenConformMode.APPLY,
        )
        tm.ok(infra.codegen_conform(request))
        manual = {"custom.mk": b"# manual project extension\n"}
        (root / "custom.mk").write_bytes(manual["custom.mk"])
        configured_policies = {
            root / item.path: item.policy
            for item in config.Infra.codegen.managed_files
            if item.path.as_posix() in c.Infra.MAKEFILE_BOOTSTRAP_DESTINATIONS
        }
        before = tuple(
            sorted(
                (path.relative_to(root).as_posix(), path.read_bytes())
                for path in root.rglob("*")
                if path.is_file() and ".git" not in path.relative_to(root).parts
            ),
        )

        first = infra.codegen_conform(request)
        result = tm.ok(first)
        governed = tuple(file for file in result.plan.files if file.policy is not None)
        tm.that(
            {file.path: file.policy for file in governed},
            eq=configured_policies,
        )
        tm.that(result.written_files, eq=())
        after = tuple(
            sorted(
                (path.relative_to(root).as_posix(), path.read_bytes())
                for path in root.rglob("*")
                if path.is_file() and ".git" not in path.relative_to(root).parts
            ),
        )
        tm.that(after, eq=before)
        for relative, expected in manual.items():
            tm.that((root / relative).read_bytes(), eq=expected)

    class TestsConformPlanNetworkBoundary:
        """The conform plan is a repository-local, offline inventory."""

        @staticmethod
        @pytest.mark.slow
        def test_plan_never_fetches_origin(infra_git_repo: Path) -> None:
            """Planning consumes the existing origin ref without network access."""
            root = infra_git_repo
            dist = u.Tests.repository_ref(config.Infra.name).distribution
            u.Tests.write_project_beads_config(root, dist)
            tm.ok(
                u.Cli.atomic_write_text_file(
                    root / "pyproject.toml",
                    f'[project]\nname = "{dist}"\nversion = "0.12.0.dev0"\n'
                    f'description = "{dist} governed fixture"\n'
                    f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
                    'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
                    'dependencies = ["flext-core>=0.1.0"]\n',
                ),
            )
            package_init = root / "src" / dist.replace("-", "_") / "__init__.py"
            package_init.parent.mkdir(parents=True, exist_ok=True)
            tm.ok(u.Cli.atomic_write_text_file(package_init, ""))
            tests_init = root / "tests" / "__init__.py"
            tests_init.parent.mkdir(parents=True, exist_ok=True)
            tm.ok(u.Cli.atomic_write_text_file(tests_init, ""))
            for relative_parent in (
                ".beads",
                ".github/ci-template",
                ".github/prompts",
                ".github/scripts",
                ".github/workflows",
                "config",
                "tests/fixtures/ci/docker",
            ):
                root.joinpath(relative_parent).mkdir(parents=True, exist_ok=True)
            u.Tests.commit_git_changes(root, "Seed manifest-less topology")
            # Ownership is resolved from the declared provider URL, so the remote
            # keeps it. What is removed is the local rewrite target the fixture
            # installed: any fetch would then have to leave this machine, and a
            # plan that stays offline never notices.
            (root.parent / "origin.git").rename(root.parent / "origin.git.removed")
            request = m.Infra.CodegenConformRequest(root=root)
            tm.ok(
                FlextInfraCodegenConform(repository_root=root, request=request).plan(
                    request,
                ),
            )
