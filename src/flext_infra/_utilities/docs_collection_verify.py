"""Phase-specific verification of collection inputs and attested outputs."""

from __future__ import annotations

from pathlib import Path

from flext_cli import u as cli_u

from flext_infra import m, t

from .docs_collection_sources import FlextInfraUtilitiesDocsCollectionSources


class FlextInfraUtilitiesDocsCollectionVerify(FlextInfraUtilitiesDocsCollectionSources):
    """Differentiate source drift from the transaction's own declared effects."""

    @classmethod
    def _collection_topology(
        cls,
        root: Path,
        configuration: m.Infra.PlanCollectionConfig,
        exclusions: t.VariadicTuple[Path],
    ) -> t.VariadicTuple[m.Infra.PlanCollectionSourceInventory]:
        inventories: list[m.Infra.PlanCollectionSourceInventory] = []
        for source in configuration.sources:
            paths = cls.collection_source_files(root, source, exclusions)
            discovered = set(paths)
            if source.adapter == "files":
                for path in paths:
                    discovered.update(
                        state.path
                        for state in cls.collection_artifacts(path, source, exclusions)
                    )
            inventories.append(
                m.Infra.PlanCollectionSourceInventory(
                    source_id=source.id, paths=tuple(sorted(discovered))
                )
            )
        return tuple(inventories)

    @classmethod
    def verify_plan_collection_sources(
        cls,
        root: Path,
        configuration: m.Infra.PlanCollectionConfig,
        bundle: m.Infra.PlanCollectionBundle,
    ) -> None:
        """Require original inputs and discovery topology before effects."""
        if (
            cls._collection_topology(root, configuration, bundle.excluded_outputs)
            != bundle.inventories
        ):
            msg = "plan collection source topology changed during publication"
            raise ValueError(msg)
        for expected in bundle.source_states:
            current = cli_u.Cli.atomic_read_binary_file_state(
                expected.path, required=False
            ).unwrap()
            if current != expected:
                msg = f"plan collection source changed: {expected.path}"
                raise ValueError(msg)

    @classmethod
    def verify_plan_collection_publication(
        cls,
        root: Path,
        configuration: m.Infra.PlanCollectionConfig,
        bundle: m.Infra.PlanCollectionBundle,
    ) -> None:
        """Verify exact effects while preserving every unrelated source snapshot."""
        outputs = {plan.path: plan for plan in bundle.files}
        original_paths = {path for item in bundle.inventories for path in item.paths}
        exclusions = tuple(
            sorted(set(bundle.excluded_outputs) | (set(outputs) - original_paths))
        )
        if (
            cls._collection_topology(root, configuration, exclusions)
            != bundle.inventories
        ):
            msg = "plan collection source topology changed after publication"
            raise ValueError(msg)
        for plan in bundle.files:
            current = cli_u.Cli.atomic_read_binary_file_state(
                plan.path, required=False
            ).unwrap()
            if (current.content, current.mode) != (
                plan.desired_content,
                plan.desired_mode,
            ):
                msg = f"collection publication differs from its plan: {plan.path}"
                raise ValueError(msg)
        for expected in bundle.source_states:
            if expected.path in outputs:
                continue
            current = cli_u.Cli.atomic_read_binary_file_state(
                expected.path, required=False
            ).unwrap()
            if current != expected:
                msg = f"unmodified collection input changed: {expected.path}"
                raise ValueError(msg)


__all__: list[str] = ["FlextInfraUtilitiesDocsCollectionVerify"]
