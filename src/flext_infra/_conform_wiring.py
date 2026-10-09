"""Conform wiring collaborators for the public API facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m, r, t, u
from flext_infra.codegen import (
    FlextInfraCodegenConform,
    FlextInfraCodegenMiseArtifacts,
    FlextInfraCodegenTransaction,
)
from flext_infra.docs import FlextInfraDocGenerator
from flext_infra.gates import FlextInfraMarkdownFormatGate

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraConformWiring:
    """Bind the cross-family collaborators conform crosses into."""

    @staticmethod
    def generation_participant_policy(
        root: Path,
    ) -> p.Result[m.Infra.CodegenParticipantPolicy]:
        """Authorize the actual physical coordination root and declared members.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenParticipantPolicy]``.
        """
        return FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root),
        ).participant_policy()

    @staticmethod
    def codegen_footprint(
        request: m.Infra.CodegenConformRequest,
    ) -> p.Result[str]:
        """Inspect recorded authority and the public plan without any writer route.

        Returns:
            The resulting ``p.Result[str]``.
        """
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=request.root),
        )
        observed = transaction.inspect_journal()
        if observed.failure:
            return r[str].from_failure(observed)
        # Preserve the actual journal receipt even if subsequent planning fails.
        u.Cli.info(observed.value.model_dump_json())
        policy = transaction.participant_policy()
        if policy.failure:
            return r[str].from_failure(policy)
        footprint = observed.value.model_copy(
            update={
                "authorized_roots": tuple(root.target for root in policy.value.roots)
            },
        )
        u.Cli.info(footprint.model_dump_json())
        bounded = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=request.root),
            participant_policy=policy.value,
        )
        authorized = bounded.validate_footprint(footprint)
        if authorized.failure:
            return r[str].from_failure(authorized)
        planned = FlextInfraCodegenConform(
            repository_root=request.root,
            ports=None,
        ).plan(request)
        if planned.failure:
            return r[str].from_failure(planned)
        unchanged = bounded.validate_footprint(footprint)
        if unchanged.failure:
            return r[str].from_failure(unchanged)
        return r[str].ok(
            footprint.model_copy(
                update={
                    "planned_roots": tuple(
                        dict.fromkeys((
                            *(
                                environment.project_root
                                for environment in planned.value.uv_environments
                            ),
                            *(file.project for file in planned.value.files),
                        )),
                    ),
                    "planned_destinations": tuple(
                        file.path for file in planned.value.files
                    ),
                },
            ).model_dump_json(),
        )

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
            participant_policy=self.generation_participant_policy,
        )


__all__: list[str] = ["FlextInfraConformWiring"]
