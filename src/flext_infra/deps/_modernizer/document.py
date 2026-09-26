"""Read, normalize, and render one pyproject document through every phase."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, config, m, t, u
from flext_infra.refactor.project_classifier import FlextInfraProjectClassifier

from ..extra_paths import FlextInfraExtraPathsManager
from ..phases.consolidate_groups import FlextInfraConsolidateGroupsPhase
from ..phases.ensure_packaging import FlextInfraEnsurePackagingPhase
from ..phases.ensure_pyrefly import FlextInfraEnsurePyreflyConfigPhase
from ..phases.ensure_pyright import FlextInfraEnsurePyrightConfigPhase
from ..phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase
from ..phases.inject_comments import FlextInfraInjectCommentsPhase
from ..phases.tool_tables import FlextInfraToolTablesPhase

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraPyprojectModernizerDocument:
    """Own the parsed document state and the ordered phase pipeline."""

    if TYPE_CHECKING:
        # Members supplied by the composed modernizer service.
        tomlsort_sort_first: t.StrSequence
        managed_artifacts: m.Infra.ProjectManagedArtifactsResolution | None

        @property
        def root(self) -> Path: ...

    def _project_kind(
        self, path: Path, payload: t.JsonMapping, project_kind: str | None
    ) -> str:
        """Return the declared kind, classifying member projects on demand."""
        if project_kind is not None:
            return project_kind
        if path.parent.resolve() == self.root.resolve():
            return "core"
        return (
            FlextInfraProjectClassifier(path.parent, pyproject_payload=payload)
            .classify()
            .project_kind
        )

    def _read_document_state(
        self, path: Path, *, source: str | None = None
    ) -> p.Result[m.Infra.PyprojectDocumentState]:
        """Parse one pyproject once into one validated plain payload state."""
        result_type = r[m.Infra.PyprojectDocumentState]
        if source is None:
            read = u.Cli.files_read_text(path)
            if read.failure:
                return result_type.from_failure(read)
            source = read.value
        payload_source = u.Cli.toml_mapping_from_text(source)
        if payload_source is None:
            return result_type.fail(f"invalid TOML: {path}")
        validated: p.Result[t.MutableJsonMapping] = u.validate_value(
            t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER, payload_source
        )
        if validated.failure:
            return result_type.fail_op("TOML payload validation", validated.error)
        return result_type.ok(
            m.Infra.PyprojectDocumentState(
                pyproject_path=path, original_rendered=source, payload=validated.value
            )
        )

    @staticmethod
    def _normalize_build_payload(payload: t.MutableJsonMapping) -> t.StrSequence:
        """Pin the hatchling backend and drop empty Poetry dependency groups."""
        changes: t.MutableSequenceOf[str] = []
        if u.Cli.toml_mapping_child(payload, "build-system") is None:
            changes.append("created [build-system]")
        build_system = u.Cli.toml_mapping_ensure_table(payload, "build-system")
        if u.Cli.toml_mapping_sync_value(
            build_system, "build-backend", "hatchling.build"
        ):
            changes.append("build-system.build-backend set to hatchling.build")
        if u.Cli.toml_mapping_sync_string_list(
            build_system, "requires", ["hatchling"], sort_values=True
        ):
            changes.append("build-system.requires set to ['hatchling']")
        metadata = u.Cli.toml_mapping_ensure_path(
            payload, (c.Infra.TOOL, "hatch", "metadata")
        )
        if metadata.get("allow-direct-references") is not True:
            metadata["allow-direct-references"] = True
            changes.append("tool.hatch.metadata.allow-direct-references set to true")
        groups = u.Cli.toml_mapping_path(
            payload, (c.Infra.TOOL, c.Infra.POETRY, c.Infra.GROUP)
        )
        if groups is None:
            return changes
        for name in [
            name
            for name in groups
            if u.Cli.toml_mapping_path(groups, (name, c.Infra.DEPENDENCIES)) == {}
        ]:
            del groups[name]
            changes.append(f"removed empty poetry group '{name}'")
        poetry = u.Cli.toml_mapping_path(payload, (c.Infra.TOOL, c.Infra.POETRY))
        if not groups and poetry is not None:
            del poetry[c.Infra.GROUP]
            changes.append("removed empty poetry group container")
        return changes

    @staticmethod
    def _ordered_keys(
        container: t.Cli.TomlDocument | t.Cli.TomlTable, preferred_first: t.StrSequence
    ) -> t.Pair[t.StrSequence, t.StrSequence]:
        """Return current keys and their preferred-first, then alphabetical order."""
        current = [str(key) for key in container]
        ordered = [key for key in preferred_first if key in current]
        ordered.extend(sorted(set(current) - set(ordered)))
        return current, ordered

    @classmethod
    def _reorder_item(
        cls, item: t.Cli.TomlContainer | t.Cli.TomlItem, table_key: str
    ) -> None:
        """Reorder one table, or every table of an array, below ``table_key``."""
        if table_key == "per-file-ignores":
            return
        if u.Cli.toml_is_aot(item):
            for entry in item.body:
                cls._reorder_item(entry, table_key)
            return
        if not u.Cli.toml_is_table(item):
            return
        current, ordered = cls._ordered_keys(item, ())
        items = {key: item[key] for key in current}
        if ordered != current:
            for key in current:
                del item[key]
        # Children are reordered before re-insertion: tomlkit renders super
        # tables from the item as inserted.
        for key in ordered:
            cls._reorder_item(items[key], key)
            if ordered != current:
                item[key] = items[key]

    @classmethod
    def _reorder_document(
        cls, doc: t.Cli.TomlDocument, *, preferred_first: t.StrSequence
    ) -> None:
        """Apply deterministic ordering to top-level groups and nested tables."""
        current, ordered = cls._ordered_keys(doc, preferred_first)
        if ordered != current:
            items = {key: doc[key] for key in current}
            for key in current:
                del doc[key]
            for key in ordered:
                doc[key] = items[key]
        tool = u.Cli.toml_table_child(doc, c.Infra.TOOL)
        if tool is not None:
            cls._reorder_item(tool, c.Infra.TOOL)
        for key in ordered:
            if key != c.Infra.TOOL:
                cls._reorder_item(doc[key], key)

    def _process_document_state(
        self,
        state: m.Infra.PyprojectDocumentState,
        *,
        canonical_dev: t.StrSequence,
        dry_run: bool,
        skip_comments: bool,
        format_source: bool = True,
        root_modules: t.StrSequence = (),
        root_packages: t.StrSequence = (),
        declared_python_dirs: t.StrSequence = (),
        declared_python_dirs_are_complete: bool = False,
        generated_python_roots: t.StrSequence = (),
        project_kind: str | None = None,
        analysis_exclusions: t.StrSequence | None = None,
    ) -> t.StrSequence:
        """Run every phase over one parsed state; write unless ``dry_run``."""
        path, payload = state.pyproject_path, state.payload
        is_root = path.parent.resolve() == self.root.resolve()
        # Scaffold (pre-write) contexts have no on-disk project root yet: derive
        # analyzer configuration from declared roots only; disk discovery
        # converges on the first post-write conformance pass.
        exists = path.is_file()
        paths_manager = (
            FlextInfraExtraPathsManager(
                repository_root=self.root,
                generated_python_roots=generated_python_roots,
                analysis_exclusions=analysis_exclusions or (),
            )
            if exists
            else None
        )
        resolved_kind = self._project_kind(path, payload, project_kind)
        tooling = config.Infra.tooling
        changes: t.MutableSequenceOf[str] = [
            *self._normalize_build_payload(payload),
            *FlextInfraConsolidateGroupsPhase().apply_payload(payload, canonical_dev),
            *FlextInfraToolTablesPhase(tooling).apply_payload(payload, path=path),
            # Pyrefly derives its include globs from the canonical Pyright
            # roots, so resolve Pyright first and converge in one pass.
            *FlextInfraEnsurePyrightConfigPhase(tooling).apply_payload(
                payload,
                is_root=is_root,
                repository_root=self.root if exists else None,
                project_dir=path.parent if exists else None,
                project_kind=resolved_kind,
                paths_manager=paths_manager,
                declared_python_dirs=declared_python_dirs,
                declared_python_dirs_are_complete=declared_python_dirs_are_complete,
                analysis_exclusions=analysis_exclusions,
            ),
            # Declared roots are topology facts only during atomic creation;
            # normal modernization derives productive roots on disk.
            *FlextInfraEnsurePyreflyConfigPhase(tooling).apply_payload(
                payload,
                is_root=is_root,
                project_dir=path.parent if exists else None,
                paths_manager=paths_manager,
                declared_python_dirs=declared_python_dirs,
                declared_python_dirs_are_complete=(
                    declared_python_dirs_are_complete or not exists
                ),
            ),
            *FlextInfraEnsureRuffConfigPhase(
                tooling, self.managed_artifacts
            ).apply_payload(payload, path=path),
            *FlextInfraEnsurePackagingPhase(tooling).apply_payload(
                payload,
                path=path,
                root_modules=root_modules,
                root_packages=root_packages,
            ),
        ]
        if paths_manager is not None:
            changes.extend(
                paths_manager.sync_payload(
                    payload, project_dir=path.parent, is_root=is_root
                )
            )
        doc = u.Cli.toml_document_from_mapping(payload)
        self._reorder_document(doc, preferred_first=self.tomlsort_sort_first)
        rendered = doc.as_string()
        if not skip_comments:
            rendered, comment_changes = FlextInfraInjectCommentsPhase().apply(rendered)
            changes.extend(comment_changes)
        if format_source:
            formatted = u.Infra.format_toml_source(
                rendered,
                path=path,
                toolchain_root=self.root,
                taplo_version=config.Infra.codegen.toolchain.taplo_version,
                process_timeout_seconds=(
                    config.Infra.tooling.tools.tomlsort.process_timeout_seconds
                ),
            )
            if formatted.failure:
                return [formatted.error or "taplo format failed"]
            rendered = formatted.value
        state.rendered = rendered.rstrip() + "\n"
        if state.rendered == state.original_rendered.rstrip() + "\n":
            return ()
        if not dry_run:
            u.write_file(path, state.rendered, encoding=c.Cli.ENCODING_DEFAULT)
        return changes


__all__: list[str] = ["FlextInfraPyprojectModernizerDocument"]
