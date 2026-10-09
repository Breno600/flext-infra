"""Guarded semantic phase for detection-only ``make mod`` findings.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from pathlib import Path

from flext_cli import cli

from flext_infra import c, config, m, p, r, t, u
from flext_infra.transformers import FlextInfraSemanticPublication


class FlextInfraCodemodSemanticApply:
    """Plan semantic cutovers, preflight the batch, then publish guarded files."""

    @classmethod
    def source_fingerprint(
        cls,
        root: Path,
        preflight: m.Infra.ModScanReport,
    ) -> t.VariadicTuple[t.Pair[str, str]]:
        """Identify the complete governed source state between mod phases.

        Returns:
            The resulting ``t.VariadicTuple[t.Pair[str, str]]``.

        """
        return tuple(
            (path.as_posix(), u.Cli.sha256_bytes(source.encode(c.Cli.ENCODING_DEFAULT)))
            for path, source in sorted(cls._source_inventory(root, preflight).items())
        )

    @classmethod
    def plan_transaction_paths(
        cls,
        root: Path,
        preflight: m.Infra.ModScanReport,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Return one immutable Rope callback for the mod loop's progress identity.

        Returns:
            One immutable Rope callback for the mod loop's progress identity.

        """
        original = cls._source_inventory(root, preflight)
        from flext_infra._utilities.codegen_path_cutover import (
            FlextInfraUtilitiesCodegenPathCutover,
        )

        return FlextInfraUtilitiesCodegenPathCutover.plan_transaction_path_cutover(
            rope_workspace=rope_workspace,
            sources=original,
        )

    @classmethod
    def apply_transaction_paths(
        cls,
        root: Path,
        edits: t.VariadicTuple[m.Infra.SemanticMigrationEdit],
    ) -> None:
        """Publish the exact callback included in the existing progress fingerprint."""
        original = {edit.file_path: edit.original_source for edit in edits}
        working = dict(original)
        changed: set[Path] = set()
        cls._apply_plan(working, edits, changed)
        cls._publish(root, original, working, changed).unwrap()
        cli.display_text(f"mod: Rope transaction paths changed_files={len(changed)}")

    @classmethod
    def apply(
        cls,
        root: Path,
        preflight: m.Infra.ModScanReport,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
    ) -> p.Result[bool]:
        """Apply every semantic cutover selected by the canonical mod circuit.

        Every planner failure (per module) is returned as a failed Result so the
        mod circuit reports it without a traceback and publishes nothing.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        original = cls._source_inventory(root, preflight)
        working = dict(original)
        changed: set[Path] = set()

        # Phase 0: Import alignment (rope-native; toggle in tooling.yaml).
        # Runs first so rope plans against disk truth that still equals the
        # in-memory working map.
        alignment = cls._phase_import_alignment(root, working, rope_workspace)
        if alignment.failure:
            return r[bool].from_failure(alignment)
        cls._apply_plan(working, alignment.value, changed)

        # Phase 1: Future annotations
        future_annotations = cls._phase_future_annotations(root, preflight, working)
        cls._apply_plan(working, future_annotations, changed)
        counts: MutableMapping[str, int] = {
            "import_alignment_files": len(alignment.value),
            "future_annotations": len(future_annotations),
        }
        residue = r[bool].ok(value=True)
        if future_annotations:
            residue = cls._check_residue(
                "future-annotations",
                r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].ok(
                    cls._phase_future_annotations(root, preflight, working),
                ),
            )
        # Class nesting establishes declaration scopes before references are
        # normalized; aliases and private imports follow those owner changes.
        for phase in c.Infra.SemanticCutoverPhase:
            if residue.failure:
                return r[bool].from_failure(residue)
            cli.display_text(f"mod: plan semantic phase {phase}")
            planned = u.Infra.plan_semantic_cutover(
                phase,
                rope_workspace=rope_workspace,
                sources=working,
                findings=preflight.entries,
            )
            if planned.failure:
                return r[bool].from_failure(planned)
            cls._apply_plan(working, planned.value, changed)
            counts[phase] = len(planned.value)
            if planned.value:
                residue = cls._check_residue(
                    phase,
                    u.Infra.plan_semantic_cutover(
                        phase,
                        rope_workspace=rope_workspace,
                        sources=working,
                        findings=preflight.entries,
                    ),
                )
            if phase is c.Infra.SemanticCutoverPhase.CLASS_NESTING:
                deferred = cls._deferred_model_edits(working)
                cls._apply_plan(working, deferred, changed)
                counts["deferred_models"] = len(deferred)
                if deferred:
                    residue = residue.flat_map(
                        lambda _: cls._check_residue(
                            "deferred-models",
                            r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].ok(
                                cls._deferred_model_edits(working),
                            ),
                        ),
                    )
            if residue.failure:
                return r[bool].from_failure(residue)
            cli.display_text(f"mod: semantic phase {phase} complete")
        cli.display_text(
            "mod: semantic cutover "
            + " ".join(f"{name}={count}" for name, count in counts.items()),
        )
        if not changed:
            # Every phase just planned against this identical source snapshot.
            # With no publication there is no second state to validate.
            return r[bool].ok(value=True)

        def validate_published() -> p.Result[bool]:
            published = dict(cls._source_inventory(root, preflight))
            rope_workspace.refresh()
            return cls._verify_fixed_point(
                root,
                published,
                preflight,
                rope_workspace,
            ).flat_map(
                lambda _: cls._check_residue(
                    "import-alignment",
                    cls._phase_import_alignment(root, published, rope_workspace),
                ),
            )

        return cls._publish(
            root,
            original,
            working,
            changed,
            validator=validate_published,
        )

    @classmethod
    def _phase_import_alignment(
        cls,
        root: Path,
        working: t.MappingKV[Path, str],
        rope_workspace: p.Infra.RopeWorkspaceDsl,
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan rope-native absolute import alignment when tooling enables it.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        """
        planned_edits = r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]
        if not config.Infra.tooling.mod.phases.import_alignment:
            return planned_edits.ok(())
        planned = u.Infra.align_module_imports(
            rope_project=rope_workspace.rope_project,
            repository_root=root.resolve(),
            index=rope_workspace.workspace_index,
        )
        if planned.failure:
            return planned_edits.fail(
                f"import-alignment failed to plan: {planned.error}",
            )
        return planned_edits.ok(
            tuple(
                m.Infra.SemanticMigrationEdit(
                    file_path=plan.path,
                    original_source=working[plan.path],
                    updated_source=(plan.desired_content or b"").decode(
                        c.Cli.ENCODING_DEFAULT,
                    ),
                )
                for plan in planned.value
                if plan.path in working
            ),
        )

    @staticmethod
    def _phase_future_annotations(
        root: Path,
        preflight: m.Infra.ModScanReport,
        working: MutableMapping[Path, str],
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Plan the future-annotations phase; the pipeline applies the edits.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.SemanticMigrationEdit]``.

        Raises:
            ValueError: If authenticated source disappeared during mod preflight.

        """
        future_annotations: list[m.Infra.SemanticMigrationEdit] = []
        for file_path in sorted({
            (root / finding.file).resolve()
            for finding in preflight.entries
            if finding.rule_id == "require-future-annotations"
        }):
            original_source = working.get(file_path)
            if original_source is None:
                state = u.Cli.atomic_read_binary_file_state(
                    file_path,
                    required=True,
                ).unwrap()
                content = state.content
                if content is None:
                    msg = (
                        "authenticated source disappeared during mod preflight: "
                        f"{file_path}"
                    )
                    raise ValueError(msg)
                original_source = content.decode(c.Cli.ENCODING_DEFAULT)
                working[file_path] = original_source
            updated_source = u.Infra.ensure_future_annotations(original_source)
            if updated_source != original_source:
                future_annotations.append(
                    m.Infra.SemanticMigrationEdit(
                        file_path=file_path,
                        original_source=original_source,
                        updated_source=updated_source,
                        changes=("inserted canonical future annotations import",),
                    ),
                )
        return tuple(future_annotations)

    @staticmethod
    def _check_residue(
        phase: str,
        planned: p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]],
    ) -> p.Result[bool]:
        """Reject a replan failure or edits replanned by a completed phase.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if planned.failure:
            return r[bool].from_failure(planned)
        if planned.value:
            files = ", ".join(edit.file_path.as_posix() for edit in planned.value)
            return r[bool].fail(
                f"{phase} phase left residue after application: {files}",
            )
        return r[bool].ok(value=True)

    @classmethod
    def _verify_fixed_point(
        cls,
        root: Path,
        working: MutableMapping[Path, str],
        preflight: m.Infra.ModScanReport,
        rope_workspace: p.Infra.RopeWorkspaceDsl,
    ) -> p.Result[bool]:
        """Replan every phase against the proposed or reread published sources.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        edits = r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]
        verified = cls._check_residue(
            "future-annotations",
            edits.ok(cls._phase_future_annotations(root, preflight, working)),
        ).flat_map(
            lambda _: cls._check_residue(
                "deferred-models",
                edits.ok(cls._deferred_model_edits(working)),
            ),
        )
        for phase in c.Infra.SemanticCutoverPhase:
            if verified.failure:
                return verified
            verified = cls._check_residue(
                phase,
                u.Infra.plan_semantic_cutover(
                    phase,
                    rope_workspace=rope_workspace,
                    sources=working,
                    findings=preflight.entries,
                ),
            )
        return verified

    @staticmethod
    def _source_inventory(
        root: Path,
        preflight: m.Infra.ModScanReport,
    ) -> t.MappingKV[Path, str]:
        """Read governed sources and every Python path reported by preflight.

        Returns:
            The resulting ``t.MappingKV[Path, str]``.

        Raises:
            ValueError: If authenticated source disappeared during mod preflight.

        """
        project_roots = u.Infra.governed_project_roots(root)
        refactor_config = u.Infra.load_refactor_config(root)
        scan_dirs = refactor_config.project_scan_dirs
        # The scan-ignore SSOT owns source visibility everywhere: preflight
        # findings and ast-grep targets may name paths under an ignored
        # resource (a tool hook scanned outside governed roots), and feeding
        # those into the semantic planners crashes the phase on files that
        # are declared non-source.
        ignored = frozenset(config.Infra.codegen.source_scan_ignored)
        paths = {
            path.resolve()
            for project_root in project_roots
            for directory in scan_dirs
            for path in u.Infra.iter_directory_python_files(project_root / directory)
            if not ignored.intersection(path.relative_to(root).parts[:-1])
        }
        paths.update(
            path
            for finding in preflight.entries
            if (path := (root / finding.file).resolve()).suffix == c.Infra.EXT_PYTHON
            and not ignored.intersection(path.relative_to(root).parts[:-1])
        )
        for target in u.Infra.ast_grep_scan_targets(root):
            candidate = root / target
            if ignored.intersection(candidate.relative_to(root).parts):
                continue
            paths.update(
                path.absolute()
                for path in (
                    candidate.rglob(f"*{c.Infra.EXT_PYTHON}")
                    if candidate.is_dir()
                    else (candidate,)
                )
            )
        sources: MutableMapping[Path, str] = {}
        for path in sorted(paths):
            state = u.Cli.atomic_read_binary_file_state(path, required=True).unwrap()
            content = state.content
            if content is None:
                msg = f"authenticated source disappeared during mod preflight: {path}"
                raise ValueError(msg)
            sources[path] = content.decode(c.Cli.ENCODING_DEFAULT)
        return sources

    @staticmethod
    def _deferred_model_edits(
        sources: t.MappingKV[Path, str],
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Normalize every handwritten canonical model source from its AST.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.SemanticMigrationEdit]``.

        """
        edits: list[m.Infra.SemanticMigrationEdit] = []
        models = u.Infra.facade_family_declared_by(c.Infra.MODELS_PY)
        for path, source in sorted(sources.items()):
            if source.startswith("# AUTO-GENERATED FILE"):
                continue
            if (
                path.name not in models.file_names
                and not models.directories.intersection(path.parts)
            ):
                continue
            updated = u.Infra.normalize_deferred_self_references(source)
            if updated != source:
                edits.append(
                    m.Infra.SemanticMigrationEdit(
                        file_path=path,
                        original_source=source,
                        updated_source=updated,
                        changes=("normalized definition-time model references",),
                    ),
                )
        return tuple(edits)

    @staticmethod
    def _apply_plan(
        sources: MutableMapping[Path, str],
        edits: t.SequenceOf[m.Infra.SemanticMigrationEdit],
        changed: set[Path],
    ) -> None:
        """Compose validated edit plans in memory without partial effects.

        Raises:
            ValueError: If semantic plans disagree for.

        """
        for edit in edits:
            current = sources.get(edit.file_path)
            if current != edit.original_source:
                msg = f"semantic plans disagree for {edit.file_path}"
                raise ValueError(msg)
            sources[edit.file_path] = edit.updated_source
            changed.add(edit.file_path)

    @classmethod
    def _publish(
        cls,
        root: Path,
        original: t.MappingKV[Path, str],
        updated: t.MappingKV[Path, str],
        changed: set[Path],
        *,
        validator: Callable[[], p.Result[bool]] | None = None,
    ) -> p.Result[bool]:
        """Normalize and preflight every source before journaled publication.

        Returns:
            The resulting ``p.Result[bool]``.

        Raises:
            ValueError: If source changed after semantic preflight.

        """
        from flext_infra.refactor._census_apply_formatting import (
            FlextInfraRefactorCensusApplyFormattingMixin,
        )

        semantic_plans: list[m.Infra.SemanticFilePlan] = []
        consumer_first = sorted(changed, key=cls._path_key)
        for path in consumer_first:
            state = u.Cli.atomic_read_binary_file_state(path, required=True).unwrap()
            content = state.content
            if (
                content is None
                or content.decode(c.Cli.ENCODING_DEFAULT) != original[path]
            ):
                msg = f"source changed after semantic preflight: {path}"
                raise ValueError(msg)
            project_root = u.Infra.project_root(path)
            if project_root is None:
                project_root = root
            normalized = FlextInfraRefactorCensusApplyFormattingMixin.normalize_source(
                root,
                path,
                updated[path],
            )
            if normalized.failure:
                return r[bool].from_failure(normalized)
            new_content = normalized.value.encode(c.Cli.ENCODING_DEFAULT)
            if content == new_content:
                continue
            semantic_plans.append(
                m.Infra.SemanticFilePlan(
                    project=project_root.resolve(),
                    path=path.resolve(),
                    before=state,
                    desired_content=new_content,
                    desired_mode=state.mode,
                    changes=("semantic migration",),
                ),
            )
        if not semantic_plans:
            return validator() if validator is not None else r[bool].ok(value=True)
        return FlextInfraSemanticPublication.publish_semantic_file_plans(
            semantic_plans,
            repository_root=root,
            validator=validator,
        ).map(lambda _: True)

    @staticmethod
    def _path_key(path: Path) -> t.Pair[bool, str]:
        """Sort consumers before the public API owner in a typed key.

        Returns:
            The resulting ``t.Pair[bool, str]``.

        """
        return (path.name == c.Infra.API_PY, path.as_posix())


__all__: list[str] = ["FlextInfraCodemodSemanticApply"]
