"""Render one canonical pyproject and resolve its typed template context."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, config, m, t, u

from ..extra_paths import FlextInfraExtraPathsManager
from ..phases.ensure_pyright import FlextInfraEnsurePyrightConfigPhase

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraPyprojectModernizerTooling:
    """Conform in-memory pyproject sources and derive template runtime values."""

    if TYPE_CHECKING:
        # Members supplied by the composed modernizer service.
        @property
        def root(self) -> Path: ...

        @property
        def repository_root(self) -> Path: ...

        def _project_kind(
            self, path: Path, payload: t.JsonMapping, project_kind: str | None
        ) -> str: ...

        def _read_document_state(
            self, path: Path, *, source: str | None = None
        ) -> p.Result[m.Infra.PyprojectDocumentState]: ...

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
        ) -> t.StrSequence: ...

    def conform_source(
        self,
        source: str,
        *,
        path: Path,
        format_source: bool = True,
        root_modules: t.StrSequence = (),
        root_packages: t.StrSequence = (),
        declared_python_dirs: t.StrSequence = (),
        declared_python_dirs_are_complete: bool = False,
        generated_python_roots: t.StrSequence = (),
        project_kind: str | None = None,
        analysis_exclusions: t.StrSequence | None = None,
    ) -> p.Result[str]:
        """Return one canonical pyproject using the same phases as workspace apply.

        ``declared_python_dirs_are_complete`` says the caller enumerated EVERY
        Python root, so discovery must not widen the set. An atomic scaffold
        knows its future roots before they exist on disk; filesystem discovery
        would find none and silently produce a different fixed point than the
        post-write conformance pass.
        """
        state = self._read_document_state(path, source=source)
        if state.failure:
            return r[str].from_failure(state)
        canonical_dev: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER,
            u.Infra.canonical_dev_dependencies_from_payload(state.value.payload),
        )
        if canonical_dev.failure:
            return r[str].fail_op("pyproject model validation", canonical_dev.error)
        # flext-j47u (codex): atomic scaffolds provide validated future roots;
        # existing repositories keep filesystem discovery through the empty default.
        changes = self._process_document_state(
            state.value,
            canonical_dev=canonical_dev.value,
            dry_run=True,
            skip_comments=False,
            format_source=format_source,
            root_modules=root_modules,
            root_packages=root_packages,
            declared_python_dirs=declared_python_dirs,
            declared_python_dirs_are_complete=declared_python_dirs_are_complete,
            generated_python_roots=generated_python_roots,
            project_kind=project_kind,
            analysis_exclusions=analysis_exclusions,
        )
        if not state.value.rendered:
            return r[str].fail(
                changes[0] if changes else f"pyproject tooling render failed: {path}"
            )
        return r[str].ok(state.value.rendered)

    def resolve_tooling_context(
        self,
        *,
        project_name: t.NonEmptyStr,
        package_name: t.NonEmptyStr,
        path: Path,
        source: str | None = None,
        root_modules: t.StrSequence = (),
        root_packages: t.StrSequence = (),
        declared_python_dirs: t.StrSequence = (),
        declared_python_dirs_are_complete: bool = False,
        project_kind: str | None = None,
        analysis_exclusions: t.StrSequence | None = None,
    ) -> p.Result[m.Infra.ToolingRuntimeContext]:
        """Resolve typed Jinja values from canonical or already-conformed TOML."""
        result_type = r[m.Infra.ToolingRuntimeContext]
        if source is None:
            seed: t.JsonMapping = {
                c.Infra.PROJECT: {c.Infra.NAME: project_name},
                c.Infra.TOOL: {"flext": {"docs": {"package_name": package_name}}},
            }
            conformed = self.conform_source(
                u.Cli.toml_dumps(u.Cli.toml_document_from_mapping(seed)),
                path=path,
                format_source=False,
                root_modules=root_modules,
                root_packages=root_packages,
                declared_python_dirs=declared_python_dirs,
                declared_python_dirs_are_complete=declared_python_dirs_are_complete,
                project_kind=project_kind,
                analysis_exclusions=analysis_exclusions,
            )
            if conformed.failure:
                return result_type.from_failure(conformed)
            source = conformed.value
        payload = u.Cli.toml_mapping_from_text(source)
        if payload is None:
            return result_type.fail(f"tooling resolution produced invalid TOML: {path}")
        tools_result: p.Result[m.Infra.ToolingConformedTools] = u.validate_value(
            m.Infra.ToolingConformedTools,
            u.Cli.toml_mapping_child(payload, c.Infra.TOOL) or {},
        )
        if tools_result.failure:
            return result_type.fail_op(
                f"tooling resolution for {path}", tools_result.error
            )
        tools = tools_result.value
        project_dir = path.parent
        raw_environments = (
            FlextInfraEnsurePyrightConfigPhase(
                config.Infra.tooling
            ).environment_payloads_for_dirs(declared_python_dirs)
            if declared_python_dirs
            else u.Cli.json_as_sequence(tools.pyright.get("executionEnvironments"))
        )
        # One owner for the includes: the live tree intersected with the
        # declared env dirs, with the scaffold's own roots passed as the
        # generated roots they are so a plan that is still materializing
        # tests/ converges on its first write.
        declared_pyrefly_includes = FlextInfraExtraPathsManager(
            repository_root=self.repository_root,
            generated_python_roots=declared_python_dirs,
        ).pyrefly_project_includes(
            project_dir=project_dir, is_root=not declared_python_dirs_are_complete
        )
        # Seed for a project whose analyzer paths were never synced yet. The
        # manager derives from directories that EXIST, so before src/ is
        # written it returns []. Writing that empty list made the next plan
        # re-derive ['src', '.'], so apply never reached its fixed point.
        # Prefer the DECLARED roots, exactly like the ensure-pyrefly phase.
        seed_manager = FlextInfraExtraPathsManager(repository_root=self.root)
        path_rules = config.Infra.tooling.tools.pyrefly.path_rules
        # A shared search path belongs to the project when the scaffold
        # declares it or the tree already has it — the same rule
        # `pyrefly_search_paths` applies after the write.
        declared_roots = (
            (
                path_rules.source_dir,
                *(
                    shared
                    for shared in path_rules.project_shared_search_paths
                    if shared in declared_python_dirs or (project_dir / shared).is_dir()
                ),
                path_rules.project_root,
            )
            if path_rules.source_dir in declared_python_dirs
            else ()
        )
        # Why: partial disk discovery returns ('.',) before src/ exists, which is
        # truthy and blocked declared_roots ('src', '.'). Prefer declared roots
        # for search/mypy whenever scaffolding supplied them; pyright extras keep
        # discovery order (sorted {'.', 'src'}) so the first write matches sync.
        # mypy and pyrefly diverge (cosmos-45hiv, 2026-08-31): mypy enumerates
        # each search-path root as a package root, so roots that re-spell the
        # same files make it abort with source-file-found-twice; pyrefly
        # resolves first-match and needs the extra roots.
        derived_search_path = declared_roots or seed_manager.pyrefly_search_paths(
            project_dir=project_dir, is_root=True
        )
        derived_mypy_path = (
            tuple(root for root in declared_roots if root != ".")
            if declared_roots
            else derived_search_path
        )
        scalar_keys = frozenset({
            c.Infra.EXCLUDE,
            c.Infra.IGNORE,
            c.Infra.INCLUDE,
            c.Infra.EXTRA_PATHS,
            "executionEnvironments",
            "venv",
            "venvPath",
        })
        environment_keys = frozenset({"root", c.Infra.EXTRA_PATHS})
        environments: t.MutableSequenceOf[m.Infra.ToolingPyrightEnvironment] = []
        for raw_environment in raw_environments:
            environment = u.Cli.json_as_mapping(raw_environment)
            validated_environment: p.Result[m.Infra.ToolingPyrightEnvironment] = (
                u.validate_value(
                    m.Infra.ToolingPyrightEnvironment,
                    {
                        "root": environment.get("root"),
                        "extra_paths": environment.get(c.Infra.EXTRA_PATHS, ()),
                        "settings": [
                            {"name": key, "value": value}
                            for key, value in sorted(environment.items())
                            if key not in environment_keys
                        ],
                    },
                )
            )
            if validated_environment.failure:
                return result_type.fail_op(
                    "validate pyright execution environment",
                    validated_environment.error,
                )
            environments.append(validated_environment.value)
        # Absent analyzer-path keys fall back to the DERIVED value: they are
        # written by the analyzer-path sync, so a project that has not run it
        # yet has them missing, and an empty default would make the NEXT plan
        # re-derive them, so apply would never reach its fixed point.
        validated: p.Result[m.Infra.ToolingRuntimeContext] = u.validate_value(
            m.Infra.ToolingRuntimeContext,
            {
                "project_kind": self._project_kind(path, payload, project_kind),
                "first_party": tools.first_party,
                "mypy_path": (
                    derived_mypy_path
                    if declared_roots
                    else tools.mypy_path or derived_mypy_path
                ),
                "pyrefly_search_path": (
                    derived_search_path
                    if declared_roots
                    else tools.pyrefly_search_path or derived_search_path
                ),
                "pyrefly_project_includes": declared_pyrefly_includes,
                "pyright_exclude": tools.pyright.get(c.Infra.EXCLUDE, ()),
                "pyright_ignore": tools.pyright.get(c.Infra.IGNORE, ()),
                "pyright_include": (
                    declared_python_dirs or tools.pyright.get(c.Infra.INCLUDE, ())
                ),
                "pyright_extra_paths": (
                    tools.pyright.get(c.Infra.EXTRA_PATHS)
                    or seed_manager.pyright_extra_paths(
                        project_dir=project_dir, is_root=True
                    )
                    or declared_roots
                ),
                "pyright_settings": [
                    {"name": key, "value": value}
                    for key, value in sorted(tools.pyright.items())
                    if key not in scalar_keys
                ],
                "pyright_execution_environments": environments,
                "ruff_src": tools.ruff_src,
                "ruff_exclude": tools.ruff_exclude,
                "ruff_ignore": tools.ruff_ignore,
            },
        )
        if validated.failure:
            return result_type.fail_op(
                "tooling runtime context validation", validated.error
            )
        return result_type.ok(validated.value)


__all__: list[str] = ["FlextInfraPyprojectModernizerTooling"]
