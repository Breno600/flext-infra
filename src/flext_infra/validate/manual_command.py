"""Manual-command blocker (AGENTS.md `Build & Test`).

``command_blocked`` — predicate flagging a bare tool invocation (ruff/pytest/git/…)
that bypasses the ``make`` / ``python -m flext_infra`` monopoly. Deny rules are
evaluated FIRST, per shell segment, after stripping wrappers and path components
— an allow-list substring can never short-circuit a deny.

The former pre-commit-config drift half of this module is retired: the
``.pre-commit-config.yaml`` content has one owner, the codegen template
``templates/project/base/.pre-commit-config.yaml.j2``, and its drift has one
detector, ``codegen conform --mode check`` (wired into ``make check``). A
second detector diffing the live file against a hand-copied constant was
permanently red on any conforming repository.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shlex
from pathlib import Path

from flext_infra import c, t
from flext_infra.base import s


class FlextInfraManualCommandValidator(s[bool]):
    """Flag bare tool invocations that bypass the make / flext_infra monopoly."""

    @classmethod
    def command_blocked(cls, command: str) -> bool:
        """Check whether any shell segment runs a managed tool outside make/flext_infra.

        Returns:
            The resulting ``bool``.

        """
        stripped = command.strip()
        if not stripped:
            return False
        return any(
            cls._segment_blocked(segment.strip())
            for segment in c.Infra.MANUAL_CMD_SEGMENT_RE.split(stripped)
        )

    @classmethod
    def _segment_blocked(cls, segment: str) -> bool:
        """Apply deny rules to a single shell segment after normalisation.

        Returns:
            The resulting ``bool``.

        """
        tokens: t.MutableSequenceOf[str] = (
            cls._strip_wrappers(shlex.split(segment)) if segment else []
        )
        if not tokens:
            return False
        head = Path(tokens[0]).name
        rest = tokens[1:]
        blocked_tools = c.Infra.MANUAL_CMD_BLOCKED_TOOLS
        if head in blocked_tools:
            return True
        if (
            head in c.Infra.MANUAL_CMD_RUNNERS
            and cls._module_after_m(rest) in blocked_tools
        ):
            return True
        if head == "git" and rest and rest[0] in c.Infra.MANUAL_CMD_BLOCKED_GIT:
            return True
        if head == "sed" and any(cls._is_sed_inplace(arg) for arg in rest):
            return True
        return head in c.Infra.MANUAL_CMD_REWRITE_TOOLS and any(
            arg in c.Infra.MANUAL_CMD_REWRITE_FLAGS or arg.startswith("--rewrite=")
            for arg in rest
        )

    @classmethod
    def _strip_wrappers(cls, tokens: t.StrSequence) -> t.MutableSequenceOf[str]:
        """Drop leading wrapper commands and ``env VAR=val`` assignments.

        Returns:
            The resulting ``t.MutableSequenceOf[str]``.

        """
        out: t.MutableSequenceOf[str] = list(tokens)
        while out:
            name = Path(out[0]).name
            if name == "env":
                out = out[1:]
                while out and "=" in out[0] and not out[0].startswith("-"):
                    out = out[1:]
                continue
            if name in c.Infra.MANUAL_CMD_WRAPPERS:
                out = out[1:]
                continue
            if name == "uv" and len(out) > 1 and out[1] == "run":
                out = cls._strip_uv_run_options(out[2:])
                continue
            break
        return out

    @classmethod
    def _strip_uv_run_options(cls, tokens: t.StrSequence) -> t.MutableSequenceOf[str]:
        """Return the real command after ``uv run`` and its options.

        Returns:
            The real command after ``uv run`` and its options.

        """
        out = list(tokens)
        while out:
            arg = out[0]
            if arg == "--":
                return out[1:]
            if not arg.startswith("-"):
                return out
            option = arg.split("=", maxsplit=1)[0]
            out = out[1:]
            if (
                "=" not in arg
                and option in c.Infra.MANUAL_CMD_UV_RUN_VALUE_OPTIONS
                and out
            ):
                out = out[1:]
        return out

    @staticmethod
    def _module_after_m(rest: t.StrSequence) -> str:
        """Return the module name following ``-m`` (``python -m <module>``).

        Returns:
            The module name following ``-m`` (``python -m <module>``).

        """
        for index, arg in enumerate(rest):
            if arg == "-m" and index + 1 < len(rest):
                module_name: str = t.Infra.STR_ADAPTER.validate_python(rest[index + 1])
                return module_name
        return ""

    @staticmethod
    def _is_sed_inplace(arg: str) -> bool:
        """Check for GNU/BSD in-place edit flags (``-i``, ``-i.bak``, ``--in-place``).

        Returns:
            The resulting ``bool``.

        """
        return (
            arg == "--in-place"
            or arg.startswith("--in-place=")
            or (arg.startswith("-i") and not arg.startswith("--"))
        )


__all__: list[str] = ["FlextInfraManualCommandValidator"]
