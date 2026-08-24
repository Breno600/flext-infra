"""Typed semantic Git composition for ``u.Infra``."""

from __future__ import annotations

from flext_infra._utilities._git.semantic_submodule import (
    FlextInfraUtilitiesGitSemanticSubmoduleMixin,
)


class FlextInfraUtilitiesGitSemanticMixin(FlextInfraUtilitiesGitSemanticSubmoduleMixin):
    pass


__all__: list[str] = ["FlextInfraUtilitiesGitSemanticMixin"]
