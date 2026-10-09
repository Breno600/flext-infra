"""Informative lint rules report as warnings and never fail the lint gate.

Operator ruling 2026-10-05: rules the operator never authorized as blocking
are informative only. The declared rule family keeps flowing through Ruff
and every report surface while the gate verdict ignores it.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import c, config, m, u


class TestsFlextInfraLintInformativeRules:
    """The declared family is advisory end to end: config, severity, verdict."""

    @staticmethod
    def test_ssot_declares_the_complexity_family() -> None:
        """Test ssot declares the complexity family."""
        declared = config.Infra.tooling.tools.ruff.informative_rules
        assert "too-many-arguments" in declared
        assert "too-many-positional-arguments" in declared
        assert "too-many-locals" in declared
        assert "too-many-return-statements" in declared
        assert "too-many-branches" in declared
        assert "too-many-public-methods" in declared
        assert "too-many-statements" in declared
        assert "complex-structure" in declared

    @staticmethod
    def test_advisory_rules_report_at_warning_severity() -> None:
        """Test advisory rules report at warning severity."""
        advisory = config.Infra.tooling.tools.ruff.informative_rules
        for code in advisory:
            tm.that(
                u.Infra.ruff_finding_severity(code, advisory),
                eq=c.Infra.GateSeverity.WARNING.value,
            )

    @staticmethod
    def test_undeclared_rules_report_at_error_severity() -> None:
        """Test undeclared rules report at error severity."""
        advisory = frozenset(config.Infra.tooling.tools.ruff.informative_rules)
        blocking = next(
            name
            for name in ("undefined-name", "banned-api", "line-too-long")
            if name not in advisory
        )
        tm.that(
            u.Infra.ruff_finding_severity(blocking, advisory),
            eq=c.Infra.GateSeverity.ERROR.value,
        )

    @staticmethod
    def test_warning_findings_never_block_the_verdict() -> None:
        """Test warning findings never block the verdict."""
        advisory = config.Infra.tooling.tools.ruff.informative_rules
        warning_only = u.Infra.blocking_gate_findings(
            (
                m.Infra.Issue(
                    file="src/sample.py",
                    line=1,
                    column=1,
                    code=next(iter(advisory)),
                    message="advisory finding",
                    severity=c.Infra.GateSeverity.WARNING.value,
                ),
            ),
        )
        tm.that(warning_only, eq=())
        mixed = u.Infra.blocking_gate_findings(
            (
                m.Infra.Issue(
                    file="src/sample.py",
                    line=1,
                    column=1,
                    code=next(iter(advisory)),
                    message="advisory finding",
                    severity=c.Infra.GateSeverity.WARNING.value,
                ),
                m.Infra.Issue(
                    file="src/sample.py",
                    line=2,
                    column=1,
                    code="undefined-name",
                    message="blocking finding",
                    severity=c.Infra.GateSeverity.ERROR.value,
                ),
            ),
        )
        assert len(mixed) == 1
        assert mixed[0].code == "undefined-name"
