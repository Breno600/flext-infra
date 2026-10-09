"""Render one canonical pyproject and resolve its typed template context.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, config, m, r, t, u
from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
from flext_infra.deps.phases.ensure_pyright import FlextInfraEnsurePyrightConfigPhase

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraPyprojectModernizerTooling:
    """Conform in-memory pyproject sources and derive template runtime values."""

    if TYPE_CHECKING:
        # Members supplied by the composed modernizer service.
        @property
        def root(self) -> Path: ...

        repository_root: Path

        def _project_kind(
            self,
            path: Path,
            payload: t.JsonMapping,
            project_kind: str | None,
        ) -> str: ...

        def _read_document_state(
            self,
            path: Path,
            *,
            source: str | None = None,
        ) -> p.Result[m.Infra.PyprojectDocumentState]: ...

        def _apply_document_phases(
            self,
            state: m.Infra.PyprojectDocumentState,
            *,
            canonical_dev: t.StrSequence,
            topology: m.Infra.PyprojectDeclaredTopology,
        ) -> t.StrSequence: ...

        def _render_document_state(
            self,
            state: m.Infra.PyprojectDocumentState,
            changes: t.StrSequence,
            *,
            dry_run: bool,
            skip_comments: bool,
            format_source: bool = True,
        ) -> p.Result[t.StrSequence]: ...

    def conform_source(
        self,
        source: str,
        *,
        path: Path,
        format_source: bool = True,
        topology: m.Infra.PyprojectDeclaredTopology,
    ) -> p.Result[str]:
        """Return one canonical pyproject using the same phases as workspace apply.

        ``topology.declared_python_dirs_are_complete`` says the caller enumerated
        EVERY Python root, so discovery must not widen the set. An atomic
        scaffold knows its future roots before they exist on disk; filesystem
        discovery would find none and silently produce a different fixed point
        than the post-write conformance pass. An empty topology keeps discovery.

        Returns:
            One canonical pyproject using the same phases as workspace apply.

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
        rendered = self._render_document_state(
            state.value,
            self._apply_document_phases(
                state.value,
                canonical_dev=canonical_dev.value,
                topology=topology,
            ),
            dry_run=True,
            skip_comments=False,
            format_source=format_source,
        )
        if rendered.failure:
            return r[str].from_failure(rendered)
        return r[str].ok(state.value.rendered)

    def resolve_tooling_context(
        self,
        request: m.Infra.ToolingContextRequest,
    ) -> p.Result[m.Infra.ToolingRuntimeContext]:
        """Resolve typed Jinja values from the seed conformed to one topology.

        Returns:
            The resulting ``p.Result[m.Infra.ToolingRuntimeContext]``.

        """
        result_type = r[m.Infra.ToolingRuntimeContext]
        conformed = self._conformed_seed_tools(
            request.path,
            request.topology,
            request.scaffold_project,
            (request.project_name, request.package_name),
            (
                request.runtime_dependency_overlay,
                request.declared_project_dependencies,
                request.upstream,
            ),
        )
        if conformed.failure:
            return result_type.from_failure(conformed)
        tools, payload = conformed.value
        declared_python_dirs = request.topology.declared_python_dirs
        project_dir = request.path.parent
        raw_environments = (
            FlextInfraEnsurePyrightConfigPhase(
                config.Infra.tooling,
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
            project_dir=project_dir,
            is_root=not request.topology.declared_python_dirs_are_complete,
        )
        # Seed for a project whose analyzer paths were never synced yet. The
        # manager derives from directories that EXIST, so before src/ is
        # written it returns []. Writing that empty list made the next plan
        # re-derive ['src', '.'], so apply never reached its fixed point.
        # Prefer the DECLARED roots, exactly like the ensure-pyrefly phase.
        seed_manager = FlextInfraExtraPathsManager(repository_root=self.root)
        declared_roots, derived_search_path, derived_mypy_path = self._derived_paths(
            project_dir,
            declared_python_dirs,
            seed_manager,
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
        environments = self._pyright_environments(raw_environments)
        if environments.failure:
            return result_type.fail_op(
                "validate pyright execution environment",
                environments.error,
            )
        # Absent analyzer-path keys fall back to the DERIVED value: they are
        # written by the analyzer-path sync, so a project that has not run it
        # yet has them missing, and an empty default would make the NEXT plan
        # re-derive them, so apply would never reach its fixed point.
        validated: p.Result[m.Infra.ToolingRuntimeContext] = u.validate_value(
            m.Infra.ToolingRuntimeContext,
            {
                "project_kind": self._project_kind(
                    request.path,
                    payload,
                    request.topology.project_kind,
                ),
                "first_party": tools.first_party,
                "mypy_path": (
                    derived_mypy_path
                    if declared_roots
                    else tools.mypy_path or derived_mypy_path
                ),
                # The tree as it stands; a scaffold re-derives this field from
                # its planned sources before its final pyproject render.
                "mypy_facade_rebind_modules": u.Infra.facade_rebind_modules(
                    project_dir,
                    {},
                ),
                "mypy_generated_source_modules": tuple(
                    pattern
                    for package in u.Infra.generated_source_packages(project_dir)
                    for pattern in (package, f"{package}.*")
                ),
                "ruff_runtime_evaluated_base_classes": (
                    u.Infra.runtime_evaluated_base_classes(
                        project_dir,
                        {},
                        config.Infra.tooling.tools.ruff.lint.flake8_type_checking.runtime_evaluated_roots,
                    )
                ),
                "pyrefly_search_path": (
                    derived_search_path
                    if declared_roots
                    else tools.pyrefly_search_path or derived_search_path
                ),
                "pyrefly_project_includes": declared_pyrefly_includes,
                "pyrefly_project_excludes": u.Infra.pyrefly_project_excludes(
                    config.Infra.tooling.tools.pyrefly.project_exclude_globs,
                ),
                "pyright_exclude": tools.pyright.get(c.Infra.EXCLUDE, ()),
                "pyright_ignore": tools.pyright.get(c.Infra.IGNORE, ()),
                "pyright_include": (
                    declared_python_dirs or tools.pyright.get(c.Infra.INCLUDE, ())
                ),
                "pyright_extra_paths": (
                    tools.pyright.get(c.Infra.EXTRA_PATHS)
                    or seed_manager.pyright_extra_paths(
                        project_dir=project_dir,
                        is_root=True,
                    )
                    or declared_roots
                ),
                "pyright_settings": [
                    {"name": key, "value": value}
                    for key, value in sorted(tools.pyright.items())
                    if key not in scalar_keys
                ],
                "pyright_execution_environments": environments.value,
                "ruff_src": tools.ruff_src,
                "ruff_extend_exclude": tools.ruff_extend_exclude,
            },
        )
        if validated.failure:
            return result_type.fail_op(
                "tooling runtime context validation",
                validated.error,
            )
        return result_type.ok(validated.value)

    def _live_dev_dependencies(self, path: Path) -> p.Result[t.StrSequence]:
        """Collect the live dev groups plus canonical dev dependencies.

        Returns:
            The resulting merged live dev dependency sequence.

        """
        if not path.is_file():
            return r[t.StrSequence].ok(())
        live_state = self._read_document_state(path)
        if live_state.failure:
            return r[t.StrSequence].from_failure(live_state)
        groups = (
            u.Cli.toml_mapping_child(
                live_state.value.payload,
                c.Infra.DEPENDENCY_GROUPS,
            )
            or {}
        )
        group_dev = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER,
            groups.get(str(c.Infra.DEV), []),
            strict=True,
        )
        if group_dev.failure:
            return r[t.StrSequence].fail_op(
                "validate live dev dependencies",
                group_dev.error,
            )
        return r[t.StrSequence].ok((
            *group_dev.value,
            *u.Infra.canonical_dev_dependencies_from_payload(
                live_state.value.payload,
            ),
        ))

    def _conformed_seed_tools(
        self,
        path: Path,
        topology: m.Infra.PyprojectDeclaredTopology,
        scaffold_project: m.Infra.ScaffoldProjectSpec,
        names: t.Pair[t.NonEmptyStr, t.NonEmptyStr],
        overlays: t.Triple[t.StrSequence, t.StrSequence, t.NonEmptyStr],
    ) -> p.Result[t.Pair[m.Infra.ToolingConformedTools, t.MappingKV[str, t.JsonValue]]]:
        """Conform a seeded document and validate its derived tool tables.

        Returns:
            The resulting ``(tools, payload)`` pair of the conformed document.

        """
        project_name, package_name = names
        runtime_dependency_overlay, declared_project_dependencies, upstream = overlays
        result_type = r[
            t.Pair[m.Infra.ToolingConformedTools, t.MappingKV[str, t.JsonValue]]
        ]
        profile = u.Infra.composed_dependency_profile(
            scaffold_project.dependency_profiles,
            upstream=upstream,
            distribution=project_name,
        )
        if profile is None:
            return result_type.fail(f"unsupported scaffold upstream: {upstream}")
        live_dev_result = self._live_dev_dependencies(path)
        if live_dev_result.failure:
            return result_type.from_failure(live_dev_result)
        live_dev = live_dev_result.value
        # Seed the declared dependency families before Ruff derives its
        # first-party sections. The template emits the profile/config rows and
        # preserves live project dependencies, so docs and tool tables agree.
        seed: t.JsonMapping = {
            c.Infra.PROJECT: {
                c.Infra.NAME: project_name,
                c.Infra.DEPENDENCIES: [
                    *declared_project_dependencies,
                    *runtime_dependency_overlay,
                    *(item for item in profile.runtime if item != project_name),
                ],
            },
            c.Infra.DEPENDENCY_GROUPS: {
                "codegen": [item for item in profile.codegen if item != project_name],
                c.Infra.DEV: [
                    *(item for item in scaffold_project.dev if item != project_name),
                    *live_dev,
                ],
            },
            c.Infra.TOOL: {"flext": {"docs": {"package_name": package_name}}},
        }
        # Atomic scaffolds provide validated future roots;
        # existing repositories keep filesystem discovery through empty ones.
        conformed = self.conform_source(
            u.Cli.toml_dumps(u.Cli.toml_document_from_mapping(seed)),
            path=path,
            format_source=False,
            topology=topology,
        )
        if conformed.failure:
            return result_type.from_failure(conformed)
        payload = u.Cli.toml_mapping_from_text(conformed.value)
        if payload is None:
            return result_type.fail(f"tooling resolution produced invalid TOML: {path}")
        tools_result: p.Result[m.Infra.ToolingConformedTools] = u.validate_value(
            m.Infra.ToolingConformedTools,
            u.Cli.toml_mapping_child(payload, c.Infra.TOOL) or {},
        )
        if tools_result.failure:
            return result_type.fail_op(
                f"tooling resolution for {path}",
                tools_result.error,
            )
        return result_type.ok((tools_result.value, payload))

    @staticmethod
    def _derived_paths(
        project_dir: Path,
        declared_python_dirs: t.StrSequence,
        seed_manager: FlextInfraExtraPathsManager,
    ) -> t.Triple[t.StrSequence, t.StrSequence, t.StrSequence]:
        """Derive the declared or discovered analyzer search roots.

        Returns:
            The ``(declared_roots, search_path, mypy_path)`` triple.

        """
        path_rules = config.Infra.tooling.tools.pyrefly.path_rules
        # A shared search path belongs to the project when the scaffold
        # declares it or the tree already has it — the same rule
        # `pyrefly_search_paths` applies after the write.
        declared_roots: t.StrSequence = (
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
        # mypy and pyrefly diverge: mypy enumerates
        # each search-path root as a package root, so roots that re-spell the
        # same files make it abort with source-file-found-twice; pyrefly
        # resolves first-match and needs the extra roots.
        derived_search_path: t.StrSequence = (
            declared_roots
            or seed_manager.pyrefly_search_paths(
                project_dir=project_dir,
                is_root=True,
            )
        )
        derived_mypy_path: t.StrSequence = (
            tuple(root for root in declared_roots if root != ".")
            if declared_roots
            else derived_search_path
        )
        return (declared_roots, derived_search_path, derived_mypy_path)

    @staticmethod
    def _pyright_environments(
        raw_environments: t.SequenceOf[t.JsonValue],
    ) -> p.Result[t.SequenceOf[m.Infra.ToolingPyrightEnvironment]]:
        """Validate the conformed pyright environments and order them by root.

        Returns:
            The resulting validated environments sorted by root.

        """
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
                return r[t.SequenceOf[m.Infra.ToolingPyrightEnvironment]].from_failure(
                    validated_environment,
                )
            environments.append(validated_environment.value)
        # Why: the canonical pyproject layer orders the
        # [[tool.pyright.executionEnvironments]] array tables by root, so a
        # declared order (for example src, tests, skills) re-renders differently
        # from the formatted output and `make gen` reports drift forever.
        # Canonicalize by root here so the first write already matches the
        # formatted file and generation reaches its fixed point.
        return r[t.SequenceOf[m.Infra.ToolingPyrightEnvironment]].ok(
            sorted(environments, key=lambda environment: environment.root or ""),
        )


__all__: list[str] = ["FlextInfraPyprojectModernizerTooling"]
