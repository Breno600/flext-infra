"""Rope-owned migration of transaction path capability consumers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .rope_runtime_refactors import FlextInfraUtilitiesRopeRuntimeRefactors

if TYPE_CHECKING:
    from flext_infra import m, p, t


class FlextInfraUtilitiesCodegenPathCutover:
    """Plan one immutable Rope change set per existing mod-loop iteration."""

    @classmethod
    def plan_transaction_path_cutover(
        cls,
        *,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
        sources: t.MappingKV[Path, str],
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Migrate exact owner calls, preserving homonyms and root-only callers."""
        from flext_infra import m, p

        project = rope_workspace.rope_project
        root = Path(project.root.real_path)
        owner_module = "flext_infra.codegen._mise_artifacts_files"
        owners = tuple(
            module.file_path.resolve()
            for module in rope_workspace.modules()
            if module.module_name == owner_module
            and module.file_path.resolve() in sources
        )
        if not owners:
            return ()
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
        selected = tuple(
            path
            for path in sorted(sources)
            if path.parent == owner_path.parent and path != owner_path
        )
        resources = tuple(
            project.get_resource(path.relative_to(root).as_posix()) for path in selected
        )
        for resource, path in zip(resources, selected, strict=True):
            if resource.read() != sources[path]:
                msg = f"Rope source differs from the mod planning snapshot: {path}"
                raise ValueError(msg)
        owner = f"name={owner_module}.FlextInfraMiseArtifactsFiles,exact"
        # Each ChangeSet observes one real source snapshot. The existing mod
        # loop publishes it and replans before the next semantic operation.
        transformations = (
            (
                "${files}.resolve_relative(${layout}.scope_root, ${path}, purpose=${purpose})",
                "${files}.resolve_transaction(${layout}, ${path}, purpose=${purpose})",
            ),
            (
                "${files}.workspace_relative(${layout}.scope_root, ${path})",
                "${files}.transaction_relative(${layout}, ${path})",
            ),
        )
        for pattern, goal in transformations:
            changes = FlextInfraUtilitiesRopeRuntimeRefactors.restructure_changes(
                project, pattern, goal, arguments={"files": owner}, resources=resources
            )
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
                    )
                )
            if edits:
                return tuple(edits)
        return ()


__all__: list[str] = ["FlextInfraUtilitiesCodegenPathCutover"]
