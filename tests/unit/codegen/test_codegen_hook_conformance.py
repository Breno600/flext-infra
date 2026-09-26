"""Behavioral contracts for generated Git-hook conformance."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, config, m, t, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import c as test_c, u as test_u

pytestmark = pytest.mark.slow

if TYPE_CHECKING:
    from flext_infra import p

_HOOK_TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "flext_infra"
    / "templates"
    / "project"
    / "base"
    / ".pre-commit-config.yaml.j2"
)


class TestsFlextInfraCodegenHookConformance:
    """Prove generation owns hook artifacts and preserves runtime installation."""

    @staticmethod
    def _standalone_workspace(root: Path) -> m.Infra.WorkspaceSpec:
        """Load the smallest repository-local topology needed by conform."""
        return test_u.Tests.standalone_workspace(root)

    @staticmethod
    def _render_hooks(root: Path) -> str:
        """Render the manifest-owned hook artifact through the public owner."""
        rendered = tm.ok(
            u.Cli.template_render(
                _HOOK_TEMPLATE,
                m.Infra.MakeWorkflowRenderSpec(
                    dist="flext-demo", make=config.Infra.codegen.make
                ),
            )
        )
        tm.ok(u.Cli.atomic_write_text_file(root / ".pre-commit-config.yaml", rendered))
        return rendered

    @staticmethod
    def _check(
        root: Path, workspace: m.Infra.WorkspaceSpec
    ) -> p.Result[m.Infra.CodegenResult]:
        return FlextInfraCodegenConform.execute_request(
            test_u.Tests.conform_request(
                root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            ),
            initial_workspace=workspace,
        )

    def test_check_never_requires_runtime_hook_installation(
        self, infra_git_repo: Path
    ) -> None:
        """Conform owns generated files; AI Hub owns hook installation."""
        root = infra_git_repo
        workspace = self._standalone_workspace(root)
        self._render_hooks(root)

        result = self._check(root, workspace)

        if result.failure:
            tm.that(result.error or "", lacks="git hook is not installed")

    def test_apply_does_not_install_hook_shims(self, infra_git_repo: Path) -> None:
        """Apply materializes files only and never provisions hook shims."""
        root = infra_git_repo
        workspace = self._standalone_workspace(root)
        hooks_dir = root / ".git" / "hooks"

        FlextInfraCodegenConform.execute_request(
            test_u.Tests.conform_request(
                root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )

        for stage in ("pre-commit", "pre-push"):
            hook = hooks_dir / stage
            if hook.is_file():
                tm.that(hook.read_text(encoding="utf-8"), lacks=f"--hook-type={stage}")

    def test_generated_hooks_use_one_strict_shell_per_workflow_step(
        self, infra_git_repo: Path
    ) -> None:
        """Each enabled stage runs every declared verb in its own strict shell.

        The template gives each Make verb its own hook so the pre-commit runner
        reports per-step status natively.
        """
        root = infra_git_repo
        make = config.Infra.codegen.make.model_copy(
            update={"pre_commit": True, "pre_push": True}
        )
        rendered = tm.ok(
            u.Cli.template_render(
                _HOOK_TEMPLATE,
                m.Infra.MakeWorkflowRenderSpec(dist="flext-demo", make=make),
            )
        )
        tm.ok(u.Cli.atomic_write_text_file(root / ".pre-commit-config.yaml", rendered))
        expected = sum(
            1
            for step in make.workflow
            for context in ("pre_commit", "pre_push")
            if context in step.contexts
        )
        tm.that(rendered.count("bash -eu -o pipefail -c"), eq=expected)
        tm.that(rendered, lacks=".local")

    @pytest.mark.parametrize("inherited", ["ci", "local"])
    def test_pre_push_check_unsets_inherited_ci_before_the_real_make_runtime(
        self, tmp_path: Path, inherited: str
    ) -> None:
        """Execute the generated hook entry without replacing any runtime owner."""
        root, _ = test_u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        tm.ok(test_u.Tests.create_python_environment(root))
        policy = config.Infra.codegen.make
        make = m.Infra.MakeSpec.model_validate({
            **policy.model_dump(exclude_computed_fields=True),
            "pre_commit": False,
            "pre_push": True,
            "workflow": (
                m.Infra.MakeWorkflowStepSpec(
                    verb="check", contexts=("local", "pre_push")
                ),
            ),
        })
        rendered = tm.ok(
            u.Cli.template_render(
                _HOOK_TEMPLATE,
                m.Infra.MakeWorkflowRenderSpec(dist="fixture-project", make=make),
            )
        )
        hook_config = root / c.Infra.PRE_COMMIT_CONFIG_FILENAME
        tm.ok(u.Cli.atomic_write_text_file(hook_config, rendered))
        document = u.Cli.yaml_load_mapping(hook_config)
        repositories = document["repos"]
        assert isinstance(repositories, list)
        repository = t.Cli.JSON_MAPPING_ADAPTER.validate_python(repositories[0])
        hooks = repository["hooks"]
        assert isinstance(hooks, list)
        tm.that(len(hooks), eq=1)
        hook = t.Cli.JSON_MAPPING_ADAPTER.validate_python(hooks[0])
        entry = hook["entry"]
        assert isinstance(entry, str)
        process = tm.ok(
            u.Cli.run_raw(
                shlex.split(entry),
                cwd=root,
                env={
                    policy.ci.variable: (
                        policy.ci.value if inherited == "ci" else policy.ci.local_value
                    )
                },
                remove_env_keys=test_c.Tests.MAKE_ISOLATION_ENV_KEYS,
            )
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(
            process.stdout,
            has=(
                "INFO: default context runs check gates: "
                f"{' '.join(policy.check_gates_default)}\n"
            ),
        )
        tm.that(
            process.stderr,
            has=(
                "No module named flext_infra"
                if policy.check_gates_default
                else "no active check gates remain in the selected context"
            ),
        )
        for suspension in policy.check_gate_suspensions:
            tm.that(process.stdout, has=f"SUSPENDED check gate {suspension.gate};")

    def test_check_and_apply_never_overwrite_foreign_hook_shims(
        self, infra_git_repo: Path
    ) -> None:
        """Conform never overwrites a foreign executable hook."""
        root = infra_git_repo
        workspace = self._standalone_workspace(root)
        self._render_hooks(root)
        hooks_dir = root / ".git" / "hooks"
        foreign = "#!/bin/sh\nexit 0\n"
        for stage in ("pre-commit", "pre-push"):
            (hooks_dir / stage).write_text(foreign, encoding="utf-8")

        self._check(root, workspace)
        FlextInfraCodegenConform.execute_request(
            test_u.Tests.conform_request(
                root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )

        for stage in ("pre-commit", "pre-push"):
            tm.that((hooks_dir / stage).read_text(encoding="utf-8"), eq=foreign)

    def test_hook_stages_follow_configuration(self) -> None:
        """The projection follows the current typed configuration."""
        make = config.Infra.codegen.make
        rendered = tm.ok(
            u.Cli.template_render(
                _HOOK_TEMPLATE,
                m.Infra.MakeWorkflowRenderSpec(dist="flext-demo", make=make),
            )
        )
        tm.that("flext-pre-commit-" in rendered, eq=make.pre_commit)
        tm.that("flext-pre-push-" in rendered, eq=make.pre_push)

    def test_disabled_gates_render_no_hook_stages(self) -> None:
        """With both gates off the generated config carries zero hook steps."""
        rendered = tm.ok(
            u.Cli.template_render(
                _HOOK_TEMPLATE,
                m.Infra.MakeWorkflowRenderSpec(
                    dist="flext-demo",
                    make=config.Infra.codegen.make.model_copy(
                        update={"pre_commit": False, "pre_push": False}
                    ),
                ),
            )
        )

        tm.that(rendered, lacks="stages: [pre-commit]")
        tm.that(rendered, lacks="stages: [pre-push]")
        tm.that(rendered, lacks="flext-pre-commit-")
        tm.that(rendered, lacks="flext-pre-push-")

    def test_enabled_gates_render_exactly_the_declared_stages(self) -> None:
        """Each gate renders exactly its configured workflow rows, no more."""
        make = config.Infra.codegen.make

        both = tm.ok(
            u.Cli.template_render(
                _HOOK_TEMPLATE,
                m.Infra.MakeWorkflowRenderSpec(
                    dist="flext-demo",
                    make=make.model_copy(update={"pre_commit": True, "pre_push": True}),
                ),
            )
        )
        expected = sum(
            1
            for step in make.workflow
            for context in ("pre_commit", "pre_push")
            if context in step.contexts
        )
        tm.that(both.count("bash -eu -o pipefail -c"), eq=expected)

        commit_only = tm.ok(
            u.Cli.template_render(
                _HOOK_TEMPLATE,
                m.Infra.MakeWorkflowRenderSpec(
                    dist="flext-demo",
                    make=make.model_copy(
                        update={"pre_commit": True, "pre_push": False}
                    ),
                ),
            )
        )
        tm.that(commit_only, has="stages: [pre-commit]")
        tm.that(commit_only, lacks="stages: [pre-push]")

    def test_standalone_hook_config_is_not_retired(self, tmp_path: Path) -> None:
        """Keep a generated projection whose template declares standalone."""
        root = tmp_path / "flext-member"
        root.mkdir()
        hook_config = root / ".pre-commit-config.yaml"
        hook_config.write_text(
            "# Generated by flext_infra codegen for flext-member — DO NOT EDIT\n"
            "repos: []\n",
            encoding="utf-8",
        )

        planned = FlextInfraCodegenConform.retired_projection_plans(
            root, c.Infra.MakeProfile.STANDALONE
        )

        retired = {plan.path for plan in tm.ok(planned) if plan.desired_content is None}
        tm.that(hook_config in retired, eq=False)

    def test_standalone_retires_workspace_only_generated_projection(
        self, tmp_path: Path
    ) -> None:
        """Remove a generated projection excluded from the selected profile."""
        target = tmp_path / ".github/ci-template/ci.yml"
        target.parent.mkdir(parents=True)
        target.write_text(
            f"# {c.Infra.TEMPLATE_GENERATED_MARKERS[0]}\n", encoding="utf-8"
        )

        planned = FlextInfraCodegenConform.retired_projection_plans(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )

        retired = {plan.path for plan in tm.ok(planned) if plan.desired_content is None}
        tm.that(target in retired, eq=True)
