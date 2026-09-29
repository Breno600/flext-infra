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

    """cosmos-command registry protocol namespace."""

    @runtime_checkable
    class PromotedParam(Protocol):
        """Promoted command parameter contract."""

        @property
        def name(self) -> str:
            """Name."""

        @property
        def help(self) -> str:
            """Help."""

        @property
        def required(self) -> bool:
            """Required."""

        @property
        def default(self) -> str:
            """Default."""

        @property
        def choices(self) -> t.VariadicTuple[str]:
            """Choices."""

    @runtime_checkable
    class PromotedCommand(Protocol):
        """Promoted command contract discovered from a script header."""

        @property
        def verb(self) -> str:
            """Verb."""

        @property
        def what(self) -> str:
            """What."""

        @property
        def domain(self) -> str:
            """Domain."""

        @property
        def summary(self) -> str:
            """Summary."""

        @property
        def description(self) -> str:
            """Description."""

        @property
        def example(self) -> str:
            """Example."""

        @property
        def path(self) -> Path:
            """Path."""

        @property
        def mutates(self) -> bool:
            """Mutates."""

        @property
        def aliases(self) -> t.VariadicTuple[str]:
            """Aliases."""

        @property
        def params(self) -> tuple[FlextInfraProtocolsPromoted.PromotedParam, ...]:
            """Params."""

        @property
        def rules(self) -> t.VariadicTuple[str]:
            """Rules."""

    @runtime_checkable
    class PromotedAliasTarget(Protocol):
        """Resolved command alias target contract."""

        @property
        def verb(self) -> str:
            """Verb."""

        @property
        def what(self) -> str:
            """What."""

    @runtime_checkable
    class PromotedWorkspaceSpec(Protocol):
        """Repository facts contract the promoted framework consumes."""

        @property
        def root(self) -> Path:
            """Repository root."""

        @property
        def scripts(self) -> Path:
            """Scripts directory."""

        @property
        def local_python(self) -> Path:
            """Declared local ``.venv`` interpreter."""

        @property
        def submodule_script_roots(self) -> t.VariadicTuple[Path]:
            """Submodule script roots in first-wins order."""

        @property
        def consumer_scripts_root(self) -> Path | None:
            """Consuming workspace scripts root when vendored as a submodule."""

    @runtime_checkable
    class PromotedRegistry(Protocol):
        """In-memory promoted command registry discovered from script headers."""

        def add(self, command: FlextInfraProtocolsPromoted.PromotedCommand) -> None:
            """Add one command and its aliases."""

        def validate(self) -> None:
            """Validate registry invariants after discovery."""

        def resolve_verb(self, verb: str) -> str:
            """Resolve a public verb or alias to the canonical verb."""

        def alias_target(
            self, verb: str
        ) -> FlextInfraProtocolsPromoted.PromotedAliasTarget | None:
            """Return the alias target for a requested verb, if any."""

        def commands(
            self, verb: str
        ) -> t.MappingKV[str, FlextInfraProtocolsPromoted.PromotedCommand]:
            """Return commands registered for a verb or alias."""

        def command(
            self, verb: str, what: str
        ) -> FlextInfraProtocolsPromoted.PromotedCommand:
            """Return one command by verb and WHAT."""

        def verbs(self) -> t.StrSequence:
            """Return registered verbs in display order."""

        def aliases_for(self, verb: str) -> t.StrSequence:
            """Return aliases that point to one canonical verb."""

        def has(self, verb: str, what: str) -> bool:
            """Return whether a (verb, WHAT) command is registered."""


__all__: list[str] = ["FlextInfraProtocolsPromoted"]
