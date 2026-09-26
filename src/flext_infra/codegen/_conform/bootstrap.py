"""Conform service root: validated request state and toolchain policy."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import Annotated

from ... import c, m, s, t


class FlextInfraCodegenConformBootstrap(s[m.Infra.CodegenResult]):
    """Root of the conform chain: request state and toolchain policy projections.

    This is the only orchestrator for Make/toolchain/source conformance.
    Rendering stays in flext-cli; Git-source TOML policy and attached detection
    are composed from their separately owned u.Infra/workspace services.
    """

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

    @staticmethod
    def link_mode(
        repository: m.Infra.RepositoryRef, toolchain: m.Infra.ToolchainSpec
    ) -> str:
        """Resolve the repository override through one codegen authority."""
        return repository.uv_link_mode or toolchain.uv_link_mode

    @staticmethod
    def _discover_script_verbs(
        repository_root: Path,
    ) -> t.VariadicTuple[m.Infra.MakeVerbSpec]:
        """Discover script verbs from scripts/<verb>/all.sh in the repository root.

        The filesystem is the SSOT: a verb is emitted only when its all.sh
        entrypoint exists. No manual list is required.
        """
        scripts_dir = repository_root / c.Infra.DIR_SCRIPTS
        if not scripts_dir.is_dir():
            return ()
        discovered = [
            m.Infra.MakeVerbSpec(
                name=entry.name, description=f"Script command: {entry.name}"
            )
            for entry in sorted(scripts_dir.iterdir())
            if entry.is_dir() and (entry / "all.sh").is_file()
        ]
        return tuple(discovered)

    @staticmethod
    def _merge_extra_verbs(
        declared: t.VariadicTuple[m.Infra.MakeVerbSpec],
        discovered: t.VariadicTuple[m.Infra.MakeVerbSpec],
        canonical_names: frozenset[str],
    ) -> t.VariadicTuple[m.Infra.MakeVerbSpec]:
        """Union declared and discovered script verbs deduplicated by name.

        Why (cosmos-3flk9): object-level dedup never converges because declared
        verbs carry their canonical config descriptions while discoveries carry
        ``Script command: <name>``, so every verb entered ``extra_verbs`` twice
        and the generated Makefile emitted colliding ``_builtin-<verb>``
        recipes. The declared config verb is the writable authority and wins;
        a discovery is dropped when it would shadow a canonical ``make.verbs``
        builtin, whose native ``_builtin-<verb>`` implementation is the only
        owner of that name in the generated Makefile.
        """
        merged: MutableMapping[str, m.Infra.MakeVerbSpec] = {}
        for verb in discovered:
            if verb.name in canonical_names:
                continue
            merged.setdefault(verb.name, verb)
        for verb in declared:
            if verb.name in canonical_names:
                msg = (
                    f"config extra_verbs declares canonical verb {verb.name!r}; "
                    "extra verbs must never shadow canonical make.verbs builtins"
                )
                raise ValueError(msg)
            merged[verb.name] = verb
        return tuple(merged.values())

    @classmethod
    def surface_contract(
        cls, surface: c.Infra.CodegenConformSurface
    ) -> m.Infra.CodegenConformSurfaceContract:
        match surface:
            case c.Infra.CodegenConformSurface.ALL:
                return m.Infra.CodegenConformSurfaceContract(complete_governed=True)
            case (
                c.Infra.CodegenConformSurface.DEPENDENCIES
                | c.Infra.CodegenConformSurface.PYPROJECT
            ):
                return m.Infra.CodegenConformSurfaceContract(
                    destinations=frozenset({c.PYPROJECT_FILENAME}),
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
                return m.Infra.CodegenConformSurfaceContract(
                    destinations=frozenset({c.PYPROJECT_FILENAME}),
                    delegates=False,
                    custom=False,
                )


__all__: list[str] = ["FlextInfraCodegenConformBootstrap"]
