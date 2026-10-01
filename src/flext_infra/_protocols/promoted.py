"""Promoted-command protocol contracts for flext-infra.

Structural contracts for the frozen models in ``m.Infra.Promoted*`` — leaf
code annotates with these protocols, never with the concrete models.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from flext_infra import t


@runtime_checkable
class FlextInfraProtocolsPromoted(Protocol):
    """Promoted-command protocol definitions."""

    @runtime_checkable
    class PromotedParam(Protocol):
        """Promoted command parameter contract."""

        @property
        def name(self) -> str: ...

        @property
        def help(self) -> str: ...

        @property
        def required(self) -> bool: ...

        @property
        def default(self) -> str: ...

        @property
        def choices(self) -> t.VariadicTuple[str]: ...

    @runtime_checkable
    class PromotedCommand(Protocol):
        """Promoted command contract discovered from a script header."""

        @property
        def verb(self) -> str: ...

        @property
        def what(self) -> str: ...

        @property
        def domain(self) -> str: ...

        @property
        def summary(self) -> str: ...

        @property
        def description(self) -> str: ...

        @property
        def example(self) -> str: ...

        @property
        def path(self) -> Path: ...

        @property
        def mutates(self) -> bool: ...

        @property
        def aliases(self) -> t.VariadicTuple[str]: ...

        @property
        def params(self) -> tuple[FlextInfraProtocolsPromoted.PromotedParam, ...]: ...

        @property
        def rules(self) -> t.VariadicTuple[str]: ...

    @runtime_checkable
    class PromotedAliasTarget(Protocol):
        """Resolved command alias target contract."""

        @property
        def verb(self) -> str: ...

        @property
        def what(self) -> str: ...

    @runtime_checkable
    class PromotedWorkspaceSpec(Protocol):
        """Repository facts contract the promoted framework consumes."""

        @property
        def root(self) -> Path: ...

        @property
        def scripts(self) -> Path: ...

        @property
        def local_python(self) -> Path: ...

        @property
        def submodule_script_roots(self) -> t.VariadicTuple[Path]: ...

        @property
        def consumer_scripts_root(self) -> Path | None: ...

    @runtime_checkable
    class PromotedRegistry(Protocol):
        """In-memory promoted command registry discovered from script headers."""

        def add(self, command: FlextInfraProtocolsPromoted.PromotedCommand) -> None: ...

        def validate(self) -> None: ...

        def resolve_verb(self, verb: str) -> str: ...

        def alias_target(
            self, verb: str
        ) -> FlextInfraProtocolsPromoted.PromotedAliasTarget | None: ...

        def commands(
            self, verb: str
        ) -> t.MappingKV[str, FlextInfraProtocolsPromoted.PromotedCommand]: ...

        def command(
            self, verb: str, what: str
        ) -> FlextInfraProtocolsPromoted.PromotedCommand: ...

        def verbs(self) -> t.StrSequence: ...

        def aliases_for(self, verb: str) -> t.StrSequence: ...

        def has(self, verb: str, what: str) -> bool: ...


__all__: list[str] = ["FlextInfraProtocolsPromoted"]
