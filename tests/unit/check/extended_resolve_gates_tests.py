"""Tests for workspace checker gate resolution and CSV parsing.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from tests import c


class TestsFlextInfraWorkspaceCheckerResolveGates:
    """Test FlextInfraWorkspaceChecker.resolve_gates."""

    @staticmethod
    def test_resolve_gates_type_is_rejected() -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates(["type"])
        tm.fail(result, has="unknown gate")

    @staticmethod
    def test_resolve_gates_rejects_empty_strings() -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates(["lint", "", "format"])
        tm.fail(result, has="invalid gate name")

    @staticmethod
    def test_resolve_gates_rejects_duplicate_entries() -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates([
            "lint",
            "lint",
            "format",
            "lint",
        ])
        tm.fail(result, has="duplicate gate")

    @staticmethod
    def test_resolve_gates_invalid_gate_fails() -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates(["invalid"])
        tm.fail(result, has="unknown gate")

    @staticmethod
    def test_resolve_gates_accepts_every_declared_gate() -> None:
        gates = sorted(c.Infra.ALLOWED_GATES)
        result = FlextInfraWorkspaceChecker.resolve_gates(gates)
        tm.ok(result)
        tm.that(sorted(result.value), eq=gates)
