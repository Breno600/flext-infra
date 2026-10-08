"""Promoted-command discovery across first-wins script roots.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from flext_infra import c, u
from flext_infra._promoted.registry import FlextInfraPromotedRegistry

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraPromotedDiscovery(FlextInfraPromotedRegistry):
    """Build one validated registry from ``scripts/<verb>/<WHAT>`` headers."""

    @classmethod
    def discover(
        cls,
        *,
        script_roots: Sequence[Path] | None = None,
        spec: p.Infra.PromotedWorkspaceSpec | None = None,
    ) -> Self:
        """Discover promoted commands from every configured script root.

        The first root is authoritative; later roots only fill gaps, so a
        workspace can inject ``scripts/`` before its subrepos while each isolated
        subrepo stays authoritative over its own commands. Without injection the
        order is ``spec.scripts``, sorted submodule roots, then the consumer root.

        Returns:
            The resulting ``Self``.

        """
        message = c.Infra.PromotedMessage
        workspace = spec or u.Infra.promoted_discovered_workspace_spec()
        roots = (
            tuple(dict.fromkeys(script_roots))
            if script_roots is not None
            else (
                workspace.scripts,
                *sorted(workspace.submodule_script_roots, key=str),
                *filter(None, (workspace.consumer_scripts_root,)),
            )
        )
        if not any(root.exists() for root in roots):
            u.Infra.promoted_fail(message.NO_SCRIPTS_DIR)
        registry = cls()
        for index, root in enumerate(roots):
            cls._collect_root_commands(registry, index, root)
        registry.validate()
        return registry

    @classmethod
    def _collect_root_commands(cls, registry: Self, index: int, root: Path) -> None:
        """Collect one root's command directories into the registry.

        Later roots only fill gaps left by higher-priority roots.

        """
        message = c.Infra.PromotedMessage
        for verb_dir in sorted(root.iterdir()) if root.exists() else ():
            if verb_dir.is_file() or verb_dir.name in c.Infra.PROMOTED_IGNORED_DIRS:
                continue
            if not verb_dir.is_dir():
                u.Infra.promoted_fail(
                    message.INVALID_SCRIPTS_ENTRY,
                    path=verb_dir,
                    root=root,
                )
            # A directory where no file declares a header is not a command
            # directory; a present but invalid header stays a defect.
            headers = u.Infra.promoted_command_headers(verb_dir)
            if all(
                isinstance(header, c.Infra.PromotedMissingHeaderError)
                for header in headers.values()
            ):
                continue
            for path in sorted(verb_dir.iterdir()):
                command = cls._load_command(message, path, verb_dir, headers)
                if command is None:
                    continue
                # Later roots only fill gaps left by higher-priority roots.
                if not (index and registry.has(command.verb, command.what)):
                    registry.add(command)

    @staticmethod
    def _load_command(
        message: type[c.Infra.PromotedMessage],
        path: Path,
        verb_dir: Path,
        headers: t.MappingKV[Path, t.JsonMapping | c.Infra.PromotedRegistryError],
    ) -> p.Infra.PromotedCommand | None:
        """Validate one command file and load its promoted command.

        Returns:
            The loaded promoted command, or ``None`` for a declared
            non-command name.

        """
        if path.name in c.Infra.PROMOTED_NON_COMMAND_NAMES:
            return None
        if path.is_dir():
            u.Infra.promoted_fail(message.NESTED_DIR, path=path)
        if path.suffix not in c.Infra.PROMOTED_COMMAND_SUFFIXES:
            u.Infra.promoted_fail(message.INVALID_SUFFIX, path=path)
        header = headers[path]
        if isinstance(header, c.Infra.PromotedRegistryError):
            raise header
        return u.Infra.promoted_load_command(path, verb_dir.name, header)


__all__: list[str] = ["FlextInfraPromotedDiscovery"]
