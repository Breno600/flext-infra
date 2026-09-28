"""Promoted-command dispatcher entry point and verb routing."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from flext_infra import c, settings, u

from .discovery import FlextInfraPromotedDiscovery

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from flext_infra import p


class FlextInfraPromotedDispatch(FlextInfraPromotedDiscovery):
    """Route ``make <verb> WHAT=<action>`` to help or one promoted command."""

    @classmethod
    def main(
        cls,
        argv: Sequence[str] | None = None,
        *,
        script_roots: Sequence[Path] | None = None,
        spec: p.Infra.PromotedWorkspaceSpec | None = None,
    ) -> int:
        """Run the promoted command dispatcher.

        WHAT is resolved from the live settings singleton on every run, so
        ``FlextSettings.update_global`` propagates without monkeypatching.
        """
        args = tuple(sys.argv[1:] if argv is None else argv)
        try:
            return cls._run(args, script_roots=script_roots, spec=spec)
        except c.Infra.PromotedRegistryError as exc:
            u.Cli.error(exc.message)
            return c.Infra.ScriptExitCode.USAGE

    @classmethod
    def _run(
        cls,
        args: Sequence[str],
        *,
        script_roots: Sequence[Path] | None,
        spec: p.Infra.PromotedWorkspaceSpec | None,
    ) -> int:
        """Discover the registry, then validate, dispatch, or render help."""
        workspace = spec or u.Infra.promoted_discovered_workspace_spec()
        u.Infra.promoted_ensure_local_python(workspace)
        registry = cls.discover(script_roots=script_roots, spec=workspace)
        if args[:1] == (c.Infra.PromotedSelector.VALIDATE,):
            return c.Infra.ScriptExitCode.PASS
        requested_what = (settings.Infra.dispatch_what or "").strip()
        if args and args[0] not in c.Infra.PROMOTED_HELP_ARGS:
            return cls.dispatch(registry, args[0], requested_what)
        sys.stdout.write(
            u.Infra.promoted_render_help(registry, requested_what)
            + c.Infra.PromotedJoin.LINES
        )
        return c.Infra.ScriptExitCode.PASS

    @staticmethod
    def dispatch(
        registry: p.Infra.PromotedRegistry, requested_verb: str, requested_what: str
    ) -> int:
        """Dispatch one requested verb to help or its selected promoted command.

        ``requested_what`` is resolved once at the CLI boundary and passed
        explicitly, so dispatch never reads ambient settings. An alias pointing
        at a concrete WHAT selects it when WHAT is empty; an undeclared ``all``
        renders the verb help like an empty WHAT.
        """
        alias_target = registry.alias_target(requested_verb)
        what = requested_what
        if not what and alias_target is not None:
            what = alias_target.what
        verb = registry.resolve_verb(requested_verb)
        if u.Infra.promoted_renders_verb_help(registry, verb, what) or (
            not requested_what and what == c.Infra.PromotedSelector.ALL
        ):
            selector = requested_verb
        else:
            command = registry.command(verb, what)
            if not any(
                (u.Infra.env_lookup(name) or c.Infra.PromotedSelector.DISABLED).upper()
                in c.Infra.PROMOTED_ENV_ENABLED_VALUES
                for name in (c.Infra.PromotedEnv.HELP, c.Infra.PromotedEnv.OPTIONS)
            ):
                u.Infra.promoted_validate_invocation(command)
                return u.Infra.promoted_run(command)
            selector = c.Infra.PromotedSelector.HELP_PATH.join((requested_verb, what))
        sys.stdout.write(
            u.Infra.promoted_render_help(registry, selector)
            + c.Infra.PromotedJoin.LINES
        )
        return c.Infra.ScriptExitCode.PASS


__all__: list[str] = ["FlextInfraPromotedDispatch"]
