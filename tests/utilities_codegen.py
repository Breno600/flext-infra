"""Codegen and lazy-init fixture test utilities for flext-infra."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_core import r
from flext_infra import config, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.codegen.consolidator import FlextInfraCodegenConsolidator
from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit
from tests import c, m, p, t
from tests.utilities_fixture_project import TestsFlextInfraUtilitiesProjectFixtureMixin
from tests.utilities_git import TestsFlextInfraUtilitiesGitMixin


class TestsFlextInfraUtilitiesCodegenMixin:
    """Codegen and lazy-init workspace fixture helpers."""

    @staticmethod
    def ruff_per_file_ignores_toml() -> str:
        """Render the fleet Ruff policy as a pyproject fragment.

        Reads the same typed SSOT production reads (P0): fixture
        workspaces carry the real policy — select, ignore, preview and
        the per-file-ignores map — never a hand-rolled fragment.
        """
        ruff_cfg = config.Infra.tooling.tools.ruff
        select = ", ".join(f'"{rule}"' for rule in sorted(ruff_cfg.lint.select))
        ignore = ", ".join(
            f'"{rule}"'
            for rule in sorted({
                *ruff_cfg.lint.ignore,
                *ruff_cfg.lint.ignored_rule_rationales,
            })
        )
        quoted_rules = {
            pattern: ", ".join(f'"{rule}"' for rule in rules)
            for pattern, rules in sorted(ruff_cfg.lint.per_file_ignores.items())
        }
        rows = "\n".join(
            f'"{pattern}" = [{names}]' for pattern, names in quoted_rules.items()
        )
        isort = ruff_cfg.lint.isort
        # Why: without the fleet's isort settings (combine-as-imports in
        # particular), a fixture-generated `X, X as alias` combined import —
        # the real lazy-facade pattern flext-infra's own __init__.py uses —
        # fails ruff's default isort split, unlike production.
        return (
            f"[tool.ruff]\npreview = {str(ruff_cfg.preview).lower()}\n\n"
            f"[tool.ruff.lint]\nselect = [{select}]\nignore = [{ignore}]\n\n"
            "[tool.ruff.lint.isort]\n"
            f"combine-as-imports = {str(isort.combine_as_imports).lower()}\n"
            f"force-single-line = {str(isort.force_single_line).lower()}\n"
            f"split-on-trailing-comma = {str(isort.split_on_trailing_comma).lower()}\n\n"
            f"[tool.ruff.lint.per-file-ignores]\n{rows}\n"
        )

    @staticmethod
    def conform_request(
        root: Path,
        *,
        what: c.Infra.CodegenConformSurface = c.Infra.CodegenConformSurface.ALL,
        scope: c.Infra.CodegenConformScope = c.Infra.CodegenConformScope.SELF,
        mode: c.Infra.CodegenConformMode = c.Infra.CodegenConformMode.CHECK,
    ) -> m.Infra.CodegenConformRequest:
        """Build one codegen conform request; every default is the model's own."""
        return m.Infra.CodegenConformRequest(
            root=root, what=what, scope=scope, mode=mode
        )

    @staticmethod
    def conform_plan(
        root: Path, workspace: m.Infra.WorkspaceSpec
    ) -> m.Infra.CodegenPlan:
        """Plan one fixture workspace through the public conform boundary."""
        request = TestsFlextInfraUtilitiesCodegenMixin.conform_request(root)
        return tm.ok(
            FlextInfraCodegenConform(
                repository_root=root, request=request, initial_workspace=workspace
            ).plan(request)
        )

    @staticmethod
    def scaffold_plan(
        root: Path, *, members: t.StrSequence = ()
    ) -> m.Infra.CodegenPlan:
        """Plan every artifact conform renders for a fresh repository scaffold.

        Without members the fixture repository is standalone; each member
        makes it a workspace composing that project, so generated surfaces
        are observed exactly as the public codegen owner renders them.
        """
        fixture = TestsFlextInfraUtilitiesProjectFixtureMixin
        repository = fixture.repository_ref(
            "fixture-project",
            role=(
                c.Infra.MakeProfile.WORKSPACE
                if members
                else c.Infra.MakeProfile.STANDALONE
            ),
        )
        return TestsFlextInfraUtilitiesCodegenMixin.conform_plan(
            root,
            fixture.workspace_spec(
                repository,
                project=fixture.project_spec(repository.name),
                subprojects=tuple(
                    fixture.repository_ref(name, path=Path(name)) for name in members
                ),
            ),
        )

    @staticmethod
    def scaffold_text(
        root: Path, destination: str, *, members: t.StrSequence = ()
    ) -> str:
        """Return one rendered scaffold artifact, failing when it is not planned."""
        return tm.not_none(
            TestsFlextInfraUtilitiesCodegenMixin.planned_text(
                TestsFlextInfraUtilitiesCodegenMixin.scaffold_plan(
                    root, members=members
                ),
                destination,
            )
        )

    @staticmethod
    def governed_project_plan(root: Path) -> m.Infra.CodegenPlan:
        """Plan every declared artifact of one governed fixture project read-only."""
        for entry in config.Infra.codegen.templates.entries:
            destination = entry.destination.format(
                package_name="fixture_project", ns="fixture_project"
            )
            (root / destination).parent.mkdir(parents=True, exist_ok=True)
        for managed in config.Infra.codegen.managed_files:
            (root / managed.path).parent.mkdir(parents=True, exist_ok=True)
        # Scaffold entries create declaration family directories, and the
        # facade completeness law rejects owners without their public facade.
        package_dir = root / "src" / "fixture_project"
        for family in ("u", "p"):
            facade = package_dir / f"{c.Infra.FAMILY_PUBLIC_MODULES[family]}.py"
            if (package_dir / c.Infra.FAMILY_DIRECTORIES[family]).is_dir() and (
                not facade.is_file()
            ):
                facade.write_text(
                    f"class FixtureProject{family.capitalize()}Facade:\n    pass\n",
                    encoding="utf-8",
                )
        result = FlextInfraCodegenConform(repository_root=root).plan(
            TestsFlextInfraUtilitiesCodegenMixin.conform_request(root)
        )
        return m.Infra.CodegenPlan.model_validate(tm.ok(result))

    @staticmethod
    def planned_text(plan: m.Infra.CodegenPlan, destination: str) -> str | None:
        """Return the desired text of the plan entry ending with ``destination``."""
        match = next(
            (item for item in plan.files if item.path.as_posix().endswith(destination)),
            None,
        )
        return (
            None
            if match is None or match.desired_content is None
            else tm.not_none(match.desired_content).decode(c.Cli.ENCODING_DEFAULT)
        )

    @staticmethod
    def create_lazy_init_workspace(
        tmp_path: Path,
        *,
        project_name: str = "flext-test-project",
        package_name: str = "flext_test_project",
    ) -> t.Pair[Path, Path]:
        """Provide the typed test helper `create_lazy_init_workspace`."""
        repository_root = tmp_path / project_name
        package_root = repository_root / c.Infra.DEFAULT_SRC_DIR / package_name
        package_root.mkdir(parents=True)
        (repository_root / "Makefile").write_text(
            "check:\n\t@true\n", encoding=c.Infra.ENCODING_DEFAULT
        )
        (repository_root / c.PYPROJECT_FILENAME).write_text(
            (
                f'[project]\nname = "{project_name}"\nversion = "0.1.0"\n\n'
                + TestsFlextInfraUtilitiesCodegenMixin.ruff_per_file_ignores_toml()
            ),
            encoding=c.Infra.ENCODING_DEFAULT,
        )
        (package_root / c.Infra.INIT_PY).write_text(
            "", encoding=c.Infra.ENCODING_DEFAULT
        )
        TestsFlextInfraUtilitiesProjectFixtureMixin.write_project_beads_config(
            repository_root, project_name
        )
        # Semantic publication authenticates every changed path against its Git
        # checkout.  The shared workspace fixture therefore owns a real,
        # repository-local identity instead of letting individual tests depend
        # on whichever checkout happens to contain ``tmp_path``.
        TestsFlextInfraUtilitiesGitMixin.initialize_git_repo(repository_root)
        return (repository_root, package_root)

    @staticmethod
    def write_lazy_init_namespace_module(
        module_path: Path,
        *,
        class_name: str,
        alias: str,
        docstring: str = "Test namespace.",
        extra_class_names: t.StrSequence = (),
    ) -> None:
        """Write a namespace module fixture for lazy-export tests."""
        export_list = f'"{class_name}", "{alias}"'
        extra_classes = "".join(
            f"\nclass {extra_class_name}:\n    pass\n"
            for extra_class_name in extra_class_names
        )
        module_path.write_text(
            (
                f'"""{docstring}"""\n\n'
                "from __future__ import annotations\n\n"
                f"__all__: list[str] = [{export_list}]\n\n"
                f"class {class_name}:\n"
                "    pass\n\n"
                f"{alias} = {class_name}\n"
                f"{extra_classes}"
            ),
            encoding=c.Infra.ENCODING_DEFAULT,
        )

    @staticmethod
    def write_lazy_init_version_module(package_root: Path) -> None:
        """Write a version module fixture for lazy-export tests."""
        (package_root / "__version__.py").write_text(
            ('__version__ = "0.1.0"\n__version_info__ = (0, 1, 0)\n'),
            encoding=c.Infra.ENCODING_DEFAULT,
        )

    @staticmethod
    def run_lazy_init(repository_root: Path, *, check_only: bool = False) -> int:
        """Materialize immutable lazy-init plans only inside test workspaces."""
        service = FlextInfraCodegenLazyInit(repository_root=repository_root)
        planned = service.plan_files().unwrap()
        changed = tuple(
            plan for plan in planned.files if u.Infra.codegen_file_requires_effect(plan)
        )
        if check_only:
            return len(changed)
        materialized = TestsFlextInfraUtilitiesCodegenMixin.materialize_lazy_init(
            service
        )
        return 0 if materialized.success else 1

    @staticmethod
    def plan_lazy_init(repository_root: Path) -> p.Result[m.Infra.CodegenPhaseAnalysis]:
        """Return the lazy-init planning receipt WITHOUT unwrapping it.

        Refusing to plan is a first-class planning outcome — ambiguous export
        ownership stops the phase before a single file plan is built. A helper
        that unwraps turns that refusal into an exception and makes the
        pre-effect contract unobservable through the public surface.
        """
        return FlextInfraCodegenLazyInit(repository_root=repository_root).plan_files()

    @staticmethod
    def materialize_lazy_init(service: FlextInfraCodegenLazyInit) -> p.Result[bool]:
        """Publish one service plan through canonical guarded file primitives."""
        planned = service.plan_files()
        if planned.failure:
            return r[bool].from_failure(planned)
        return TestsFlextInfraUtilitiesCodegenMixin.materialize_codegen_plans(
            r[tuple[m.Infra.CodegenFilePlan, ...]].ok(planned.value.files)
        )

    @staticmethod
    def materialize_codegen_plans(
        planned: p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]],
    ) -> p.Result[bool]:
        """Publish immutable codegen plans only inside test workspaces."""
        if planned.failure:
            return r[bool].from_failure(planned)
        changed = tuple(
            plan for plan in planned.value if u.Infra.codegen_file_requires_effect(plan)
        )
        for plan in changed:
            before = u.Infra.codegen_file_before_state(plan)
            if plan.desired_content is not None and (
                before.failure or before.value.parent_inode is None
            ):
                # Planning is read-only, so a destination planned into an absent
                # directory chain carries no parent identity. Like the
                # transaction owner at apply, the publisher materializes the
                # chain and reads the destination again before publishing.
                plan.path.parent.mkdir(parents=True, exist_ok=True)
                before = u.Cli.atomic_read_binary_file_state(plan.path)
            if before.failure:
                return r[bool].from_failure(before)
            if plan.desired_content is None:
                result = u.Cli.atomic_delete_binary_file_guarded(before.value)
            else:
                if plan.desired_mode is None:
                    return r[bool].fail(
                        f"lazy-init plan has no desired mode: {plan.path}"
                    )
                result = u.Cli.atomic_write_binary_file_guarded(
                    before.value,
                    plan.desired_content,
                    permission_mode=plan.desired_mode,
                )
            if result.failure:
                return r[bool].from_failure(result)
        return r[bool].ok(True)

    @staticmethod
    def create_lazy_init_service(repository_root: Path) -> FlextInfraCodegenLazyInit:
        """Provide the typed test helper `create_lazy_init_service`."""
        return FlextInfraCodegenLazyInit(repository_root=repository_root)

    @staticmethod
    def lazy_init_scenario(
        tmp_path: Path,
    ) -> t.Triple[Path, Path, FlextInfraCodegenLazyInit]:
        """Create the workspace, write its namespace module, build the service."""
        repository_root, package_root = (
            TestsFlextInfraUtilitiesCodegenMixin.create_lazy_init_workspace(tmp_path)
        )
        TestsFlextInfraUtilitiesCodegenMixin.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        init_path = package_root / c.Infra.INIT_PY
        service = TestsFlextInfraUtilitiesCodegenMixin.create_lazy_init_service(
            repository_root
        )
        return package_root, init_path, service

    @staticmethod
    def extract_lazy_init_exports(source: str) -> t.Pair[bool, t.StrSequence]:
        """Read the published lazy export contract from generated source."""
        assignments = dict(u.Infra.get_module_level_assignments(source))
        all_value = assignments.get(c.Infra.DUNDER_ALL)
        if all_value is None:
            return (False, ())
        literal_exports = tuple(c.Tests.LAZY_INIT_EXPORT_NAME_RE.findall(all_value))
        if literal_exports:
            return (True, literal_exports)
        public_value = assignments.get("_PUBLIC_EXPORTS", "")
        return (
            "_PUBLIC_EXPORTS" in all_value,
            tuple(c.Tests.LAZY_INIT_EXPORT_NAME_RE.findall(public_value)),
        )

    @staticmethod
    def consolidate_codegen(
        *, repository_root: Path, project: str | None = None, dry_run: bool = True
    ) -> p.Result[str]:
        """Provide the typed test helper `consolidate_codegen`."""
        service: FlextInfraCodegenConsolidator = FlextInfraCodegenConsolidator(
            repository_root=repository_root, dry_run=dry_run, project_name=project
        )
        result: p.Result[str] = service.execute()
        return result


__all__: list[str] = ["TestsFlextInfraUtilitiesCodegenMixin"]
