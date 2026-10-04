"""Import-cycle admission honors the source scan's ignored trees.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m
from tests import u


class TestsFlextInfraCodemodImportCycleSourceScan:
    """A source-scan-ignored tree is not a missing production module."""

    @staticmethod
    def _cycle_rule() -> m.Infra.CodemodRule:
        """Return a probe rule whose only predicate is the import cycle.

        Returns:
            A probe rule whose only predicate is the import cycle.

        """
        return m.Infra.CodemodRule(
            id="import-cycle-probe",
            digest="probe",
            provider="probe",
            resource=Path("probe.yml"),
            fixable=False,
            context=(
                m.Infra.CodemodContextCondition(
                    variable="MODULE",
                    predicate=c.Infra.CodemodContextPredicate.IMPORT_CYCLE,
                    holds=True,
                    of="NAME",
                ),
            ),
        )

    @staticmethod
    def _facts() -> m.Infra.CodemodProjectFacts:
        """Return cycle facts whose graph contains no module.

        Returns:
            Cycle facts whose graph contains no module.

        """
        return m.Infra.CodemodProjectFacts(
            predicates=frozenset({c.Infra.CodemodContextPredicate.IMPORT_CYCLE}),
            import_graph={},
            import_modules={},
            import_cycles={},
            runtime_modules=frozenset(),
        )

    def test_legado_is_outside_the_scanned_import_graph(
        self,
        tmp_path: Path,
    ) -> None:
        """A source-scan-ignored legado module is not a missing graph node."""
        project = u.Tests.mk_project(
            tmp_path,
            "demo",
            pyproject='[project]\nname = "demo"\nversion = "0.1.0"\n',
            with_src=True,
        )
        legado = project / "src" / "demo" / "legado" / "app_recovery.py"
        legado.parent.mkdir(parents=True)
        legado.write_text("from demo.live import value\n", encoding="utf-8")
        live = project / "src" / "demo" / "live.py"
        live.write_text("value = 1\n", encoding="utf-8")
        rule = self._cycle_rule()
        facts = self._facts()

        verdict = u.Infra.codemod_context_admits(
            project,
            rule,
            legado,
            {"MODULE": {"text": "demo.live"}, "NAME": {"text": "value"}},
            facts,
        )

        tm.that(verdict, eq=False)
        with pytest.raises(ValueError, match="absent from the project import graph"):
            u.Infra.codemod_context_admits(
                project,
                rule,
                live,
                {"MODULE": {"text": "demo.live"}, "NAME": {"text": "value"}},
                facts,
            )
