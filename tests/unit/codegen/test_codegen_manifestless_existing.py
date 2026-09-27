"""Public regression coverage for manifestless existing repositories."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from flext_infra.codegen import FlextInfraCodegenConform
from flext_infra.workspace import FlextInfraWorkspaceDetector
from tests import c, u


# Exemplar: conform materializes a full managed tree on disk, so the render
# itself dominates the runtime. The class carries the config-owned slow budget
# (Infra.tooling.tools.pytest.slow-timeout-seconds) instead of a hardcoded
# ceiling, so a real hang still aborts at the declared wall.
@pytest.mark.slow
class TestsFlextInfraCodegenManifestlessExisting:
    def test_existing_root_uses_pep621_metadata_for_managed_artifacts(
        self, infra_git_repo: Path
    ) -> None:
        root = infra_git_repo
        repository = u.Tests.repository_ref(config.Infra.name)
        # Why: LICENSE has no generator and is genuinely exists_or_absent.
        # README.md is also externally_managed/exists_or_absent for conform's
        # managed-file surface, but `execute_request` runs the full apply
        # pipeline including docs generation, which regenerates README.md
        # from live project metadata regardless of prior content — so only
        # LICENSE is proven byte-preserved here.
        preserved = {"LICENSE": "existing license\n"}
        seeded = {**preserved, "README.md": "# Existing repository\n"}
        pyproject_source = tm.ok(u.Cli.files_read_text(Path.cwd() / "pyproject.toml"))
        tm.ok(u.Cli.atomic_write_text_file(root / "pyproject.toml", pyproject_source))
        package_init = root / "src" / "flext_infra" / "__init__.py"
        package_init.parent.mkdir(parents=True)
        tm.ok(u.Cli.atomic_write_text_file(package_init, ""))
        vscode_settings = root / ".vscode" / "settings.json"
        vscode_settings.parent.mkdir()
        tm.ok(
            u.Cli.atomic_write_text_file(
                vscode_settings,
                tm.ok(u.Cli.files_read_text(Path.cwd() / ".vscode" / "settings.json")),
            )
        )
        for relative, content in seeded.items():
            tm.ok(u.Cli.atomic_write_text_file(root / relative, content))
        u.Tests.write_project_beads_config(root, config.Infra.name)
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "--no-verify", "-m", "Seed manifestless tree"],
                cwd=root,
            )
        )

        derived = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        tm.that(derived.repository.name, eq=repository.name)
        tm.that(derived.repository.distribution, eq=repository.distribution)
        tm.that(derived.repository.path, eq=Path())
        tm.that(derived.project, eq=None)
        # Apply is complete or nothing: a partial surface is a check-only view.
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
        )
        tm.ok(FlextInfraCodegenConform.execute_request(request))
        initial_plan = tm.ok(
            FlextInfraCodegenConform(repository_root=root).plan(request)
        )
        plans = {
            file.path.relative_to(root).as_posix(): file for file in initial_plan.files
        }
        tm.that(
            sum(file.path == root / "pyproject.toml" for file in initial_plan.files),
            eq=1,
        )
        tm.that(u.Infra.codegen_file_requires_effect(plans["pyproject.toml"]), eq=False)

        # Why: .env.example carries no managed_files entry, so it is never
        # planned for an existing (manifestless) checkout.
        tm.that(".env.example" in plans, eq=False)
        tm.that((root / ".env.example").exists(), eq=False)
        # Why: LICENSE and README.md are not managed_files entries — conform
        # never plans them, so the preserved bytes are proven by direct read.
        for relative, content in preserved.items():
            tm.that(relative in plans, eq=False)
            tm.that((root / relative).read_text(encoding="utf-8"), eq=content)
        # Why: the real PEP 621-derived ProjectSpec (authors + upstream) now
        # resolves the tooling context correctly on the first pass, so these
        # managed files already converge after one apply — the fabricated
        # synthetic spec previously left them requiring a second pass.
        for required in ("Makefile", ".mise.toml", ".python-version", ".gitignore"):
            tm.that(u.Infra.codegen_file_requires_effect(plans[required]), eq=False)

        tm.ok(FlextInfraCodegenConform.execute_request(request))
        tm.that((root / ".env.example").exists(), eq=False)
        for relative, content in preserved.items():
            tm.that((root / relative).read_text(encoding="utf-8"), eq=content)
        tm.that((root / "README.md").is_file(), eq=True)
        for required in ("Makefile", ".mise.toml", ".python-version", ".gitignore"):
            tm.that((root / required).is_file(), eq=True)
        fixed_point = FlextInfraCodegenConform(repository_root=root).plan(
            request.model_copy(update={"mode": c.Infra.CodegenConformMode.CHECK})
        )
        verified = tm.ok(fixed_point)
        tm.that(
            tuple(
                file.path
                for file in verified.files
                if u.Infra.codegen_file_requires_effect(file)
            ),
            eq=(),
        )

    def test_root_distribution_owns_its_dependency_profile(
        self, tmp_path: Path
    ) -> None:
        """The foundation needs no runtime parent and declares its tooling source."""
        profile = next(
            item
            for item in config.Infra.codegen.scaffold.project.dependency_profiles
            if item.project is None
            and not any(
                other.upstream.replace("_", "-")
                in {u.Infra.dep_name(dependency) for dependency in item.runtime}
                for other in config.Infra.codegen.scaffold.project.dependency_profiles
                if other is not item and other.project is None
            )
        )
        distribution = profile.upstream.replace("_", "-")
        dev = tm.ok(
            u.Cli.json_dumps([
                *u.Tests.declared_requirements(
                    config.Infra.codegen.scaffold.project.dev, distribution=distribution
                )
            ])
        )
        root = tmp_path / distribution
        package = root / c.Infra.DEFAULT_SRC_DIR / profile.upstream
        package.mkdir(parents=True)
        tm.ok(u.Cli.atomic_write_text_file(package / "__init__.py", ""))
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "pyproject.toml",
                f'[project]\nname = "{distribution}"\nversion = "0.12.0.dev0"\n'
                f'description = "{distribution} root fixture"\n'
                f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
                'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
                f"dependencies = []\n[dependency-groups]\ndev = {dev}\n",
            )
        )
        u.Tests.write_project_beads_config(root, distribution)
        u.Tests.initialize_git_repo(
            root, origin_url=u.Tests.repository_ref(distribution).url
        )

        plan = tm.ok(
            FlextInfraCodegenConform(repository_root=root).plan(
                u.Tests.conform_request(
                    root,
                    what=c.Infra.CodegenConformSurface.PYPROJECT,
                    scope=c.Infra.CodegenConformScope.SELF,
                    mode=c.Infra.CodegenConformMode.CHECK,
                )
            )
        )
        rendered = u.Tests.codegen_file_text(
            next(file for file in plan.files if file.path.name == "pyproject.toml")
        )
        owned_runtime = tuple(
            dependency
            for dependency in profile.runtime
            if u.Infra.dep_name(dependency) != distribution
        )
        tm.that(
            set(owned_runtime).issubset(
                u.Tests.toml_strings_at(rendered, "project", "dependencies")
            ),
            eq=True,
        )


__all__: list[str] = ["TestsFlextInfraCodegenManifestlessExisting"]
