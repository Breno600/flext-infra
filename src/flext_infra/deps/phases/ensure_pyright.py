"""Phase: Ensure standard Pyright configuration for strict type checking."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, t, u
from flext_infra.deps.toml_phase import FlextInfraTomlPhaseService
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

if TYPE_CHECKING:
    from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager


class FlextInfraEnsurePyrightConfigPhase:
    """Ensure standard Pyright configuration for strict type checking."""

    def __init__(self, tool_config: m.Infra.ToolConfigDocument) -> None:
        """Initialize the phase with the canonical tool configuration."""
        self._tool_config = tool_config

    def _report_private_usage_for_env(
        self,
        env_dir: str,
        *,
        rules: m.Infra.PyrightConfig.PathRulesConfig | None = None,
    ) -> str:
        """Only ``source_dir`` (src/) is strict; all auto-discovered dirs relax."""
        effective_rules = rules or self._tool_config.tools.pyright.path_rules
        if env_dir == effective_rules.source_dir:
            source_report: str = effective_rules.source_report_private_usage
            return source_report
        test_report: str = effective_rules.test_like_report_private_usage
        return test_report

    def _env_entry(
        self,
        *,
        env_dir: str,
        root: str,
        extra_paths: t.StrSequence,
        rules: m.Infra.PyrightConfig.PathRulesConfig,
    ) -> m.Infra.PyrightConfig.ExecutionEnvironment:
        """Env entry."""
        return m.Infra.PyrightConfig.ExecutionEnvironment(
            root=root,
            report_private_usage=self._report_private_usage_for_env(
                env_dir, rules=rules
            ),
            extra_paths=[*extra_paths],
        )

    def _extra_paths_for_env(
        self, *, env_dir: str, source_path: str, project_root: str, source_dir: str
    ) -> t.StrSequence:
        """``src/`` owns only its own path; every other discovered dir also imports from src + root."""
        if env_dir == source_dir:
            return [source_path]
        if source_path != project_root:
            return [project_root, source_path]
        return [project_root]

    def _envs_for_dirs(
        self,
        *,
        env_dirs: t.StrSequence,
        source_path: str,
        project_root: str,
        rules: m.Infra.PyrightConfig.PathRulesConfig,
    ) -> t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]:
        """Envs for dirs."""
        return [
            self._env_entry(
                env_dir=env_dir,
                root=env_dir,
                extra_paths=self._extra_paths_for_env(
                    env_dir=env_dir,
                    source_path=source_path,
                    project_root=project_root,
                    source_dir=rules.source_dir,
                ),
                rules=rules,
            )
            for env_dir in env_dirs
        ]

    def _declared_envs(
        self,
        *,
        declared_python_dirs: t.StrSequence,
        project_dir: Path | None,
        rules: m.Infra.PyrightConfig.PathRulesConfig,
    ) -> t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]:
        """Build environments for roots declared before they exist on disk.

        Declared roots and on-disk discovery must select the SAME environments,
        diagnostic overrides included. Emitting only the broad roots here made
        the declared render drop the override blocks that the on-disk render
        keeps, so apply and check disagreed and conform never converged.
        """
        source_path = self._project_source_path()
        return (
            *self._diagnostic_override_envs(
                project_dir=project_dir, root_prefix=None, source_path=source_path
            ),
            *self._envs_for_dirs(
                env_dirs=self._declared_environment_dirs(declared_python_dirs),
                source_path=source_path,
                project_root=rules.project_root,
                rules=rules,
            ),
        )

    def _diagnostic_override_envs(
        self, *, project_dir: Path | None, root_prefix: Path | None, source_path: str
    ) -> t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]:
        """Resolve configured overrides only when their project path exists."""
        if project_dir is None:
            return ()
        rules = self._tool_config.tools.pyright.path_rules
        environments: t.MutableSequenceOf[
            m.Infra.PyrightConfig.ExecutionEnvironment
        ] = []
        for override in rules.diagnostic_path_overrides:
            if not (project_dir / override.root).is_dir():
                continue
            resolved_root = (
                root_prefix / override.root if root_prefix else Path(override.root)
            ).as_posix()
            environments.append(
                m.Infra.PyrightConfig.ExecutionEnvironment(
                    root=resolved_root,
                    report_private_usage=override.report_private_usage,
                    extra_paths=(source_path,),
                    rationale=override.rationale,
                )
            )
        return tuple(environments)

    def _project_source_path(self, *, prefix: str = "") -> str:
        """Project source path."""
        rules = self._tool_config.tools.pyright.path_rules
        return f"{prefix}/{rules.source_dir}" if prefix else rules.source_dir

    def _expected_envs(
        self, *, is_root: bool, workspace_root: Path | None, project_dir: Path | None
    ) -> t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]:
        """Return the expected execution environments."""
        if not is_root or workspace_root is None:
            return self._expected_envs_for_project(project_dir=project_dir)
        rules = self._tool_config.tools.pyright.path_rules
        expected_envs: t.MutableSequenceOf[
            m.Infra.PyrightConfig.ExecutionEnvironment
        ] = []
        root_source_path = self._project_source_path()
        # mro-j47u (codex): specific roots precede the broad source environment.
        expected_envs.extend(
            self._diagnostic_override_envs(
                project_dir=workspace_root,
                root_prefix=None,
                source_path=root_source_path,
            )
        )
        for env_dir in u.Infra.discover_python_dirs(workspace_root):
            if (workspace_root / env_dir / c.Infra.PYPROJECT_FILENAME).is_file():
                continue
            expected_envs.append(
                self._env_entry(
                    env_dir=env_dir,
                    root=env_dir,
                    extra_paths=self._extra_paths_for_env(
                        env_dir=env_dir,
                        source_path=root_source_path,
                        project_root=rules.project_root,
                        source_dir=rules.source_dir,
                    ),
                    rules=rules,
                )
            )
        discovered = u.Infra.discover_projects(workspace_root)
        child_projects = (
            sorted(
                (
                    project.path
                    for project in discovered.value
                    if (
                        project.workspace_role
                        == c.Infra.WorkspaceProjectRole.WORKSPACE_MEMBER
                    )
                ),
                key=lambda project_path: project_path.name,
            )
            if discovered.success
            else []
        )
        for child_project in child_projects:
            relative_root = child_project.relative_to(workspace_root)
            relative_project_root = relative_root.as_posix()
            child_source_path = self._project_source_path(prefix=relative_project_root)
            expected_envs.extend(
                self._diagnostic_override_envs(
                    project_dir=child_project,
                    root_prefix=relative_root,
                    source_path=child_source_path,
                )
            )
            for env_dir in u.Infra.discover_python_dirs(child_project):
                expected_envs.append(
                    self._env_entry(
                        env_dir=env_dir,
                        root=(relative_root / env_dir).as_posix(),
                        extra_paths=self._extra_paths_for_env(
                            env_dir=env_dir,
                            source_path=child_source_path,
                            project_root=relative_project_root,
                            source_dir=rules.source_dir,
                        ),
                        rules=rules,
                    )
                )
        return expected_envs

    def _expected_envs_for_project(
        self, *, project_dir: Path | None
    ) -> t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]:
        """Build environments only for productive directories that exist."""
        rules = self._tool_config.tools.pyright.path_rules
        # mro-j47u (codex): absent optional roots are not valid Pyright inputs.
        # mro-0ccx4: a directory that exists but holds no Python files (e.g.
        # examples/ with only a README) is not a productive root.
        # mro-be9ld: u.Infra.analyzer_python_roots is the single owner conform
        # and the extra-paths sync already share. Filtering rules.env_dirs alone
        # missed every Python root outside that list (flext-grpc/docs), so
        # conform emitted its execution environment and this phase removed it on
        # the next pass -- gen check reported drift gen apply could never fix.
        declared = tuple(
            env_dir
            for env_dir in rules.env_dirs
            if project_dir is None
            or (
                (project_dir / env_dir).is_dir()
                and any((project_dir / env_dir).rglob(c.Infra.EXT_PYTHON_GLOB))
            )
        )
        env_dirs = (
            declared
            if project_dir is None
            else tuple(u.Infra.analyzer_python_roots(project_dir, declared))
        )
        source_path = self._project_source_path()
        return (
            *self._diagnostic_override_envs(
                project_dir=project_dir, root_prefix=None, source_path=source_path
            ),
            *self._envs_for_dirs(
                env_dirs=env_dirs,
                source_path=source_path,
                project_root=rules.project_root,
                rules=rules,
            ),
        )

    def environment_payloads_for_dirs(
        self, env_dirs: t.StrSequence, *, project_dir: Path | None = None
    ) -> t.SequenceOf[t.JsonDict]:
        """Render configured environments for Python roots declared before writes."""
        environments = self._declared_envs(
            declared_python_dirs=env_dirs,
            project_dir=project_dir,
            rules=self._tool_config.tools.pyright.path_rules,
        )
        return tuple(self._environment_payload(item) for item in environments)

    @staticmethod
    def _declared_environment_dirs(env_dirs: t.StrSequence) -> t.StrSequence:
        """Apply canonical Python discovery exclusions to pre-write declarations."""
        # NOTE (multi-agent, mro-wkii.17.9.2.1): declared and on-disk roots must
        # select the same first-class analyzer environments in the first pass.
        return tuple(
            env_dir
            for env_dir in env_dirs
            if env_dir not in c.Infra.PYTHON_DISCOVERY_SKIP_DIRS
        )

    def _environment_payload(
        self, environment: m.Infra.PyrightConfig.ExecutionEnvironment
    ) -> t.JsonDict:
        """Render one environment with its closed, scope-specific diagnostics."""
        rules = self._tool_config.tools.pyright.path_rules
        env_dir = Path(environment.root).name
        diagnostics: t.MutableStrMapping = {
            **self._tool_config.tools.pyright.lazy_import_suppressions
        }
        if env_dir == rules.source_dir:
            diagnostics.update(self._tool_config.tools.pyright.source_env_suppressions)
        elif env_dir in rules.test_like_dirs:
            diagnostics.update(
                self._tool_config.tools.pyright.test_like_env_suppressions
            )
        payload: t.JsonDict = environment.model_dump(mode="json", by_alias=True)
        payload.update(diagnostics)
        return payload

    def _override_for_kind(
        self, project_kind: str
    ) -> m.Infra.ProjectTypeOverrideConfig | None:
        """Return the project-type override settings for the given kind."""
        overrides = self._tool_config.project_type_overrides
        kind_map: t.MappingKV[str, m.Infra.ProjectTypeOverrideConfig] = {
            "core": overrides.core,
            "domain": overrides.domain,
            "platform": overrides.platform,
            "integration": overrides.integration,
            "app": overrides.app,
        }
        raw = kind_map.get(project_kind)
        if raw is None:
            return None
        validated: m.Infra.ProjectTypeOverrideConfig = (
            m.Infra.ProjectTypeOverrideConfig.model_validate(raw)
        )
        return validated

    def _expected_excludes(
        self, project_root: Path | None, analysis_exclusions: t.StrSequence
    ) -> t.StrSequence:
        """Return the complete config-owned Pyright exclude list."""
        rules = self._tool_config.tools.pyright.path_rules
        workspace_excludes: t.StrSequence = ()
        if project_root is not None:
            excluded = FlextInfraWorkspaceDetector.analysis_exclusion_paths(
                project_root
            )
            if excluded.failure:
                raise ValueError(
                    excluded.error or "workspace analysis scope is unavailable"
                )
            workspace_excludes = tuple(path.as_posix() for path in excluded.value)
        return sorted({
            *rules.default_excludes,
            *workspace_excludes,
            *analysis_exclusions,
        })

    def _existing_paths(
        self, base_dir: Path | None, configured_paths: t.StrSequence
    ) -> t.StrSequence:
        """Existing paths."""
        if base_dir is None:
            return ()
        existing: t.StrSequence = [
            relative_path
            for relative_path in configured_paths
            if (base_dir / relative_path).is_dir()
        ]
        return existing

    def _expected_ignores(
        self, *, is_root: bool, workspace_root: Path | None, project_dir: Path | None
    ) -> t.StrSequence:
        """Ignore typings and stub diagnostics."""
        rules = self._tool_config.tools.pyright.path_rules
        ignores: t.MutableSequenceOf[str] = []
        if is_root:
            root_dir = workspace_root or project_dir
            ignores.extend(self._existing_paths(root_dir, rules.root_typings_paths))
        else:
            ignores.extend(
                self._existing_paths(project_dir, rules.project_typings_paths)
            )
        for pattern in rules.ignored_diagnostic_globs:
            if pattern not in ignores:
                ignores.append(pattern)
        return list(ignores)

    def _expected_includes(
        self, *, is_root: bool, workspace_root: Path | None, project_dir: Path | None
    ) -> t.StrSequence:
        """Return the auto-discovered top-level Python roots that pyright should analyze."""
        rules = self._tool_config.tools.pyright.path_rules
        # u.Infra.analyzer_python_roots is the single owner shared with conform
        # and the extra-paths sync, so a root one surface writes is never erased
        # by the next. It skips directories owning a pyproject.toml, so the
        # workspace members the child loop below contributes with their own
        # prefix are never duplicated as roots of this project.
        if not is_root:
            if project_dir is None:
                return list(rules.env_dirs)
            return list(
                u.Infra.analyzer_python_roots(
                    project_dir,
                    tuple(
                        env_dir
                        for env_dir in rules.env_dirs
                        if (project_dir / env_dir).is_dir()
                        and any((project_dir / env_dir).rglob(c.Infra.EXT_PYTHON_GLOB))
                    ),
                )
            )
        if workspace_root is None:
            return ()
        includes: t.MutableSequenceOf[str] = list(
            u.Infra.analyzer_python_roots(
                workspace_root,
                tuple(
                    env_dir
                    for env_dir in rules.env_dirs
                    if (workspace_root / env_dir).is_dir()
                    and any((workspace_root / env_dir).rglob(c.Infra.EXT_PYTHON_GLOB))
                ),
            )
        )
        discovered = u.Infra.discover_projects(workspace_root)
        if discovered.failure:
            return includes
        child_projects = sorted(
            (
                project.path
                for project in discovered.value
                if (
                    project.workspace_role
                    == c.Infra.WorkspaceProjectRole.WORKSPACE_MEMBER
                )
            ),
            key=lambda project_path: project_path.name,
        )
        for child_project in child_projects:
            relative_root = child_project.relative_to(workspace_root)
            for env_dir in u.Infra.discover_python_dirs(child_project):
                includes.append((relative_root / env_dir).as_posix())
        return includes

    def _phase(
        self,
        *,
        is_root: bool,
        workspace_root: Path | None = None,
        project_dir: Path | None = None,
        project_kind: str = "core",
        paths_manager: FlextInfraExtraPathsManager | None = None,
        declared_python_dirs: t.StrSequence = (),
        declared_python_dirs_are_complete: bool = False,
        analysis_exclusions: t.StrSequence = (),
    ) -> m.Infra.Deps.Toml.PhaseConfig:
        """Build the managed pyright phase for one project context."""
        project_root = workspace_root if is_root else project_dir
        expected_excludes = self._expected_excludes(project_root, analysis_exclusions)
        expected_ignores = self._expected_ignores(
            is_root=is_root, workspace_root=workspace_root, project_dir=project_dir
        )
        expected_includes = (
            declared_python_dirs
            if declared_python_dirs_are_complete
            else self._expected_includes(
                is_root=is_root, workspace_root=workspace_root, project_dir=project_dir
            )
        )
        stub_rules = self._tool_config.tools.pyright.path_rules
        expected_stub_path: str | None = (
            stub_rules.root_typings_paths[0]
            if is_root and stub_rules.root_typings_paths
            else (
                stub_rules.project_typings_paths[0]
                if stub_rules.project_typings_paths
                else None
            )
        )
        if declared_python_dirs_are_complete:
            expected_envs = (
                self._declared_envs(
                    declared_python_dirs=declared_python_dirs,
                    project_dir=project_dir,
                    rules=stub_rules,
                )
                if declared_python_dirs
                else ()
            )
        else:
            expected_envs = self._expected_envs(
                is_root=is_root, workspace_root=workspace_root, project_dir=project_dir
            )
        phase_builder = m.Infra.Deps.Toml.PhaseConfig.Builder("pyright").table(
            c.Infra.PYRIGHT
        )
        if expected_excludes:
            phase_builder = phase_builder.list(c.Infra.EXCLUDE, expected_excludes)
        else:
            phase_builder = phase_builder.deprecated(c.Infra.EXCLUDE)
        if expected_ignores:
            phase_builder = phase_builder.list(c.Infra.IGNORE, expected_ignores)
        else:
            phase_builder = phase_builder.deprecated(c.Infra.IGNORE)
        if declared_python_dirs_are_complete and not expected_includes:
            phase_builder = phase_builder.value("include", [])
        elif expected_includes:
            phase_builder = phase_builder.list("include", expected_includes)
        else:
            phase_builder = phase_builder.deprecated("include")
        if project_root is not None and paths_manager is not None:
            phase_builder = phase_builder.list(
                "extraPaths",
                paths_manager.pyright_extra_paths(
                    project_dir=project_root, is_root=is_root
                ),
            )
        if expected_stub_path is not None:
            existing = project_root / expected_stub_path if project_root else None
            if existing is not None and existing.is_dir():
                phase_builder = phase_builder.value("stubPath", expected_stub_path)
            else:
                phase_builder = phase_builder.deprecated("stubPath")
        else:
            phase_builder = phase_builder.deprecated("stubPath")
        phase_builder = phase_builder.deprecated("venv").deprecated(c.Infra.VENV_PATH)
        phase_builder = phase_builder.value(
            "executionEnvironments",
            [
                u.normalize_to_json_value(self._environment_payload(expected_env))
                for expected_env in expected_envs
            ],
        )
        if is_root:
            for key, value in self._tool_config.tools.pyright.strict_settings.items():
                phase_builder = phase_builder.value(key, value)
            for key, value in self._tool_config.tools.pyright.extended_settings.items():
                phase_builder = phase_builder.value(key, value)
            return phase_builder.build()
        for key, value in self._tool_config.tools.pyright.strict_settings.items():
            phase_builder = phase_builder.value(key, value)
        merged_settings: t.MutableStrMapping = {
            **self._tool_config.tools.pyright.extended_settings
        }
        override = self._override_for_kind(project_kind)
        if override is not None:
            merged_settings.update(override.pyright)
        for key, value in merged_settings.items():
            phase_builder = phase_builder.value(key, value)
        return phase_builder.build()

    def apply(
        self,
        doc: t.Cli.TomlDocument,
        *,
        is_root: bool,
        workspace_root: Path | None = None,
        project_dir: Path | None = None,
        project_kind: str = "core",
        paths_manager: FlextInfraExtraPathsManager | None = None,
        declared_python_dirs: t.StrSequence = (),
        declared_python_dirs_are_complete: bool = False,
        analysis_exclusions: t.StrSequence = (),
    ) -> t.StrSequence:
        """Apply the managed pyright configuration for one TOML document."""
        return FlextInfraTomlPhaseService.apply_phases(
            doc,
            self._phase(
                is_root=is_root,
                workspace_root=workspace_root,
                project_dir=project_dir,
                project_kind=project_kind,
                paths_manager=paths_manager,
                declared_python_dirs=declared_python_dirs,
                declared_python_dirs_are_complete=declared_python_dirs_are_complete,
                analysis_exclusions=analysis_exclusions,
            ),
        )

    def apply_payload(
        self,
        payload: t.MutableJsonMapping,
        *,
        is_root: bool,
        workspace_root: Path | None = None,
        project_dir: Path | None = None,
        project_kind: str = "core",
        paths_manager: FlextInfraExtraPathsManager | None = None,
        declared_python_dirs: t.StrSequence = (),
        declared_python_dirs_are_complete: bool = False,
        analysis_exclusions: t.StrSequence = (),
    ) -> t.StrSequence:
        """Apply managed pyright settings directly to one normalized payload."""
        return FlextInfraTomlPhaseService.apply_payload_phases(
            payload,
            self._phase(
                is_root=is_root,
                workspace_root=workspace_root,
                project_dir=project_dir,
                project_kind=project_kind,
                paths_manager=paths_manager,
                declared_python_dirs=declared_python_dirs,
                declared_python_dirs_are_complete=declared_python_dirs_are_complete,
                analysis_exclusions=analysis_exclusions,
            ),
        )


__all__: list[str] = ["FlextInfraEnsurePyrightConfigPhase"]
