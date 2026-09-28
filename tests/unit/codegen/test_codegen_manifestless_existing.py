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
        package_name = u.Infra.project_package_name(Path.cwd())
        package_init = root / c.Infra.DEFAULT_SRC_DIR / package_name / "__init__.py"
        package_init.parent.mkdir(parents=True)
        tm.ok(u.Cli.atomic_write_text_file(package_init, ""))
        # The copied manifest declares scripts and entry points; conform's
        # fresh-import gate loads each one, so the seeded tree carries every
        # declared target (module and attribute) inside its own package —
        # never a copy of the whole production package.
        manifest = tm.not_none(u.Cli.toml_mapping_from_text(pyproject_source))
        project_table = u.Cli.json_as_mapping(
            u.Cli.toml_mapping_child(manifest, "project")
        )
        entry_groups = u.Cli.json_as_mapping(
            u.Cli.toml_mapping_child(project_table, "entry-points")
        )
        declared_groups = (
            u.Cli.json_as_mapping(u.Cli.toml_mapping_child(project_table, "scripts")),
            u.Cli.json_as_mapping(
                u.Cli.toml_mapping_child(project_table, "gui-scripts")
            ),
            *(u.Cli.json_as_mapping(group) for group in entry_groups.values()),
        )
        targets: dict[Path, set[str]] = {}
        for entries in declared_groups:
            for target in entries.values():
                module_name, _, attribute = str(target).partition(":")
                module_path = (
                    root / c.Infra.DEFAULT_SRC_DIR / Path(*module_name.split("."))
                ).with_suffix(".py")
                targets.setdefault(module_path, set()).add(attribute.split(".")[0])
        for module_path, attributes in targets.items():
            tm.ok(
                u.Cli.atomic_write_text_file(
                    module_path,
                    "".join(
                        f"class {attribute}:\n    pass\n\n\n"
                        for attribute in sorted(attributes)
                    ),
                )
            )
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
        """The tree's root declares no flext runtime dependency and still conforms.

        Since 208716f4f the checkout must declare the infrastructure line it
        consumes; a manifestless root declares it the way a real member does,
        through its development group's direct Git source.
        """
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
        # Every internal development dependency the SSOT requires carries its
        # own direct Git source, exactly as a real standalone member declares.
        internal_dev = tuple(
            u.Tests.repository_ref(name)
            for name in dict.fromkeys(
                u.Infra.dep_name(requirement)
                for requirement in (
                    config.Infra.codegen.infra_repository.distribution,
                    *config.Infra.codegen.scaffold.project.dev,
                )
            )
            if name is not None and name.startswith("flext-")
        )
        dev_group = ", ".join(
            f'"{ref.distribution} @ git+{ref.url}@{u.Tests.provider_branch()}"'
            for ref in internal_dev
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
                "dependencies = []\n"
                "\n[dependency-groups]\n"
                f"dev = [{dev_group}]\n",
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
        tm.that(owned_runtime[0] in rendered, eq=True)
