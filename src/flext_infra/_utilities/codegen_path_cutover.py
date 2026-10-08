"""Rope-owned migration of transaction path capability consumers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import m, p, t
from flext_infra._utilities import (
    FlextInfraUtilitiesRopeRuntime,
    FlextInfraUtilitiesRopeRuntimeRefactors,
)


class FlextInfraUtilitiesCodegenPathCutover:
    """Plan one immutable Rope change set per existing mod-loop iteration."""

    @staticmethod
    def _governed_owner_path(
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
        owner_module: str,
    ) -> Path | None:
        """Resolve the single governed owner module path inside the inventory.

        Returns:
            The resulting ``Path | None``.

        Raises:
            ValueError: If transaction path implementation has ambiguous governed
                ownership; or if Rope could not resolve the transaction path
                implementation owner; or if Rope resolved a transaction owner outside
                the governed inventory.

        """
        project = rope_workspace.rope_project
        owners = tuple(
            module.file_path.resolve()
            for module in rope_workspace.modules()
            if module.module_name == owner_module
            and module.file_path.resolve() in sources
        )
        if not owners:
            return None
        if len(owners) != 1:
            msg = "transaction path implementation has ambiguous governed ownership"
            raise ValueError(msg)
        owner_path = owners[0]
        owner_resource = project.get_module(owner_module).get_resource()
        if owner_resource is None:
            msg = "Rope could not resolve the transaction path implementation owner"
            raise ValueError(msg)
        if Path(owner_resource.real_path) != owner_path:
            msg = "Rope resolved a transaction owner outside the governed inventory"
            raise ValueError(msg)
        return owner_path

    @staticmethod
    def _verified_resources(
        project: p.Infra.RopeProject,
        root: Path,
        sources: t.MappingKV[Path, str],
        owner_path: Path,
    ) -> t.Pair[t.VariadicTuple[p.Infra.RopeResource], t.VariadicTuple[Path]]:
        """Pair each sibling resource with its path after snapshot verification.

        Returns:
            The resulting ``(resources, selected paths)`` pair.

        Raises:
            TypeError: If a sibling resource is not a Rope file resource.
            ValueError: If Rope source differs from the mod planning snapshot.

        """
        selected = tuple(
            path
            for path in sorted(sources)
            if path.parent == owner_path.parent and path != owner_path
        )
        resources = tuple(
            project.get_resource(path.relative_to(root).as_posix()) for path in selected
        )
        for resource, path in zip(resources, selected, strict=True):
            if not FlextInfraUtilitiesRopeRuntime.file_resource(resource):
                msg = f"expected a Rope file resource: {path}"
                raise TypeError(msg)
            if resource.read() != sources[path]:
                msg = f"Rope source differs from the mod planning snapshot: {path}"
                raise ValueError(msg)
        return resources, selected

    @classmethod
    def _content_edits(
        cls,
        changes: p.Infra.RopeChangeSet,
        sources: t.MappingKV[Path, str],
        selected: t.VariadicTuple[Path],
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Project one Rope change set into governed content edits.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.SemanticMigrationEdit]``.

        Raises:
            TypeError: If transaction path restructuring produced a non-content effect.
            ValueError: If Rope change escaped the governed source inventory.

        """
        edits: list[m.Infra.SemanticMigrationEdit] = []
        for change in changes.changes:
            if not isinstance(change, p.Infra.RopeChangeContents):
                msg = "transaction path restructuring produced a non-content effect"
                raise TypeError(msg)
            path = Path(change.resource.real_path)
            if path not in sources or path not in selected:
                msg = f"Rope change escaped the governed source inventory: {path}"
                raise ValueError(msg)
            edits.append(
                m.Infra.SemanticMigrationEdit(
                    file_path=path,
                    original_source=sources[path],
                    updated_source=change.new_contents,
                    changes=("Rope transaction path capability migration",),
                ),
            )
        return tuple(edits)

    @classmethod
    def _transformation_edits(
        cls,
        project: p.Infra.RopeProject,
        sources: t.MappingKV[Path, str],
        selected: t.VariadicTuple[Path],
        resources: t.VariadicTuple[p.Infra.RopeResource],
        owner: str,
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Run the two call-shape transformations and return the first edits.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.SemanticMigrationEdit]``.

        """
        transformations = (
            (
                (
                    "${files}.resolve_relative(${layout}.scope_root, "
                    "${path}, purpose=${purpose})"
                ),
                "${files}.resolve_transaction(${layout}, ${path}, purpose=${purpose})",
            ),
            (
                "${files}.workspace_relative(${layout}.scope_root, ${path})",
                "${files}.transaction_relative(${layout}, ${path})",
            ),
        )
        for pattern, goal in transformations:
            changes = FlextInfraUtilitiesRopeRuntimeRefactors.restructure_changes(
                project,
                pattern,
                goal,
                arguments={"files": owner},
                resources=resources,
            )
            edits = cls._content_edits(changes, sources, selected)
            if edits:
                return edits
        return ()

    @classmethod
    def plan_transaction_path_cutover(
        cls,
        *,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Migrate exact owner calls, preserving homonyms and root-only callers.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.SemanticMigrationEdit]``.

        """
        project = rope_workspace.rope_project
        root = Path(project.root.real_path)
        owner_module = "flext_infra.codegen._mise_artifacts_files"
        owner_path = cls._governed_owner_path(rope_workspace, sources, owner_module)
        if owner_path is None:
            return ()
        resources, selected = cls._verified_resources(
            project,
            root,
            sources,
            owner_path,
        )
        owner = f"name={owner_module}.FlextInfraMiseArtifactsFiles,exact"
        # Each ChangeSet observes one real source snapshot. The existing mod
        # loop publishes it and replans before the next semantic operation.
        return cls._transformation_edits(project, sources, selected, resources, owner)


__all__: list[str] = ["FlextInfraUtilitiesCodegenPathCutover"]
