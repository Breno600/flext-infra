"""Docs scope helpers for FLEXT-only discovery and project classification."""

from __future__ import annotations

from ._docs_scope_projects import FlextInfraUtilitiesDocsScopeProjectsMixin


class FlextInfraUtilitiesDocsScope(FlextInfraUtilitiesDocsScopeProjectsMixin):
    """Utility helpers for docs scope policy and project classification."""


__all__: list[str] = ["FlextInfraUtilitiesDocsScope"]
