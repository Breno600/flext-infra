"""Tests for workspace checker gate resolution and CSV parsing.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker


class TestsFlextInfraWorkspaceCheckerResolveGates:
    """Test FlextInfraWorkspaceChecker.resolve_gates."""

    def test_resolve_gates_type_is_rejected(self) -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates(["type"])
        tm.fail(result, has="unknown gate")

    def test_resolve_gates_rejects_empty_strings(self) -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates(["lint", "", "format"])
        tm.fail(result, has="invalid gate name")

    def test_resolve_gates_rejects_duplicate_entries(self) -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates([
            "lint",
            "lint",
            "format",
            "lint",
        ])
        tm.fail(result, has="duplicate gate")

    def test_resolve_gates_invalid_gate_fails(self) -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates(["invalid"])
        tm.fail(result, has="unknown gate")

    def test_resolve_gates_all_valid_types(self) -> None:
        gates = [
            "lint",
            "format",
            "pyrefly",
            "mypy",
            "pyright",
            "silent-failure",
            "security",
            "markdown",
        ]
        result = FlextInfraWorkspaceChecker.resolve_gates(gates)
        tm.ok(result)
        tm.that(len(result.value) > 0, eq=True)

    def test_resolve_gates_accepts_silent_failure(self) -> None:
        result = FlextInfraWorkspaceChecker.resolve_gates(["silent-failure"])
        tm.ok(result)
        tm.that(result.value, eq=["silent-failure"])
