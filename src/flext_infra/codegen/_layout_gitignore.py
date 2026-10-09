"""Gitignore ownership for the layout engine apply path.

Codegen-managed projects converge through the canonical conform render (one
owner, one template); unmanaged or external projects receive idempotent
appends of the missing patterns only.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, m, p, r, t, u
from flext_infra.codegen._layout_plan import FlextInfraCodegenLayoutPlanMixin
from flext_infra.codegen._mise_artifacts_publication import FlextInfraMisePublication
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraCodegenLayoutGitignoreMixin:
    """Ensure the layout gitignore patterns for one project directory."""

    def _apply_gitignore(
        self,
        project_dir: Path,
        patterns: t.StrSequence,
    ) -> p.Result[t.Infra.LayoutStatus]:
        """Ensure gitignore patterns via the canonical render or appending.

        Returns:
            The resulting ``p.Result[t.Infra.LayoutStatus]``.

        """
        managed = self._managed_profile(project_dir)
        if managed.failure:
            return r[t.Infra.LayoutStatus].from_failure(managed)
        profile = managed.value
        if profile is not None:
            return self._apply_gitignore_managed(project_dir, profile)
        return self._apply_gitignore_append(project_dir, patterns)

    @staticmethod
    def _apply_gitignore_managed(
        project_dir: Path,
        profile: c.Infra.MakeProfile,
    ) -> p.Result[t.Infra.LayoutStatus]:
        """Write the canonical rendered gitignore for a governed project.

        Returns:
            The resulting ``p.Result[t.Infra.LayoutStatus]``.

        """
        rendered = u.Infra.render_project_gitignore(
            config.Infra.codegen,
            profile=profile,
            project_name=FlextInfraCodegenLayoutPlanMixin.layout_project_name(
                project_dir,
            ),
            project_dir=project_dir,
        )
        if rendered.failure:
            return r[t.Infra.LayoutStatus].from_failure(rendered)
        gitignore_path = project_dir / c.Infra.GITIGNORE
        current = ""
        if gitignore_path.is_file():
            read = u.Cli.files_read_text(gitignore_path)
            if read.failure:
                return r[t.Infra.LayoutStatus].from_failure(read)
            current = read.value
        if rendered.value == current:
            noop_status: t.Infra.LayoutStatus = "noop"
            return r[t.Infra.LayoutStatus].ok(noop_status)
        before = u.Cli.atomic_read_binary_file_state(gitignore_path, required=False)
        if before.failure:
            return r[t.Infra.LayoutStatus].from_failure(before)
        planned = m.Infra.CodegenFilePlan(
            project=project_dir,
            path=gitignore_path,
            before=before.value,
            desired_content=rendered.value.encode(c.Cli.ENCODING_DEFAULT),
            desired_mode=0o644,
            owner="codegen",
            policy="full",
        )
        written = FlextInfraMisePublication.publish_file_plan(
            planned,
            phase=c.Infra.CodegenStagedFilePhase.LAYOUT,
        )
        if written.failure:
            return r[t.Infra.LayoutStatus].from_failure(written)
        applied_status: t.Infra.LayoutStatus = "applied"
        return r[t.Infra.LayoutStatus].ok(applied_status)

    @staticmethod
    def _apply_gitignore_append(
        project_dir: Path,
        patterns: t.StrSequence,
    ) -> p.Result[t.Infra.LayoutStatus]:
        """Append missing patterns for an unmanaged or external project.

        Returns:
            The resulting ``p.Result[t.Infra.LayoutStatus]``.

        """
        gitignore_path = project_dir / c.Infra.GITIGNORE
        current = ""
        if gitignore_path.is_file():
            read = u.Cli.files_read_text(gitignore_path)
            if read.failure:
                return r[t.Infra.LayoutStatus].from_failure(read)
            current = read.value
        covered = {line.strip() for line in current.splitlines()}
        missing = tuple(
            pattern
            for pattern in patterns
            if pattern not in covered and pattern.rstrip("/") not in covered
        )
        if not missing:
            noop_status: t.Infra.LayoutStatus = "noop"
            return r[t.Infra.LayoutStatus].ok(noop_status)
        text = current
        if text and not text.endswith("\n"):
            text += "\n"
        if text:
            text += "\n"
        text += f"# {c.Infra.GITIGNORE_LAYOUT_SECTION_NAME}\n"
        text += "\n".join(missing) + "\n"
        before = u.Cli.atomic_read_binary_file_state(gitignore_path, required=False)
        if before.failure:
            return r[t.Infra.LayoutStatus].from_failure(before)
        planned = m.Infra.CodegenFilePlan(
            project=project_dir,
            path=gitignore_path,
            before=before.value,
            desired_content=text.encode(c.Cli.ENCODING_DEFAULT),
            desired_mode=0o644,
            owner="codegen",
            policy="merge",
        )
        written = FlextInfraMisePublication.publish_file_plan(
            planned,
            phase=c.Infra.CodegenStagedFilePhase.LAYOUT,
        )
        if written.failure:
            return r[t.Infra.LayoutStatus].from_failure(written)
        applied_status: t.Infra.LayoutStatus = "applied"
        return r[t.Infra.LayoutStatus].ok(applied_status)

    @staticmethod
    def _managed_profile(project_dir: Path) -> p.Result[c.Infra.MakeProfile | None]:
        """Make profile when the project is governed by a workspace.

        Returns:
            The resulting ``p.Result[c.Infra.MakeProfile | None]``.

        """
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(
            u.Infra.resolve_repository_root_or_cwd(project_dir),
        )
        if workspace.failure:
            return r[c.Infra.MakeProfile | None].from_failure(workspace)
        target = FlextInfraWorkspaceDetector.conform_target(
            project_dir,
            workspace.value,
        )
        if target.failure:
            return r[c.Infra.MakeProfile | None].from_failure(target)
        return r[c.Infra.MakeProfile | None].ok(target.value.make_profile)


__all__: list[str] = ["FlextInfraCodegenLayoutGitignoreMixin"]
