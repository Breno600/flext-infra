"""Promoted-command help rendering from a discovered registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraUtilitiesPromotedRendering:
    """Render global, verb, and command help for the promoted dispatcher."""

    @staticmethod
    def promoted_renders_verb_help(
        registry: p.Infra.PromotedRegistry, verb: str, what: str
    ) -> bool:
        """Return whether a selected WHAT renders the verb help.

        An empty or ``help`` WHAT always does; ``all`` does only when the verb
        declares no ``all`` command, so a declared ``all`` command still runs.
        """
        return what in c.Infra.PROMOTED_VERB_HELP_SELECTORS or (
            what == c.Infra.PromotedSelector.ALL
            and not registry.has(registry.resolve_verb(verb), what)
        )

    @classmethod
    def promoted_render_help(
        cls, registry: p.Infra.PromotedRegistry, selector: str
    ) -> str:
        """Render global help, ``<verb>`` help, or ``<verb>/<WHAT>`` help."""
        help_, join = c.Infra.PromotedHelp, c.Infra.PromotedJoin
        if selector in c.Infra.PROMOTED_GLOBAL_HELP_SELECTORS:
            lines: list[str] = [help_.GLOBAL_HEADER, ""]
            for verb in registry.verbs():
                commands = registry.commands(verb)
                catalog = commands.get(c.Infra.PromotedSelector.ALL)
                summary = (
                    join.LIST.join(sorted(commands))
                    if catalog is None
                    else catalog.summary
                )
                lines.append(
                    help_.GLOBAL_LINE.format(
                        verb=verb,
                        domain=next(iter(commands.values())).domain,
                        summary=summary,
                        suffix=cls._promoted_alias_suffix(registry, verb),
                    )
                )
            return join.LINES.join((*lines, *c.Infra.PROMOTED_HELP_GLOBAL_FOOTER))
        verb, separator, what = selector.partition(c.Infra.PromotedSelector.HELP_PATH)
        if not separator or cls.promoted_renders_verb_help(registry, verb, what):
            return cls._promoted_verb_help(registry, verb)
        command = registry.command(verb, what)
        mutates = help_.YES if command.mutates else help_.NO
        command_lines: list[str] = [
            help_.COMMAND_HEADER.format(verb=verb, what=what),
            "",
            help_.COMMAND_DOMAIN.format(domain=command.domain),
            help_.COMMAND_MUTATES.format(mutates=mutates),
            "",
            command.summary,
            command.description,
        ]
        if command.params:
            command_lines.extend(("", help_.PARAMS))
        for param in command.params:
            default, choices = cls._promoted_param_details(param)
            command_lines.append(
                help_.PARAM_LINE.format(
                    name=param.name,
                    help=param.help,
                    required=help_.PARAM_REQUIRED if param.required else "",
                    default=f"{join.WORDS}{default}" if default else "",
                    choices=f"{join.WORDS}{choices}" if choices else "",
                )
            )
        command_lines.extend(
            cls._promoted_section(help_.RULES, help_.RULE_LINE, command.rules)
        )
        example = cls._promoted_example(command, verb)
        command_lines.extend(
            cls._promoted_section(help_.EXAMPLE, help_.EXAMPLE_LINE, (example,))
        )
        return join.LINES.join(command_lines)

    @classmethod
    def _promoted_verb_help(
        cls, registry: p.Infra.PromotedRegistry, requested_verb: str
    ) -> str:
        """Render one verb, its actions, parameters, rules, and examples."""
        help_, join = c.Infra.PromotedHelp, c.Infra.PromotedJoin
        verb = registry.resolve_verb(requested_verb)
        suffix = cls._promoted_alias_suffix(registry, verb)
        commands = sorted(registry.commands(verb).items())
        lines: list[str] = [
            help_.VERB_HEADER.format(verb=requested_verb, suffix=suffix),
            "",
            help_.VERB_WHATS,
        ]
        options: list[str] = []
        for what, command in commands:
            marker = help_.MUTATES_MARKER if command.mutates else ""
            lines.append(
                help_.VERB_LINE.format(
                    what=what,
                    domain=command.domain,
                    summary=command.summary,
                    marker=marker,
                )
            )
            inline: list[str] = []
            for param in command.params:
                rendered = param.name + (
                    help_.INLINE_REQUIRED if param.required else ""
                )
                details = [item for item in cls._promoted_param_details(param) if item]
                inline.append(
                    help_.INLINE_DETAIL.format(
                        rendered=rendered, detail=join.DETAIL.join(details)
                    )
                    if details
                    else rendered
                )
            if inline:
                options.append(
                    help_.VERB_OPTION_LINE.format(
                        what=what, params=join.LIST.join(inline)
                    )
                )
        if options:
            lines.extend(("", help_.VERB_OPTIONS, *options, "", help_.VERB_DETAIL))
            lines.extend((
                help_.VERB_DETAIL_HELP.format(verb=requested_verb),
                help_.VERB_DETAIL_OPTIONS.format(verb=requested_verb),
            ))
        rules = {rule for _, command in commands for rule in command.rules}
        examples = {
            cls._promoted_example(command, requested_verb) for _, command in commands
        }
        lines.extend(cls._promoted_section(help_.RULES, help_.RULE_LINE, sorted(rules)))
        lines.extend(
            cls._promoted_section(help_.EXAMPLES, help_.EXAMPLE_LINE, sorted(examples))
        )
        return join.LINES.join(lines)

    @staticmethod
    def _promoted_alias_suffix(registry: p.Infra.PromotedRegistry, verb: str) -> str:
        """Render the alias suffix of one canonical verb, empty without aliases."""
        aliases = registry.aliases_for(verb)
        if not aliases:
            return ""
        return c.Infra.PromotedHelp.ALIAS_SUFFIX.format(
            aliases=c.Infra.PromotedJoin.LIST.join(aliases)
        )

    @staticmethod
    def _promoted_param_details(param: p.Infra.PromotedParam) -> t.Pair[str, str]:
        """Render the ``default=`` and ``choices=`` details, empty when undeclared."""
        help_ = c.Infra.PromotedHelp
        choices = c.Infra.PromotedJoin.VALUES.join(param.choices)
        return (
            help_.PARAM_DEFAULT.format(default=param.default) if param.default else "",
            help_.PARAM_CHOICES.format(choices=choices) if choices else "",
        )

    @staticmethod
    def _promoted_section(
        title: str, template: str, items: t.StrSequence
    ) -> t.StrSequence:
        """Render one titled help section, empty without items."""
        if not items:
            return ()
        return ("", title, *(template.format(item=item) for item in items))

    @staticmethod
    def _promoted_example(command: p.Infra.PromotedCommand, requested_verb: str) -> str:
        """Render a declared example through the requested alias when needed."""
        help_ = c.Infra.PromotedHelp
        canonical = help_.MAKE_VERB.format(verb=command.verb)
        requested = help_.MAKE_VERB.format(verb=requested_verb)
        if requested_verb != command.verb and command.example == (
            help_.CANONICAL_EXAMPLE.format(canonical=canonical, what=command.what)
        ):
            return requested
        if command.example.startswith(canonical):
            return requested + command.example.removeprefix(canonical)
        return command.example


__all__: list[str] = ["FlextInfraUtilitiesPromotedRendering"]
