"""Read-only publication plans for generated package initializers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import infra
from flext_infra.codegen import FlextInfraCodegenConform
from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit
from flext_infra.workspace import FlextInfraWorkspaceDetector
from tests import c, m, u


class TestsFlextInfraCodegenLazyInitFilePlans:
    """Prove lazy-init describes effects without owning publication."""

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("scope", tuple(c.Infra.CodegenConformScope))
    def test_lazy_publication_owns_exact_conform_repositories(
        tmp_path: Path,
        scope: c.Infra.CodegenConformScope,
    ) -> None:
        """Root and nested Git repositories retain their selected publication scope."""
        root = tmp_path / "flext-scope-root"
        member = root / "apps" / "flext-scope-member"
        packages: list[Path] = []
        for repository in (root, member):
            _, package = u.Tests.create_lazy_init_workspace(
                repository.parent,
                project_name=repository.name,
                package_name=repository.name.replace("-", "_"),
            )
            packages.append(package)
            u.Tests.initialize_git_repo(
                repository,
                origin_url=u.Tests.repository_ref(repository.name).url,
            )
            u.Tests.standalone_workspace(repository, repository.name)
            # Conform formats pyproject through the Taplo release the committed
            # Mise lock pins; generation never resolves a moving selector.
            u.Tests.seed_locked_taplo(repository)
            u.Tests.write_lazy_init_namespace_module(
                package / "models.py",
                class_name=u.derive_class_stem(repository.name) + "Models",
                alias="m",
            )
            u.Tests.commit_git_changes(repository, "Seed scope fixture")
            # Conform's fresh-import stage runs in the checkout's own runtime,
            # which a real checkout gets from make setup.
            u.Tests.provision_checkout(repository)
        if scope is c.Infra.CodegenConformScope.DECLARED:
            # A members-only run meets a root that already carries its runtime
            # Mise declaration, launchers and pin: each member's launchers are
            # validated as projections of that runtime root.
            u.Tests.copy_tracked_mise_seeds(root)
        u.Tests.WorktreeFixture.attach_submodule(
            root,
            member,
            distribution=member.name,
            relative_path=member.relative_to(root).as_posix(),
        )
        for repository, package in zip((root, member), packages, strict=True):
            observed = tm.ok(
                FlextInfraWorkspaceDetector.load_workspace_spec(repository),
            )
            manifest = m.Infra.WorkspaceManifestSpec(
                version=c.Infra.WORKSPACE_MANIFEST_VERSION,
                name=observed.repository.name,
                repository=observed.repository,
                # The declaration states what the tree ships: these packages
                # own no cli module, so conform declares no console script
                # for its fresh-import stage to load.
                project=u.Tests.project_spec(observed.repository.name).model_copy(
                    update={
                        "cli_module": (
                            package / c.Infra.CODEGEN_CLI_MODULE_FILENAME
                        ).is_file(),
                    },
                ),
            )
            tm.ok(
                u.Cli.yaml_dump(
                    u.Infra.workspace_manifest_path(repository),
                    manifest.model_dump(mode="json"),
                ),
            )
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        request = u.Tests.conform_request(
            root,
            scope=scope,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(
            FlextInfraCodegenConform(
                repository_root=root,
                request=request,
                initial_workspace=workspace,
            ).plan(request),
        )
        selected = tuple(
            (root / repository.path).resolve() for repository in plan.repositories
        )
        expected = (
            {root.resolve()}
            if scope is c.Infra.CodegenConformScope.SELF
            else {member.resolve()}
            if scope is c.Infra.CodegenConformScope.DECLARED
            else {root.resolve(), member.resolve()}
        )
        tm.that(set(selected), eq=expected)
        before = {
            package / c.Infra.INIT_PY: (package / c.Infra.INIT_PY).read_bytes()
            for package in packages
        }
        analyses = tuple(
            tm.ok(
                FlextInfraCodegenLazyInit(
                    repository_root=repository,
                    project_scope_roots=(repository,),
                ).plan_files(),
            )
            for repository in selected
        )
        tm.that(
            {file.project for analysis in analyses for file in analysis.files},
            eq=expected,
        )
        tm.that({path: path.read_bytes() for path in before}, eq=before)
        applied = request.model_copy(update={"mode": c.Infra.CodegenConformMode.APPLY})
        tm.ok(infra.codegen_conform(applied, workspace))
        for repository, package in zip((root, member), packages, strict=True):
            initializer = package / c.Infra.INIT_PY
            tm.that(
                initializer.read_bytes() != before[initializer],
                eq=repository.resolve() in expected,
            )
        tm.ok(infra.codegen_conform(request, workspace))

    @staticmethod
    def test_scope_outside_workspace_is_a_causal_plan_failure(
        tmp_path: Path,
    ) -> None:
        """A selected repository outside the workspace fails instead of widening."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path / "workspace",
        )
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py",
            class_name="FlextTestsModels",
            alias="m",
        )
        foreign_root = tmp_path / "foreign"
        foreign_root.mkdir()
        init_path = package_root / c.Infra.INIT_PY
        before = init_path.read_bytes()

        result = FlextInfraCodegenLazyInit(
            repository_root=repository_root,
            project_scope_roots=(foreign_root,),
        ).plan_files()

        tm.that(result.failure, eq=True)
        tm.that(result.error, contains="lazy-init repository scope is missing")
        tm.that(init_path.read_bytes(), eq=before)

    @staticmethod
    def test_plan_files_binds_init_and_sidecar_effects_without_writing(
        tmp_path: Path,
    ) -> None:
        """Return exact target/source states while preserving every target byte."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        module_path = package_root / "models.py"
        u.Tests.write_lazy_init_namespace_module(
            module_path,
            class_name="FlextTestsModels",
            alias="m",
        )
        init_path = package_root / c.Infra.INIT_PY
        unit_path = package_root / "__unit__.py"
        unit_path.write_text(
            f"{c.Infra.AUTOGEN_HEADER}\n",
            encoding=c.Cli.ENCODING_DEFAULT,
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
            any(path.name == "lazy_init_root.py.j2" for path in source_paths),
            eq=True,
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

    @staticmethod
    def test_plan_files_includes_all_retired_generated_sidecars(
        tmp_path: Path,
    ) -> None:
        """Describe the closed sidecar cleanup set, including one-pass constants."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py",
            class_name="FlextTestsModels",
            alias="m",
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

    @staticmethod
    def test_execute_rejects_apply_and_preserves_planned_targets(
        tmp_path: Path,
    ) -> None:
        """The standalone command is a check surface, never a second writer."""
        _, init_path, service = u.Tests.lazy_init_scenario(tmp_path)
        before = init_path.read_bytes()
        service.apply_changes = True

        result = service.execute()

        tm.that(result.failure, eq=True)
        tm.that(result.error, contains="owned by codegen conform")
        tm.that(init_path.read_bytes(), eq=before)

    @staticmethod
    def test_unknown_target_is_a_causal_plan_failure(tmp_path: Path) -> None:
        """A missing target fails instead of widening to the workspace."""
        _, init_path, service = u.Tests.lazy_init_scenario(tmp_path)
        before = init_path.read_bytes()
        service.target_module = "flext_missing"

        result = service.plan_files()

        tm.that(result.failure, eq=True)
        tm.that(result.error, contains="lazy-init target module not found")
        tm.that(init_path.read_bytes(), eq=before)
