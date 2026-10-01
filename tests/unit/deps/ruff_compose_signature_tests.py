"""The Ruff exemption map is the tooling owner's fleet map, scoped per project."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import config
from flext_infra.deps.phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRuffProjectExemptions:
    """A project inherits exactly the declared fleet exemptions."""

    @staticmethod
    def test_project_map_is_the_fleet_map(tmp_path: Path) -> None:
        """A project without retired roots receives every fleet entry unchanged."""
        fleet = config.Infra.tooling.tools.ruff.lint.per_file_ignores

        scoped = FlextInfraEnsureRuffConfigPhase.project_per_file_ignores(
            tmp_path,
            fleet,
        )

        tm.that(
            dict(scoped),
            eq={pattern: tuple(sorted(rules)) for pattern, rules in fleet.items()},
        )
