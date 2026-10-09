"""Workspace environment sync owner for the public ``infra`` facade.

This is the canonical in-process surface for keeping one workspace's direnv
activation aligned with the codegen SSOT. ``codegen conform`` exclusively owns
``.mise.toml`` so environment sync cannot race toolchain publication.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, config, m, r, t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkspaceEnvironmentMixin:
    """Generate and sync canonical direnv/mise workspace files."""

    @classmethod
    def sync_environment_files(
        cls,
        request: m.Infra.WorkspaceEnvironmentSyncRequest,
        *,
        runner: p.Cli.CommandRunner | None = None,
    ) -> p.Result[m.Infra.WorkspaceEnvironmentSyncResult]:
        """Sync one workspace's generated environment files.

        Returns:
            The resulting ``p.Result[m.Infra.WorkspaceEnvironmentSyncResult]``.

        """
        result_type = m.Infra.WorkspaceEnvironmentSyncResult
        repository_root = request.repository_root
        if not (repository_root / c.PYPROJECT_FILENAME).is_file():
            result = cls._remove_generated_environment_files(request)
        else:
            envrc_result = cls._sync_envrc(request)
            if envrc_result.failure:
                return r[result_type].from_failure(envrc_result)
            changed = (
                (repository_root / c.Infra.ENVRC_FILENAME,)
                if envrc_result.value
                else ()
            )
            result = r[result_type].ok(result_type(changed_files=changed))
        if result.failure:
            return result
        allow_result = cls._allow_direnv_if_requested(request, runner=runner)
        if allow_result.failure:
            return r[result_type].from_failure(allow_result)
        return result

    @classmethod
    def _sync_envrc(
        cls,
        request: m.Infra.WorkspaceEnvironmentSyncRequest,
    ) -> p.Result[bool]:
        """Write the Python workspace ``.envrc`` without storage routing.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        rendered = cls._render_environment_template(c.Infra.ENVRC_FILENAME)
        if rendered.failure:
            return r[bool].from_failure(rendered)
        return cls._write_generated_text(
            request.repository_root / c.Infra.ENVRC_FILENAME,
            rendered.value,
            apply=request.apply,
            force=request.force,
        )

    @classmethod
    def _render_environment_template(cls, destination: str) -> p.Result[str]:
        """Render one SSOT environment template from the toolchain spec.

        Returns:
            The resulting ``p.Result[str]``.

        """
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / config.Infra.codegen.templates.root
            / "base"
            / f"{destination}.j2"
        )
        render_context = m.Infra.EnvrcRenderSpec(
            worktree_environment_directory=(
                config.Infra.codegen.toolchain.worktree_environment_directory
            ),
            repository_root_rel=".",
            environment_path_prepends=(
                config.Infra.codegen.toolchain.environment_path_prepends
            ),
            mise_bootstrap=u.Infra.mise_bootstrap_environment(),
        )
        return u.Cli.template_render(template_path, render_context)

    @classmethod
    def _allow_direnv_if_requested(
        cls,
        request: m.Infra.WorkspaceEnvironmentSyncRequest,
        *,
        runner: p.Cli.CommandRunner | None = None,
    ) -> p.Result[bool]:
        """Run ``direnv allow`` for one applied sync that owns the envrc.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        envrc = request.repository_root / c.Infra.ENVRC_FILENAME
        if not request.apply or not request.allow_direnv or not envrc.is_file():
            return r[bool].ok(value=False)
        runner_service = runner or u.Cli
        result = runner_service.run_raw(
            (c.Infra.CLI_DIRENV, "allow", str(request.repository_root)),
            cwd=request.repository_root,
            timeout=c.Infra.TIMEOUT_DEFAULT,
        )
        if result.failure:
            return r[bool].from_failure(result)
        output = result.value
        if not u.Cli.process_succeeded(output.outcome):
            return r[bool].fail(
                f"direnv allow failed for {request.repository_root}: "
                f"{output.stderr.strip() or output.stdout.strip()}",
            )
        return r[bool].ok(value=True)

    @classmethod
    def execute_request(
        cls,
        request: m.Infra.WorkspaceEnvironmentSyncRequest,
    ) -> p.Result[t.Cli.ResultValue]:
        """Run one sync request through the public workspace owner.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        result = cls.sync_environment_files(request)
        if result.failure:
            return r[t.Cli.ResultValue].from_failure(result)
        return r[t.Cli.ResultValue].ok(
            tuple(str(path) for path in result.value.changed_files),
        )

    @classmethod
    def _remove_generated_environment_files(
        cls,
        request: m.Infra.WorkspaceEnvironmentSyncRequest,
    ) -> p.Result[m.Infra.WorkspaceEnvironmentSyncResult]:
        """Remove generated environment files from non-Python workspaces.

        Returns:
            The resulting ``p.Result[m.Infra.WorkspaceEnvironmentSyncResult]``.

        """
        result_type = m.Infra.WorkspaceEnvironmentSyncResult
        removed: list[Path] = []
        for filename in c.Infra.WORKSPACE_ENV_FILES:
            target_path = request.repository_root / filename
            result = cls._remove_generated_environment_file(
                target_path,
                apply=request.apply,
            )
            if result.failure:
                return r[result_type].from_failure(result)
            if result.value:
                removed.append(target_path)
        return r[result_type].ok(result_type(changed_files=tuple(removed)))

    @classmethod
    def _remove_generated_environment_file(
        cls,
        target_path: Path,
        *,
        apply: bool,
    ) -> p.Result[bool]:
        """Remove one generated environment file without touching custom files.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not target_path.exists():
            return r[bool].ok(value=False)
        read = u.Cli.files_read_text(target_path)
        if read.failure:
            return r[bool].from_failure(read)
        if not cls._is_generated_environment_text(read.value):
            return r[bool].ok(value=False)
        if not apply:
            return r[bool].ok(value=True)
        delete_result = u.Cli.files_delete(target_path)
        if delete_result.failure:
            return r[bool].from_failure(delete_result)
        return r[bool].ok(value=True)

    @classmethod
    def _write_generated_text(
        cls,
        target_path: Path,
        content: str,
        *,
        apply: bool,
        force: bool,
    ) -> p.Result[bool]:
        """Write generated content without clobbering custom files.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if target_path.exists():
            read = u.Cli.files_read_text(target_path)
            if read.failure:
                return r[bool].from_failure(read)
            existing = read.value
            if u.Cli.sha256_content(existing) == u.Cli.sha256_content(content):
                return r[bool].ok(value=False)
            if not force and not cls._is_generated_environment_text(existing):
                return r[bool].ok(value=False)
        return cls._write_text_if_different(target_path, content, apply=apply)

    @staticmethod
    def _write_text_if_different(
        target_path: Path,
        content: str,
        *,
        apply: bool,
    ) -> p.Result[bool]:
        """Write text when content differs.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if target_path.is_file():
            read = u.Cli.files_read_text(target_path)
            if read.failure:
                return r[bool].from_failure(read)
            if read.value == content:
                return r[bool].ok(value=False)
        if not apply:
            return r[bool].ok(value=True)
        return u.Cli.atomic_write_text_file(target_path, content)

    @staticmethod
    def _is_generated_environment_text(content: str) -> bool:
        """Return True when content carries a canonical generated marker.

        Returns:
            True when content carries a canonical generated marker.

        """
        return any(
            marker in content for marker in c.Infra.WORKSPACE_ENV_GENERATED_MARKERS
        )


__all__: list[str] = ["FlextInfraWorkspaceEnvironmentMixin"]
