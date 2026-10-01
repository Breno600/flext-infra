"""Fixed-effect plan collection through the shared generation transaction."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m, u
from flext_infra.codegen.codegen_transaction import FlextInfraCodegenTransaction
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraDocCollector:
    """Publish only fully supported source associations under explicit leases."""

    @staticmethod
    def collect(request: m.Infra.DocsCollectRequest) -> p.Result[bool]:
        """Authenticate configuration, collect sources, and commit one file phase."""
        root = request.repository_root
        if not root.is_absolute() or ".." in root.parts or root.resolve() != root:
            return r[bool].fail(
                f"plan collection repository root is not a physical absolute path: {root}"
            )
        configuration_path = request.configuration
        if not configuration_path.is_absolute():
            configuration_path = root / configuration_path
        captured = u.Cli.atomic_read_binary_file_state(
            configuration_path, required=True
        )
        if captured.failure:
            return r[bool].from_failure(captured)
        snapshot = captured.value
        if snapshot.content is None:
            return r[bool].fail(
                f"plan collection configuration is absent: {configuration_path}"
            )
        parsed = u.Cli.yaml_parse(snapshot.content.decode("utf-8"))
        if parsed.failure:
            return r[bool].from_failure(parsed)
        validated: p.Result[m.Infra.PlanCollectionConfig] = u.validate_value(
            m.Infra.PlanCollectionConfig, parsed.value, strict=False
        )
        if validated.failure:
            return r[bool].from_failure(validated)
        configuration = validated.value
        roots = {"@canonical": root}
        if configuration.projection_root is not None:
            roots["@projection"] = configuration.projection_root.expanduser()
        transaction = FlextInfraCodegenTransaction(
            FlextInfraCodegenMiseArtifacts(repository_root=root)
        )

        def publish(scope_root: Path) -> p.Result[bool]:
            current = u.Cli.atomic_read_binary_file_state(
                configuration_path, required=True
            )
            if current.failure:
                return r[bool].from_failure(current)
            if current.value != snapshot:
                return r[bool].fail(
                    "plan collection configuration changed before collection"
                )
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
                    f"plan source extraction is incomplete; private inventories are not extracted plans: {pending}"
                )
            u.Infra.verify_plan_collection_sources(scope_root, configuration, bundle)
            inputs = (snapshot, *bundle.source_states)
            analysis = m.Infra.CodegenPhaseAnalysis(
                phase="docs", files=bundle.files, inputs=inputs
            )

            def validate() -> p.Result[bool]:
                final_configuration = u.Cli.atomic_read_binary_file_state(
                    configuration_path, required=True
                )
                if final_configuration.failure:
                    return r[bool].from_failure(final_configuration)
                if final_configuration.value != snapshot:
                    return r[bool].fail(
                        "plan collection configuration changed during publication"
                    )
                u.Infra.verify_plan_collection_publication(
                    scope_root, configuration, bundle
                )
                return r[bool].ok(True)

            published = transaction.publish_file_phase_locked(
                scope_root,
                roots,
                analysis,
                tuple(
                    path
                    for path in bundle.required_directories
                    if path not in roots.values()
                ),
                validate,
            )
            if published.failure:
                return r[bool].from_failure(published)
            for directory in bundle.prunable_directories:
                observed = u.Cli.atomic_read_empty_directory_state(
                    directory, required=False
                )
                if observed.failure:
                    return r[bool].from_failure(observed)
                if not observed.value.exists:
                    continue
                removed = u.Cli.atomic_delete_empty_directory_guarded(observed.value)
                if removed.failure:
                    return r[bool].from_failure(removed)
            return r[bool].ok(True)

        return transaction.run_files_locked(roots, publish)


__all__: list[str] = ["FlextInfraDocCollector"]
