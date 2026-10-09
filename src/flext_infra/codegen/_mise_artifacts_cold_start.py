"""Projection of flext-infra's own `make upg` triple into its packaged copy.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r, t, u
from flext_infra.codegen._mise_artifacts_derivation import (
    FlextInfraMiseArtifactsDerivation,
)
from flext_infra.codegen._mise_artifacts_files import (
    FlextInfraMiseArtifactsFiles as files,
)
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts
from flext_infra.codegen.mise_artifacts_workspace import FlextInfraMiseWorkspacePlanner

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraMiseColdStart:
    """Keep the packaged cold-start triple a byte copy of the runtime root's.

    A repository that has never carried a Mise pin and launchers, or still
    carries the pre-bake projection whose launchers resolve the latest release
    at run time, starts from the copy the installed flext-infra ships. Only
    the repository whose ``src/`` holds the running ``flext_infra`` package
    owns that copy, so every
    other repository plans nothing and nobody maintains a hand-written seed.
    """

    @staticmethod
    def candidate_plans(root: Path) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Recover one complete candidate triple from the packaged upg output.

        Returns:
            The resulting ``p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]``.

        """
        result_type = r[t.SequenceOf[m.Infra.CodegenFilePlan]]
        source_root = files.cold_start_directory()
        validated = FlextInfraMiseArtifactsDerivation.validate_packaged(source_root)
        if validated.failure:
            return result_type.from_failure(validated)
        sources: list[m.Cli.AtomicFileState] = []
        for name, _mode in c.Infra.ARTIFACT_SPECS:
            state = u.Cli.atomic_read_binary_file_state(
                source_root / Path(name).name,
                required=True,
            )
            if state.failure:
                return result_type.from_failure(state)
            sources.append(state.value)
        if len(sources) != len(c.Infra.ARTIFACT_SPECS) or any(
            state.content is None for state in sources
        ):
            return result_type.fail("packaged Mise recovery triple is incomplete")
        plans: list[m.Infra.CodegenFilePlan] = []
        for source, (name, mode) in zip(sources, c.Infra.ARTIFACT_SPECS, strict=True):
            destination = root / name
            before = u.Cli.atomic_read_binary_file_state(destination, required=False)
            if before.failure:
                return result_type.from_failure(before)
            plans.append(
                m.Infra.CodegenFilePlan(
                    project=root,
                    path=destination,
                    before=before.value,
                    desired_content=source.content,
                    desired_mode=mode,
                    source_states=(source,),
                ),
            )
        return result_type.ok(tuple(plans))

    @classmethod
    def plans(cls, root: Path) -> p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]:
        """Plan the packaged copy when ``root`` holds the running package.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]``.

        """
        result_type = r[tuple[m.Infra.CodegenFilePlan, ...]]
        project = root.expanduser().resolve()
        package = files.package_directory()
        if not package.is_relative_to(project) or package.relative_to(project).parts[
            :1
        ] != (c.Infra.DEFAULT_SRC_DIR,):
            return result_type.ok(())
        planner = FlextInfraMiseWorkspacePlanner(
            FlextInfraCodegenMiseArtifacts(repository_root=project),
        )
        scope_root = planner.scope_root()
        if scope_root.failure:
            return result_type.from_failure(scope_root)
        runtime = planner.runtime_artifacts(scope_root.value)
        if runtime.failure:
            return result_type.from_failure(runtime)
        sources = runtime.value.states
        plans: list[m.Infra.CodegenFilePlan] = []
        for source, (name, mode) in zip(sources, c.Infra.ARTIFACT_SPECS, strict=True):
            path = files.cold_start_directory() / Path(name).name
            before = u.Cli.atomic_read_binary_file_state(path, required=False)
            if before.failure:
                return result_type.from_failure(before)
            plans.append(
                m.Infra.CodegenFilePlan(
                    project=project,
                    path=path,
                    before=before.value,
                    desired_content=source.content,
                    desired_mode=mode,
                    source_states=(source,),
                ),
            )
        return result_type.ok(tuple(plans))


__all__: list[str] = ["FlextInfraMiseColdStart"]
