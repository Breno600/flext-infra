"""Tests that conforming pyproject.toml never widens the lint surface.

``codegen conform`` regenerates the ``[MANAGED]`` pyproject sections from the
tooling SSOT. When a per-file-ignore that the workspace genuinely relies on is
absent from that SSOT, the rendered tree silently *adds* lint errors, the
transaction guard reports ``breakage=yes`` and refuses to apply -- so a missing
SSOT entry blocks every other generated artifact from landing. Every glob that
any governed pyproject still declares must therefore trace back to the tooling
SSOT (or to a project-local overlay), never to a hand-edited projection.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config
from tests import TestsFlextInfraUtilities as tu, u


class TestsFlextInfraPyprojectConformPreservesLintScope:
    """Tests for ``FlextInfraPyprojectConformPreservesLintScope``."""

    @staticmethod
    def _repository_root() -> Path:
        """Return the repository root that owns this checkout.

        Returns:
            The repository root that owns this checkout.

        """
        return Path(__file__).resolve().parents[2]

    def _live_per_file_ignores(self) -> frozenset[str]:
        """Return the per-file-ignore globs the governed pyproject declares.

        Returns:
            The per-file-ignore globs the governed pyproject declares.

        """
        content = (self._repository_root() / "pyproject.toml").read_text(
            encoding="utf-8",
        )
        ignores = tu.Tests.toml_table_at(
            content,
            "tool",
            "ruff",
            "lint",
            "per-file-ignores",
        )
        return frozenset(ignores)

    def _ssot_per_file_ignores(self) -> frozenset[str]:
        """Return every per-file-ignore glob the generator can reproduce.

        Two sources feed the rendered pyproject, and conform merges both:
        ``Infra.tooling`` is the FLEET policy every generated project inherits,
        while a ``ManagedArtifacts.Ruff`` block in the project's own
        ``config/*.yaml`` adds exemptions that belong to that repository alone.
        A path that exists in one repository is declared project-locally so the
        fleet policy does not write a dead exemption into every project.

        Returns:
            Every per-file-ignore glob the generator can reproduce.

        """
        ruff = config.Infra.tooling.tools.ruff
        fleet = frozenset(ruff.lint.per_file_ignores)

        project: set[str] = set()
        for path in sorted((self._repository_root() / "config").glob("*.yaml")):
            payload = tm.ok(u.Cli.yaml_safe_load(path))
            managed = u.Tests.toml_mapping(payload.get("ManagedArtifacts") or {})
            ruff_section = u.Tests.toml_mapping(managed.get("Ruff") or {})
            project.update(
                u.Tests.toml_mapping(ruff_section.get("per_file_ignores") or {}),
            )
        return fleet | frozenset(project)

    def test_ssot_declares_every_governed_per_file_ignore(self) -> None:
        """No governed lint exemption is missing from the tooling SSOT."""
        missing = self._live_per_file_ignores() - self._ssot_per_file_ignores()

        tm.that(missing, eq=frozenset())
