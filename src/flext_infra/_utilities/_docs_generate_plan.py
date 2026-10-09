"""Normalized artifact inventory and destination planning for generated docs.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_cli import u as cli_u

from flext_infra import m, r, t
from flext_infra._utilities._docs_generate_sources import (
    FlextInfraUtilitiesDocsGenerateSourcesMixin,
)
from flext_infra._utilities.docs_contract import FlextInfraUtilitiesDocsContract

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesDocsGeneratePlanMixin(
    FlextInfraUtilitiesDocsGenerateSourcesMixin,
):
    """Normalize rendered artifacts and bind them to exact destination states."""

    @staticmethod
    def _directory_sort_key(path: Path) -> t.Pair[int, str]:
        """Return the stable parent-first ordering key for a directory.

        Returns:
            The stable parent-first ordering key for a directory.

        """
        return len(path.parts), path.as_posix()

    @staticmethod
    def docs_normalize_artifacts(
        artifacts: t.SequenceOf[t.Infra.DocsRenderedArtifactTuple],
    ) -> p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]:
        """Validate one unique lexical owner and target without dereferencing.

        Returns:
            The resulting
                ``p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]``.

        """
        normalized: list[t.Infra.DocsRenderedArtifactTuple] = []
        targets: set[Path] = set()
        for project, target, content in artifacts:
            if (
                not project.is_absolute()
                or not target.is_absolute()
                or ".." in project.parts
                or ".." in target.parts
            ):
                return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].fail(
                    f"docs publication paths must be absolute and lexical: {target}",
                )
            if not target.is_relative_to(project):
                return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].fail(
                    f"docs publication target escapes project {project}: {target}",
                )
            if target in targets:
                return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].fail(
                    f"duplicate docs publication target: {target}",
                )
            targets.add(target)
            normalized.append((project, target, content))
        return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].ok(
            tuple(normalized),
        )

    @staticmethod
    def docs_required_directories(
        bundle: m.Infra.DocsGenerationBundle,
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Return unique target directories ordered parent before child.

        Returns:
            Unique target directories ordered parent before child.

        """
        required: set[Path] = set()
        for scoped in bundle.scopes:
            for artifact in scoped.artifacts:
                if artifact.desired_content is None:
                    continue
                parent = scoped.scope.path
                for part in artifact.relative_path.parent.parts:
                    parent /= part
                    required.add(parent)
        return r[t.VariadicTuple[Path]].ok(
            tuple(
                sorted(
                    required,
                    key=FlextInfraUtilitiesDocsGeneratePlanMixin._directory_sort_key,
                ),
            ),
        )

    @staticmethod
    def docs_file_plans(
        bundle: m.Infra.DocsGenerationBundle,
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]:
        """Snapshot targets from the canonical rendered artifact inventory.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]``.

        """
        # The physical repository root is carried by the bundle: the first output
        # scope is a member when the root is excluded from the render.
        repository_root = bundle.repository_root
        scope_roots = tuple(scoped.scope.path for scoped in bundle.scopes)
        # The single race barrier of the docs cycle: every snapshotted source is
        # re-read here, once, immediately before publication planning; the
        # destination CAS re-validates physically at publish time.
        stable = FlextInfraUtilitiesDocsGeneratePlanMixin.docs_verify_sources(
            repository_root,
            bundle.source_states,
            extra_roots=scope_roots,
        )
        if stable.failure:
            return r[tuple[m.Infra.CodegenFilePlan, ...]].from_failure(stable)
        plans: list[m.Infra.CodegenFilePlan] = []
        for scoped in bundle.scopes:
            for artifact in scoped.artifacts:
                planned = FlextInfraUtilitiesDocsContract.docs_file_plan(
                    scoped.scope.path,
                    scoped.scope.path / artifact.relative_path,
                    artifact.desired_content,
                    desired_mode=artifact.desired_mode,
                    source_states=bundle.source_states,
                )
                if planned.failure:
                    return r[tuple[m.Infra.CodegenFilePlan, ...]].from_failure(planned)
                plans.append(planned.value)
        return r[tuple[m.Infra.CodegenFilePlan, ...]].ok(tuple(plans))

    @staticmethod
    def _prune_generated_tree_artifacts(
        project: Path,
        root: Path,
        rendered: t.SequenceOf[t.Pair[Path, str]],
    ) -> p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]:
        """Describe stale files owned by one generated tree as absent artifacts.

        Returns:
            The resulting
                ``p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]``.

        """
        planned = cli_u.Cli.atomic_plan_directory_chain(root)
        if planned.failure:
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].from_failure(
                planned,
            )
        if planned.value.directories:
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].ok(())
        inventory = cli_u.Cli.atomic_inventory_physical_tree(root)
        if inventory.failure:
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].from_failure(
                inventory,
            )
        expected_paths = {
            path for path, _content in rendered if path.is_relative_to(root)
        }
        return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].ok(
            tuple(
                (project, entry.path, None)
                for entry in inventory.value.entries
                if entry.kind == "file"
                and entry.path.suffix == ".md"
                and entry.path not in expected_paths
            ),
        )


__all__: list[str] = ["FlextInfraUtilitiesDocsGeneratePlanMixin"]
