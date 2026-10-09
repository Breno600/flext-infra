"""Gate vocabulary contract: one SSOT, every gate reachable.

``c.Infra.SARIF_TOOL_INFO`` owns the gate ids; the registry classes and the
`make check` vocabulary are derived from it and must never diverge.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from flext_infra import config
from flext_infra.check import FlextInfraGateRegistry
from tests import c


class TestsFlextInfraGateRegistry:
    """Tests for ``FlextInfraGateRegistry``."""

    @staticmethod
    def test_every_allowed_gate_resolves_in_registry() -> None:
        """Test every allowed gate resolves in registry."""
        registry = FlextInfraGateRegistry.default()
        for gate_id in c.Infra.ALLOWED_GATES:
            gate_cls = registry.get(gate_id)
            tm.that(gate_cls is not None, eq=True)
            tm.that(gate_cls is not None and gate_cls.gate_id == gate_id, eq=True)

    @staticmethod
    def test_check_vocabulary_is_the_whole_registry() -> None:
        """Every registered gate checks read-only, the formatters included."""
        tm.that(frozenset(c.Infra.CANONICAL_GATE_IDS), eq=c.Infra.ALLOWED_GATES)

    @staticmethod
    def test_default_and_fixable_are_subsets_of_check_vocabulary() -> None:
        """Default, local-only and fixable gates stay in the check vocabulary."""
        make = config.Infra.codegen.make
        allowed = frozenset(make.check_gates_allowed)
        tm.that(frozenset(make.check_gates_default) <= allowed, eq=True)
        tm.that(frozenset(make.ci.local_check_gates) <= allowed, eq=True)
        tm.that(
            frozenset(c.Infra.CANONICAL_FIXABLE_GATE_IDS)
            <= frozenset(c.Infra.CANONICAL_GATE_IDS),
            eq=True,
        )

    @staticmethod
    def test_every_allowed_gate_resolves_in_the_registry() -> None:
        """Every gate the Make surface accepts must be instantiable.

        `format` once sat in the canonical check-gate vocabulary
        and FlextInfraRuffFormatGate declared gate_id="format" with
        can_fix=True, but the class was never listed in the registry. The
        generated check command could therefore name a gate that silently
        resolved to nothing.
        """
        registry = FlextInfraGateRegistry.default()
        unresolved = [
            gate_id
            for gate_id in c.Infra.CANONICAL_GATE_IDS
            if registry.get(gate_id) is None
        ]

        tm.that(unresolved, eq=[])

    @staticmethod
    def test_fixable_gate_vocabulary_matches_the_registry() -> None:
        """The Make fixable-gate vocabulary equals the gates that declare can_fix.

        `make fix` routes through `check run --fix`. Without a
        gate selector that run executes EVERY gate, including pyright and
        mypy, which cannot fix anything and cost ~37s -- the verb timed out
        (exit 124).

        Runtime contract: verbs own tools by intent. `fmt` owns formatting
        (ruff format plus the fmt_gates writers such as markdown-format),
        `fix` repairs findings (markdown, markdown-code, smells), `check` is
        read-only. `format` therefore appears in NO check vocabulary: not in
        ALLOWED (check never mutates) and not in FIXABLE (fix never formats).
        """
        registry = FlextInfraGateRegistry.default()
        mutating = {
            gate_id
            for gate_id in c.Infra.ALLOWED_GATES
            if (gate_cls := registry.get(gate_id)) is not None and gate_cls.can_fix
        }
        # `make fix` owns every mutating check-gate EXCEPT the fmt-owned
        # formatters (single-pass verb law: one operation per tool per verb).
        fmt_owned = set(config.Infra.codegen.make.fmt_gates)
        tm.that(set(c.Infra.CANONICAL_FIXABLE_GATE_IDS), eq=mutating - fmt_owned)
        tm.that(fmt_owned & set(c.Infra.CANONICAL_GATE_IDS) <= mutating, eq=True)
        registered_mutating = {
            gate_id
            for gate_id in c.Infra.ALLOWED_GATES
            if (gate_cls := registry.get(gate_id)) is not None and gate_cls.can_fix
        }
        tm.that(fmt_owned <= registered_mutating, eq=True)
        # `format` belongs to `make fmt` alone: absent from the read-only
        # check vocabulary AND from the fix vocabulary.
        tm.that(c.Infra.FORMAT not in c.Infra.CANONICAL_FIXABLE_GATE_IDS, eq=True)
        tm.that(c.Infra.FORMAT not in c.Infra.CANONICAL_GATE_IDS, eq=True)
