"""Public surface contract of the conform verb: docs, CLI routing, dependency scope.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import main
from flext_infra.codegen import FlextInfraCodegenConform
from flext_infra.services.cli_routes_codegen import FlextInfraCodegenRoutes
from tests import c, u
from tests.unit.codegen.conform_support import TestsFlextInfraConformSupport

pytestmark = [pytest.mark.slow]


class TestsFlextInfraCodegenConformPublicSurface:
    """The conform public surface: docs bootstrap, CLI routing, dependency scope."""

    @staticmethod
    def test_workspace_uv_plan_owns_root_lock_and_editable_repositories(
        tmp_path: Path,
    ) -> None:
        """Keep workspace setup data complete without Make-side re-derivation."""
        root_repository = u.Tests.repository_ref("flext")
        member = u.Tests.repository_ref("flext-core", path=Path("flext-core"))
        workspace = u.Tests.workspace_spec(
            root_repository,
            project=u.Tests.project_spec("flext"),
            subprojects=(member,),
        )
        root = tmp_path / "flext"
        # The governed tree above the workspace carries the committed Taplo pin.
        u.Tests.seed_locked_taplo(tmp_path)
        service, request = TestsFlextInfraConformSupport.check_conform_service(
            root,
            workspace,
        )
        planned = service.plan(request)
        tm.ok(planned)
        environment = planned.value.uv_environments[0]
        tm.that(environment.environment_root, eq=root.resolve())
        tm.that(environment.groups, eq=("dev", "codegen", "workspace"))
        tm.that(
            tuple(item.name for item in environment.editable_repositories),
            eq=("flext-core",),
        )

    @staticmethod
    def test_docs_config_apply_materializes_an_absent_docs_parent(
        infra_git_repo: Path,
    ) -> None:
        """Bootstrapping docs-config on a checkout without ``docs/`` publishes it."""
        root = infra_git_repo
        workspace = TestsFlextInfraConformSupport.standalone_workspace(root)
        docs_dir = root / c.Infra.DIR_DOCS
        if docs_dir.exists():
            shutil.rmtree(docs_dir)

        TestsFlextInfraConformSupport.apply_conform_surface(
            root,
            workspace,
            c.Infra.CodegenConformSurface.DOCS_CONFIG,
        )

        projection = docs_dir / c.Infra.DOCS_CONFIG_FILENAME
        tm.ok(u.Cli.json_loads(projection.read_bytes()))

    @staticmethod
    @pytest.mark.parametrize("mode", tuple(c.Infra.CodegenConformMode))
    def test_public_cli_routes_check_and_apply_to_one_handler(
        infra_git_repo: Path,
        mode: c.Infra.CodegenConformMode,
    ) -> None:
        """Execute one public mode without changing an already conform tree."""
        root = infra_git_repo
        workspace = TestsFlextInfraConformSupport.standalone_workspace(root)
        TestsFlextInfraConformSupport.apply_conform_surface(
            root,
            workspace,
            c.Infra.CodegenConformSurface.MAKEFILE,
        )
        u.Tests.commit_git_changes(root, "Seed generated project")
        route = next(
            route
            for route in FlextInfraCodegenRoutes.codegen_routes[
                c.Infra.CLI_GROUP_CODEGEN
            ]
            if route.name == "conform"
        )
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=mode,
        )
        tm.ok(route.handler(request))
        status = tm.ok(u.Cli.capture(["git", "status", "--porcelain"], cwd=root))
        tm.that(status, eq="")

    # Why (suite budget): dependencies-only apply+check runs two full conform
    # cycles on a real git repo; the per-case wall only holds on an idle CPU.
    @staticmethod
    @pytest.mark.slow
    def test_dependency_surface_excludes_unowned_managed_files(
        infra_git_repo: Path,
    ) -> None:
        """Plan only dependency metadata when another managed surface is invalid."""
        root = infra_git_repo
        workspace = TestsFlextInfraConformSupport.standalone_workspace(root)
        TestsFlextInfraConformSupport.apply_conform_surface(
            root,
            workspace,
            c.Infra.CodegenConformSurface.ALL,
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk",
                ".PHONY: public-handler\npublic-handler:\n\t@true\n",
            ),
        )
        u.Tests.commit_git_changes(root, "Seed generated project")
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.DEPENDENCIES,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(repository_root=root, request=request).plan(
            request,
        )
        tm.ok(planned)
        tm.that(
            tuple(file.path.name for file in planned.value.files),
            eq=("pyproject.toml",),
        )
        tm.that(
            tuple(
                u.Infra.codegen_file_requires_effect(file)
                for file in planned.value.files
            ),
            eq=(False,),
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
