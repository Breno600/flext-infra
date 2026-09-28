"""Promoted-command execution on the workspace process boundary."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c

from .invocation import FlextInfraUtilitiesPromotedInvocation

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraUtilitiesPromotedExecution(FlextInfraUtilitiesPromotedInvocation):
    """Run one promoted command in its canonical command environment."""

    @classmethod
    def promoted_run(cls, command: p.Infra.PromotedCommand) -> int:
        """Run one promoted command from its owner root and stream it live.

        The single workspace venv is authoritative for every inherited command;
        the owner root only fixes the working directory. The child is not
        captured, so output, Ctrl-C/SIGINT, and the exact exit code propagate.
        """
        from flext_infra import settings, u

        message, env_name = c.Infra.PromotedMessage, c.Infra.PromotedEnv
        project_root = cls.promoted_find_owner_root(command.path)
        if project_root is None:
            cls.promoted_fail(message.OWNER_UNKNOWN, path=command.path)
        python = Path(sys.executable)
        if not python.is_file():
            cls.promoted_fail(message.WORKSPACE_PYTHON_MISSING, python=python)
        live_settings = type(settings).fetch_global()
        active_venv = live_settings.Infra.virtual_env
        venv = Path(active_venv) if active_venv else Path(sys.prefix)
        env = os.environ.copy()
        env.update({
            param.name: cls.promoted_param_value(param, command)
            for param in command.params
        })
        env.update({
            env_name.WHAT: command.what,
            env_name.DISPATCHED: c.Infra.PromotedSelector.DISPATCHED,
            env_name.VERB: command.verb,
            env_name.COMMAND_WHAT: command.what,
            env_name.DOMAIN: command.domain,
            env_name.PATH: str(command.path.resolve()),
            env_name.VIRTUAL_ENV: str(venv),
            env_name.UV_PROJECT_ENVIRONMENT: str(venv),
            env_name.PYTHON: str(python),
            c.Infra.ORCHESTRATOR_ENV_PATH: os.pathsep.join((
                str(venv / c.Infra.PromotedSelector.VENV_BIN),
                env[c.Infra.ORCHESTRATOR_ENV_PATH],
            )),
            env_name.SUBMODULE_ROOT: str(project_root.resolve()),
        })
        interpreter: t.StrSequence = (
            str(python),
            c.Infra.PromotedSelector.PYTHON_SAFE_PATH,
        )
        if command.path.suffix != c.Infra.EXT_PYTHON:
            bash = shutil.which(c.Infra.PromotedSelector.BASH)
            if bash is None:
                cls.promoted_fail(message.BASH_MISSING)
            interpreter = (bash,)
        result = u.Cli.run_raw(
            (*interpreter, str(command.path)),
            cwd=project_root,
            env=env,
            remove_env_keys=(c.Infra.ORCHESTRATOR_ENV_PYTHONPATH,),
            capture=False,
        )
        if result.failure:
            # The process error is literal text, never a message template.
            raise c.Infra.PromotedRegistryError(
                result.error or message.PROCESS_START_FAILED
            )
        output: p.Cli.CommandOutput = result.value
        # flext-cli carries the causal completion state instead of a bare status:
        # the raw OS return code lives on the process outcome.
        exit_code: int = output.outcome.raw_return_code
        return exit_code


__all__: list[str] = ["FlextInfraUtilitiesPromotedExecution"]
