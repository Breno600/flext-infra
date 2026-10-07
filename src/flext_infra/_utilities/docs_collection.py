"""Deterministic plan collection through existing documentation file plans.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from flext_infra import c, m, t
from flext_infra._utilities import (
    FlextInfraUtilitiesDocsCollectionVerify,
    FlextInfraUtilitiesDocsContract,
)


class FlextInfraUtilitiesDocsCollection(FlextInfraUtilitiesDocsCollectionVerify):
    """Plan effects only; the docs transaction owns publication and locking."""

    class _CollectionState:
        """Mutable accumulators one collection pass fills."""

        def __init__(
            self,
            canonical: Path,
            projection: Path | None,
            manifest: m.Infra.PlanCollectionManifest,
        ) -> None:
            self.canonical = canonical
            self.projection = projection
            self.manifest = manifest
            self.states: t.MutableMappingKV[Path, m.Cli.AtomicFileState] = {}
            self.desired: t.MutableMappingKV[Path, bytes] = {}
            self.history = list(manifest.revisions)
            self.observed = {
                (item.identity, item.digest) for item in manifest.revisions
            }
            self.revisions_by_identity = {
                item.identity: item for item in manifest.revisions
            }
            self.coverage: list[m.Infra.PlanCollectionCoverage] = []
            self.inventories: list[m.Infra.PlanCollectionSourceInventory] = []
            self.invalid_owned: MutableMapping[Path, str] = {}

        def absorb_owned_artifacts(self) -> None:
            """Record desired canonical bytes and flag mutated owned artifacts."""
            canonical_plans = {
                self.canonical / revision.canonical_path
                for revision in self.manifest.revisions
            }
            for artifact in self.manifest.artifacts:
                path = self.canonical / artifact.relative_path
                content = self.states[path].content
                if content is None:
                    self.invalid_owned[path] = artifact.digest
                    continue
                if (
                    path not in canonical_plans
                    and sha256(content).hexdigest() != artifact.digest
                ):
                    self.invalid_owned[path] = artifact.digest
                    continue
                self.desired[path] = content

        def absorb_artifacts(
            self,
            artifacts: t.VariadicTuple[m.Cli.AtomicFileState],
        ) -> None:
            """Merge one path's collected states, rejecting concurrent change.

            Raises:
                ValueError: If collection source changed during read.

            """
            for state in artifacts:
                previous = self.states.get(state.path)
                if previous is not None and previous != state:
                    msg = f"collection source changed during read: {state.path}"
                    raise ValueError(msg)
                self.states[state.path] = state

        def previous_revision(
            self,
            path: Path,
        ) -> m.Infra.PlanCollectionRevision | None:
            """Return the recorded revision that owns one collected path.

            Returns:
                The resulting ``m.Infra.PlanCollectionRevision | None``.

            """
            projection = self.projection
            return next(
                (
                    item
                    for item in self.manifest.revisions
                    if self.canonical / item.canonical_path == path
                    or (
                        projection is not None
                        and path.is_relative_to(projection)
                        and item.canonical_path == path.relative_to(projection)
                    )
                ),
                None,
            )

        def record_revision(self, revision: m.Infra.PlanCollectionRevision) -> None:
            """Append one new revision identity to the history."""
            key = (revision.identity, revision.digest)
            if key not in self.observed:
                self.history.append(revision)
                self.observed.add(key)
                self.revisions_by_identity[revision.identity] = revision

        def record_private(
            self,
            source: m.Infra.PlanCollectionSource,
            paths: t.VariadicTuple[Path],
        ) -> None:
            """Record a private-inventory source's coverage and inventory."""
            self.coverage.append(
                m.Infra.PlanCollectionCoverage(
                    source_id=source.id,
                    provider=source.provider,
                    adapter=source.adapter,
                    files=len(paths),
                    status="private-inventory" if paths else "empty",
                    private_paths=paths,
                ),
            )
            self.inventories.append(
                m.Infra.PlanCollectionSourceInventory(
                    source_id=source.id,
                    paths=paths,
                ),
            )

        @staticmethod
        def require_publishable(source: m.Infra.PlanCollectionSource) -> None:
            """Require a plan-artifacts publication approval.

            Raises:
                ValueError: If file source requires publication approval.

            """
            if source.publication != "plan-artifacts":
                msg = f"file source requires publication approval: {source.id}"
                raise ValueError(msg)

        def record_public(
            self,
            source: m.Infra.PlanCollectionSource,
            paths: t.VariadicTuple[Path],
            source_paths: t.IterableOf[Path],
        ) -> None:
            """Record a published source's coverage and inventory."""
            self.inventories.append(
                m.Infra.PlanCollectionSourceInventory(
                    source_id=source.id,
                    paths=tuple(sorted(source_paths)),
                ),
            )
            self.coverage.append(
                m.Infra.PlanCollectionCoverage(
                    source_id=source.id,
                    provider=source.provider,
                    adapter=source.adapter,
                    files=len(paths),
                    status="collected" if paths else "empty",
                ),
            )

        def sorted_revisions(self) -> list[m.Infra.PlanCollectionRevision]:
            """Return the history sorted by source time, then identity.

            Returns:
                The resulting ``list[m.Infra.PlanCollectionRevision]``.

            """
            return sorted(
                self.revisions_by_identity.values(),
                key=lambda item: (
                    item.source_updated_at_utc is not None,
                    item.source_updated_at_utc or "",
                    item.identity,
                ),
            )

        def verify_immutable_owned(self) -> None:
            """Require flagged immutable artifacts to remain byte-identical.

            Raises:
                ValueError: If immutable canonical artifact changed or
                    disappeared.

            """
            for path, digest in self.invalid_owned.items():
                content = self.desired.get(path)
                if content is None or sha256(content).hexdigest() != digest:
                    msg = f"immutable canonical artifact changed or disappeared: {path}"
                    raise ValueError(msg)

        def record_manifest(self) -> None:
            """Serialize the updated manifest into the desired outputs."""
            manifest_path = self.canonical / "collection-manifest.json"
            owned = {item.relative_path: item for item in self.manifest.artifacts}
            owned.update({
                path.relative_to(self.canonical): m.Infra.PlanCollectionOwnedArtifact(
                    relative_path=path.relative_to(self.canonical),
                    digest=sha256(content).hexdigest(),
                )
                for path, content in self.desired.items()
            })
            self.desired[manifest_path] = (
                m.Infra.PlanCollectionManifest(
                    revisions=tuple(self.history),
                    artifacts=tuple(owned[path] for path in sorted(owned)),
                ).model_dump_json(indent=2)
                + "\n"
            ).encode()

        def mirror_projection(self) -> None:
            """Mirror every desired canonical output into the projection root."""
            projection = self.projection
            if projection is not None:
                for path, content in tuple(self.desired.items()):
                    self.desired[projection / path.relative_to(self.canonical)] = (
                        content
                    )

    @classmethod
    def _validated_collection_roots(
        cls,
        repository_root: Path,
        configuration: m.Infra.PlanCollectionConfig,
    ) -> t.Triple[Path, Path, Path | None]:
        """Validate and resolve the collection canonical and projection roots.

        Returns:
            The resulting ``(root, canonical, projection)`` triple.

        Raises:
            ValueError: If unsafe canonical collection directory; or if unsafe
                collection projection association.

        """
        root = repository_root.absolute()
        relative = configuration.canonical_dir
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            msg = f"unsafe canonical collection directory: {relative}"
            raise ValueError(msg)
        canonical = root / relative
        projection = (
            configuration.projection_root.expanduser()
            if configuration.projection_root is not None
            else None
        )
        if projection is not None and (
            not projection.is_absolute()
            or ".." in projection.parts
            or projection == canonical
        ):
            msg = f"unsafe collection projection association: {projection}"
            raise ValueError(msg)
        return root, canonical, projection

    @staticmethod
    def _require_unique_sources(
        configuration: m.Infra.PlanCollectionConfig,
    ) -> None:
        """Require every collection source identity to be unique.

        Raises:
            ValueError: If collection source identities must be unique.

        """
        identifiers = tuple(source.id for source in configuration.sources)
        if len(set(identifiers)) != len(identifiers):
            msg = "collection source identities must be unique"
            raise ValueError(msg)

    @classmethod
    def _disabled_collection_bundle(
        cls,
        root: Path,
        state: _CollectionState,
    ) -> m.Infra.PlanCollectionBundle:
        """Plan removal-only effects when collection is disabled.

        Returns:
            The resulting ``m.Infra.PlanCollectionBundle``.

        """
        canonical = state.canonical
        owned_outputs = {
            canonical / "collection-manifest.json",
            *(
                canonical / artifact.relative_path
                for artifact in state.manifest.artifacts
            ),
        }
        for path in owned_outputs:
            cls.collection_capture(path, state.states)
        plans_list = [
            FlextInfraUtilitiesDocsContract.docs_file_plan(
                root,
                path,
                None,
                desired_mode=None,
                source_states=tuple(
                    state.states[item] for item in sorted(state.states)
                ),
            ).unwrap()
            for path in sorted(owned_outputs)
        ]
        directories = {
            parent
            for path in owned_outputs
            for parent in path.parents
            if parent != canonical and parent.is_relative_to(canonical)
        }
        return m.Infra.PlanCollectionBundle(
            files=tuple(plans_list),
            source_states=tuple(state.states[path] for path in sorted(state.states)),
            required_directories=(),
            prunable_directories=tuple(
                sorted(
                    directories,
                    key=lambda path: (len(path.parts), path.as_posix()),
                    reverse=True,
                ),
            ),
            revisions=(),
            coverage=(),
            inventories=(),
            excluded_outputs=tuple(sorted(owned_outputs)),
        )

    @classmethod
    def _collect_source_paths(
        cls,
        source_root: Path,
        source: m.Infra.PlanCollectionSource,
        paths: t.VariadicTuple[Path],
        state: _CollectionState,
        excluded_outputs: t.VariadicTuple[Path],
    ) -> set[Path]:
        """Collect every published artifact of one source path set.

        Returns:
            The resulting ``set[Path]``.

        """
        source_paths: set[Path] = set(paths)
        for path in paths:
            artifacts = cls.collection_artifacts(path, source, excluded_outputs)
            source_paths.update(item.path for item in artifacts)
            state.absorb_artifacts(artifacts)
            incoming_revision = cls._docs_incoming_revision(
                state.canonical,
                source_root,
                source,
                artifacts,
                previous=state.previous_revision(path),
            )
            revision = cls._docs_collect_revision(
                state.canonical,
                incoming_revision,
                artifacts,
                state.desired,
                states=state.states,
            )
            state.record_revision(revision)
        return source_paths

    @classmethod
    def _collect_all_sources(
        cls,
        root: Path,
        configuration: m.Infra.PlanCollectionConfig,
        state: _CollectionState,
        excluded_outputs: t.VariadicTuple[Path],
    ) -> None:
        """Run every configured source through its collection adapter.

        Raises:
            ValueError: If private source cannot publish; or if file source
                requires publication approval.

        """
        for source in configuration.sources:
            paths = cls.collection_source_files(root, source, excluded_outputs)
            if source.adapter == "private-inventory":
                if source.publication != "private":
                    msg = f"private source cannot publish: {source.id}"
                    raise ValueError(msg)
                state.record_private(source, paths)
                continue
            state.require_publishable(source)
            source_root = cls.collection_source_root(root, source)
            source_paths = cls._collect_source_paths(
                source_root,
                source,
                paths,
                state,
                excluded_outputs,
            )
            state.record_public(source, paths, source_paths)

    @staticmethod
    def _collection_index_text(
        revisions: t.SequenceOf[m.Infra.PlanCollectionRevision],
    ) -> str:
        """Render the collected-plan index markdown.

        Returns:
            The resulting ``str``.

        """
        lines = [
            "# Collected plans",
            "",
            "Source order only; execution status and closure belong to Beads.",
            "",
        ]
        lines.extend(
            f"- [{revision.identity}]({revision.canonical_path.name})"
            f" — {revision.source_updated_at or 'source update unknown'}"
            + (
                " (chronology unresolved: no timezone-aware instant)"
                if revision.source_updated_at_utc is None
                else ""
            )
            for revision in revisions
        )
        index, _changed = FlextInfraUtilitiesDocsContract.docs_contract_update_toc(
            "\n".join(lines) + "\n",
        )
        return index

    @classmethod
    def _planned_collection_bundle(
        cls,
        root: Path,
        state: _CollectionState,
        excluded_outputs: t.VariadicTuple[Path],
        revisions: t.SequenceOf[m.Infra.PlanCollectionRevision],
    ) -> m.Infra.PlanCollectionBundle:
        """Plan every desired output and assemble the collection bundle.

        Returns:
            The resulting ``m.Infra.PlanCollectionBundle``.

        Raises:
            ValueError: If undeclared collection destination; or if collection
                target changed after source read.

        """
        canonical = state.canonical
        projection = state.projection
        state.record_manifest()
        state.mirror_projection()
        inputs = tuple(state.states[path] for path in sorted(state.states))
        plans: list[m.Infra.CodegenFilePlan] = []
        for path, content in sorted(state.desired.items()):
            owner = root if path.is_relative_to(canonical) else projection
            if owner is None:
                msg = f"undeclared collection destination: {path}"
                raise ValueError(msg)
            planned = FlextInfraUtilitiesDocsContract.docs_file_plan(
                owner,
                path,
                content,
                desired_mode=c.Infra.DOCS_ARTIFACT_MODE,
                source_states=inputs,
            ).unwrap()
            expected = state.states.get(path)
            if expected is not None and planned.before != expected:
                msg = f"collection target changed after source read: {path}"
                raise ValueError(msg)
            plans.append(planned)
        required_directories = tuple(
            sorted(
                {path.parent for path in state.desired},
                key=lambda path: (len(path.parts), path.as_posix()),
            ),
        )
        return m.Infra.PlanCollectionBundle(
            files=tuple(plans),
            source_states=inputs,
            required_directories=required_directories,
            revisions=tuple(revisions),
            coverage=tuple(state.coverage),
            inventories=tuple(state.inventories),
            excluded_outputs=excluded_outputs,
        )

    @classmethod
    def docs_collect_plan_files(
        cls,
        repository_root: Path,
        configuration: m.Infra.PlanCollectionConfig,
    ) -> m.Infra.PlanCollectionBundle:
        """Capture sources before any canonical or home projection writes.

        Returns:
            The resulting ``m.Infra.PlanCollectionBundle``.

        """
        root, canonical, projection = cls._validated_collection_roots(
            repository_root,
            configuration,
        )
        cls._require_unique_sources(configuration)
        states: t.MutableMappingKV[Path, m.Cli.AtomicFileState] = {}
        manifest, excluded_outputs = cls.collection_manifest(
            canonical,
            projection,
            states,
        )
        state = cls._CollectionState(canonical, projection, manifest)
        state.states = states
        if not configuration.enabled:
            return cls._disabled_collection_bundle(root, state)
        state.absorb_owned_artifacts()
        cls._collect_all_sources(root, configuration, state, excluded_outputs)
        revisions = state.sorted_revisions()
        index_text = cls._collection_index_text(revisions)
        state.desired[canonical / "collection-index.md"] = index_text.encode()
        state.verify_immutable_owned()
        return cls._planned_collection_bundle(
            root,
            state,
            excluded_outputs,
            revisions,
        )

    @classmethod
    def _docs_incoming_revision(
        cls,
        canonical: Path,
        source_root: Path,
        source: m.Infra.PlanCollectionSource,
        artifacts: t.VariadicTuple[m.Cli.AtomicFileState],
        *,
        previous: m.Infra.PlanCollectionRevision | None,
    ) -> m.Infra.PlanCollectionRevision:
        """Derive the revision one collected plan and its companions represent.

        ``artifacts`` starts with the plan itself, followed by its companion
        attachments; a previously recorded revision keeps its identity and its
        canonical destination, which must stay inside ``canonical``.

        Returns:
            The resulting ``m.Infra.PlanCollectionRevision``.

        Raises:
            ValueError: If plan content absent; or if absent collected artifact.

        """
        path = artifacts[0].path
        identity = (
            previous.identity
            if previous is not None
            else sha256(
                f"{source.id}:{path.relative_to(source_root).as_posix()}".encode(),
            ).hexdigest()
        )
        digest = sha256()
        for artifact in artifacts:
            if artifact.content is None:
                msg = f"absent collected artifact: {artifact.path}"
                raise ValueError(msg)
            name = artifact.path.relative_to(path.parent).as_posix().encode()
            digest.update(len(name).to_bytes(8, "big"))
            digest.update(name)
            digest.update(len(artifact.content).to_bytes(8, "big"))
            digest.update(artifact.content)
        plan = artifacts[0].content
        if plan is None:
            msg = f"plan content absent: {path}"
            raise ValueError(msg)
        original, normalized = cls.collection_source_updated(
            plan,
            source.updated_fields,
        )
        target = canonical / (
            previous.canonical_path
            if previous is not None
            else Path(f"{source.id}-{path.stem}-{identity[:16]}.md")
        )
        return m.Infra.PlanCollectionRevision(
            identity=identity,
            provider=source.provider,
            source_id=source.id,
            source_path=path.relative_to(source_root),
            driver=source.driver,
            driver_version=source.driver_version,
            digest=digest.hexdigest(),
            canonical_path=target.relative_to(canonical),
            source_updated_at=normalized or original,
            source_updated_at_original=original,
            source_updated_at_utc=normalized,
            collected_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            attachments=tuple(
                attachment.path.relative_to(path.with_suffix("")).as_posix()
                for attachment in artifacts[1:]
            ),
        )

    @classmethod
    def _docs_collect_revision(
        cls,
        canonical: Path,
        incoming_revision: m.Infra.PlanCollectionRevision,
        artifacts: t.VariadicTuple[m.Cli.AtomicFileState],
        desired: t.MutableMappingKV[Path, bytes],
        *,
        states: t.MutableMappingKV[Path, m.Cli.AtomicFileState],
    ) -> m.Infra.PlanCollectionRevision:
        """Keep curated canonical text intact while recording incoming revisions.

        Returns:
            The resulting ``m.Infra.PlanCollectionRevision``.

        Raises:
            ValueError: If plan content absent; or if attachment content absent; or if
                incoming revision receipt identity changed.

        """
        target = canonical / incoming_revision.canonical_path
        incoming = target.with_suffix("") / "incoming" / incoming_revision.digest
        plan = artifacts[0].content
        if plan is None:
            msg = f"plan content absent: {artifacts[0].path}"
            raise ValueError(msg)
        existing = cls.collection_capture(target, states)
        desired[target] = existing.content if existing.content is not None else plan
        desired[incoming / "plan.md"] = plan
        for name, attachment in zip(
            incoming_revision.attachments,
            artifacts[1:],
            strict=True,
        ):
            if attachment.content is None:
                msg = f"attachment content absent: {artifacts[0].path}"
                raise ValueError(msg)
            desired[incoming / "attachments" / name] = attachment.content
        revision = incoming_revision
        receipt_path = incoming / "provenance.json"
        receipt = cls.collection_capture(receipt_path, states)
        if receipt.content is not None:
            recorded = m.Infra.PlanCollectionRevision.model_validate_json(
                receipt.content,
            )
            if (recorded.identity, recorded.digest) != (
                revision.identity,
                revision.digest,
            ):
                msg = f"incoming revision receipt identity changed: {receipt_path}"
                raise ValueError(msg)
            revision = recorded
        desired[receipt_path] = (
            receipt.content
            if receipt.content is not None
            else (revision.model_dump_json(indent=2) + "\n").encode()
        )
        return revision


__all__: list[str] = ["FlextInfraUtilitiesDocsCollection"]
