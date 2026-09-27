"""Read-only publication plans for generated package initializers."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import c, u


class TestsFlextInfraCodegenLazyInitFilePlans:
    """Prove lazy-init describes effects without owning publication."""

    def test_plan_files_binds_init_and_sidecar_effects_without_writing(
        self, tmp_path: Path
    ) -> None:
        """Return exact target/source states while preserving every target byte."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        module_path = package_root / "models.py"
        u.Tests.write_lazy_init_namespace_module(
            module_path, class_name="FlextTestsModels", alias="m"
        )
        init_path = package_root / c.Infra.INIT_PY
        unit_path = package_root / "__unit__.py"
        unit_path.write_text(
            f"{c.Infra.AUTOGEN_HEADER}\n", encoding=c.Cli.ENCODING_DEFAULT
        )
        before = {path: path.read_bytes() for path in (init_path, unit_path)}
        service = u.Tests.create_lazy_init_service(repository_root)

        result = service.plan_files()

        tm.that(result.success, eq=True)
        analysis = result.value
        tm.that(analysis.phase, eq="lazy-init")
        plans = {plan.path: plan for plan in analysis.files}
        init_plan = plans[init_path.resolve()]
        tm.that(init_plan.project, eq=repository_root.resolve())
        tm.that(
            tm.ok(u.Infra.codegen_file_before_state(init_plan)).content,
            eq=before[init_path],
        )
        tm.that(init_plan.desired_mode, eq=0o644)
        tm.that(u.Tests.codegen_file_text(init_plan), contains="FlextTestsModels")
        tm.that(u.Infra.codegen_file_requires_effect(init_plan), eq=True)
        source_paths = {state.path for state in init_plan.source_states}
        tm.that(module_path.resolve() in source_paths, eq=True)
        tm.that(
            any(path.name == "lazy_init_root.py.j2" for path in source_paths), eq=True
        )
        input_paths = {state.path for state in analysis.inputs}
        tm.that(source_paths.issubset(input_paths), eq=True)
        tm.that(init_path.resolve() in input_paths, eq=True)
        unit_plan = plans[unit_path.resolve()]
        tm.that(
            tm.ok(u.Infra.codegen_file_before_state(unit_plan)).content,
            eq=before[unit_path],
        )
        tm.that(unit_plan.desired_content, eq=None)
        tm.that(unit_plan.desired_mode, eq=None)
        tm.that(u.Infra.codegen_file_requires_effect(unit_plan), eq=True)
        tm.that({path: path.read_bytes() for path in (init_path, unit_path)}, eq=before)

    def test_plan_files_includes_all_retired_generated_sidecars(
        self, tmp_path: Path
    ) -> None:
        """Describe the closed sidecar cleanup set, including one-pass constants."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextTestsModels", alias="m"
        )
        generated_header = f"{c.Infra.AUTOGEN_HEADER}\n"
        stub_path = package_root / c.Infra.INIT_PYI
        stub_path.write_text(generated_header, encoding=c.Cli.ENCODING_DEFAULT)
        root_sidecar = package_root / "_exports.py"
        root_sidecar.write_text(generated_header, encoding=c.Cli.ENCODING_DEFAULT)
        constants_dir = package_root / c.Infra.ROOT_EXPORTS_DIR
        constants_dir.mkdir()
        constants_init = constants_dir / c.Infra.INIT_PY
        constants_init.write_text(generated_header, encoding=c.Cli.ENCODING_DEFAULT)
        constants_sidecar = constants_dir / "_exports_lazy.py"
        constants_sidecar.write_text(generated_header, encoding=c.Cli.ENCODING_DEFAULT)
        obsolete_dir = package_root / "_root_exports"
        obsolete_dir.mkdir()
        obsolete_init = obsolete_dir / c.Infra.INIT_PY
        obsolete_init.write_text(generated_header, encoding=c.Cli.ENCODING_DEFAULT)
        obsolete_part = obsolete_dir / "part.py"
        obsolete_part.write_text(generated_header, encoding=c.Cli.ENCODING_DEFAULT)
        expected_deletes = {
            stub_path.resolve(),
            root_sidecar.resolve(),
            constants_init.resolve(),
            constants_sidecar.resolve(),
            obsolete_init.resolve(),
            obsolete_part.resolve(),
        }
        before = {path: path.read_bytes() for path in expected_deletes}

        result = u.Tests.create_lazy_init_service(repository_root).plan_files()

        tm.that(result.success, eq=True)
        deletes = {
            plan.path
            for plan in result.value.files
            if plan.desired_content is None
            and u.Infra.codegen_file_requires_effect(plan)
        }
        tm.that(expected_deletes.issubset(deletes), eq=True)
        tm.that({path: path.read_bytes() for path in expected_deletes}, eq=before)

    def test_execute_rejects_apply_and_preserves_planned_targets(
        self, tmp_path: Path
    ) -> None:
        """The standalone command is a check surface, never a second writer."""
        _, init_path, service = u.Tests.lazy_init_scenario(tmp_path)
        before = init_path.read_bytes()
        service.apply_changes = True

        result = service.execute()

        tm.that(result.failure, eq=True)
        tm.that(result.error, contains="owned by codegen conform")
        tm.that(init_path.read_bytes(), eq=before)

    def test_unknown_target_is_a_causal_plan_failure(self, tmp_path: Path) -> None:
        """A missing target fails instead of widening to the workspace."""
        _, init_path, service = u.Tests.lazy_init_scenario(tmp_path)
        before = init_path.read_bytes()
        service.target_module = "flext_missing"

        result = service.plan_files()

        tm.that(result.failure, eq=True)
        tm.that(result.error, contains="lazy-init target module not found")
        tm.that(init_path.read_bytes(), eq=before)
