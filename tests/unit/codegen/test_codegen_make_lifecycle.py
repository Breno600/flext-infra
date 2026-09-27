"""Public composite lifecycles preserve setup's failure boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config
from flext_infra.codegen import FlextInfraCodegenConform
from tests import u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeLifecycle:
    @pytest.fixture
    def generated_project(self, tmp_path: Path) -> Path:
        """Render a real governed consumer through the public generator."""
        root = tmp_path / "consumer"
        repository = u.Tests.repository_ref(
            "flext-lifecycle", role=c.Infra.MakeProfile.STANDALONE
        )
        beads = u.Tests.beads_project(repository.distribution)
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            repository.distribution,
            workspace=beads.workspace,
            database=beads.database,
            issue_prefix=beads.issue_prefix,
        )
        workspace = u.Tests.workspace_spec(
            repository, project=u.Tests.project_spec(repository.name)
        )
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(
            FlextInfraCodegenConform(
                repository_root=root, request=request, initial_workspace=workspace
            ).plan(request)
        )
        makefile = next(
            file for file in plan.files if file.path.name == c.Infra.MAKEFILE_FILENAME
        )
        (root / c.Infra.MAKEFILE_FILENAME).write_text(
            u.Tests.codegen_file_text(makefile), encoding="utf-8"
        )
        return root

    @pytest.mark.parametrize("verb", ["setup", "dev", "upg"])
    def test_local_binding_in_ci_stops_before_environment_provisioning(
        self, tmp_path: Path, generated_project: Path, verb: str
    ) -> None:
        """Composites propagate a real setup rejection without touching the runtime."""
        root = generated_project
        ci = config.Infra.codegen.make.ci
        result = tm.ok(
            u.Tests.run_isolated_make(
                [verb],
                cwd=root,
                env={ci.variable: ci.value, "FLEXT": str(tmp_path / "supplier")},
            )
        )
        output = f"{result.stdout}\n{result.stderr}"
        tm.that(result.outcome.raw_return_code, eq=2, msg=output)
        tm.that(
            output,
            contains=f"local editable binding is incompatible with {ci.variable}={ci.value}",
        )
        environment = root / config.Infra.tooling.tools.pyright.path_rules.venv_name
        tm.that(environment.exists(), eq=False)

    @pytest.mark.parametrize("verb", ["dev", "upg"])
    @pytest.mark.parametrize("hook", ["pre", "_custom"])
    def test_borrowed_environment_is_rejected_before_custom_hooks(
        self, tmp_path: Path, generated_project: Path, verb: str, hook: str
    ) -> None:
        """Lifecycle hooks cannot mutate a checkout with a borrowed environment."""
        root = generated_project
        foreign = tmp_path / "foreign-environment"
        foreign.mkdir()
        environment = root / config.Infra.tooling.tools.pyright.path_rules.venv_name
        environment.symlink_to(foreign, target_is_directory=True)
        custom = root / config.Infra.codegen.make.custom_handler_policy.filename
        custom.write_text(
            f'{hook}-{verb}:\n\t@printf executed > "$(PROJECT_ROOT)/hook-executed"\n',
            encoding="utf-8",
        )
        result = tm.ok(u.Tests.run_isolated_make([verb], cwd=root))
        output = f"{result.stdout}\n{result.stderr}"
        tm.that(result.outcome.raw_return_code, eq=2, msg=output)
        tm.that(output, contains="workspace environment must be physical")
        tm.that((root / "hook-executed").exists(), eq=False)
        tm.that(tuple(foreign.iterdir()), eq=())
