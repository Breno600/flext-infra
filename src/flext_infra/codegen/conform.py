"""Unified, fail-closed conformance for new and existing repositories.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, p, r, t, u
from flext_infra.codegen._conform import FlextInfraCodegenConformExecute


class FlextInfraCodegenConform(FlextInfraCodegenConformExecute):
    """Plan every selected output, then atomically write only a clean plan."""

    @staticmethod
    def _mise_bootstrap_environment() -> m.Infra.MiseBootstrapEnvironmentSpec:
        """Project the single generated Mise isolation contract into templates."""
        return u.Infra.mise_bootstrap_environment()

    @staticmethod
    def _link_mode(
        repository: m.Infra.RepositoryRef, toolchain: m.Infra.ToolchainSpec
    ) -> str:
        """Resolve the repository override through one codegen authority."""
        link_mode = repository.uv_link_mode or toolchain.uv_link_mode
        if not isinstance(link_mode, str):
            msg = "resolved uv link mode must be a string"
            raise TypeError(msg)
        return link_mode

    @staticmethod
    def _dependency_cooldown_policy(
        repository: m.Infra.RepositoryRef, toolchain: m.Infra.ToolchainSpec
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
        discovered: list[m.Infra.MakeVerbSpec] = []
        for entry in sorted(scripts_dir.iterdir()):
            if entry.is_dir() and (entry / "all.sh").is_file():
                discovered.append(
                    m.Infra.MakeVerbSpec(
                        name=entry.name,
                        description=f"Script command: {entry.name}",
                        requires_apply=True,
                    )
                )
        return tuple(discovered)

    @classmethod
    def _surface_contract(
        cls, surface: c.Infra.CodegenConformSurface
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
        refresh_git_peers: bool = False,
    ) -> p.Result[bool]:
        """Conform every projection of ``root``, then lock it without upgrading.

        ``ports`` are the facade-bound collaborators the complete conform
        crosses into; without them the conform fails before any effect.

        Conform settles ``pyproject.toml`` and every rendered projection first,
        so the lock resolves against them; it upgrades nothing (only ``upg``
        resolves the newest releases). The lock is ``root``'s own: a checkout
        uv resolves as a member of an enclosing uv workspace fails before any
        effect, because ``uv lock`` there rewrites the enclosing lock and never
        this one. ``refresh_git_peers`` refreshes the
        metadata of the dependencies declared through git only — moving
        sources by declaration — because a peer that moved on the
        integration branch carries stale cached requires-dist a retaining
        lock cannot see through; the propagate caller owns the flag and the
        default stays hermetic. Identical inputs regenerate identical bytes,
        so a rerun changes nothing.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        owned = cls.require_own_lock(root)
        if owned.failure:
            return r[bool].from_failure(owned)
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
        command = [c.Infra.UV, "lock", "--project", str(root)]
        for name in cls._git_dependency_names(root) if refresh_git_peers else ():
            command.extend(("--refresh-package", name))
        return u.Cli.run_checked(command, cwd=root)

    @staticmethod
    def require_own_lock(root: Path) -> p.Result[Path]:
        """Return ``root`` when uv resolves it as the owner of its own lock.

        uv owns workspace discovery: ``uv workspace dir`` names the root whose
        ``uv.lock`` a ``uv lock --project root`` writes. A checkout attached
        inside an enclosing uv workspace resolves to that workspace, so locking
        it would rewrite the enclosing lock and leave its own stale; that is a
        failure here, never a silent relock of another repository.

        Returns:
            ``root`` when it owns its lock, otherwise the failure naming the
            enclosing uv workspace and the right way.

        """
        resolved = u.Cli.capture(
            [c.Infra.UV, "workspace", "dir", "--project", str(root)],
            cwd=root,
        )
        if resolved.failure:
            return r[Path].from_failure(resolved)
        owner = Path(resolved.value.strip()).resolve()
        if owner == root.resolve():
            return r[Path].ok(root)
        return r[Path].fail(
            f"uv resolves {root} as a member of the uv workspace {owner}: "
            f"`uv lock` there rewrites {owner}/uv.lock, never {root}/uv.lock. "
            f"Lock {root.name} from a linked worktree of it outside {owner}, "
            "where uv resolves it alone.",
        )

    @staticmethod
    def _git_dependency_names(root: Path) -> t.StrSequence:
        """Return the dependency names ``root`` declares through git.

        Branch-tracked git dependencies are moving sources by declaration:
        their cached metadata outlives the peer's tip, so the propagate
        caller refreshes exactly these and nothing else.

        Returns:
            The resulting ``t.StrSequence``.

        """
        payload = u.Infra.pyproject_payload(root / c.PYPROJECT_FILENAME)
        project = payload.get("project")
        if not isinstance(project, dict):
            return ()
        dependencies = project.get("dependencies")
        if not isinstance(dependencies, list):
            return ()
        declared = project.get("dependencies")
        if not isinstance(declared, list):
            return ()
        return tuple(
            spec.split(" @ ", 1)[0].strip()
            for spec in declared
            if isinstance(spec, str) and "git+" in spec and " @ " in spec
        )


__all__: list[str] = ["FlextInfraCodegenConform"]
