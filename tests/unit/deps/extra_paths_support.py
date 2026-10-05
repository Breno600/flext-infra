"""Shared test helpers for extra-path manager contracts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager

if TYPE_CHECKING:
    from tests import t

_TEST_REPOSITORY_ROOT = Path(__file__).resolve().parent


class TestsFlextInfraExtraPathsSupport:
    """Factory helpers for validated extra-path manager instances."""

    @staticmethod
    def manager(repository_root: Path | None = None) -> FlextInfraExtraPathsManager:
        """Return a manager built through the Pydantic validation path.

        Returns:
            A manager built through the Pydantic validation path.

        """
        return FlextInfraExtraPathsManager(
            repository_root=repository_root or _TEST_REPOSITORY_ROOT,
        )

    @staticmethod
    def project(root: Path, name: str, package: str, *, with_git: bool = True) -> Path:
        """Materialize one importable project with a declared distribution name.

        Returns:
            The resulting ``Path``.

        """
        project = root / name
        (project / "src" / package).mkdir(parents=True)
        (project / "src" / package / "__init__.py").write_text("", encoding="utf-8")
        if with_git:
            (project / ".git").mkdir()
        (project / "Makefile").write_text("", encoding="utf-8")
        (project / "pyproject.toml").write_text(
            f"[project]\nname = '{name}'\n",
            encoding="utf-8",
        )
        return project

    @classmethod
    def workspace_with_dependency(
        cls,
        root: Path,
        *,
        uv_workspace: bool = True,
    ) -> t.Pair[Path, Path]:
        """Write one governed root and its ``flext-core`` dependency checkout.

        Returns:
            The resulting ``t.Pair[Path, Path]``.

        """
        (root / ".git").mkdir()
        (root / "src").mkdir()
        pyproject = "[project]\nname = 'flext'\ndependencies = ['flext-core']\n"
        if uv_workspace:
            pyproject += "[tool.uv.workspace]\nmembers = ['flext-core']\n"
        (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
        dep_root = cls.project(root, "flext-core", "flext_core")
        return root, dep_root
