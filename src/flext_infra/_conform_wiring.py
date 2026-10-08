"""Conform wiring collaborators for the public API facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m, t
from flext_infra.docs import FlextInfraDocGenerator
from flext_infra.gates import FlextInfraMarkdownFormatGate

if TYPE_CHECKING:
    from flext_infra import p


class _FlextInfraConformWiringMixin:
    """Bind the cross-family collaborators conform crosses into."""

    @staticmethod
    def docs_artifact_planner(
        *,
        repository_root: Path,
        projects: t.StrSequence,
        include_root: bool,
    ) -> p.Infra.DocsArtifactPlanner:
        """Build the docs planner complete conform publishes through.

        Returns:
            The resulting ``p.Infra.DocsArtifactPlanner``.

        """


        return FlextInfraDocGenerator(
            repository_root=repository_root,
            projects=projects,
            include_root=include_root,
        )

    @staticmethod
    def markdown_format_gate(repository_root: Path) -> p.Infra.MarkdownFormatGate:
        """Build the markdown format gate the docs formatter delegates to.

        Returns:
            The resulting ``p.Infra.MarkdownFormatGate``.

        """


        return FlextInfraMarkdownFormatGate(repository_root)

    def codegen_conform_collaborators(self) -> m.Infra.CodegenConformPorts:
        """Bind the docs family complete conform crosses into.

        Returns:
            The resulting ``m.Infra.CodegenConformPorts``.

        """
        return m.Infra.CodegenConformPorts(
            docs_planner=self.docs_artifact_planner,
        )
