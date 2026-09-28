"""Structural contracts for dependency-analysis collaborators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import m, p, t


@runtime_checkable
class FlextInfraProtocolsDeps(Protocol):
    """Dependency-analysis protocols exposed through ``p.Infra``."""

    @runtime_checkable
    class ProjectSelector(Protocol):
        """Resolve selected workspace projects without a concrete utility dependency."""

        def resolve_projects(
            self, repository_root: Path, names: t.StrSequence
        ) -> p.Result[t.SequenceOf[m.Infra.ProjectInfo]]:
            """Resolve project names into canonical project descriptors."""
            ...

    @runtime_checkable
    class TypeCheckerPathRules(Protocol):
        """Path-rule fields every type-checker configuration declares."""

        @property
        def source_dir(self) -> str:
            """Import root the generated search paths order first."""
            ...

        @property
        def project_root(self) -> str:
            """Project-root entry the generated search paths order last."""
            ...

        @property
        def root_typings_paths(self) -> t.StrSequence:
            """Typings roots configured for a workspace root."""
            ...

        @property
        def project_typings_paths(self) -> t.StrSequence:
            """Typings roots configured for a non-root project."""
            ...


__all__: list[str] = ["FlextInfraProtocolsDeps"]
