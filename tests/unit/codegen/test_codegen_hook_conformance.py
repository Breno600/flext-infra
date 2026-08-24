"""Behavioral contracts for generated Git-hook conformance."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, config, m, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_tests import tm
from tests import u as test_u

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


class TestGitHookConformance:
    """Prove generated hook configs and installed shims converge together."""

    @staticmethod
    def _standalone_workspace(root: Path) -> m.Infra.WorkspaceSpec:
        """Load the smallest owner-written manifest needed by conform."""
        test_u.Tests.write_standalone_workspace_manifest(
            root, "flext-demo", upstream="flext_cli"
        )
        return tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

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
            m.Infra.CodegenConformRequest(
                root=root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            ),
            initial_workspace=workspace,
        )

    def test_check_fails_when_declared_hooks_are_not_installed(
        self, infra_git_repo: Path
    ) -> None:
        """An emitted hook config that was never activated is drift."""
        root = infra_git_repo
        workspace = self._standalone_workspace(root)
        self._render_hooks(root)

        result = self._check(root, workspace)

        tm.fail(result)
        tm.that(result.error, has="git hook is not installed")
        tm.that(result.error, has="pre-commit")
        tm.that(result.error, has="pre-push")

    def test_apply_installs_every_declared_hook(self, infra_git_repo: Path) -> None:
        """Apply activates the hooks it emits, so the next check is green."""
        root = infra_git_repo
        workspace = self._standalone_workspace(root)
        hooks_dir = root / ".git" / "hooks"

        tm.ok(
            FlextInfraCodegenConform.execute_request(
                m.Infra.CodegenConformRequest(
                    root=root,
                    what=c.Infra.CodegenConformSurface.MAKEFILE,
                    scope=c.Infra.CodegenConformScope.SELF,
                    mode=c.Infra.CodegenConformMode.APPLY,
                ),
                initial_workspace=workspace,
            )
        )

        for stage in ("pre-commit", "pre-push"):
            hook = hooks_dir / stage
            tm.that(hook.is_file(), eq=True)
            tm.that(hook.read_text(encoding="utf-8"), has=f"--hook-type={stage}")

    def test_generated_hooks_use_one_make_only_shell_per_step(
        self, infra_git_repo: Path
    ) -> None:
        """Generated hooks expose no executable path outside canonical Make."""
        root = infra_git_repo
        rendered = self._render_hooks(root)
        hook_contexts = {"pre_commit", "pre_push"}
        expected = sum(
            len(hook_contexts.intersection(step.contexts))
            for step in config.Infra.codegen.make.workflow
        )

        tm.that(rendered.count("bash -eu -o pipefail -c"), eq=expected)
        tm.that(rendered, lacks=".local")

    def test_check_and_apply_reject_unmanaged_hook_shims(
        self, infra_git_repo: Path
    ) -> None:
        """Conform never accepts or overwrites a foreign executable hook."""
        root = infra_git_repo
        workspace = self._standalone_workspace(root)
        self._render_hooks(root)
        hooks_dir = root / ".git" / "hooks"
        foreign = "#!/bin/sh\nexit 0\n"
        for stage in ("pre-commit", "pre-push"):
            (hooks_dir / stage).write_text(foreign, encoding="utf-8")

        checked = self._check(root, workspace)
        applied = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )

        for result in (checked, applied):
            tm.fail(result)
            tm.that(result.error, has="git hook is not managed by pre-commit")
        for stage in ("pre-commit", "pre-push"):
            tm.that((hooks_dir / stage).read_text(encoding="utf-8"), eq=foreign)

    def test_member_hook_config_is_retired_by_conform(self, tmp_path: Path) -> None:
        """A workspace member keeps its own hook config; conform does not retire it."""
        root = tmp_path / "flext-member"
        root.mkdir()
        hook_config = root / ".pre-commit-config.yaml"
        hook_config.write_text(
            "# Generated by flext_infra codegen for flext-member — DO NOT EDIT\n"
            "repos: []\n",
            encoding="utf-8",
        )

        planned = FlextInfraCodegenConform.retired_projection_plans(
            root, c.Infra.MakeProfile.WORKSPACE_MEMBER
        )

        retired = {plan.path for plan in tm.ok(planned) if plan.absent}
        tm.that(hook_config in retired, eq=False)


__all__: list[str] = ["TestGitHookConformance"]
