"""Deterministic plan collection through existing documentation file plans.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from flext_infra import m, t
from flext_infra._utilities.docs_collection_verify import (
    FlextInfraUtilitiesDocsCollectionVerify,
)
from flext_infra._utilities.docs_contract import FlextInfraUtilitiesDocsContract


class FlextInfraUtilitiesDocsCollection(FlextInfraUtilitiesDocsCollectionVerify):
    """Plan effects only; the docs transaction owns publication and locking."""

    @classmethod
    def docs_collect_plan_files(
        cls,
        repository_root: Path,
        configuration: m.Infra.PlanCollectionConfig,
    ) -> m.Infra.PlanCollectionBundle:
        """Capture sources before any canonical or home projection writes.

        Returns:
            The resulting ``m.Infra.PlanCollectionBundle``.

        Raises:
            ValueError: If unsafe canonical collection directory; or if unsafe
                collection projection association; or if collection source identities
                must be unique; or if file source requires publication approval; or if
                immutable canonical artifact changed or disappeared; or if undeclared
                collection destination; or if collection target changed after source
                read; or if private source cannot publish; or if collection source
                changed during read.

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
        identifiers = tuple(source.id for source in configuration.sources)
        if len(set(identifiers)) != len(identifiers):
            msg = "collection source identities must be unique"
            raise ValueError(msg)
        states: t.MutableMappingKV[Path, m.Cli.AtomicFileState] = {}
        manifest, excluded_outputs = cls.collection_manifest(
            canonical,
            projection,
            states,
        )
        if not configuration.enabled:
            owned_outputs = {
                canonical / "collection-manifest.json",
                *(
                    canonical / artifact.relative_path
                    for artifact in manifest.artifacts
                ),
            }
            for path in owned_outputs:
                cls.collection_capture(path, states)
            plans_list = [
                FlextInfraUtilitiesDocsContract.docs_file_plan(
                    root,
                    path,
                    None,
                    desired_mode=None,
                    source_states=tuple(states[item] for item in sorted(states)),
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
                source_states=tuple(states[path] for path in sorted(states)),
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
        history = list(manifest.revisions)
        observed = {(item.identity, item.digest) for item in history}
        revisions_by_identity = {item.identity: item for item in manifest.revisions}
        coverage: list[m.Infra.PlanCollectionCoverage] = []
        inventories: list[m.Infra.PlanCollectionSourceInventory] = []
        desired: t.MutableMappingKV[Path, bytes] = {}
        canonical_plans = {
            canonical / revision.canonical_path for revision in manifest.revisions
        }
        invalid_owned: MutableMapping[Path, str] = {}
        for artifact in manifest.artifacts:
            path = canonical / artifact.relative_path
            content = states[path].content
            if content is None:
                invalid_owned[path] = artifact.digest
                continue
            if (
                path not in canonical_plans
                and sha256(content).hexdigest() != artifact.digest
            ):
                invalid_owned[path] = artifact.digest
                continue
            desired[path] = content
        for source in configuration.sources:
            paths = cls.collection_source_files(root, source, excluded_outputs)
            source_paths = set(paths)
            if source.adapter == "private-inventory":
                if source.publication != "private":
                    msg = f"private source cannot publish: {source.id}"
                    raise ValueError(msg)
                coverage.append(
                    m.Infra.PlanCollectionCoverage(
                        source_id=source.id,
                        provider=source.provider,
                        adapter=source.adapter,
                        files=len(paths),
                        status="private-inventory" if paths else "empty",
                        private_paths=paths,
                    ),
                )
                inventories.append(
                    m.Infra.PlanCollectionSourceInventory(
                        source_id=source.id,
                        paths=paths,
                    ),
                )
                continue
            if source.publication != "plan-artifacts":
                msg = f"file source requires publication approval: {source.id}"
                raise ValueError(msg)
            source_root = cls.collection_source_root(root, source)
            for path in paths:
                artifacts = cls.collection_artifacts(path, source, excluded_outputs)
                source_paths.update(state.path for state in artifacts)
                for state in artifacts:
                    previous = states.get(state.path)
                    if previous is not None and previous != state:
                        msg = f"collection source changed during read: {state.path}"
                        raise ValueError(msg)
                    states[state.path] = state
                incoming_revision = cls._docs_incoming_revision(
                    canonical,
                    source_root,
                    source,
                    artifacts,
                    previous=next(
                        (
                            item
                            for item in manifest.revisions
                            if canonical / item.canonical_path == path
                            or (
                                projection is not None
                                and path.is_relative_to(projection)
                                and item.canonical_path == path.relative_to(projection)
                            )
                        ),
                        None,
                    ),
                )
                revision = cls._docs_collect_revision(
                    canonical,
                    incoming_revision,
                    artifacts,
                    desired,
                    states=states,
                )
                key = (revision.identity, revision.digest)
                if key not in observed:
                    history.append(revision)
                    observed.add(key)
                    revisions_by_identity[revision.identity] = revision
            inventories.append(
                m.Infra.PlanCollectionSourceInventory(
                    source_id=source.id,
                    paths=tuple(sorted(source_paths)),
                ),
            )
            coverage.append(
                m.Infra.PlanCollectionCoverage(
                    source_id=source.id,
                    provider=source.provider,
                    adapter=source.adapter,
                    files=len(paths),
                    status="collected" if paths else "empty",
                ),
            )
        revisions = sorted(
            revisions_by_identity.values(),
            key=lambda item: (
                item.source_updated_at_utc is not None,
                item.source_updated_at_utc or "",
                item.identity,
            ),
        )
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
        desired[canonical / "collection-index.md"] = index.encode()
        for path, digest in invalid_owned.items():
            content = desired.get(path)
            if content is None or sha256(content).hexdigest() != digest:
                msg = f"immutable canonical artifact changed or disappeared: {path}"
                raise ValueError(msg)
        manifest_path = canonical / "collection-manifest.json"
        owned = {item.relative_path: item for item in manifest.artifacts}
        owned.update({
            path.relative_to(canonical): m.Infra.PlanCollectionOwnedArtifact(
                relative_path=path.relative_to(canonical),
                digest=sha256(content).hexdigest(),
            )
            for path, content in desired.items()
        })
        desired[manifest_path] = (
            m.Infra.PlanCollectionManifest(
                revisions=tuple(history),
                artifacts=tuple(owned[path] for path in sorted(owned)),
            ).model_dump_json(indent=2)
            + "\n"
        ).encode()
        if projection is not None:
            for path, content in tuple(desired.items()):
                desired[projection / path.relative_to(canonical)] = content
        inputs = tuple(states[path] for path in sorted(states))
        plans: list[m.Infra.CodegenFilePlan] = []
        for path, content in sorted(desired.items()):
            owner = root if path.is_relative_to(canonical) else projection
            if owner is None:
                msg = f"undeclared collection destination: {path}"
                raise ValueError(msg)
            planned = FlextInfraUtilitiesDocsContract.docs_file_plan(
                owner,
                path,
                content,
                desired_mode=0o644,
                source_states=inputs,
            ).unwrap()
            expected = states.get(path)
            if expected is not None and planned.before != expected:
                msg = f"collection target changed after source read: {path}"
                raise ValueError(msg)
            plans.append(planned)
        required_directories = tuple(
            sorted(
                {path.parent for path in desired},
                key=lambda path: (len(path.parts), path.as_posix()),
            ),
        )
        return m.Infra.PlanCollectionBundle(
            files=tuple(plans),
            source_states=inputs,
            required_directories=required_directories,
            revisions=tuple(revisions),
            coverage=tuple(coverage),
            inventories=tuple(inventories),
            excluded_outputs=excluded_outputs,
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
