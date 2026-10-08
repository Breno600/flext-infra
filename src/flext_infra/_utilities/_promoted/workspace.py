"""Promoted-command workspace boundary: owner root, interpreter, and guard.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from flext_infra import c, m
from flext_infra._settings import settings
from flext_infra._utilities import FlextInfraUtilitiesProjectDiscovery

if TYPE_CHECKING:
    from collections.abc import Callable

    from flext_infra import p, t


class FlextInfraUtilitiesPromotedWorkspace:
    """Resolve the owner workspace; every repository fact arrives as a spec."""

    @staticmethod
    def promoted_fail(template: str, **fields: t.Scalar | Path) -> NoReturn:
        """Raise the promoted registry error rendered from one message template.

        Raises:
            PromotedRegistryError: Always.

        """
        raise c.Infra.PromotedRegistryError(template.format(**fields))

    @staticmethod
    def promoted_find_owner_root(start: Path) -> Path | None:
        """Return ``start`` or nearest ancestor with ``scripts/`` + ``pyproject.toml``.

        A project root is its own owner, so discovery from the repository root
        resolves; command ownership follows the same boundary.

        Returns:
            ``start`` or its nearest ancestor owning ``scripts/`` + ``pyproject.toml``.

        """
        resolved = start.resolve()
        for candidate in (resolved, *resolved.parents):
            if (candidate / c.Infra.DIR_SCRIPTS).is_dir() and (
                candidate / c.PYPROJECT_FILENAME
            ).is_file():
                return candidate
        return None

    @staticmethod
    def promoted_workspace_spec(root: Path) -> p.Infra.PromotedWorkspaceSpec:
        """Build the workspace spec owned by one explicit repository root.

        Returns:
            The resulting ``p.Infra.PromotedWorkspaceSpec``.

        """
        return m.Infra.PromotedWorkspaceSpec(
            root=root,
            scripts=root / c.Infra.DIR_SCRIPTS,
            local_python=FlextInfraUtilitiesProjectDiscovery.runtime_python(root),
        )

    @classmethod
    def promoted_discovered_workspace_spec(cls) -> p.Infra.PromotedWorkspaceSpec:
        """Resolve the spec of the workspace owning the current working directory.

        Returns:
            The resulting ``p.Infra.PromotedWorkspaceSpec``.

        """
        root = cls.promoted_find_owner_root(Path.cwd())
        if root is None:
            cls.promoted_fail(c.Infra.PromotedMessage.NO_SCRIPTS_DIR)
        return cls.promoted_workspace_spec(root)

    @classmethod
    def promoted_ensure_local_python(cls, spec: p.Infra.PromotedWorkspaceSpec) -> None:
        """Fail unless make runs on a virtualenv or the expected local interpreter."""
        if sys.prefix != sys.base_prefix:
            return
        active = Path(sys.executable)
        expected = active
        if (
            not (settings.Infra.virtual_env and active.exists())
            and spec.local_python.exists()
        ):
            expected = spec.local_python
        if expected == spec.local_python and not spec.local_python.is_file():
            cls.promoted_fail(
                c.Infra.PromotedMessage.LOCAL_PYTHON_MISSING,
                python=spec.local_python,
            )
        if active.resolve() != expected.resolve():
            cls.promoted_fail(
                c.Infra.PromotedMessage.ACTIVE_PYTHON_MISMATCH,
                python=expected,
            )

    @staticmethod
    def promoted_main(script_file: str | Path, handler: Callable[[], int]) -> NoReturn:
        """Run a promoted Python command only when the dispatcher launched it.

        The guard writes the same canonical line as the shell guard, so consumer
        gates match one contract for ``.sh`` and ``.py`` commands.

        Raises:
            SystemExit: Always; or if ``settings.Infra.flext_command_dispatched !=
                c.Infra.PromotedSelector.DISPATCHED or settings.Infra.flext_command_path
                != str(Path(script_file).resolve())``.

        """
        if (
            settings.Infra.flext_command_dispatched
            != c.Infra.PromotedSelector.DISPATCHED
            or settings.Infra.flext_command_path != str(Path(script_file).resolve())
        ):
            sys.stderr.write(c.Infra.PromotedMessage.NOT_DISPATCHED)
            raise SystemExit(c.Infra.ScriptExitCode.USAGE)
        raise SystemExit(handler())


__all__: list[str] = ["FlextInfraUtilitiesPromotedWorkspace"]
