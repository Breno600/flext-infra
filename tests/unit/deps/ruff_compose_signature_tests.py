"""The Ruff exemption map is the tooling owner's fleet map, for every project.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import c, config, t
from flext_infra.deps.phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRuffProjectExemptions:
    """A project inherits exactly the declared fleet exemptions."""

    @staticmethod
    def test_project_map_is_the_fleet_map(tmp_path: Path) -> None:
        """The projected per-file-ignores equal the fleet map, unfiltered."""
        fleet = config.Infra.tooling.tools.ruff.lint.per_file_ignores
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python(
            u.Tests.toml_payload('[project]\nname = "fleet-exemptions"\n'),
        )

        FlextInfraEnsureRuffConfigPhase(config.Infra.tooling).apply_payload(
            payload,
            path=tmp_path / c.PYPROJECT_FILENAME,
            analysis_exclusions=(),
        )

        projected = u.Cli.toml_mapping_path(
            payload,
            (c.Infra.TOOL, c.Infra.RUFF, c.Infra.LINT_SECTION, "per-file-ignores"),
        )
        projected_rules: dict[str, tuple[str, ...]] = {}
        for pattern, rules in dict(projected or {}).items():
            entries = rules if isinstance(rules, list) else ()
            projected_rules[pattern] = tuple(
                rule for rule in entries if isinstance(rule, str)
            )
        tm.that(
            projected_rules,
            eq={pattern: tuple(sorted(rules)) for pattern, rules in fleet.items()},
        )
