"""Fixed-effect plan collection through the shared generation transaction.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r, t, u
from flext_infra.codegen.codegen_transaction import FlextInfraCodegenTransaction
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraDocCollector:
    """Publish only fully supported source associations under explicit leases."""

    @classmethod
    def collect(cls, request: m.Infra.DocsCollectRequest) -> p.Result[bool]:
        """Authenticate configuration, collect sources, and commit one file phase.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        authenticated = cls._authenticated_configuration(request)
        if authenticated.failure:
            return r[bool].from_failure(authenticated)
        configuration_path, snapshot, configuration = authenticated.value
        roots = {"@canonical": request.repository_root}
        if configuration.projection_root is not None:
            roots["@projection"] = configuration.projection_root.expanduser()
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=request.repository_root),
        )

        def publish(scope_root: Path) -> p.Result[bool]:
            unchanged = cls._require_unchanged(
                configuration_path,
                snapshot,
                "plan collection configuration changed before collection",
            )
            if unchanged.failure:
                return r[bool].from_failure(unchanged)
            bundle = u.Infra.docs_collect_plan_files(scope_root, configuration)
            incomplete = tuple(
                item for item in bundle.coverage if item.adapter == "private-inventory"
            )
            if incomplete:
                pending = ", ".join(
                    f"{item.source_id}:{item.status}:{item.files}"
                    for item in incomplete
                )
                return r[bool].fail(
                    f"plan source extraction is incomplete; private "
                    f"inventories are not extracted plans: {pending}",
                )
            u.Infra.verify_plan_collection_sources(scope_root, configuration, bundle)
            inputs = (snapshot, *bundle.source_states)
            analysis = m.Infra.CodegenPhaseAnalysis(
                phase=c.Infra.CodegenStagedFilePhase.DOCS,
                files=bundle.files,
                inputs=inputs,
            )

            def validate() -> p.Result[bool]:
                unchanged = cls._require_unchanged(
                    configuration_path,
                    snapshot,
                    "plan collection configuration changed during publication",
                )
                if unchanged.failure:
                    return unchanged
                u.Infra.verify_plan_collection_publication(
                    scope_root,
                    configuration,
                    bundle,
                )
                return r[bool].ok(value=True)

            published = transaction.publish_file_phase_locked(
                scope_root,
                roots,
                analysis,
                m.Infra.CodegenPhasePublicationPolicy(
                    directories=tuple(
                        path
                        for path in bundle.required_directories
                        if path not in roots.values()
                    ),
                    validator=validate,
                ),
            )
            if published.failure:
                return r[bool].from_failure(published)
            pruned = cls._prune_bundle_directories(bundle)
            if pruned.failure:
                return r[bool].from_failure(pruned)
            return r[bool].ok(value=True)

        return transaction.run_files_locked(roots, publish)

    @staticmethod
    def _authenticated_configuration(
        request: m.Infra.DocsCollectRequest,
    ) -> p.Result[t.Triple[Path, m.Cli.AtomicFileState, m.Infra.PlanCollectionConfig]]:
        """Authenticate the physical root and parse the collection configuration.

        Returns:
            The resulting ``(configuration_path, snapshot, configuration)`` triple.

        """
        result_type = r[
            t.Triple[Path, m.Cli.AtomicFileState, m.Infra.PlanCollectionConfig]
        ]
        root = request.repository_root
        if not root.is_absolute() or ".." in root.parts or root.resolve() != root:
            return result_type.fail(
                f"plan collection repository root is not a physical "
                f"absolute path: {root}",
            )
        configuration_path = request.configuration
        if not configuration_path.is_absolute():
            configuration_path = root / configuration_path
        captured = u.Cli.atomic_read_binary_file_state(
            configuration_path,
            required=True,
        )
        if captured.failure:
            return result_type.from_failure(captured)
        snapshot = captured.value
        if snapshot.content is None:
            return result_type.fail(
                f"plan collection configuration is absent: {configuration_path}",
            )
        parsed = u.Cli.yaml_parse(snapshot.content.decode("utf-8"))
        if parsed.failure:
            return result_type.from_failure(parsed)
        validated: p.Result[m.Infra.PlanCollectionConfig] = u.validate_value(
            m.Infra.PlanCollectionConfig,
            parsed.value,
            strict=False,
        )
        if validated.failure:
            return result_type.from_failure(validated)
        return result_type.ok((configuration_path, snapshot, validated.value))

    @staticmethod
    def _require_unchanged(
        configuration_path: Path,
        snapshot: m.Cli.AtomicFileState,
        message: str,
    ) -> p.Result[bool]:
        """Require the authenticated configuration bytes to be unchanged.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        current = u.Cli.atomic_read_binary_file_state(
            configuration_path,
            required=True,
        )
        if current.failure:
            return r[bool].from_failure(current)
        if current.value != snapshot:
            return r[bool].fail(message)
        return r[bool].ok(value=True)

    @staticmethod
    def _prune_bundle_directories(
        bundle: m.Infra.PlanCollectionBundle,
    ) -> p.Result[bool]:
        """Delete the bundle's empty prunable directories.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for directory in bundle.prunable_directories:
            observed = u.Cli.atomic_read_empty_directory_state(
                directory,
                required=False,
            )
            if observed.failure:
                return r[bool].from_failure(observed)
            if not observed.value.exists:
                continue
            removed = u.Cli.atomic_delete_empty_directory_guarded(observed.value)
            if removed.failure:
                return r[bool].from_failure(removed)
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraDocCollector"]
