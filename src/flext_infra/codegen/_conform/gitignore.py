"""Public ``.gitignore`` rendering seam of the conform facade."""

from __future__ import annotations

from pathlib import Path

from ... import c, m, p, u
from .bootstrap import FlextInfraCodegenConformBootstrap


class FlextInfraCodegenConformGitignore(FlextInfraCodegenConformBootstrap):
    """Public ``.gitignore`` rendering seam of the conform facade."""

    @staticmethod
    def render_project_gitignore(
        codegen: m.Infra.CodegenConfigSpec,
        *,
        profile: c.Infra.MakeProfile,
        project_name: str,
        workspace: m.Infra.WorkspaceSpec | None = None,
        project_dir: Path | None = None,
    ) -> p.Result[str]:
        """Render the canonical ``.gitignore`` for one named project.

        The section projection and template rendering are owned by
        ``u.Infra.render_project_gitignore``; conform exposes the same seam so
        conform planning and the layout engine never diverge.
        """
        return u.Infra.render_project_gitignore(
            codegen,
            profile=profile,
            project_name=project_name,
            workspace=workspace,
            project_dir=project_dir,
        )


__all__: list[str] = ["FlextInfraCodegenConformGitignore"]
