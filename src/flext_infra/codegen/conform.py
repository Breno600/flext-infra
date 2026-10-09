"""Unified, fail-closed conformance for new and existing repositories.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, m, p, r, u
from flext_infra.codegen._conform import FlextInfraCodegenConformExecute

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraCodegenConform(FlextInfraCodegenConformExecute):
    """Plan every selected output, then atomically write only a clean plan."""

    @staticmethod
    def _mise_bootstrap_environment() -> m.Infra.MiseBootstrapEnvironmentSpec:
        """Project the single generated Mise isolation contract into templates."""
        return u.Infra.mise_bootstrap_environment()

    @staticmethod
    def _link_mode(
        repository: m.Infra.RepositoryRef,
        toolchain: m.Infra.ToolchainSpec,
    ) -> str:
        """Resolve the repository override through one codegen authority."""
        link_mode = repository.uv_link_mode or toolchain.uv_link_mode
        if not isinstance(link_mode, str):
            msg = "resolved uv link mode must be a string"
            raise TypeError(msg)
        return link_mode

    @staticmethod
    def _dependency_cooldown_policy(
        repository: m.Infra.RepositoryRef,
        toolchain: m.Infra.ToolchainSpec,
    ) -> tuple[tuple[str, ...], dict[str, str]]:
        """Compose fleet defaults with the repository's narrower policy."""
        exclusions = dict.fromkeys(toolchain.dependency_cooldown_exclusions)
        overrides = dict(toolchain.dependency_cooldown_overrides)
        for package in repository.dependency_cooldown_exclusions:
            overrides.pop(package, None)
            exclusions[package] = None
        for package, cutoff in repository.dependency_cooldown_overrides.items():
            exclusions.pop(package, None)
            overrides[package] = cutoff
        return tuple(exclusions), overrides

    @staticmethod
    def _discover_script_verbs(
        repository_root: Path,
    ) -> tuple[m.Infra.MakeVerbSpec, ...]:
        """Discover script verbs from scripts/<verb>/all.sh in the repository root.

        The filesystem is the SSOT: a verb is emitted only when its all.sh
        entrypoint exists. No manual list is required.
        """
        scripts_dir = repository_root / "scripts"
        if not scripts_dir.is_dir():
            return ()
        discovered: list[m.Infra.MakeVerbSpec] = [
            m.Infra.MakeVerbSpec(
                name=entry.name,
                description=f"Script command: {entry.name}",
                requires_apply=True,
            )
            for entry in sorted(scripts_dir.iterdir())
            if entry.is_dir() and (entry / "all.sh").is_file()
        ]
        return tuple(discovered)

    @classmethod
    def _surface_contract(
        cls,
        surface: c.Infra.CodegenConformSurface,
    ) -> m.Infra.CodegenConformSurfaceContract:
        match surface:
            case c.Infra.CodegenConformSurface.ALL:
                return m.Infra.CodegenConformSurfaceContract(complete_governed=True)
            case c.Infra.CodegenConformSurface.DEPENDENCIES:
                return m.Infra.CodegenConformSurfaceContract(
                    destinations=frozenset({c.Infra.PYPROJECT_FILENAME}),
                    delegates=False,
                    custom=False,
                )
            case c.Infra.CodegenConformSurface.PYPROJECT:
                return m.Infra.CodegenConformSurfaceContract(
                    destinations=frozenset({c.Infra.PYPROJECT_FILENAME}),
                    delegates=False,
                    custom=False,
                )
            case c.Infra.CodegenConformSurface.MAKEFILE:
                return m.Infra.CodegenConformSurfaceContract(
                    destinations=frozenset({c.Infra.MAKEFILE_FILENAME}),
                    pyproject=False,
                    custom=False,
                )
            case _:
                msg = f"Unsupported codegen conform surface: {surface}"
                raise ValueError(msg)

    # This is the only
    # orchestrator for Make/toolchain/source conformance. Rendering stays in
    # flext-cli; Git-source TOML policy and attached detection are composed from
    # their separately owned u.Infra/workspace services.
    request: Annotated[
        m.Infra.CodegenConformRequest | None,
        m.Field(default=None, exclude=True, description="Validated conform request"),
    ] = None
    initial_workspace: Annotated[
        m.Infra.WorkspaceSpec | None,
        m.Field(
            default=None,
            exclude=True,
            description="Validated scaffold specification included in the atomic plan",
        ),
    ] = None
    scaffolded_repository: Annotated[
        bool,
        m.Field(
            default=False,
            exclude=True,
            description="Whether this invocation initialized an unpublished Git root",
        ),
    ] = False

    @classmethod
    def settle_repository(
        cls,
        root: Path,
        *,
        ports: m.Infra.CodegenConformPorts | None,
    ) -> p.Result[bool]:
        """Conform every projection of ``root``, then lock it without upgrading.

        ``ports`` are the facade-bound collaborators the complete conform
        crosses into; without them the conform fails before any effect.

        Conform settles ``pyproject.toml`` and every rendered projection first,
        so the lock resolves against them; it upgrades nothing (only ``upg``
        resolves the newest releases). Identical inputs regenerate identical
        bytes, so a rerun changes nothing.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        conformed = cls.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                scope=c.Infra.CodegenConformScope.ALL,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            ports=ports,
        )
        if conformed.failure:
            return r[bool].from_failure(conformed)
        return u.Cli.run_checked([c.Infra.UV, "lock", "--project", str(root)], cwd=root)


__all__: list[str] = ["FlextInfraCodegenConform"]
