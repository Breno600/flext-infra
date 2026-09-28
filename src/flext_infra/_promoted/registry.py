"""Promoted-command registry state and invariants."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, m, u

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraPromotedRegistry:
    """In-memory view discovered from script headers; never a static catalog."""

    def __init__(self) -> None:
        """Initialize an empty command registry."""
        self._commands: t.MutableMappingKV[
            str, t.MutableMappingKV[str, p.Infra.PromotedCommand]
        ] = {}
        self._aliases: t.MutableMappingKV[str, p.Infra.PromotedAliasTarget] = {}

    def add(self, command: p.Infra.PromotedCommand) -> None:
        """Add one command and its ``alias`` or ``alias=WHAT`` specifications."""
        message = c.Infra.PromotedMessage
        by_what = self._commands.setdefault(command.verb, {})
        if command.what in by_what:
            u.Infra.promoted_fail(
                message.DUPLICATE_COMMAND, verb=command.verb, what=command.what
            )
        by_what[command.what] = command
        for alias in command.aliases:
            name, separator, what = alias.partition(c.Infra.PromotedSelector.ALIAS)
            target = m.Infra.PromotedAliasTarget(
                verb=command.verb, what=what.strip() if separator else command.what
            )
            if not name.strip() or not target.what:
                u.Infra.promoted_fail(
                    message.INVALID_ALIAS, path=command.path, alias=alias
                )
            previous = self._aliases.setdefault(name.strip(), target)
            if previous != target:
                u.Infra.promoted_fail(
                    message.DUPLICATE_ALIAS,
                    alias=name.strip(),
                    previous_verb=previous.verb,
                    previous_what=previous.what,
                    verb=target.verb,
                    what=target.what,
                )

    def validate(self) -> None:
        """Validate registry invariants after command discovery.

        A verb needs no declared ``all`` command: ``WHAT=all`` renders its verb
        help unless the verb declares one.
        """
        message = c.Infra.PromotedMessage
        if not self._commands:
            u.Infra.promoted_fail(message.NO_COMMANDS)
        for verb, commands in sorted(self._commands.items()):
            domains = sorted({command.domain for command in commands.values()})
            if len(domains) != 1:
                u.Infra.promoted_fail(
                    message.VERB_DOMAINS,
                    verb=verb,
                    domains=c.Infra.PromotedJoin.LIST.join(domains),
                )
            for command in commands.values():
                if command.what != c.Infra.PromotedSelector.ALL and command.aliases:
                    u.Infra.promoted_fail(message.ALIAS_OUTSIDE_ALL, path=command.path)
                u.Infra.promoted_validate_command_contract(command)
            u.Infra.promoted_validate_all_choices(verb, commands)
        for alias, target in self._aliases.items():
            if alias in self._commands:
                failure = message.ALIAS_COLLIDES_VERB
            elif target.verb not in self._commands:
                failure = message.ALIAS_UNKNOWN_VERB
            elif target.what not in self._commands[target.verb]:
                failure = message.ALIAS_UNKNOWN_WHAT
            else:
                continue
            u.Infra.promoted_fail(
                failure, alias=alias, verb=target.verb, what=target.what
            )

    def resolve_verb(self, verb: str) -> str:
        """Resolve a public verb or alias to the canonical verb."""
        target = self._aliases.get(verb)
        resolved = verb if target is None else target.verb
        if resolved not in self._commands:
            u.Infra.promoted_fail(c.Infra.PromotedMessage.UNKNOWN_VERB, verb=verb)
        return resolved

    def alias_target(self, verb: str) -> p.Infra.PromotedAliasTarget | None:
        """Return the alias target for a requested verb, if any."""
        return self._aliases.get(verb)

    def commands(self, verb: str) -> t.MappingKV[str, p.Infra.PromotedCommand]:
        """Return commands registered for a verb or alias."""
        return self._commands[self.resolve_verb(verb)]

    def command(self, verb: str, what: str) -> p.Infra.PromotedCommand:
        """Return one command by verb and WHAT."""
        commands = self.commands(verb)
        if what not in commands:
            u.Infra.promoted_fail(
                c.Infra.PromotedMessage.INVALID_WHAT,
                what=what,
                verb=verb,
                valid=c.Infra.PromotedJoin.WORDS.join(sorted(commands)),
            )
        return commands[what]

    def verbs(self) -> t.StrSequence:
        """Return registered verbs in display order."""
        return sorted(self._commands)

    def aliases_for(self, verb: str) -> t.StrSequence:
        """Return aliases that point to one canonical verb."""
        return sorted(
            name for name, target in self._aliases.items() if target.verb == verb
        )

    def has(self, verb: str, what: str) -> bool:
        """Return whether a ``(verb, WHAT)`` command is registered."""
        return what in self._commands.get(verb, {})


__all__: list[str] = ["FlextInfraPromotedRegistry"]
