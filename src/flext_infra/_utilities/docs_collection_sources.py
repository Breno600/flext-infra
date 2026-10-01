"""Authenticated provider file discovery for plan collection."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from flext_cli import u as cli_u

from flext_infra import m, t


class FlextInfraUtilitiesDocsCollectionSources:
    """Read explicitly associated sources without exporting private sessions."""

    @staticmethod
    def collection_source_root(
        root: Path, source: m.Infra.PlanCollectionSource
    ) -> Path:
        """Resolve a declared source without allowing lexical parent traversal."""
        selected = source.root.expanduser()
        if ".." in selected.parts:
            msg = f"collection source escapes its association: {selected}"
            raise ValueError(msg)
        return selected if selected.is_absolute() else root / selected

    @classmethod
    def collection_source_files(
        cls,
        root: Path,
        source: m.Infra.PlanCollectionSource,
        excluded_outputs: t.VariadicTuple[Path] = (),
    ) -> t.VariadicTuple[Path]:
        """Inventory physical regular files, rejecting inaccessible sources."""
        selected = cls.collection_source_root(root, source)
        chain = cli_u.Cli.atomic_plan_directory_chain(selected).unwrap()
        if chain.directories:
            raise FileNotFoundError(selected)
        for pattern in (*source.plan_globs, *source.exclude_globs):
            if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                msg = f"unsafe collection pattern: {pattern}"
                raise ValueError(msg)
        inventory = cli_u.Cli.atomic_inventory_physical_tree(selected).unwrap()
        for entry in inventory.entries:
            if entry.kind == "symlink" and any(
                entry.path.relative_to(selected).full_match(pattern)
                for pattern in source.plan_globs
            ):
                msg = f"selected plan source is a symlink: {entry.path}"
                raise ValueError(msg)
        candidates = tuple(
            sorted(
                entry.path
                for entry in inventory.entries
                if entry.kind == "file"
                and entry.path not in excluded_outputs
                and any(
                    entry.path.relative_to(selected).full_match(pattern)
                    for pattern in source.plan_globs
                )
                and not any(
                    entry.path.relative_to(selected).full_match(pattern)
                    for pattern in source.exclude_globs
                )
            )
        )
        if not source.companion_directory or source.adapter != "files":
            return candidates
        return tuple(
            path
            for path in candidates
            if not any(
                path != parent and path.is_relative_to(parent.with_suffix(""))
                for parent in candidates
            )
        )

    @staticmethod
    def collection_read(path: Path) -> m.Cli.AtomicFileState:
        """Capture one required regular source through the shared CAS owner."""
        state = cli_u.Cli.atomic_read_binary_file_state(path, required=True).unwrap()
        if state.content is None:
            msg = f"collection source disappeared: {path}"
            raise ValueError(msg)
        return state

    @staticmethod
    def collection_capture(
        path: Path, states: t.MutableMappingKV[Path, m.Cli.AtomicFileState]
    ) -> m.Cli.AtomicFileState:
        """Bind every influential read, including absence, to its first state."""
        state = cli_u.Cli.atomic_read_binary_file_state(path, required=False).unwrap()
        previous = states.get(path)
        if previous is not None and previous != state:
            msg = f"collection input changed between reads: {path}"
            raise ValueError(msg)
        states[path] = state
        return state

    @classmethod
    def collection_artifacts(
        cls,
        path: Path,
        source: m.Infra.PlanCollectionSource,
        excluded_outputs: t.VariadicTuple[Path] = (),
    ) -> t.VariadicTuple[m.Cli.AtomicFileState]:
        """Read the plan and its same-basename companion directory."""
        states = [cls.collection_read(path)]
        if source.companion_directory:
            companion = path.with_suffix("")
            chain = cli_u.Cli.atomic_plan_directory_chain(companion).unwrap()
            if not chain.directories:
                inventory = cli_u.Cli.atomic_inventory_physical_tree(companion).unwrap()
                for entry in inventory.entries:
                    if entry.kind == "symlink":
                        msg = f"plan companion is a symlink: {entry.path}"
                        raise ValueError(msg)
                states.extend(
                    cls.collection_read(entry.path)
                    for entry in sorted(inventory.entries, key=lambda item: item.path)
                    if entry.kind == "file" and entry.path not in excluded_outputs
                )
        return tuple(states)

    @staticmethod
    def collection_source_updated(
        content: bytes, fields: t.VariadicTuple[str]
    ) -> t.Pair[str | None, str | None]:
        """Retain explicit source precision; never promote filesystem time."""
        lines = content.decode("utf-8-sig", errors="strict").splitlines()
        if not lines or lines[0] != "---":
            return None, None
        closing = next(
            (index for index, line in enumerate(lines[1:], 1) if line == "---"), None
        )
        if closing is None:
            msg = "plan frontmatter has no closing delimiter"
            raise ValueError(msg)
        metadata = "\n".join(lines[1:closing])
        parsed = cli_u.Cli.yaml_roundtrip_load_map_text(metadata).unwrap()
        selected = next((field for field in fields if field in parsed), None)
        updated = m.Infra.PlanCollectionTimestamp.model_validate(
            {"value": parsed.get(selected) if selected is not None else None},
            strict=True,
        ).value
        if updated is None:
            return None, None
        original = updated if isinstance(updated, str) else updated.isoformat()
        if isinstance(updated, str):
            timestamp = datetime.fromisoformat(updated)
            if timestamp.date().isoformat() == updated:
                return original, None
        elif isinstance(updated, datetime):
            timestamp = updated
        else:
            return original, None
        if timestamp.tzinfo is None:
            return original, None
        return original, timestamp.astimezone(UTC).isoformat().replace("+00:00", "Z")

    @classmethod
    def collection_manifest(
        cls,
        canonical: Path,
        projection: Path | None,
        states: t.MutableMappingKV[Path, m.Cli.AtomicFileState],
    ) -> t.Pair[m.Infra.PlanCollectionManifest, t.VariadicTuple[Path]]:
        """Exclude only outputs attested by the canonical generated manifest."""
        manifest_path = canonical / "collection-manifest.json"
        before = cls.collection_capture(manifest_path, states)
        if before.content is None:
            return m.Infra.PlanCollectionManifest(), ()
        manifest = m.Infra.PlanCollectionManifest.model_validate_json(before.content)
        excluded: list[Path] = [manifest_path]
        roots = (canonical,) if projection is None else (canonical, projection)
        for revision in manifest.revisions:
            for locator in (revision.canonical_path, revision.source_path):
                if locator.is_absolute() or not locator.parts or ".." in locator.parts:
                    msg = f"collection receipt has unsafe relative locator: {locator}"
                    raise ValueError(msg)
        plans = {canonical / revision.canonical_path for revision in manifest.revisions}
        affected: set[Path] = set()
        for artifact in manifest.artifacts:
            path = artifact.relative_path
            if path.is_absolute() or not path.parts or ".." in path.parts:
                msg = f"collection manifest has unsafe owned path: {path}"
                raise ValueError(msg)
            for root in roots:
                candidate = root / path
                state = cls.collection_capture(candidate, states)
                if (
                    state.content is not None
                    and sha256(state.content).hexdigest() == artifact.digest
                ):
                    excluded.append(candidate)
                elif candidate not in plans and root == canonical:
                    continue
                elif root == projection and state.content is not None:
                    projected_plans = {
                        root / plan.relative_to(canonical) for plan in plans
                    }
                    owners = tuple(
                        plan
                        for plan in projected_plans
                        if candidate.is_relative_to(plan.with_suffix(""))
                    )
                    if candidate not in projected_plans and not owners:
                        msg = f"projected collection metadata was modified: {candidate}"
                        raise ValueError(msg)
                    for plan in plans:
                        projected_plan = root / plan.relative_to(canonical)
                        if candidate.is_relative_to(projected_plan.with_suffix("")):
                            affected.add(projected_plan)
                elif root == projection and state.content is None:
                    msg = f"owned projection artifact disappeared: {candidate}"
                    raise ValueError(msg)
        if projection is not None:
            projected_manifest = projection / manifest_path.name
            projected = cls.collection_capture(projected_manifest, states)
            if projected.content is not None:
                if projected.content != before.content:
                    msg = f"projected collection manifest was modified: {projected_manifest}"
                    raise ValueError(msg)
                excluded.append(projected_manifest)
        return manifest, tuple(path for path in excluded if path not in affected)


__all__: list[str] = ["FlextInfraUtilitiesDocsCollectionSources"]
