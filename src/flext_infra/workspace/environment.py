"""Workspace environment sync owner for the public ``infra`` facade.

This is the canonical in-process surface for keeping one workspace's direnv
activation aligned with the codegen SSOT. ``codegen conform`` exclusively owns
``.mise.toml`` so environment sync cannot race toolchain publication.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, config, m, u
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraWorkspaceEnvironmentMixin:
    """Generate and sync canonical direnv/mise workspace files."""

    @classmethod
    def sync_environment_files(
        cls, request: m.Infra.WorkspaceEnvironmentSyncRequest
    ) -> p.Result[m.Infra.WorkspaceEnvironmentSyncResult]:
        """Sync one workspace's generated environment files."""
        result_type = m.Infra.WorkspaceEnvironmentSyncResult
        repository_root = request.repository_root
        if not (repository_root / c.PYPROJECT_FILENAME).is_file():
            return cls._remove_generated_environment_files(request)
        envrc_result = cls._sync_envrc(request)
        if envrc_result.failure:
            return r[result_type].from_failure(envrc_result)
        changed = (
            (repository_root / c.Infra.ENVRC_FILENAME,) if envrc_result.value else ()
        )
        return r[result_type].ok(result_type(changed_files=changed))

    @classmethod
    def _sync_envrc(
        cls, request: m.Infra.WorkspaceEnvironmentSyncRequest
    ) -> p.Result[bool]:
        """Write canonical ``.envrc`` when absent, generated, or forced.

        The rendered activation tier is declarative per repository: a
        governed Beads identity with ``gascity_enabled`` renders the city
        server wiring, one with city participation disabled renders the
        repository-local ``bd`` base, and a repository without any Beads
        identity renders only the terminal unset chain. A programmatic
        ``request.beads`` spec always carries its own backend.
        """
        gascity = request.beads
        identity = (
            request.repository_root / c.CONFIG_DIR_NAME / c.Infra.BEADS_CONFIG_FILENAME
        )
        if gascity is None:
            if not identity.is_file():
                gascity = m.Infra.BeadsWorkspaceEnvironmentSpec(backend="none")
            else:
                workspace = FlextInfraWorkspaceDetector.load_workspace_spec(
                    request.repository_root
                )
                if workspace.failure:
                    return r[bool].from_failure(workspace)
                gascity = (
                    m.Infra.BeadsWorkspaceEnvironmentSpec()
                    if workspace.value.gascity_enabled
                    else m.Infra.BeadsWorkspaceEnvironmentSpec(backend="local")
                )
        rendered = cls._render_environment_template(
            c.Infra.ENVRC_FILENAME, gascity=gascity
        )
        if rendered.failure:
            return r[bool].from_failure(rendered)
        return cls._write_generated_text(
            request.repository_root / c.Infra.ENVRC_FILENAME,
            rendered.value,
            apply=request.apply,
            force=request.force,
        )

    @classmethod
    def _render_environment_template(
        cls,
        destination: str,
        *,
        context: m.Infra.BeadsWorkspaceEnvironmentSpec | None = None,
        gascity: m.Infra.BeadsWorkspaceEnvironmentSpec | None = None,
    ) -> p.Result[str]:
        """Render one SSOT environment template from the toolchain spec."""
        template_path = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / config.Infra.codegen.templates.root
            / "base"
            / f"{destination}.j2"
        )
        render_context: (
            m.Infra.BeadsWorkspaceEnvironmentSpec | m.Infra.EnvrcRenderSpec
        ) = (
            context
            if context is not None
            else m.Infra.EnvrcRenderSpec(
                state_directory_name=config.Infra.codegen.toolchain.state_directory_name,
                scratch_namespace=config.Infra.codegen.toolchain.scratch_namespace,
                scratch_home_relative=(
                    config.Infra.codegen.toolchain.scratch_home_relative
                ),
                pycache_namespace=config.Infra.codegen.toolchain.pycache_namespace,
                environment_path_prepends=(
                    config.Infra.codegen.toolchain.environment_path_prepends
                ),
                mise_bootstrap=u.Infra.mise_bootstrap_environment(),
                gascity=gascity,
            )
        )
        return u.Cli.template_render(template_path, render_context)

    @classmethod
    def _remove_generated_environment_files(
        cls, request: m.Infra.WorkspaceEnvironmentSyncRequest
    ) -> p.Result[m.Infra.WorkspaceEnvironmentSyncResult]:
        """Remove generated environment files from non-Python workspaces."""
        result_type = m.Infra.WorkspaceEnvironmentSyncResult
        removed: list[Path] = []
        for filename in c.Infra.WORKSPACE_ENV_FILES:
            target_path = request.repository_root / filename
            result = cls._remove_generated_environment_file(
                target_path, apply=request.apply
            )
            if result.failure:
                return r[result_type].from_failure(result)
            if result.value:
                removed.append(target_path)
        return r[result_type].ok(result_type(changed_files=tuple(removed)))

    @classmethod
    def _remove_generated_environment_file(
        cls, target_path: Path, *, apply: bool
    ) -> p.Result[bool]:
        """Remove one generated environment file without touching custom files."""
        if not target_path.exists():
            return r[bool].ok(False)
        read = u.Cli.files_read_text(target_path)
        if read.failure:
            return r[bool].from_failure(read)
        if not cls._is_generated_environment_text(read.value):
            return r[bool].ok(False)
        if not apply:
            return r[bool].ok(True)
        delete_result = u.Cli.files_delete(target_path)
        if delete_result.failure:
            return r[bool].from_failure(delete_result)
        return r[bool].ok(True)

    @classmethod
    def _write_generated_text(
        cls, target_path: Path, content: str, *, apply: bool, force: bool
    ) -> p.Result[bool]:
        """Write generated content without clobbering custom files."""
        if target_path.exists():
            read = u.Cli.files_read_text(target_path)
            if read.failure:
                return r[bool].from_failure(read)
            existing = read.value
            if u.Cli.sha256_content(existing) == u.Cli.sha256_content(content):
                return r[bool].ok(False)
            if not force and not cls._is_generated_environment_text(existing):
                return r[bool].ok(False)
        return cls._write_text_if_different(target_path, content, apply=apply)

    @staticmethod
    def _write_text_if_different(
        target_path: Path, content: str, *, apply: bool
    ) -> p.Result[bool]:
        """Write text when content differs."""
        if target_path.is_file():
            read = u.Cli.files_read_text(target_path)
            if read.failure:
                return r[bool].from_failure(read)
            if read.value == content:
                return r[bool].ok(False)
        if not apply:
            return r[bool].ok(True)
        return u.Cli.atomic_write_text_file(target_path, content)

    @staticmethod
    def _is_generated_environment_text(content: str) -> bool:
        """Return True when content carries a canonical generated marker."""
        return any(
            marker in content for marker in c.Infra.WORKSPACE_ENV_GENERATED_MARKERS
        )


__all__: list[str] = ["FlextInfraWorkspaceEnvironmentMixin"]
