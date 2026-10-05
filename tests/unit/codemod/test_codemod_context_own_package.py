"""The own-package codemod predicate spans the project's internal tiers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m
from tests import u


class TestsFlextInfraCodemodContextOwnPackage:
    """An import between a project's own namespaces never crosses an owner."""

    @staticmethod
    def _private_import_rule() -> m.Infra.CodemodRule:
        return m.Infra.CodemodRule(
            id="private-import-probe",
            digest="probe",
            provider="probe",
            resource=Path("probe.yml"),
            fixable=False,
            context=(
                m.Infra.CodemodContextCondition(
                    variable="MOD",
                    predicate=c.Infra.CodemodContextPredicate.OWN_PACKAGE,
                    holds=False,
                ),
            ),
        )

    @pytest.mark.parametrize(
        ("module", "admitted"),
        [
            ("demo._support", False),
            ("tests.unit._support", False),
            ("other_package._support", True),
        ],
    )
    def test_internal_tiers_are_own_namespaces(
        self,
        tmp_path: Path,
        module: str,
        *,
        admitted: bool,
    ) -> None:
        """Test internal tiers are own namespaces."""
        project = u.Tests.mk_project(
            tmp_path,
            "demo",
            pyproject='[project]\nname = "demo"\nversion = "0.1.0"\n',
            with_src=True,
        )
        consumer = project / "tests" / "unit" / "consumer_tests.py"
        consumer.parent.mkdir(parents=True)
        consumer.write_text(f"from {module} import Helper\n", encoding="utf-8")

        rule = self._private_import_rule()
        verdict = u.Infra.codemod_context_admits(
            project,
            rule,
            consumer,
            {"MOD": {"text": module}},
            u.Infra.codemod_project_facts(project, (rule,)),
        )

        tm.that(verdict, eq=admitted)
