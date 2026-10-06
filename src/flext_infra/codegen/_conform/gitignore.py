"""Public ``.gitignore`` rendering seam of the conform facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra.codegen._conform.bootstrap import FlextInfraCodegenConformBootstrap
from flext_infra import c, p, m, u


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

        Returns:
            The resulting ``p.Result[str]``.

        """
        return u.Infra.render_project_gitignore(
            codegen,
            profile=profile,
            project_name=project_name,
            workspace=workspace,
            project_dir=project_dir,
        )


__all__: list[str] = ["FlextInfraCodegenConformGitignore"]
