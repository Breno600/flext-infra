"""Structural contracts for dependency-analysis collaborators.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from flext_infra.typings


@runtime_checkable
class FlextInfraProtocolsDeps(Protocol):
    """Dependency-analysis protocols exposed through ``p.Infra``."""

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
