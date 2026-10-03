"""Explicit registry of the workspace check gates.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, p, t
from flext_infra.gates.bandit import FlextInfraBanditGate
from flext_infra.gates.base_gate import FlextInfraGate
from flext_infra.gates.codemod import FlextInfraCodemodGate
from flext_infra.gates.direnv import FlextInfraDirenvGate
from flext_infra.gates.duplication import FlextInfraDuplicationGate
from flext_infra.gates.fresh_import import FlextInfraFreshImportGate
from flext_infra.gates.index_declarations import FlextInfraIndexDeclarationsGate
from flext_infra.gates.layout import FlextInfraLayoutGate
from flext_infra.gates.loc_cap import FlextInfraLocCapGate
from flext_infra.gates.markdown import FlextInfraMarkdownGate
from flext_infra.gates.markdown_code import FlextInfraMarkdownCodeGate
from flext_infra.gates.markdown_format import FlextInfraMarkdownFormatGate
from flext_infra.gates.mypy import FlextInfraMypyGate
from flext_infra.gates.pyrefly import FlextInfraPyreflyGate
from flext_infra.gates.pyright import FlextInfraPyrightGate
from flext_infra.gates.ruff_format import FlextInfraRuffFormatGate
from flext_infra.gates.ruff_lint import FlextInfraRuffLintGate
from flext_infra.gates.runtime_census import FlextInfraRuntimeCensusGate
from flext_infra.gates.smells import FlextInfraSmellsGate


class FlextInfraGateRegistry:
    """Explicit gate registry mapping gate IDs to gate classes."""

    def __init__(
        self,
        *,
        runners: t.MappingKV[str, p.Cli.CommandRunner] | None = None,
    ) -> None:
        """Build the gate-id to gate-class mapping used by check execution.

        The gate classes and ``c.Infra.SARIF_TOOL_INFO`` are two producers of
        the same conclusion — the gate vocabulary — keyed by ``gate_id``. They
        collapse here; any divergence (a registered class the vocabulary does
        not know, a vocabulary id with no class, or two classes claiming one
        id) is a defect that fails the registry before a single gate can run,
        never a gate that silently cannot be reached through ``make check``.

        Raises:
            ValueError: If gate registry declares duplicate gate ids; or if gate
                registry diverges from c.Infra.SARIF_TOOL_INFO.

        """
        classes = self._gate_classes()
        self._gates: MutableMapping[str, type[FlextInfraGate]] = {
            gate_cls.gate_id: gate_cls for gate_cls in classes
        }
        if len(self._gates) != len(classes):
            msg = "gate registry declares duplicate gate ids"
            raise ValueError(msg)
        registered = frozenset(self._gates)
        if registered != c.Infra.ALLOWED_GATES:
            msg = (
                "gate registry diverges from c.Infra.SARIF_TOOL_INFO: "
                f"unregistered={sorted(c.Infra.ALLOWED_GATES - registered)} "
                f"unknown={sorted(registered - c.Infra.ALLOWED_GATES)}"
            )
            raise ValueError(msg)
        self._runners = dict(runners or {})

    @staticmethod
    def _gate_classes() -> t.VariadicTuple[type[FlextInfraGate]]:
        """Return the runtime gate classes registered for workspace checks.

        Returns:
            The runtime gate classes registered for workspace checks.

        """
        return (
            FlextInfraRuffLintGate,
            FlextInfraRuffFormatGate,
            FlextInfraPyreflyGate,
            FlextInfraMypyGate,
            FlextInfraPyrightGate,
            FlextInfraBanditGate,
            FlextInfraMarkdownGate,
            FlextInfraMarkdownFormatGate,
            FlextInfraMarkdownCodeGate,
            FlextInfraLocCapGate,
            FlextInfraRuntimeCensusGate,
            FlextInfraFreshImportGate,
            FlextInfraLayoutGate,
            FlextInfraIndexDeclarationsGate,
            FlextInfraSmellsGate,
            FlextInfraCodemodGate,
            FlextInfraDirenvGate,
            FlextInfraDuplicationGate,
        )

    def get(self, gate_id: str) -> type[FlextInfraGate] | None:
        """Return the registered gate class for one gate id, when present.

        Returns:
            The registered gate class for one gate id, when present.

        """
        return self._gates.get(gate_id)

    def create(self, gate_id: str, repository_root: Path) -> FlextInfraGate | None:
        """Instantiate one registered gate for ``repository_root`` when available.

        Returns:
            The resulting ``FlextInfraGate | None``.

        """
        gate_cls = self._gates.get(gate_id)
        return (
            gate_cls(repository_root, runner=self._runners.get(gate_id))
            if gate_cls
            else None
        )

    @classmethod
    def default(cls) -> FlextInfraGateRegistry:
        """Return the default registry instance for workspace checks.

        Returns:
            The default registry instance for workspace checks.

        """
        return cls()


__all__: list[str] = ["FlextInfraGateRegistry"]
