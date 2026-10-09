"""Project-owned Ruff exemptions load through the managed-artifact document.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import u


class TestsFlextInfraProjectRuffArtifacts:
    """A project declares Ruff exemptions without a second config document."""

    @staticmethod
    def test_declared_per_file_ignores_reach_the_resolution(
        tmp_path: Path,
    ) -> None:
        """ManagedArtifacts.Ruff validates and stays on the composed resolution."""
        root = tmp_path / "project"
        (root / "config").mkdir(parents=True)
        (root / "config" / "tooling.yaml").write_text(
            "ManagedArtifacts:\n"
            "  Ruff:\n"
            "    per_file_ignores:\n"
            "      src/pkg/module.py: [invalid-function-name]\n",
            encoding="utf-8",
        )

        resolution = tm.ok(u.Infra.load_project_managed_artifacts(root))

        assert resolution.artifacts.Ruff.per_file_ignores == {
            "src/pkg/module.py": ("invalid-function-name",),
        }

    @staticmethod
    def test_pattern_declared_by_two_sources_fails(tmp_path: Path) -> None:
        """One path glob has exactly one owning source."""
        root = tmp_path / "project"
        (root / "config").mkdir(parents=True)
        declaration = (
            "ManagedArtifacts:\n"
            "  Ruff:\n"
            "    per_file_ignores:\n"
            "      src/pkg/module.py: [invalid-function-name]\n"
        )
        for name in ("one.yaml", "two.yaml"):
            (root / "config" / name).write_text(declaration, encoding="utf-8")

        error = tm.fail(u.Infra.load_project_managed_artifacts(root))

        assert "duplicate project Ruff per-file ignore" in error
