"""Public API facade for flext-infra."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_core import r
from flext_infra import FlextInfraConfig, m, t, u

from .base import s
from .check.workspace_check import FlextInfraWorkspaceChecker
from .codegen.census import FlextInfraCodegenCensus
from .codegen.fixer import FlextInfraCodegenFixer
from .codegen.pipeline import FlextInfraCodegenPipeline
from .codemod.apply_renames import FlextInfraApplyRenames
from .codemod.batch_apply import FlextInfraCodemodBatchApply
from .codemod.text_gates import FlextInfraModTextGateEngine
from .validate.namespace_validator import FlextInfraNamespaceValidator
from .workspace.environment import FlextInfraWorkspaceEnvironmentMixin
from .workspace.rope import FlextInfraRopeWorkspace

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfra(FlextInfraWorkspaceEnvironmentMixin, s[t.JsonDict]):
    """Thin public FLEXT facade over infra services."""

    app_name: ClassVar[str] = "flext-infra"

    def rope_workspace(
        self, repository_root: Path | None = None
    ) -> p.Infra.RopeWorkspaceDsl:
        """Open the public Rope workspace DSL directly from the facade."""
        # NOTE (multi-agent, flext-wkii.17.24): Rope reads its source policy
        # directly from config.Infra at the service boundary.
        resolved_root = (
            self.repository_root if repository_root is None else repository_root
        )
        return FlextInfraRopeWorkspace.open_workspace(resolved_root)

    def check(self, request: m.Infra.RunCommand) -> p.Result[bool]:
        """Compose one shared Rope cycle and execute every requested gate."""
        with FlextInfraRopeWorkspace.open_workspace(request.repository_root) as rope:
            return FlextInfraWorkspaceChecker(
                repository_root=request.repository_root, rope=rope
            ).execute_payload(request)

    def codegen_census(self, request: m.Infra.CodegenCommand) -> p.Result[str]:
        """Run the read-only census within the facade-owned Rope lifecycle."""
        with self.rope_workspace(request.repository_root) as rope:
            return FlextInfraCodegenCensus(
                repository_root=request.repository_root,
                apply_changes=request.apply,
                check_only=request.check_only,
                dry_run=request.dry_run,
                output_format=request.output_format,
                rope=rope,
            ).execute()

    def codegen_auto_fix(self, request: m.Infra.CodegenAutoFixCommand) -> p.Result[str]:
        """Run namespace fixes within the facade-owned Rope lifecycle."""
        with self.rope_workspace(request.repository_root) as rope:
            return FlextInfraCodegenFixer(
                repository_root=request.repository_root,
                apply_changes=request.apply,
                check_only=request.check_only,
                dry_run=request.dry_run,
                output_format=request.output_format,
                selected_projects=request.project_names,
                rules_only=request.rules_only,
                rope=rope,
            ).execute()

    def codegen_pipeline(self, request: m.Infra.CodegenCommand) -> p.Result[str]:
        """Run the codegen pipeline within the facade-owned Rope lifecycle."""
        with self.rope_workspace(request.repository_root) as rope:
            return FlextInfraCodegenPipeline(
                repository_root=request.repository_root,
                apply_changes=request.apply,
                check_only=request.check_only,
                dry_run=request.dry_run,
                output_format=request.output_format,
                rope=rope,
            ).execute()

    def apply_renames(
        self, request: m.Infra.ApplyRenamesInput
    ) -> p.Result[m.Infra.ApplyRenamesReport]:
        """Compose and run one explicitly supplied CSV rename campaign."""
        return FlextInfraApplyRenames().run(request)

    def mod(
        self, request: m.Infra.ModCommand, progress: p.Infra.ModProgress
    ) -> p.Result[t.Cli.ResultValue]:
        """Compose the codemod use case from typed config and real adapters."""
        root = u.Infra.resolve_repository_root_or_cwd(request.repository_root)
        config = FlextInfraConfig.fetch_global().Infra.refactor_csv_campaigns
        config_dir = FlextInfraConfig.ssot_config_dir()
        campaigns: list[m.Infra.ApplyRenamesInput] = []
        for declared in config.campaigns:
            csv = Path(declared.csv)
            campaign_roots = tuple(
                str(path if path.is_absolute() else root / path)
                for path in (Path(value) for value in declared.roots)
            )
            campaigns.append(
                m.Infra.ApplyRenamesInput(
                    csv=str(csv if csv.is_absolute() else config_dir / csv),
                    roots=campaign_roots or (str(root),),
                    apply=request.apply
                    and not request.check
                    and not request.dry_run_mode,
                    bindings=declared.bindings,
                    text_globs=declared.text_globs,
                    python_documentation=declared.python_documentation,
                    exclude_globs=declared.exclude_globs,
                )
            )
        with self.rope_workspace(root) as rope:
            return FlextInfraCodemodBatchApply(
                repository_root=root,
                apply_changes=request.apply,
                check_only=request.check,
                dry_run=request.dry_run_mode,
                rename_runner=FlextInfraApplyRenames(),
                progress=progress,
                rope=rope,
                rename_inputs=tuple(campaigns),
            ).execute()

    def mod_text(self, request: m.Infra.ModCommand) -> p.Result[t.Cli.ResultValue]:
        """Compose the standalone authenticated text-rule replay."""
        root = u.Infra.resolve_repository_root_or_cwd(request.repository_root)
        return FlextInfraModTextGateEngine.run(
            root, apply=request.apply and not request.check and not request.dry_run_mode
        )

    def validate_namespace(
        self, request: m.Infra.NamespaceValidateCommand
    ) -> p.Result[m.Infra.ValidationReport]:
        """Validate one project through a single composed Rope cycle."""
        with FlextInfraRopeWorkspace.open_workspace(request.repository_root) as rope:
            return FlextInfraNamespaceValidator(
                repository_root=request.repository_root, rope=rope
            ).build_report()

    @staticmethod
    def project_context(cwd: Path) -> p.Result[m.Infra.WorkspaceProjectContext]:
        """Derive Git, workspace, and effective project facts from ``cwd``."""
        resolved = cwd.expanduser().resolve()
        if not resolved.is_dir():
            return r[m.Infra.WorkspaceProjectContext].fail(
                f"project context cwd is not a directory: {resolved}"
            )
        identity = u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=resolved))
        if identity.failure:
            return r[m.Infra.WorkspaceProjectContext].ok(
                m.Infra.WorkspaceProjectContext(cwd=resolved)
            )
        root = identity.value.repo_root
        if not u.Infra.workspace_manifest_path(root).is_file():
            return r[m.Infra.WorkspaceProjectContext].ok(
                m.Infra.WorkspaceProjectContext(cwd=resolved, identity=identity.value)
            )
        workspace = u.Infra.workspace_spec_load(root)
        if workspace.failure:
            return r[m.Infra.WorkspaceProjectContext].from_failure(workspace)
        target = u.Infra.repository_conform_target(root, workspace.value)
        if target.failure:
            return r[m.Infra.WorkspaceProjectContext].from_failure(target)
        return r[m.Infra.WorkspaceProjectContext].ok(
            m.Infra.WorkspaceProjectContext(
                cwd=resolved,
                identity=identity.value,
                workspace=workspace.value,
                target=target.value,
                governed=True,
            )
        )

    @override
    def execute(self) -> p.Result[t.JsonDict]:
        """Execute a lightweight facade health report."""
        report: t.JsonDict = {
            "service": "flext-infra",
            "status": "ok",
            "repository_root": str(self.repository_root),
            "apply_changes": self.apply_changes,
        }
        return r[t.JsonDict].ok(report)


infra: FlextInfra = FlextInfra.fetch_global()
"""Shared FlextInfra facade instance."""


__all__: list[str] = ["FlextInfra", "infra"]
