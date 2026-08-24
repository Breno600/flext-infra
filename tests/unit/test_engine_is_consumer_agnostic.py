"""Tests that the codegen engine carries no downstream-consumer knowledge.

``flext-infra`` is a generalized engine. Its configuration SSOT declares only
the provider and repositories it owns; every downstream consumer declares its
own topology in its own ``config/workspace.yaml``. Embedding a consumer's
repositories here couples the engine to projects it must not know about.

The owning identity is never hardcoded: it is derived from the engine's own
distribution name (``pyproject.toml`` metadata SSOT) resolved against the
repository catalog the engine publishes.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import config, t, u
from flext_tests import tm
from tests import u as test_u


@pytest.fixture(scope="module")
def owned_provider() -> str:
    """Resolve the engine's own provider from its own catalog entry."""
    engine_root = Path(__file__).resolve().parents[2]
    metadata = tm.ok(u.read_project_metadata(engine_root))
    distribution = metadata.project.name
    entry = test_u.Tests.repository_ref(distribution)
    provider: str = t.Infra.STR_ADAPTER.validate_python(entry.provider)
    return provider


class TestsFlextInfraEngineIsConsumerAgnostic:
    def test_repository_catalog_uses_declared_providers(self) -> None:
        declared = {provider.name for provider in config.Infra.codegen.providers}
        referenced = {test_u.Tests.repository_ref("any-consumer").provider}

        tm.that(referenced - declared, eq=set())

    def test_engine_declares_no_directory_name_of_a_foreign_workspace(self) -> None:
        """Sibling discovery is declarative, never a directory name in the engine.

        A neighbour joins discovery by declaring ``[tool.flext.workspace]
        attached = true`` in its own pyproject. The engine therefore ships no
        directory-name list, glob, or pattern for a workspace it does not own.
        """
        engine_root = Path(__file__).resolve().parents[2]
        discovery_source = (
            engine_root
            / "src"
            / "flext_infra"
            / "_utilities"
            / "_project_discovery_candidates.py"
        ).read_text(encoding="utf-8")

        tm.that(discovery_source, has="attached")
        tm.that(discovery_source, lacks=".glob(pattern)")
