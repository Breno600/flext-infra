"""Runtime-derived dependency floors written back to the codegen SSOT.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, config, m, u

if TYPE_CHECKING:
    from ruamel.yaml.comments import CommentedMap

    from flext_infra import t


class FlextInfraDepsFloorProfileWriter:
    """Rewrite dependency_profiles floors from the provisioned runtime."""

    @staticmethod
    def _source_paths(root: Path) -> t.SequenceOf[Path]:
        """Elect the local owner from the caller's typed workspace declaration.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        Raises:
            ValueError: If ambiguous dependency floor owners in; or if dependency floor
                configuration is outside workspace; or if dependency floor owner is not
                writable in this workspace.

        """
        root = root.resolve()
        manifests = u.Infra.load_workspace_manifest(root).unwrap()
        relative = Path(c.Infra.CODEGEN_CONFIG_DIR) / c.Infra.CODEGEN_CONFIG_FILENAME
        local = root / relative
        owners = [root] if local.exists() or local.is_symlink() else []
        for manifest in manifests:
            for member in manifest.members:
                if member.distribution != config.Infra.name:
                    continue
                owner = (root / member.path).resolve()
                if not owner.is_relative_to(root) or member.read_only:
                    message = (
                        f"dependency floor owner is not writable "
                        f"in this workspace: {owner}"
                    )
                    raise ValueError(message)
                owners.append(owner)
            if manifest.repository.distribution == config.Infra.name and not owners:
                owners.append(root)
        if len(owners) > 1:
            message = f"ambiguous dependency floor owners in {root}: {owners}"
            raise ValueError(message)
        sources = tuple(owner / relative for owner in owners)
        for source in sources:
            if not source.resolve().is_relative_to(root):
                message = (
                    f"dependency floor configuration is outside workspace: {source}"
                )
                raise ValueError(message)
        return sources

    @classmethod
    def rewrite_profiles_from_resolution(
        cls,
        *,
        root: Path,
        resolved_versions: t.MappingKV[str, str],
        internal_names: t.StrSequence,
    ) -> t.StrSequence:
        """Update dependency_profiles in the caller's local codegen owner.

        ``root`` is the modernizer's own declared ``--repository-root``.
        A workspace declares its infrastructure member through its typed
        manifest; a standalone owner carries its own configuration. Neither
        route consults the installed package location.

        Returns a list of change descriptions for the deps report.

        Returns:
            The resulting ``t.StrSequence``.

        """
        sources = cls._source_paths(root)
        if not sources:
            return ()
        (ssot_path,) = sources
        document = cls._loaded_document(ssot_path)
        sections = cls._validated_sections(document, ssot_path)
        changes = cls._rewrite_profiles(
            sections,
            ssot_path,
            resolved_versions=resolved_versions,
            internal_names=internal_names,
        )
        if not changes:
            return ()

        # Dump back with comments preserved
        dumped = u.Cli.yaml_roundtrip_dump_text(document).unwrap()
        u.Cli.atomic_write_text_file(ssot_path, dumped).unwrap()

        return changes

    @staticmethod
    def _loaded_document(ssot_path: Path) -> CommentedMap:
        """Round-trip load the dependency floor owner document.

        Returns:
            The loaded comment-preserving mapping document.

        Raises:
            ValueError: If ``loaded.failure`` — a missing or unparseable owner is
                the same invalid-owner failure as a missing section: one
                ValueError contract, original cause chained.

        """
        loaded = u.Cli.yaml_roundtrip_load_map(ssot_path)
        if loaded.failure:
            raise ValueError(loaded.error) from loaded.exception
        return loaded.value

    @staticmethod
    def _validated_sections(
        document: t.MappingKV[str, t.JsonValue],
        ssot_path: Path,
    ) -> t.Pair[
        t.SequenceOf[t.JsonValue],
        t.SequenceOf[m.Infra.ScaffoldDependencyProfileSpec],
    ]:
        """Navigate to and validate the dependency-profile declaration sections.

        Returns:
            The ``(raw_profiles, validated_profiles)`` pair.

        Raises:
            ValueError: If Infra section missing in; or if Infra.codegen section
                missing in; or if Infra.codegen.scaffold section missing in; or if
                Infra.codegen.scaffold.project section missing in; or if
                dependency_profiles missing or not a list in.

        """
        # Navigate to Infra.codegen.scaffold.project.dependency_profiles
        infra = document.get("Infra")
        if not infra or not isinstance(infra, dict):
            message = f"Infra section missing in {ssot_path}"
            raise ValueError(message)
        codegen = infra.get("codegen")
        if not codegen or not isinstance(codegen, dict):
            message = f"Infra.codegen section missing in {ssot_path}"
            raise ValueError(message)
        scaffold = codegen.get("scaffold")
        if not scaffold or not isinstance(scaffold, dict):
            message = f"Infra.codegen.scaffold section missing in {ssot_path}"
            raise ValueError(message)
        project = scaffold.get("project")
        if not project or not isinstance(project, dict):
            message = f"Infra.codegen.scaffold.project section missing in {ssot_path}"
            raise ValueError(message)
        profiles = project.get("dependency_profiles")
        if not profiles or not isinstance(profiles, list):
            message = f"dependency_profiles missing or not a list in {ssot_path}"
            raise ValueError(message)
        # Dependency modernization precedes generation during an upgrade. Only
        # the profiles belong to this writer; unrelated sections may still use
        # the previous generator's schema. Validate every profile before edits.
        validated = tuple(
            m.Infra.ScaffoldDependencyProfileSpec.model_validate(profile)
            for profile in profiles
        )
        return (profiles, validated)

    @classmethod
    def _rewrite_profiles(
        cls,
        sections: t.Pair[
            t.SequenceOf[t.JsonValue],
            t.SequenceOf[m.Infra.ScaffoldDependencyProfileSpec],
        ],
        ssot_path: Path,
        *,
        resolved_versions: t.MappingKV[str, str],
        internal_names: t.StrSequence,
    ) -> t.StrSequence:
        """Rewrite each profile's runtime and codegen requirement lists.

        Returns:
            One change description per rewritten requirement constraint.

        Raises:
            TypeError: If dependency profile must be a mapping in; or if ``not
                isinstance(reqs, list)``; or if ``not isinstance(req, str)``.

        """
        profiles, validated = sections
        changes: t.MutableSequenceOf[str] = []
        for profile, contract in zip(
            profiles,
            validated,
            strict=True,
        ):
            if not isinstance(profile, dict):
                message = f"dependency profile must be a mapping in {ssot_path}"
                raise TypeError(message)
            upstream = contract.upstream
            runtime_reqs = profile.get("runtime")
            codegen_reqs = profile.get("codegen", [])
            for key_name, reqs in (
                ("runtime", runtime_reqs),
                ("codegen", codegen_reqs),
            ):
                if not isinstance(reqs, list):
                    message = f"{upstream}.{key_name} must be a list in {ssot_path}"
                    raise TypeError(message)
                for idx, req in enumerate(reqs):
                    if not isinstance(req, str):
                        message = (
                            f"{upstream}.{key_name} requires strings in {ssot_path}"
                        )
                        raise TypeError(message)
                    rewritten = u.Infra.rewrite_requirement_constraint(
                        req,
                        resolved_versions=resolved_versions,
                        internal_names=internal_names,
                    )
                    if rewritten is not None and rewritten != req:
                        # Update in place preserves surrounding comments/keys
                        reqs[idx] = rewritten
                        changes.append(
                            f"profile({upstream}).{key_name}: {req} -> {rewritten}",
                        )
        return tuple(changes)


__all__: list[str] = ["FlextInfraDepsFloorProfileWriter"]
