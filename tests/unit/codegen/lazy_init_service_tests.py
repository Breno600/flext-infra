"""Public service tests for lazy-init execution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit
from tests import c, u

if TYPE_CHECKING:
    from tests import p, t


# NOTE (multi-agent, flext-wkii.17.15): prove scoped writes and read-only drift publicly.
class TestsFlextInfraCodegenLazyInitService:
    """Validate real service execution without mocks or internal branching asserts."""

    @staticmethod
    def read_only_check_result(
        repository_root: Path,
        package_root: Path,
        *,
        check_only: bool = True,
        apply_changes: bool = False,
        dry_run: bool = False,
    ) -> t.Quad[FlextInfraCodegenLazyInit, p.Result[bool], Path, bytes]:
        """Run one lazy-init pass without writing and return its observable drift."""
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        init_path = package_root / c.Infra.INIT_PY
        original_init = init_path.read_bytes()
        service = u.Tests.create_lazy_init_service(repository_root)
        service.target_module = "flext_test_project"
        service.check_only = check_only
        service.apply_changes = apply_changes
        service.dry_run = dry_run

        result = service.execute()
        return service, result, init_path, original_init

    def test_execute_applies_only_selected_root_artifact_set(
        self, tmp_path: Path
    ) -> None:
        """Apply writes one initializer for exactly the selected package root."""
        _, selected_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-test-selected",
            package_name="flext_test_selected",
        )
        _, unrelated_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-test-unrelated",
            package_name="flext_test_unrelated",
        )
        # A multi-project root is a workspace that declares its members; an
        # undeclared nested Git checkout is foreign and is never indexed.
        u.Tests.declare_workspace_projects(
            tmp_path, ("flext-test-selected", "flext-test-unrelated")
        )
        u.Tests.write_lazy_init_namespace_module(
            selected_root / "models.py",
            class_name="FlextTestsSelectedModels",
            alias="m",
        )
        u.Tests.write_lazy_init_namespace_module(
            unrelated_root / "models.py",
            class_name="FlextTestsUnrelatedModels",
            alias="m",
        )
        unrelated_init = unrelated_root / c.Infra.INIT_PY
        unrelated_before = unrelated_init.read_bytes()
        service = u.Tests.create_lazy_init_service(tmp_path)
        service.target_module = "flext_test_selected"
        service.apply_changes = True

        result = u.Tests.materialize_lazy_init(service)

        tm.that(result.success, eq=True)
        tm.that((selected_root / c.Infra.INIT_PY).read_bytes(), ne=b"")
        tm.that((selected_root / "__unit__.py").exists(), eq=False)
        tm.that(unrelated_init.read_bytes(), eq=unrelated_before)
        tm.that((unrelated_root / "__unit__.py").exists(), eq=False)
        tm.that(service.modified_files, eq=(str(selected_root / c.Infra.INIT_PY),))

    def test_selected_root_reads_its_own_declared_public_contract(
        self, tmp_path: Path
    ) -> None:
        """Keep distinct root ABI declarations isolated across source roots."""
        repository_root, selected_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-test-selected",
            package_name="flext_test_selected",
        )
        _, unrelated_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-test-unrelated",
            package_name="flext_test_unrelated",
        )
        selected_root.joinpath(c.Infra.INIT_PY).write_text(
            '__all__ = ["FlextTestsSelectedModels", "m"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        unrelated_init = unrelated_root / c.Infra.INIT_PY
        unrelated_init.write_text(
            '__all__ = ["FlextTestsUnrelatedModels", "m"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        u.Tests.write_lazy_init_namespace_module(
            selected_root / "models.py",
            class_name="FlextTestsSelectedModels",
            alias="m",
        )
        u.Tests.write_lazy_init_namespace_module(
            unrelated_root / "models.py",
            class_name="FlextTestsUnrelatedModels",
            alias="m",
        )
        unrelated_before = unrelated_init.read_bytes()
        service = u.Tests.create_lazy_init_service(repository_root)
        service.target_module = "flext_test_selected"
        service.apply_changes = True

        result = u.Tests.materialize_lazy_init(service)
        selected_generated = selected_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )

        tm.that(result.success, eq=True)
        tm.that(selected_generated, contains="FlextTestsSelectedModels")
        tm.that(selected_generated, lacks="FlextTestsUnrelatedModels")
        tm.that(unrelated_init.read_bytes(), eq=unrelated_before)

    def test_root_aggregates_declared_module_and_subpackage_publics(
        self, tmp_path: Path
    ) -> None:
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        package_root.joinpath("runner.py").write_text(
            'class FlextTestsLibraryRunner:\n    """Root runner."""\n\n'
            '__all__ = ["FlextTestsLibraryRunner"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        services_root = package_root / "services"
        services_root.mkdir()
        services_root.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        services_root.joinpath("dbt.py").write_text(
            'class FlextTestsDbtServiceBase:\n    """DBT service."""\n\n'
            '__all__ = ["FlextTestsDbtServiceBase"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        service = u.Tests.create_lazy_init_service(repository_root)
        service.apply_changes = True

        result = u.Tests.materialize_lazy_init(service)
        generated_root = package_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )
        generated_services = services_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )

        tm.that(result.success, eq=True)
        tm.that(generated_root, contains="FlextTestsLibraryRunner")
        tm.that(generated_root, contains="FlextTestsDbtServiceBase")
        tm.that(generated_services, contains="FlextTestsDbtServiceBase")

    def test_target_plans_private_children_without_writing_them(
        self, tmp_path: Path
    ) -> None:
        """A selected root consumes child plans while writing only its own init."""
        repository_root, selected_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-test-selected",
            package_name="flext_test_selected",
        )
        u.Tests.write_lazy_init_namespace_module(
            selected_root / "models.py",
            class_name="FlextTestsSelectedModels",
            alias="m",
        )
        private_child = selected_root / "_utilities"
        private_child.mkdir()
        child_init = private_child / c.Infra.INIT_PY
        child_init.write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        child_init_before = child_init.read_bytes()
        private_child.joinpath("conversion.py").write_text(
            "class FlextTestsConversion:\n"
            '    """Established direct root import."""\n\n'
            '__all__ = ["FlextTestsConversion"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        selected_root.joinpath(c.Infra.INIT_PY).write_text(
            "_DIRECT_IMPORTS = (\n"
            '    "FlextTestsConversion",\n'
            '    "FlextTestsSelectedModels",\n'
            '    "build_lazy_import_map",\n'
            '    "install_lazy_exports",\n'
            '    "m",\n'
            ")\n"
            '__all__ = ["FlextTestsSelectedModels", "m"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        service = u.Tests.create_lazy_init_service(repository_root)
        service.target_module = "flext_test_selected"
        service.apply_changes = True

        result = u.Tests.materialize_lazy_init(service)
        generated_root = selected_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )

        tm.that(result.success, eq=True)
        tm.that(generated_root, lacks="FlextTestsConversion")
        tm.that(child_init.read_bytes(), eq=child_init_before)
        tm.that(service.modified_files, eq=(str(selected_root / c.Infra.INIT_PY),))

    def test_explicit_wrapper_target_generates_only_that_initializer(
        self, tmp_path: Path
    ) -> None:
        """Generate a declared examples root without widening default scope."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        production_init = package_root / c.Infra.INIT_PY
        production_before = production_init.read_bytes()
        examples_root = repository_root / c.Infra.DIR_EXAMPLES
        examples_root.mkdir()
        examples_init = examples_root / c.Infra.INIT_PY
        examples_init.write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        examples_root.joinpath("demo.py").write_text(
            'class ExamplesDemo:\n    """Example boundary."""\n\n'
            '__all__ = ["ExamplesDemo"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        service = u.Tests.create_lazy_init_service(repository_root)
        service.target_module = c.Infra.DIR_EXAMPLES
        service.apply_changes = True

        result = u.Tests.materialize_lazy_init(service)
        generated = examples_init.read_text(encoding=c.Cli.ENCODING_DEFAULT)

        tm.that(result.success, eq=True)
        tm.that(generated, contains="from .demo import ExamplesDemo")
        tm.that(generated, contains="ExamplesDemo")
        tm.that(generated, contains='"ExamplesDemo"')
        tm.that(generated, contains="install_lazy_exports")
        tm.that(production_init.read_bytes(), eq=production_before)
        tm.that(service.modified_files, eq=(str(examples_init),))

    def test_explicit_tests_target_generates_only_facade_exports(
        self, tmp_path: Path
    ) -> None:
        """Keep test aliases while excluding collected test classes."""
        repository_root, _package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        tests_root = repository_root / c.Infra.DIR_TESTS
        tests_root.mkdir()
        tests_init = tests_root / c.Infra.INIT_PY
        tests_init.write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        u.Tests.write_lazy_init_namespace_module(
            tests_root / "constants.py",
            class_name="TestsFlextTestsConstants",
            alias="c",
        )
        u.Tests.write_lazy_init_namespace_module(
            tests_root / "utilities.py",
            class_name="TestsFlextTestsUtilities",
            alias="u",
        )
        unit_root = tests_root / "unit"
        unit_root.mkdir()
        unit_root.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        unit_root.joinpath("test_noise.py").write_text(
            'class TestsCollectedNoise:\n    """Collected test class."""\n\n'
            '__all__ = ["TestsCollectedNoise"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        service = u.Tests.create_lazy_init_service(repository_root)
        service.target_module = c.Infra.DIR_TESTS
        service.apply_changes = True

        result = u.Tests.materialize_lazy_init(service)
        generated = tests_init.read_text(encoding=c.Cli.ENCODING_DEFAULT)

        tm.that(result.success, eq=True)
        tm.that(generated, contains="TestsFlextTestsConstants")
        tm.that(generated, contains="TestsFlextTestsUtilities")
        tm.that(generated, contains="install_lazy_exports")
        tm.that(generated, lacks='"tm"')
        tm.that(generated, lacks="TestsCollectedNoise")
        tm.that(generated, lacks=".unit.test_noise")
        child_generated = unit_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )
        tm.that(child_generated, contains="TestsCollectedNoise")
        tm.that(child_generated, contains="install_lazy_exports")

    def test_check_mode_is_read_only_and_reports_drift(self, tmp_path: Path) -> None:
        """Check reports missing generated artifacts as a failure without writing."""
        service, result, init_path, original_init = (
            TestsFlextInfraCodegenLazyInitService.read_only_check_result(
                *u.Tests.create_lazy_init_workspace(tmp_path)
            )
        )
        package_root = init_path.parent

        tm.that(result.success, eq=False)
        tm.that(init_path.read_bytes(), eq=original_init)
        tm.that((package_root / "__unit__.py").exists(), eq=False)
        tm.that(service.modified_files, eq=(str(init_path),))

    def test_dry_run_is_read_only_even_when_apply_is_requested(
        self, tmp_path: Path
    ) -> None:
        """Explicit dry-run wins over apply and reports drift without writing."""
        service, result, init_path, original_init = (
            TestsFlextInfraCodegenLazyInitService.read_only_check_result(
                *u.Tests.create_lazy_init_workspace(tmp_path),
                apply_changes=True,
                dry_run=True,
            )
        )
        package_root = init_path.parent

        tm.that(result.success, eq=False)
        tm.that(init_path.read_bytes(), eq=original_init)
        tm.that((package_root / "__unit__.py").exists(), eq=False)
        tm.that(service.modified_files, eq=(str(init_path),))

    def test_second_check_is_byte_idempotent(self, tmp_path: Path) -> None:
        """A check after apply succeeds and preserves the generated initializer."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        init_path = package_root / c.Infra.INIT_PY
        apply_service = u.Tests.create_lazy_init_service(repository_root)
        apply_service.target_module = "flext_test_project"
        apply_service.apply_changes = True

        apply_result = u.Tests.materialize_lazy_init(apply_service)
        generated_init = init_path.read_bytes()
        check_service = u.Tests.create_lazy_init_service(repository_root)
        check_service.target_module = "flext_test_project"
        check_service.check_only = True
        check_result = check_service.execute()

        tm.that(apply_result.success, eq=True)
        tm.that(check_result.success, eq=True)
        tm.that(check_service.modified_files, eq=())
        tm.that(init_path.read_bytes(), eq=generated_init)
        tm.that((package_root / "__unit__.py").exists(), eq=False)

    def test_unknown_target_fails_without_workspace_fallback(
        self, tmp_path: Path
    ) -> None:
        """An unknown target fails loudly instead of planning the full workspace."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        init_path = package_root / c.Infra.INIT_PY
        original_init = init_path.read_bytes()
        service = u.Tests.create_lazy_init_service(repository_root)
        service.target_module = "flext_missing"
        service.apply_changes = True

        result = u.Tests.materialize_lazy_init(service)

        tm.that(result.success, eq=False)
        tm.that(init_path.read_bytes(), eq=original_init)
        tm.that((package_root / "__unit__.py").exists(), eq=False)
        tm.that(service.modified_files, eq=())

    def test_ambiguous_target_fails_without_writing_either_project(
        self, tmp_path: Path
    ) -> None:
        """Duplicate package roots fail instead of selecting a collapsed map entry."""
        _, first_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-test-first", package_name="flext_shared"
        )
        _, second_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-test-second", package_name="flext_shared"
        )
        u.Tests.declare_workspace_projects(
            tmp_path, ("flext-test-first", "flext-test-second")
        )
        u.Tests.write_lazy_init_namespace_module(
            first_root / "models.py", class_name="FlextTestsFirstModels", alias="m"
        )
        u.Tests.write_lazy_init_namespace_module(
            second_root / "models.py", class_name="FlextTestsSecondModels", alias="m"
        )
        first_init = first_root / c.Infra.INIT_PY
        second_init = second_root / c.Infra.INIT_PY
        first_before = first_init.read_bytes()
        second_before = second_init.read_bytes()
        service = u.Tests.create_lazy_init_service(tmp_path)
        service.target_module = "flext_shared"
        service.apply_changes = True

        result = u.Tests.materialize_lazy_init(service)

        tm.that(result.success, eq=False)
        tm.that(first_init.read_bytes(), eq=first_before)
        tm.that(second_init.read_bytes(), eq=second_before)
        tm.that((first_root / "__unit__.py").exists(), eq=False)
        tm.that((second_root / "__unit__.py").exists(), eq=False)
        tm.that(service.modified_files, eq=())

    # flext-96j2.4 (agent: claude): lint runs as one batched stage at the end of
    # generation, not per rendered template. Applied initializers must still be
    # Ruff-clean regardless of where the check executes.
    def test_applied_initializer_passes_batched_ruff_check(
        self, tmp_path: Path
    ) -> None:
        """An applied lazy-init artifact is Ruff-clean after batched validation."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        init_path = package_root / c.Infra.INIT_PY
        service = u.Tests.create_lazy_init_service(repository_root)
        service.target_module = "flext_test_project"
        service.apply_changes = True

        result = u.Tests.materialize_lazy_init(service)

        tm.that(result.success, eq=True)
        tm.that(service.modified_files, eq=(str(init_path),))
        ruff_check = u.Cli.run_raw([
            c.Infra.RUFF,
            c.Infra.CHECK,
            "--no-fix",
            str(init_path),
        ])
        tm.that(ruff_check.success, eq=True)
        tm.that(
            u.Cli.process_succeeded(ruff_check.value.outcome),
            eq=True,
            msg=f"{ruff_check.value.stdout}\n{ruff_check.value.stderr}",
        )

    @pytest.mark.parametrize("width_offset", [-1, 0, 1])
    def test_export_tuple_is_formatter_stable_at_line_width(
        self, tmp_path: Path, width_offset: int
    ) -> None:
        """Public generation agrees with Ruff on both sides of its wrap boundary."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        first, second = "FlextTestsFirst", "FlextTestsSecond"
        compact = f'__all__: tuple[str, ...] = ("{first}", "{second}")'
        second += "x" * (c.Infra.MAX_LINE_LENGTH + width_offset - len(compact))
        package_root.joinpath("runner.py").write_text(
            f'class {first}:\n    """First export."""\n\n'
            f'class {second}:\n    """Second export."""\n\n'
            f'__all__ = ["{first}", "{second}"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        service = u.Tests.create_lazy_init_service(repository_root)
        service.target_module = "flext_test_project"
        service.apply_changes = True
        result = u.Tests.materialize_lazy_init(service)
        tm.that(result.success, eq=True)

        formatted = u.Cli.run_raw([
            c.Infra.RUFF,
            "format",
            "--check",
            "--config",
            str(Path(__file__).resolve().parents[3] / c.PYPROJECT_FILENAME),
            "--line-length",
            str(c.Infra.MAX_LINE_LENGTH),
            str(package_root / c.Infra.INIT_PY),
        ])
        tm.that(formatted.success, eq=True)
        tm.that(
            u.Cli.process_succeeded(formatted.value.outcome),
            eq=True,
            msg=f"{formatted.value.stdout}\n{formatted.value.stderr}",
        )

    def test_execute_command_rejects_publication_outside_conform(
        self, tmp_path: Path
    ) -> None:
        """The public route checks plans while conform alone owns publication."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        init_path = package_root / c.Infra.INIT_PY
        original_init = init_path.read_bytes()
        apply_service = u.Tests.create_lazy_init_service(repository_root)
        apply_service.target_module = "flext_test_project"
        apply_service.apply_changes = True

        apply_result = apply_service.execute()
        applied_init = init_path.read_bytes()
        materialized = u.Tests.materialize_lazy_init(apply_service)
        check_service = u.Tests.create_lazy_init_service(repository_root)
        check_service.target_module = "flext_test_project"
        check_service.check_only = True

        check_result = check_service.execute()

        tm.that(apply_result.success, eq=False)
        tm.that(apply_result.error, has="publication is owned by codegen conform")
        tm.that(applied_init, eq=original_init)
        tm.that(materialized.success, eq=True)
        tm.that(check_result.success, eq=True)
        tm.that(init_path.read_bytes(), ne=original_init)

    # flext-udpm5: reproduces flext_ldif.servers._base's exact shape -- a
    # doubly-nested package whose modules import the project root's own
    # already-published facade aliases directly (``from <root> import m``)
    # via a local ``constants.py``, without aliasing any local class under
    # that same letter. _resolve_aliases inherits the root's own alias
    # entry into this package's lazy_map; before the fix that redundant
    # self-import reached the TYPE_CHECKING renderer as an unrenderable
    # absolute import and crashed both check and apply with "expected a
    # relative owner" (converting it to a relative import is not an option
    # either -- member projects that write every local import absolutely,
    # like flext-ldif, ban parent-relative imports in their own Ruff
    # config). Check and apply must now agree and neither may error.
    def test_nested_package_consuming_only_inherited_root_alias(
        self, tmp_path: Path
    ) -> None:
        """A nested package inheriting a root alias plans without error."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        nested_root = package_root / "servers" / "_base"
        nested_root.mkdir(parents=True)
        nested_root.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        nested_root.joinpath("constants.py").write_text(
            '"""Base constants consumer."""\n\n'
            "from __future__ import annotations\n\n"
            "from typing import TYPE_CHECKING\n\n"
            "if TYPE_CHECKING:\n"
            "    from flext_test_project import m\n\n"
            "class FlextTestsBaseConstants:\n"
            '    """Base constants class."""\n\n'
            '    VALUE: str = ""\n\n\n'
            '__all__: list[str] = ["FlextTestsBaseConstants"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        init_path = nested_root / c.Infra.INIT_PY
        apply_service = u.Tests.create_lazy_init_service(repository_root)
        apply_service.target_module = "flext_test_project.servers._base"
        apply_service.apply_changes = True

        apply_result = u.Tests.materialize_lazy_init(apply_service)
        applied_init = init_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        check_service = u.Tests.create_lazy_init_service(repository_root)
        check_service.target_module = "flext_test_project.servers._base"
        check_service.check_only = True

        check_result = check_service.execute()

        tm.that(apply_result.success, eq=True)
        tm.that(check_result.success, eq=True)
        tm.that(check_service.modified_files, eq=())
        tm.that(applied_init, contains="FlextTestsBaseConstants")
        # The inherited root alias is a redundant upstream re-export, not a
        # local owner of this nested package: it stays out of __all__.
        tm.that(applied_init, lacks='"m",')

    # flext-mh7g4: a tests category directory named like a stdlib module
    # (``tests/typing/``) can never be a legal generated package: the render
    # would shadow the stdlib module and the generator's own Ruff gate rejects
    # it (stdlib-module-shadowing). Apply must remove generator-owned residue,
    # never write a new initializer, drop the child from the parent inventory
    # in the same pass, and a following check must be a byte fixed point.
    @pytest.mark.parametrize("directory_name", ["typing", "done-check", "class", "123"])
    def test_invalid_directory_is_never_a_generated_package(
        self, tmp_path: Path, directory_name: str
    ) -> None:
        """Unimportable and stdlib-shadowing directories lose generated residue."""
        repository_root, _package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        tests_root = repository_root / c.Infra.DIR_TESTS
        tests_root.mkdir()
        tests_init = tests_root / c.Infra.INIT_PY
        tests_init.write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        shadowing_root = tests_root / directory_name
        shadowing_root.mkdir()
        residue_init = shadowing_root / c.Infra.INIT_PY
        residue_init.write_text(
            f'{c.Infra.AUTOGEN_HEADER}\n"""Generated package."""\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        shadowing_root.joinpath("test_contracts.py").write_text(
            'class TestsTypingContracts:\n    """Collected test class."""\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        # A stdlib-named directory that is NOT first-level under the source
        # root imports as ``unit.io`` and is a legal generated package.
        nested_io_root = tests_root / "unit" / "io"
        nested_io_root.mkdir(parents=True)
        tests_root.joinpath("unit", c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        nested_io_root.joinpath("test_streams.py").write_text(
            'class TestsIoStreams:\n    """Collected test class."""\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        apply_service = u.Tests.create_lazy_init_service(repository_root)
        apply_service.target_module = c.Infra.DIR_TESTS
        apply_service.apply_changes = True

        apply_result = u.Tests.materialize_lazy_init(apply_service)
        generated_tests_init = tests_init.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        check_service = u.Tests.create_lazy_init_service(repository_root)
        check_service.target_module = c.Infra.DIR_TESTS
        check_service.check_only = True

        check_result = check_service.execute()

        tm.that(apply_result.success, eq=True)
        tm.that(residue_init.exists(), eq=False)
        tm.that(generated_tests_init, lacks=f".{directory_name}")
        tm.that(generated_tests_init, lacks=f'"{directory_name}"')
        tm.that((nested_io_root / c.Infra.INIT_PY).exists(), eq=True)
        tm.that(check_result.success, eq=True)
        tm.that(check_service.modified_files, eq=())
