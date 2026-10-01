"""Git-specific fixtures for FLEXT infra tests.

Provides fixtures for creating real git repositories with commits.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests import u

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def real_git_repo(tmp_path: Path) -> Path:
    """Create a real git repository with initial commit.

    Args:
        tmp_path: Pytest temporary directory

    Returns:
        Path to git repository root

    """
    repo_root = tmp_path / "git_repo"
    repo_root.mkdir()
    (repo_root / "README.md").write_text("# Test Repository\n", encoding="utf-8")
    # FLEXT: one real-Git initializer owns branch, identity, staging, and commit.
    u.Tests.initialize_git_repo(repo_root)

    return repo_root
