# Copyright 2026 FLEXT
"""Bootstrap child processes, all spawned through the canonical ``u.Cli`` runner.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraBootstrapProcessMixin:
    """Spawn git, Mise and uv for the bootstrap; failures escape loudly."""

    @staticmethod
    def _spawn(
        command: list[str],
        environment: t.StrMapping | None = None,
    ) -> p.Cli.CommandOutput:
        """Run one command; an ``environment`` replaces the inherited one entirely.

        Returns:
            The resulting ``p.Cli.CommandOutput``.

        Raises:
            ValueError: If the command could not be executed.
        """
        executed = u.Cli.run_raw(
            command,
            env=environment,
            remove_env_keys=() if environment is None else tuple(os.environ),
        )
        if executed.failure:
            raise ValueError(f"{command[0]} could not run: {executed.error}")
        return executed.value

    @classmethod
    def _checked(
        cls,
        tool: str,
        command: list[str],
        environment: t.StrMapping | None = None,
    ) -> p.Cli.CommandOutput:
        """Run one command that must exit zero; its stderr is forwarded.

        Returns:
            The resulting ``p.Cli.CommandOutput``.

        Raises:
            ValueError: If the command exited nonzero.
        """
        completed = cls._spawn(command, environment)
        if not u.Cli.process_succeeded(completed.outcome):
            sys.stderr.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            raise ValueError(
                f"{tool} exited {completed.outcome.raw_return_code}: "
                f"{' '.join(command[1:])}\n"
                + (completed.stdout + completed.stderr).strip(),
            )
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        return completed

    @staticmethod
    def _git_executable() -> str:
        """Resolve git to an absolute path so PATH cannot substitute it.

        Returns:
            The resulting ``str``.

        Raises:
            ValueError: If git executable is absent from PATH.
        """
        resolved = shutil.which("git")
        if resolved is None:
            raise ValueError("git executable is absent from PATH")
        return resolved

    @classmethod
    def _git_output(cls, project: Path, *arguments: str) -> bytes | None:
        """Read byte-exact git stdout; ``None`` when git fails or exits nonzero.

        Returns:
            The resulting ``bytes | None``.
        """
        executed = u.Cli.run_bytes(
            [cls._git_executable(), "-C", str(project), *arguments],
        )
        if executed.failure or not u.Cli.process_succeeded(executed.value.outcome):
            return None
        return executed.value.stdout


__all__: list[str] = ["FlextInfraBootstrapProcessMixin"]
