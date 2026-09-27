"""Runtime-derived dependency floors written back to the codegen SSOT (flext-gzfd2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import t


class FlextInfraDepsFloorProfileWriter:
    """Rewrite dependency_profiles floors from the provisioned runtime."""

    @classmethod
    def rewrite_profiles_from_resolution(
        cls,
        *,
        root: Path,
        resolved_versions: t.MappingKV[str, str],
        internal_names: t.StrSequence,
    ) -> t.StrSequence:
        """Update dependency_profiles in ``<root>/config/codegen.yaml``.

        ``root`` is the modernizer's own declared ``--repository-root``: the
        governed SSOT belongs to the repository being modernized, never the
        installed/editable ``flext_infra`` package location (flext-eles2). A
        second caller's ``root`` never leaks into a different checkout's
        tracked config, including this generator's own tests.

        Returns a list of change descriptions for the deps report.
        """
        ssot_path = root / c.Infra.CODEGEN_CONFIG_DIR / c.Infra.CODEGEN_CONFIG_FILENAME

        # A standalone consumer (ai-hub, cosmos, product repos) carries no
        # codegen SSOT and therefore owns no dependency_profiles floors: the
        # rewrite has nothing to do there. A PRESENT but malformed SSOT keeps
        # failing loud below — only absence is skippable.
        if not ssot_path.is_file():
            u.Cli.info(
                "deps: no config/codegen.yaml SSOT — dependency_profiles floors "
                "not rewritten"
            )
            return ()

        # Round-trip load preserves comments and ordering
        loaded = u.Cli.yaml_roundtrip_load_map(ssot_path)
        if loaded.failure:
            raise ValueError(loaded.error or f"failed to load {ssot_path}")

        document = loaded.value

        # Navigate to Infra.codegen.scaffold.project.dependency_profiles
        infra = document.get("Infra")
        if not infra or not isinstance(infra, dict):
            u.Cli.error("Infra section missing in codegen.yaml")
            return ()
        codegen = infra.get("codegen")
        if not codegen or not isinstance(codegen, dict):
            u.Cli.error("Infra.codegen section missing in codegen.yaml")
            return ()
        scaffold = codegen.get("scaffold")
        if not scaffold or not isinstance(scaffold, dict):
            u.Cli.error("Infra.codegen.scaffold section missing in codegen.yaml")
            return ()
        project = scaffold.get("project")
        if not project or not isinstance(project, dict):
            u.Cli.error(
                "Infra.codegen.scaffold.project section missing in codegen.yaml"
            )
            return ()
        profiles = project.get("dependency_profiles")
        if not profiles or not isinstance(profiles, list):
            u.Cli.error("dependency_profiles missing or not a list in codegen.yaml")
            return ()

        changes: t.MutableSequenceOf[str] = []

        # Rewrite each profile's runtime and codegen requirement lists
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            upstream = str(profile.get("upstream", ""))
            runtime_reqs = profile.get("runtime")
            codegen_reqs = profile.get("codegen")
            for key_name, reqs in (
                ("runtime", runtime_reqs),
                ("codegen", codegen_reqs),
            ):
                if not isinstance(reqs, list):
                    continue
                for idx, req in enumerate(reqs):
                    if not isinstance(req, str):
                        continue
                    rewritten = u.Infra.rewrite_requirement_constraint(
                        req,
                        resolved_versions=resolved_versions,
                        internal_names=internal_names,
                    )
                    if rewritten is not None and rewritten != req:
                        # Update in place preserves surrounding comments/keys
                        reqs[idx] = rewritten
                        changes.append(
                            f"profile({upstream}).{key_name}: {req} -> {rewritten}"
                        )

        if not changes:
            return ()

        # Dump back with comments preserved
        dumped = u.Cli.yaml_roundtrip_dump_text(document)
        if dumped.failure:
            raise ValueError(dumped.error or "failed to dump codegen.yaml")

        # Atomic write
        write_result = u.Cli.atomic_write_text_file(ssot_path, dumped.value)
        if write_result.failure:
            raise ValueError(write_result.error or f"failed to write {ssot_path}")

        return tuple(changes)


__all__: list[str] = ["FlextInfraDepsFloorProfileWriter"]
