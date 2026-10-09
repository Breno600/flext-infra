"""Strict isolated subprocess environment for Mise artifact generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r, settings, t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraMiseArtifactsProcess:
    """Strict isolated subprocess environment for Mise artifact generation."""

    @classmethod
    def prepare_isolation(
        cls,
        scratch: Path,
        contract: m.Infra.MiseBootstrapEnvironmentSpec,
    ) -> p.Result[bool]:
        """Create only invocation-local policy, home, and receipt paths.

        Returns:
            The resulting ``p.Result[bool]``.

        """

        def directory_key(path: Path) -> t.Pair[int, str]:
            return len(path.parts), path.as_posix()

        if not settings.Infra.system_path:
            return r[bool].fail("PATH is required for isolated Mise execution")
        if scratch.exists() or scratch.is_symlink():
            return r[bool].fail(f"isolated Mise runtime already exists: {scratch}")
        empty_files = tuple(scratch / relative for relative in contract.empty_files)
        transient_directories = {
            scratch / relative
            for _name, relative in contract.transient_environment
            if scratch / relative not in empty_files
        }
        directories = sorted(
            {
                scratch / "seed" / "bin",
                scratch / "receipt" / "bin",
                *(path.parent for path in empty_files),
                *transient_directories,
            },
            key=directory_key,
        )
        for directory in directories:
            planned = u.Cli.atomic_plan_directory_chain(directory)
            if planned.failure:
                return r[bool].from_failure(planned)
            created = u.Cli.atomic_create_directory_chain_guarded(
                planned.value,
                permission_mode=0o700,
            )
            if created.failure:
                return r[bool].from_failure(created)
        for path in empty_files:
            written = cls.write_new(path, b"", 0o600)
            if written.failure:
                return written
        return r[bool].ok(value=True)

    @classmethod
    def environment(
        cls,
        scratch: Path,
        storage_root: Path,
        release: str,
        contract: m.Infra.MiseBootstrapEnvironmentSpec,
    ) -> p.Result[MutableMapping[str, str]]:
        """Build one isolated environment backed by release-addressed storage.

        Returns:
            The resulting ``p.Result[MutableMapping[str, str]]``.

        """
        install_path = u.Infra.mise_runtime_install_path(storage_root, release)
        if install_path.failure:
            return r[MutableMapping[str, str]].from_failure(install_path)
        isolated = dict(contract.fixed_environment)
        isolated.update({
            name: str(scratch / relative)
            for name, relative in contract.transient_environment
        })
        isolated.update({
            name: str(storage_root if relative == "." else storage_root / relative)
            for name, relative in contract.persistent_environment
        })
        isolated.update({
            "GIT_CEILING_DIRECTORIES": str(scratch.parent),
            "MISE_CEILING_PATHS": str(scratch.parent),
            "MISE_TRUSTED_CONFIG_PATHS": str(scratch),
            "MISE_INSTALL_PATH": str(install_path.value),
        })
        for name in contract.passthrough_environment:
            if value := u.Infra.env_lookup(name):
                isolated[name] = value
        return r[MutableMapping[str, str]].ok(isolated)

    @classmethod
    def no_config_environment(
        cls,
        environment_values: t.StrMapping,
    ) -> MutableMapping[str, str]:
        """Select Mise's documented config-free mode for runtime-only commands.

        Returns:
            The resulting ``MutableMapping[str, str]``.

        """
        result = dict(environment_values)
        result["MISE_NO_CONFIG"] = "1"
        return result

    @classmethod
    def run(
        cls,
        command: t.StrSequence,
        *,
        cwd: Path,
        env: t.StrMapping,
        operation: str,
    ) -> p.Result[str]:
        """Run one Mise process and reject nonzero status or any Mise warning.

        Returns:
            The resulting ``p.Result[str]``.

        """
        u.Cli.info(f"mise-toolchain: start operation={operation}")
        executed = u.Cli.run_raw(
            command,
            cwd=cwd,
            env=env,
            remove_env_keys=tuple(os.environ),
            timeout=c.Infra.TIMEOUT_LONG,
        )
        if executed.failure:
            return r[str].from_failure(executed)
        command_output = executed.value
        output = command_output.stdout + command_output.stderr
        if not u.Cli.process_succeeded(command_output.outcome):
            detail = output.strip() or f"exit {command_output.outcome.raw_return_code}"
            return r[str].fail(f"{operation} failed: {detail}")
        if "mise WARN" in output:
            return r[str].fail(f"{operation} emitted a warning: {output.strip()}")
        u.Cli.info(f"mise-toolchain: complete operation={operation}")
        return r[str].ok(command_output.stdout.strip())

    @classmethod
    def write_new(cls, path: Path, content: bytes, mode: int) -> p.Result[bool]:
        """Create exact isolated state through the canonical atomic owner.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        before = u.Cli.atomic_read_binary_file_state(path, required=False)
        if before.failure:
            return r[bool].from_failure(before)
        return u.Cli.atomic_write_binary_file_guarded(
            before.value,
            content,
            permission_mode=mode,
        )


__all__: list[str] = ["FlextInfraMiseArtifactsProcess"]
