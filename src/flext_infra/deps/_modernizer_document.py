"""Document-state processing mixin for pyproject modernization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, config, m, t, u
from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
from flext_infra.deps.phases.consolidate_groups import FlextInfraConsolidateGroupsPhase
from flext_infra.deps.phases.ensure_coverage import FlextInfraEnsureCoverageConfigPhase
from flext_infra.deps.phases.ensure_formatting import (
    FlextInfraEnsureFormattingToolingPhase,
)
from flext_infra.deps.phases.ensure_mypy import FlextInfraEnsureMypyConfigPhase
from flext_infra.deps.phases.ensure_namespace import (
    FlextInfraEnsureNamespaceToolingPhase,
)
from flext_infra.deps.phases.ensure_packaging import FlextInfraEnsurePackagingPhase
from flext_infra.deps.phases.ensure_pydantic_mypy import (
    FlextInfraEnsurePydanticMypyConfigPhase,
)
from flext_infra.deps.phases.ensure_pyrefly import FlextInfraEnsurePyreflyConfigPhase
from flext_infra.deps.phases.ensure_pyright import FlextInfraEnsurePyrightConfigPhase
from flext_infra.deps.phases.ensure_pytest import FlextInfraEnsurePytestConfigPhase
from flext_infra.deps.phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase
from flext_infra.deps.phases.ensure_vulture import FlextInfraEnsureVultureConfigPhase
from flext_infra.deps.phases.inject_comments import FlextInfraInjectCommentsPhase
from flext_infra.refactor.project_classifier import FlextInfraProjectClassifier

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from flext_infra import p


class FlextInfraPyprojectModernizerDocumentMixin:
    """Read, classify, and process one parsed pyproject document state."""

    if TYPE_CHECKING:
        # Members provided by sibling mixins / the facade at runtime via MRO.
        _rewrite_dependency_constraints_payload: Callable[..., t.StrSequence]

        @property
        def root(self) -> Path: ...

        def _ensure_build_system_payload(
            self, payload: t.MutableJsonMapping
        ) -> t.StrSequence: ...

        def _remove_empty_poetry_groups_payload(
            self, payload: t.MutableJsonMapping
        ) -> t.StrSequence: ...

        # Declared as a plain attribute, not a property: the concrete owner
        # (FlextInfraPyprojectModernizer) supplies it as a Pydantic field whose
        # default comes from the tomlsort SSOT. A property here would make the
        # field an incompatible override of a read-only descriptor.
        tomlsort_sort_first: t.StrSequence

        def _reorder_document_inplace(
            self,
            doc: t.Cli.TomlDocument,
            *,
            preferred_first: t.StrSequence | None = None,
        ) -> None: ...

    def _classify_project(
        self, project_dir: Path, *, payload: t.JsonMapping | None = None
    ) -> p.Result[str]:
        """Classify project kind for pyright/coverage settings selection."""
        classifier = FlextInfraProjectClassifier(project_dir, pyproject_payload=payload)
        return r[str].ok(classifier.classify().project_kind)

    def _read_document_state(
        self, path: Path
    ) -> p.Result[m.Infra.PyprojectDocumentState]:
        """Read one pyproject once and keep one validated plain payload state."""
        read = u.Cli.files_read_text(path)
        if read.failure:
            return r[m.Infra.PyprojectDocumentState].fail(
                read.error or f"failed to read {path}"
            )
        original_rendered = read.value
        payload_source = u.Cli.toml_mapping_from_text(original_rendered)
        if payload_source is None:
            return r[m.Infra.PyprojectDocumentState].fail(f"invalid TOML: {path}")
        try:
            payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python(
                payload_source
            )
        except c.ValidationError as exc:
            return r[m.Infra.PyprojectDocumentState].fail_op(
                "TOML payload validation", exc
            )
        return r[m.Infra.PyprojectDocumentState].ok(
            m.Infra.PyprojectDocumentState(
                pyproject_path=path,
                original_rendered=original_rendered,
                payload=payload,
            )
        )

    def _format_rendered_pyproject(self, path: Path, rendered: str) -> p.Result[str]:
        """Format rendered pyproject TOML with the workspace Taplo contract."""
        return u.Infra.format_toml_source(
            rendered,
            path=path,
            toolchain_root=self.root,
            taplo_version=config.Infra.codegen.toolchain.taplo_version,
        )

    def _project_is_flext_child(self, project_dir: Path) -> p.Result[bool]:
        """Detect a FLEXT consumer that shares a parent workspace ``.venv``.

        Git topology distinguishes workspace roots from attached members for
        analyzer scope, packaging, and search paths. Virtualenv locations are not
        committed analyzer settings; the governed Make runtime selects the active
        environment for each checkout.
        """
        rules = config.Infra.tooling.tools.pyright.path_rules
        venv_name = rules.venv_name
        superproject = u.Infra.git_superproject_working_tree(
            m.Infra.GitRepoRequest(repo_root=project_dir)
        )
        if superproject.success:
            # Git topology is authoritative inside a work tree: a nested
            # repository names its superproject, an independent checkout or
            # linked worktree names nothing. A local .venv (including a
            # borrowed symlink to the parent runtime) must not outrank this.
            return r[bool].ok(bool(superproject.value.text.strip()))
        local_venv = project_dir / venv_name
        if local_venv.is_symlink():
            target = local_venv.resolve()
            if not target.is_relative_to(project_dir.resolve()):
                return r[bool].ok(True)
        if local_venv.is_dir():
            return r[bool].ok(False)
        if (project_dir.parent / venv_name).is_dir():
            return r[bool].ok(True)
        makefile = project_dir / "Makefile"
        if not makefile.exists():
            return r[bool].ok(False)
        if not makefile.is_file():
            return r[bool].fail(f"project Makefile is not a regular file: {makefile}")
        read = u.Cli.files_read_text(makefile)
        if read.failure:
            return r[bool].fail(
                read.error or f"project Makefile read failed: {makefile}"
            )
        for raw_line in read.value.splitlines():
            stripped = raw_line.strip()
            key, separator, value = stripped.partition(":=")
            if separator != ":=" or key.strip() != "MAKE_PROFILE":
                continue
            return r[bool].ok(
                value.strip() == c.Infra.MakeProfile.WORKSPACE_MEMBER.value
            )
        return r[bool].ok(False)

    def _process_document_state(
        self,
        state: m.Infra.PyprojectDocumentState,
        *,
        canonical_dev: t.StrSequence,
        dry_run: bool,
        skip_comments: bool,
        format_source: bool = True,
        rewrite_constraints: bool = False,
        locked_versions: t.MappingKV[str, str] | None = None,
        internal_names: t.StrSequence = (),
        declared_python_dirs: t.StrSequence = (),
        declared_python_dirs_are_complete: bool = False,
        project_kind: str | None = None,
        analysis_exclusions: t.StrSequence = (),
    ) -> t.StrSequence:
        """Process one parsed pyproject state and collect changes."""
        path = state.pyproject_path
        original_rendered = state.original_rendered
        payload = state.payload
        child_result = self._project_is_flext_child(path.parent)
        if child_result.failure:
            return [child_result.error or "failed to resolve project Git topology"]
        # Inside a work tree the target's own Git topology is authoritative,
        # never the scope the modernizer was invoked with. Outside a work tree,
        # relative position distinguishes a root from its nested members.
        governed = u.Infra.git_superproject_working_tree(
            m.Infra.GitRepoRequest(repo_root=path.parent)
        )
        is_root = (
            not child_result.value
            if governed.success
            else path.parent.resolve() == self.root.resolve()
        )
        # mro-j47u (codex): scaffold (pre-write) contexts have no on-disk project
        # root yet. Derive pyright/pyrefly configuration from declared roots only;
        # disk discovery converges on the first post-write conformance pass.
        project_root_exists = path.is_file()
        effective_project_dir = path.parent if project_root_exists else None
        effective_workspace_root = self.root if project_root_exists else None
        paths_manager = FlextInfraExtraPathsManager(workspace_root=self.root)
        effective_paths_manager = paths_manager if project_root_exists else None
        resolved_project_kind: str = project_kind or "core"
        if project_kind is None and not is_root:
            kind_result = self._classify_project(path.parent, payload=payload)
            if kind_result.success:
                resolved_project_kind = kind_result.value
        declared_roots_are_usable = (
            declared_python_dirs_are_complete or not project_root_exists
        )
        changes: t.MutableSequenceOf[str] = []
        changes.extend(self._ensure_build_system_payload(payload))
        changes.extend(self._remove_empty_poetry_groups_payload(payload))
        if rewrite_constraints:
            changes.extend(
                self._rewrite_dependency_constraints_payload(
                    payload,
                    locked_versions=locked_versions or {},
                    internal_names=internal_names,
                )
            )
        changes.extend(
            FlextInfraConsolidateGroupsPhase().apply_payload(payload, canonical_dev)
        )
        changes.extend(
            FlextInfraEnsurePytestConfigPhase(config.Infra.tooling).apply_payload(
                payload
            )
        )
        # mro-j47u (codex): Pyrefly derives its include globs from the canonical
        # Pyright roots, so resolve Pyright first and converge in one pass.
        changes.extend(
            FlextInfraEnsurePyrightConfigPhase(config.Infra.tooling).apply_payload(
                payload,
                is_root=is_root,
                workspace_root=effective_workspace_root,
                project_dir=effective_project_dir,
                project_kind=resolved_project_kind,
                paths_manager=effective_paths_manager,
                declared_python_dirs=declared_python_dirs,
                declared_python_dirs_are_complete=declared_roots_are_usable,
                analysis_exclusions=analysis_exclusions,
            )
        )
        changes.extend(
            FlextInfraEnsurePyreflyConfigPhase(config.Infra.tooling).apply_payload(
                payload,
                is_root=is_root,
                project_dir=effective_project_dir,
                paths_manager=effective_paths_manager,
                declared_python_dirs=declared_python_dirs,
                declared_python_dirs_are_complete=declared_roots_are_usable,
            )
        )
        changes.extend(
            FlextInfraEnsureMypyConfigPhase(config.Infra.tooling).apply_payload(payload)
        )
        changes.extend(
            FlextInfraEnsurePydanticMypyConfigPhase(config.Infra.tooling).apply_payload(
                payload
            )
        )
        changes.extend(
            FlextInfraEnsureFormattingToolingPhase(config.Infra.tooling).apply_payload(
                payload
            )
        )
        changes.extend(
            FlextInfraEnsureNamespaceToolingPhase().apply_payload(payload, path=path)
        )
        changes.extend(
            FlextInfraEnsureRuffConfigPhase(config.Infra.tooling).apply_payload(
                payload, path=path
            )
        )
        changes.extend(
            FlextInfraEnsurePackagingPhase(config.Infra.tooling).apply_payload(
                payload, path=path, is_root=is_root
            )
        )
        # mro-j47u: existing projects consume the same Vulture SSOT as scaffolds.
        changes.extend(
            FlextInfraEnsureVultureConfigPhase(config.Infra.tooling).apply_payload(
                payload
            )
        )
        changes.extend(
            FlextInfraEnsureCoverageConfigPhase(config.Infra.tooling).apply_payload(
                payload, project_kind=resolved_project_kind
            )
        )
        if effective_paths_manager is not None:
            changes.extend(
                effective_paths_manager.sync_payload(
                    payload, project_dir=path.parent, is_root=is_root
                )
            )
        doc: t.Cli.TomlDocument = u.Cli.toml_document_from_mapping(payload)
        self._reorder_document_inplace(doc, preferred_first=self.tomlsort_sort_first)
        state.payload = payload
        rendered = doc.as_string()
        if not skip_comments:
            rendered, comment_changes = FlextInfraInjectCommentsPhase().apply(rendered)
            changes.extend(comment_changes)
        if format_source:
            formatted_result = self._format_rendered_pyproject(path, rendered)
            if formatted_result.failure:
                return [formatted_result.error or "taplo format failed"]
            rendered = formatted_result.value
        normalized_original = original_rendered.rstrip() + "\n"
        normalized_rendered = rendered.rstrip() + "\n"
        state.rendered = normalized_rendered
        if normalized_rendered == normalized_original:
            return ()
        if not dry_run:
            # Persist the same normalized value used for change detection.
            u.write_file(path, normalized_rendered, encoding=c.Cli.ENCODING_DEFAULT)
        return changes


__all__: list[str] = ["FlextInfraPyprojectModernizerDocumentMixin"]
