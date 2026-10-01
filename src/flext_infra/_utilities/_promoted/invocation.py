"""Promoted-command contract and invocation validation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c

from .workspace import FlextInfraUtilitiesPromotedWorkspace

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraUtilitiesPromotedInvocation(FlextInfraUtilitiesPromotedWorkspace):
    """Validate static header rules and runtime parameter values."""

    @classmethod
    def promoted_validate_invocation(cls, command: p.Infra.PromotedCommand) -> None:
        """Validate environment parameters before command execution."""
        for param in command.params:
            value = cls.promoted_param_value(param, command)
            if param.required and not value:
                message = c.Infra.PromotedMessage.MISSING_PARAM
            elif value and param.choices and value not in param.choices:
                message = c.Infra.PromotedMessage.INVALID_CHOICE
            else:
                continue
            cls.promoted_fail(
                message,
                verb=command.verb,
                what=command.what,
                name=param.name,
                example=command.example,
                value=value,
                valid=c.Infra.PromotedJoin.CHOICES.join(param.choices),
            )

    @classmethod
    def promoted_validate_command_contract(
        cls, command: p.Infra.PromotedCommand
    ) -> None:
        """Require the incident safety parameters on incident-domain mutations."""
        if (
            command.domain != c.Infra.PromotedSelector.INCIDENT_DOMAIN
            or not command.mutates
        ):
            return
        required = {param.name for param in command.params if param.required}
        for name in c.Infra.PROMOTED_INCIDENT_MUTATION_REQUIRED_PARAMS - required:
            cls.promoted_fail(
                c.Infra.PromotedMessage.PARAM_MUST_BE_REQUIRED,
                path=command.path,
                name=name,
            )

    @classmethod
    def promoted_validate_all_choices(
        cls, verb: str, commands: t.MappingKV[str, p.Infra.PromotedCommand]
    ) -> None:
        """Validate the WHAT choices declared on a verb's ``all`` command.

        The catalog is a LOCAL contract mirroring the project owning ``all``: a
        lower-priority root never forces a subrepo to enumerate the parent's
        surface. A verb without a declared ``all`` has no catalog.
        """
        catalog = commands.get(c.Infra.PromotedSelector.ALL)
        if catalog is None:
            return
        declared = next(
            (
                tuple(sorted(param.choices))
                for param in catalog.params
                if param.name == c.Infra.PromotedSelector.WHAT
            ),
            (),
        )
        if not declared:
            return
        owner = cls.promoted_find_owner_root(catalog.path)
        actual = tuple(
            sorted(
                what
                for what, command in commands.items()
                if cls.promoted_find_owner_root(command.path) == owner
            )
        )
        if declared != actual:
            cls.promoted_fail(
                c.Infra.PromotedMessage.ALL_CHOICES_DIVERGE,
                path=catalog.path,
                verb=verb,
                declared=c.Infra.PromotedJoin.VALUES.join(declared),
                actual=c.Infra.PromotedJoin.VALUES.join(actual),
            )

    @staticmethod
    def promoted_param_value(
        param: p.Infra.PromotedParam, command: p.Infra.PromotedCommand
    ) -> str:
        """Return one parameter value: the command WHAT, the environment, or default."""
        from flext_infra import u

        if param.name == c.Infra.PromotedSelector.WHAT:
            return command.what
        return u.Infra.env_value(param.name, param.default)


__all__: list[str] = ["FlextInfraUtilitiesPromotedInvocation"]
