"""Generation helpers for docs services."""

from __future__ import annotations

from .._utilities._docs_generate_root import FlextInfraUtilitiesDocsGenerateRootMixin

# Why: restored lost composition — FlextInfraUtilitiesDocsGuidesMixin was
# never wired into any composed Docs* facade, leaving consumers unresolved.
from ._docs_guides import FlextInfraUtilitiesDocsGuidesMixin
from .docs_collection import FlextInfraUtilitiesDocsCollection


class FlextInfraUtilitiesDocsGenerate(
    FlextInfraUtilitiesDocsGenerateRootMixin,
    FlextInfraUtilitiesDocsGuidesMixin,
    FlextInfraUtilitiesDocsCollection,
):
    """Reusable generation helpers exposed through ``u.Infra``."""


__all__: list[str] = ["FlextInfraUtilitiesDocsGenerate"]
