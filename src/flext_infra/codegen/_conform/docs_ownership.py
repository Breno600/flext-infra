"""Docs publication ownership scoped to the invoked repository."""

from __future__ import annotations

from pathlib import Path

from ... import m, t
from .gitignore import FlextInfraCodegenConformGitignore


class FlextInfraCodegenConformDocsOwnership(FlextInfraCodegenConformGitignore):
    """Docs publication ownership scoped to the invoked repository."""

    @staticmethod
    def _member_repository_roots(
        request: m.Infra.CodegenConformRequest, plan: m.Infra.CodegenPlan
    ) -> t.VariadicTuple[Path]:
        """Return the physical roots of the declared member repositories."""
        return tuple(
            (request.root / repository.path).resolve()
            for repository in plan.repositories
            if repository.path != Path()
        )

    @staticmethod
    def owned_docs_files(
        request: m.Infra.CodegenConformRequest,
        files: t.SequenceOf[m.Infra.CodegenFilePlan],
    ) -> t.VariadicTuple[m.Infra.CodegenFilePlan]:
        """Keep only docs plans owned by the invoked repository's own scope.

        Member repositories declared ``codegen: conform`` are self-governing:
        their generated docs (``mkdocs.yml``, ``docs/api-reference/generated/**``)
        are planned and published exclusively by the member's own conform run.
        The planner already stamps each docs plan with its physical owning
        project root, so the workspace-root conform drops every plan whose
        owner is a member; otherwise the root and member scopes publish
        different content to the same file and gen never reaches a fixed
        point across the root and member CI gates.
        """
        root = request.root.resolve()
        return tuple(file for file in files if file.project.resolve() == root)

    @classmethod
    def _owned_docs_directories(
        cls,
        request: m.Infra.CodegenConformRequest,
        plan: m.Infra.CodegenPlan,
        directories: t.SequenceOf[Path],
    ) -> t.VariadicTuple[Path]:
        """Keep only docs directory chains inside the invoked repository."""
        root = request.root.resolve()
        member_roots = cls._member_repository_roots(request, plan)
        owned: list[Path] = []
        for directory in directories:
            resolved = directory.resolve()
            if root not in resolved.parents:
                continue
            if any(member in resolved.parents for member in member_roots):
                continue
            owned.append(directory)
        return tuple(owned)


__all__: list[str] = ["FlextInfraCodegenConformDocsOwnership"]
