"""Phase: Ensure standard Pyright configuration for strict type checking.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, config, m, t, u
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
        """Apply the configured privacy policy for each declared root category.

        Returns:
            The resulting ``str``.

        """
        effective_rules = rules or self._tool_config.tools.pyright.path_rules
        if env_dir == effective_rules.source_dir:
            source_report: str = effective_rules.source_report_private_usage
            return source_report
        if env_dir in effective_rules.test_like_dirs:
            test_report: str = effective_rules.test_like_report_private_usage
            return test_report
        other_report: str = effective_rules.other_report_private_usage
        return other_report

    def _env_entry(
        self,
        *,
        env_dir: str,
        root: str,
        extra_paths: t.StrSequence,
        rules: m.Infra.PyrightConfig.PathRulesConfig,
    ) -> m.Infra.PyrightConfig.ExecutionEnvironment:
        """Env entry.

        Returns:
            The resulting ``m.Infra.PyrightConfig.ExecutionEnvironment``.

        """
        return m.Infra.PyrightConfig.ExecutionEnvironment(
            root=root,
            report_private_usage=self._report_private_usage_for_env(
                env_dir,
                rules=rules,
            ),
            extra_paths=[*extra_paths],
        )

    @staticmethod
    def _extra_paths_for_env(
        *,
        env_dir: str,
        source_path: str,
        project_root: str,
        source_dir: str,
        member_src_paths: t.SequenceOf[str] = (),
    ) -> t.StrSequence:
        """``src/`` owns only its path; other dirs also import from src + root.

        Returns:
            The resulting ``t.StrSequence``.

        """
        if env_dir == source_dir:
            paths = [source_path]
        elif source_path != project_root:
            paths = [project_root, source_path]
        else:
            paths = [project_root]
        return [*paths, *member_src_paths]

    def _envs_for_dirs(
        self,
        *,
        env_dirs: t.StrSequence,
        source_path: str,
        project_root: str,
        rules: m.Infra.PyrightConfig.PathRulesConfig,
    ) -> t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]:
        """Envs for dirs.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]``.

        """
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

    def _diagnostic_override_envs(
        self,
        *,
        project_dir: Path | None,
        root_prefix: Path | None,
        source_path: str,
    ) -> t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]:
        """Resolve configured overrides only when their project path exists.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]``.

        """
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
                ),
            )
        return tuple(environments)

    def _project_source_path(self, *, prefix: str = "") -> str:
        """Project source path.

        Returns:
            The resulting ``str``.

        """
        rules = self._tool_config.tools.pyright.path_rules
        return f"{prefix}/{rules.source_dir}" if prefix else rules.source_dir

    def _expected_envs(
        self,
        *,
        is_root: bool,
        repository_root: Path | None,
        project_dir: Path | None,
        project_roots: t.StrSequence,
    ) -> t.SequenceOf[m.Infra.PyrightConfig.ExecutionEnvironment]:
        """Return the expected execution environments.

        Returns:
            The expected execution environments.

        """
        if not is_root or repository_root is None:
            rules = self._tool_config.tools.pyright.path_rules
            return (
                *self._diagnostic_override_envs(
                    project_dir=project_dir,
                    root_prefix=None,
                    source_path=self._project_source_path(),
                ),
                *self._envs_for_dirs(
                    env_dirs=project_roots,
                    source_path=self._project_source_path(),
                    project_root=rules.project_root,
                    rules=rules,
                ),
            )
        rules = self._tool_config.tools.pyright.path_rules
        expected_envs: t.MutableSequenceOf[
            m.Infra.PyrightConfig.ExecutionEnvironment
        ] = []
        root_source_path = self._project_source_path()
        member_src_paths = tuple(
            f"{member}/src"
            for member in u.Infra.workspace_project_paths(repository_root)
        )
        # Specific roots precede the broad source environment.
        expected_envs.extend(
            self._diagnostic_override_envs(
                project_dir=repository_root,
                root_prefix=None,
                source_path=root_source_path,
            ),
        )
        for env_dir in project_roots:
            if (repository_root / env_dir / c.PYPROJECT_FILENAME).is_file():
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
                        member_src_paths=member_src_paths,
                    ),
                    rules=rules,
                ),
            )
        return expected_envs

    def environment_payloads_for_dirs(
        self,
        env_dirs: t.StrSequence,
    ) -> t.SequenceOf[t.JsonDict]:
        """Render configured environments for Python roots declared before writes.

        Returns:
            The resulting ``t.SequenceOf[t.JsonDict]``.

        """
        rules = self._tool_config.tools.pyright.path_rules
        environments = self._envs_for_dirs(
            env_dirs=self._declared_environment_dirs(env_dirs),
            source_path=self._project_source_path(),
            project_root=rules.project_root,
            rules=rules,
        )
        return tuple(self._environment_payload(item) for item in environments)

    @staticmethod
    def _declared_environment_dirs(env_dirs: t.StrSequence) -> t.StrSequence:
        """Apply canonical Python discovery exclusions to pre-write declarations.

        Returns:
            The resulting ``t.StrSequence``.

        """
        # Declared and on-disk roots must
        # select the same first-class analyzer environments in the first pass.
        return tuple(
            env_dir
            for env_dir in env_dirs
            if env_dir not in c.Infra.PYTHON_DISCOVERY_SKIP_DIRS
        )

    @staticmethod
    def _environment_payload(
        environment: m.Infra.PyrightConfig.ExecutionEnvironment,
    ) -> t.JsonDict:
        """Render one execution environment.

        Returns:
            The resulting ``t.JsonDict``.

        """
        payload: t.JsonDict = environment.model_dump(mode="json", by_alias=True)
        return payload

    def _expected_excludes(
        self,
        project_root: Path | None,
        analysis_exclusions: t.StrSequence | None,
    ) -> t.StrSequence:
        """Return the complete config-owned Pyright exclude list.

        Returns:
            The complete config-owned Pyright exclude list.

        """
        rules = self._tool_config.tools.pyright.path_rules
        workspace_excludes: t.StrSequence = ()
        if analysis_exclusions is None and project_root is not None:
            workspace_excludes = tuple(
                path.as_posix()
                for path in FlextInfraWorkspaceDetector.analysis_exclusion_paths(
                    project_root,
                ).unwrap()
            )
        provided_exclusions = () if analysis_exclusions is None else analysis_exclusions
        return sorted({
            *rules.default_excludes,
            *config.Infra.codegen.generated_source_globs,
            *workspace_excludes,
            *provided_exclusions,
        })

    @staticmethod
    def _existing_paths(
        base_dir: Path | None,
        configured_paths: t.StrSequence,
    ) -> t.StrSequence:
        """Existing paths.

        Returns:
            The resulting ``t.StrSequence``.

        """
        if base_dir is None:
            return ()
        existing: t.StrSequence = [
            relative_path
            for relative_path in configured_paths
            if (base_dir / relative_path).is_dir()
        ]
        return existing

    def _expected_ignores(
        self,
        *,
        is_root: bool,
        repository_root: Path | None,
        project_dir: Path | None,
    ) -> t.StrSequence:
        """Ignore typings and stub diagnostics.

        Returns:
            The resulting ``t.StrSequence``.

        """
        rules = self._tool_config.tools.pyright.path_rules
        ignores: t.MutableSequenceOf[str] = []
        if is_root:
            root_dir = repository_root or project_dir
            ignores.extend(self._existing_paths(root_dir, rules.root_typings_paths))
        else:
            ignores.extend(
                self._existing_paths(project_dir, rules.project_typings_paths),
            )
        for pattern in rules.ignored_diagnostic_globs:
            if pattern not in ignores:
                ignores.append(pattern)
        return list(ignores)

    def _expected_project_roots(
        self,
        *,
        context: m.Infra.PyprojectAnalyzerContext,
        paths_manager: FlextInfraExtraPathsManager | None,
    ) -> t.StrSequence:
        """Resolve the one analyzer-root set consumed by includes and environments.

        Returns:
            The resulting ``t.StrSequence``.

        """
        generated_roots = (
            paths_manager.generated_python_roots if paths_manager is not None else ()
        )
        declared = self._declared_environment_dirs(
            tuple(dict.fromkeys((*context.declared_python_dirs, *generated_roots))),
        )
        repository_root = context.repository_root
        if (
            context.is_root
            and repository_root is not None
            and (repository_root / c.Infra.GITMODULES).is_file()
        ):
            return u.Infra.analyzer_python_roots(
                repository_root,
                generated_roots,
                workspace_excluded_top_dirs=(
                    paths_manager.analysis_excluded_top_dirs
                    if paths_manager is not None
                    else FlextInfraWorkspaceDetector.analysis_excluded_top_dirs(
                        repository_root,
                    ).unwrap()
                ),
            )
        if context.declared_python_dirs_are_complete:
            return declared
        if context.project_dir is not None:
            return u.Infra.analyzer_python_roots(
                context.project_dir,
                declared,
                workspace_excluded_top_dirs=(
                    paths_manager.analysis_excluded_top_dirs
                    if paths_manager is not None
                    else FlextInfraWorkspaceDetector.analysis_excluded_top_dirs(
                        context.project_dir,
                    ).unwrap()
                ),
            )
        if declared:
            return declared
        return self._tool_config.tools.pyright.path_rules.env_dirs

    def _phase(
        self,
        *,
        context: m.Infra.PyprojectAnalyzerContext,
        paths_manager: FlextInfraExtraPathsManager | None,
        analysis_exclusions: t.StrSequence | None,
    ) -> m.Infra.DepsToml.PhaseConfig:
        """Build the managed pyright phase for one project context.

        Returns:
            The resulting ``m.Infra.DepsToml.PhaseConfig``.

        """
        is_root = context.is_root
        repository_root, project_dir = context.repository_root, context.project_dir
        project_root = repository_root if is_root else project_dir
        expected_excludes = self._expected_excludes(project_root, analysis_exclusions)
        expected_ignores = self._expected_ignores(
            is_root=is_root,
            repository_root=repository_root,
            project_dir=project_dir,
        )
        expected_roots = self._expected_project_roots(
            context=context,
            paths_manager=paths_manager,
        )
        # Include only the Python roots owned by the selected project manifest.
        expected_includes = list(expected_roots)
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
        expected_envs = self._expected_envs(
            is_root=is_root,
            repository_root=repository_root,
            project_dir=project_dir,
            project_roots=expected_roots,
        )
        toml = m.Infra.DepsToml
        operations: t.MutableSequenceOf[
            m.Infra.DepsToml.SetOp | m.Infra.DepsToml.ListOp | m.Infra.DepsToml.RemoveOp
        ] = [
            toml.ListOp(key=c.Infra.EXCLUDE, values=expected_excludes)
            if expected_excludes
            else toml.RemoveOp(key=c.Infra.EXCLUDE),
            toml.ListOp(key=c.Infra.IGNORE, values=expected_ignores)
            if expected_ignores
            else toml.RemoveOp(key=c.Infra.IGNORE),
            toml.ListOp(key="include", values=expected_includes)
            if expected_includes
            else toml.RemoveOp(key="include"),
        ]
        if project_root is not None and paths_manager is not None:
            operations.append(
                toml.ListOp(
                    key="extraPaths",
                    values=paths_manager.pyright_extra_paths(
                        project_dir=project_root,
                        is_root=is_root,
                    ),
                ),
            )
        if expected_stub_path is not None:
            existing = project_root / expected_stub_path if project_root else None
            if existing is not None and existing.is_dir():
                operations.append(toml.SetOp(key="stubPath", value=expected_stub_path))
            else:
                operations.append(toml.RemoveOp(key="stubPath"))
        else:
            operations.append(toml.RemoveOp(key="stubPath"))
        operations.extend((
            toml.RemoveOp(key="venv"),
            toml.RemoveOp(key=c.Infra.VENV_PATH),
            toml.SetOp(
                key="executionEnvironments",
                value=[
                    u.normalize_to_json_value(self._environment_payload(expected_env))
                    for expected_env in expected_envs
                ],
            ),
        ))
        operations.extend(
            toml.SetOp(key=key, value=value)
            for settings in (
                self._tool_config.tools.pyright.strict_settings,
                self._tool_config.tools.pyright.extended_settings,
            )
            for key, value in settings.items()
        )
        return toml.PhaseConfig(
            name="pyright",
            table_path=(c.Infra.PYRIGHT,),
            operations=tuple(operations),
        )

    def apply_payload(
        self,
        payload: t.MutableJsonMapping,
        *,
        context: m.Infra.PyprojectAnalyzerContext,
        paths_manager: FlextInfraExtraPathsManager | None = None,
        analysis_exclusions: t.StrSequence | None = None,
    ) -> t.StrSequence:
        """Apply managed pyright settings directly to one normalized payload.

        Returns:
            The resulting ``t.StrSequence``.

        """
        return u.Infra.apply_toml_phases(
            payload,
            self._phase(
                context=context,
                paths_manager=paths_manager,
                analysis_exclusions=analysis_exclusions,
            ),
        )


__all__: list[str] = ["FlextInfraEnsurePyrightConfigPhase"]
