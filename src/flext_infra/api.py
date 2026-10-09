"""Public API facade for flext-infra.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import FlextInfraConfig, m, r, s, t, u
from flext_infra._conform_wiring import FlextInfraConformWiring
from flext_infra.check import FlextInfraWorkspaceChecker
from flext_infra.codegen import (
    FlextInfraCodegenCensus,
    FlextInfraCodegenConform,
    FlextInfraCodegenFixer,
    FlextInfraCodegenMiseArtifacts,
    FlextInfraCodegenPipeline,
    FlextInfraCodegenTransaction,
)
from flext_infra.codemod import (
    FlextInfraAccessorRenamePhase,
    FlextInfraApplyRenames,
    FlextInfraCodemodBatchApply,
    FlextInfraImportNormalizationPhase,
    FlextInfraModTextGateEngine,
    FlextInfraNamespaceRelocationPhase,
)
from flext_infra.services import FlextInfraCandidateBootstrapService
from flext_infra.validate import FlextInfraNamespaceValidator
from flext_infra.workspace import (
    FlextInfraRopeWorkspace,
    FlextInfraWorkspaceDetector,
    FlextInfraWorkspaceEnvironmentMixin,
)

if TYPE_CHECKING:
    from flext_infra import p
    from flext_infra.codegen import FlextInfraCodegenProjectNew
    from flext_infra.docs import FlextInfraDocFormatter
    from flext_infra.release import FlextInfraReleaseOrchestrator
    from flext_infra.workspace import FlextInfraWorkspacePropagation


class FlextInfra(
    FlextInfraWorkspaceEnvironmentMixin,
    FlextInfraConformWiring,
    s[t.JsonDict],
):
    """Thin public FLEXT facade over infra services."""

    app_name: ClassVar[str] = "flext-infra"

    @staticmethod
    def bootstrap_candidate(
        request: m.Infra.CandidateBootstrapCommand,
    ) -> p.Result[bool]:
        """Compose typed declarations, conform planner and one atomic publisher.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        identity = u.Infra.exact_worktree_root(
            request.repository_root.expanduser().absolute(),
        )
        if identity.failure:
            return r[bool].from_failure(identity)
        source_root = identity.value.repo_root
        manifest = u.Cli.atomic_read_binary_file_state(
            u.Infra.workspace_manifest_path(source_root),
            required=True,
        )
        if manifest.failure:
            return r[bool].from_failure(manifest)
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(source_root)
        if workspace.failure:
            return r[bool].from_failure(workspace)
        return FlextInfraCandidateBootstrapService(
            # The campaign only plans through conform; it publishes through its
            # own transaction and never runs the complete surface.
            planner=FlextInfraCodegenConform(repository_root=source_root, ports=None),
            transaction=FlextInfraCodegenTransaction(
                FlextInfraCodegenMiseArtifacts(repository_root=source_root),
            ),
        ).execute(source_root, workspace.value, request, manifest.value)

    def rope_workspace(
        self,
        repository_root: Path | None = None,
    ) -> p.Infra.RopeWorkspaceDsl:
        """Open the public Rope workspace DSL directly from the facade.

        Returns:
            The resulting ``p.Infra.RopeWorkspaceDsl``.

        """
        # NOTE (multi-agent, flext-wkii.17.24): Rope reads its source policy
        # directly from config.Infra at the service boundary.

        resolved_root = (
            self.repository_root if repository_root is None else repository_root
        )
        return FlextInfraRopeWorkspace.open_workspace(resolved_root)

    @staticmethod
    def check(request: m.Infra.RunCommand) -> p.Result[bool]:
        """Compose one shared Rope cycle and execute every requested gate.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return FlextInfraWorkspaceChecker(
            repository_root=request.repository_root,
        ).execute_payload(request)

    @staticmethod
    def codegen_census(request: m.Infra.CodegenCommand) -> p.Result[str]:
        """Run the read-only census within the facade-owned Rope lifecycle.

        Returns:
            The resulting ``p.Result[str]``.

        """
        return FlextInfraCodegenCensus(
            repository_root=request.repository_root,
            apply_changes=request.apply,
            check_only=request.check_only,
            dry_run=request.dry_run,
            output_format=request.output_format,
        ).execute()

    @staticmethod
    def codegen_auto_fix(request: m.Infra.CodegenAutoFixCommand) -> p.Result[str]:
        """Run namespace fixes within the facade-owned Rope lifecycle.

        Returns:
            The resulting ``p.Result[str]``.

        """
        return FlextInfraCodegenFixer(
            repository_root=request.repository_root,
            apply_changes=request.apply,
            check_only=request.check_only,
            dry_run=request.dry_run,
            output_format=request.output_format,
            selected_projects=request.project_names,
            rules_only=request.rules_only,
        ).execute()

    def codegen_pipeline(self, request: m.Infra.CodegenCommand) -> p.Result[str]:
        """Run the codegen pipeline with the facade-wired conform ports.

        Returns:
            The resulting ``p.Result[str]``.

        """
        return FlextInfraCodegenPipeline(
            repository_root=request.repository_root,
            apply_changes=request.apply,
            check_only=request.check_only,
            dry_run=request.dry_run,
            output_format=request.output_format,
            conform_collaborators=self.codegen_conform_collaborators(),
        ).execute()

    def codegen_conform(
        self,
        request: m.Infra.CodegenConformRequest,
        initial_workspace: m.Infra.WorkspaceSpec | None = None,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Conform generated files with the facade-wired cross-family ports.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        return FlextInfraCodegenConform.execute_request(
            request,
            initial_workspace,
            ports=self.codegen_conform_collaborators(),
        )

    def codegen_new(
        self,
        command: FlextInfraCodegenProjectNew,
    ) -> p.Result[m.Infra.CodegenResult]:
        """Scaffold one project through conform with the facade-wired ports.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenResult]``.

        """
        return command.model_copy(
            update={"conform_collaborators": self.codegen_conform_collaborators()},
        ).execute()

    def release_run(self, command: FlextInfraReleaseOrchestrator) -> p.Result[bool]:
        """Run one release phase with the facade-wired conform ports.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return command.model_copy(
            update={"conform_collaborators": self.codegen_conform_collaborators()},
        ).execute()

    def workspace_propagate(
        self,
        command: FlextInfraWorkspacePropagation,
    ) -> p.Result[bool]:
        """Propagate to every member with the facade-wired conform ports.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return command.model_copy(
            update={"conform_collaborators": self.codegen_conform_collaborators()},
        ).execute()

    def docs_format(self, command: FlextInfraDocFormatter) -> p.Result[bool]:
        """Format docs through the facade-bound markdown format gate.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return command.model_copy(
            update={"format_gate": self.markdown_format_gate},
        ).execute()

    @staticmethod
    def apply_renames(
        request: m.Infra.ApplyRenamesInput,
    ) -> p.Result[m.Infra.ApplyRenamesReport]:
        """Compose and run one explicitly supplied CSV rename campaign.

        Returns:
            The resulting ``p.Result[m.Infra.ApplyRenamesReport]``.

        """
        return FlextInfraApplyRenames().run(request)

    def mod(
        self,
        request: m.Infra.ModCommand,
        progress: p.Infra.ModProgress,
    ) -> p.Result[t.Cli.ResultValue]:
        """Compose the codemod use case from typed config and real adapters.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        root = u.Infra.resolve_repository_root_or_cwd(request.repository_root)
        config = FlextInfraConfig.fetch_global().Infra.refactor_csv_campaigns
        config_dir = FlextInfraConfig.ssot_config_dir()
        config_root = config_dir.resolve()
        repository_root = root.resolve()
        campaigns: list[m.Infra.ApplyRenamesInput] = []
        for declared in config.campaigns:
            csv = config_dir / declared.csv
            if not csv.resolve().is_relative_to(config_root):
                return r[t.Cli.ResultValue].fail(
                    f"CSV campaign driver escapes config directory: {csv}",
                )
            campaign_roots = tuple(
                (root / value).resolve() for value in declared.roots
            ) or (root,)
            for path in campaign_roots:
                if not path.resolve().is_relative_to(repository_root):
                    return r[t.Cli.ResultValue].fail(
                        f"CSV campaign scan root escapes repository: {path}",
                    )
            campaigns.append(
                m.Infra.ApplyRenamesInput(
                    csv=str(csv),
                    roots=tuple(str(path) for path in campaign_roots),
                    apply=request.apply
                    and not request.check
                    and not request.dry_run_mode,
                    bindings=declared.bindings,
                    text_globs=declared.text_globs,
                    python_documentation=declared.python_documentation,
                    exclude_globs=declared.exclude_globs,
                ),
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
                phase_callbacks=(
                    FlextInfraImportNormalizationPhase(),
                    FlextInfraNamespaceRelocationPhase(),
                    FlextInfraAccessorRenamePhase(),
                ),
            ).execute()

    @staticmethod
    def validate_namespace(
        request: m.Infra.NamespaceValidateCommand,
    ) -> p.Result[m.Infra.ValidationReport]:
        """Validate one project against the rule catalog.

        Returns:
            The resulting ``p.Result[m.Infra.ValidationReport]``.

        """
        return FlextInfraNamespaceValidator(
            repository_root=request.repository_root,
        ).build_report()

    @staticmethod
    def mod_text(request: m.Infra.ModTextCommand) -> p.Result[t.Cli.ResultValue]:
        """Compose the standalone authenticated text-rule replay.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        root = u.Infra.resolve_repository_root_or_cwd(request.repository_root)
        return FlextInfraModTextGateEngine.run(root, apply=request.apply)

    @staticmethod
    def mod_text_candidate(
        request: m.Infra.ModTextCommand,
    ) -> p.Result[t.Cli.ResultValue]:
        """Replay one manifest-declared candidate using this healthy provider.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        source_root = u.Infra.resolve_repository_root_or_cwd(request.repository_root)
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(source_root)
        if workspace.failure:
            return r[t.Cli.ResultValue].from_failure(workspace)
        targets = workspace.value.candidate_bootstrap_targets
        if len(targets) != 1:
            return r[t.Cli.ResultValue].fail(
                "mod-text-candidate requires exactly one candidate_bootstrap_target",
            )
        # Non-strict: a missing declared worktree is graded by the exact-root
        # owner's typed failure instead of escaping as FileNotFoundError.
        identity = u.Infra.exact_worktree_root(
            (source_root / targets[0].path).resolve(),
        )
        if identity.failure:
            return r[t.Cli.ResultValue].from_failure(identity)
        return FlextInfraModTextGateEngine.run(
            identity.value.repo_root,
            apply=request.apply,
        )

    @staticmethod
    def project_context(cwd: Path) -> p.Result[m.Infra.WorkspaceProjectContext]:
        """Derive Git, workspace, and effective project facts from ``cwd``.

        Returns:
            The resulting ``p.Result[m.Infra.WorkspaceProjectContext]``.

        """
        resolved = cwd.expanduser().resolve()
        if not resolved.is_dir():
            return r[m.Infra.WorkspaceProjectContext].fail(
                f"project context cwd is not a directory: {resolved}",
            )
        identity = u.Infra.git_identity(m.Infra.GitRepoRequest(repo_root=resolved))
        if identity.failure:
            return r[m.Infra.WorkspaceProjectContext].ok(
                m.Infra.WorkspaceProjectContext(cwd=resolved),
            )
        root = identity.value.repo_root
        if not u.Infra.workspace_manifest_path(root).is_file():
            return r[m.Infra.WorkspaceProjectContext].ok(
                m.Infra.WorkspaceProjectContext(cwd=resolved, identity=identity.value),
            )
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(root)
        if workspace.failure:
            return r[m.Infra.WorkspaceProjectContext].from_failure(workspace)
        target = FlextInfraWorkspaceDetector.conform_target(root, workspace.value)
        if target.failure:
            return r[m.Infra.WorkspaceProjectContext].from_failure(target)
        return r[m.Infra.WorkspaceProjectContext].ok(
            m.Infra.WorkspaceProjectContext(
                cwd=resolved,
                identity=identity.value,
                workspace=workspace.value,
                target=target.value,
                governed=True,
            ),
        )

    @override
    def execute(self) -> p.Result[t.JsonDict]:
        """Execute a lightweight facade health report.

        Returns:
            The resulting ``p.Result[t.JsonDict]``.

        """
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
