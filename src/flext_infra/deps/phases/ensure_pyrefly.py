"""Phase: Ensure standard Pyrefly configuration for max-strict typing.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, m, t, u

if TYPE_CHECKING:
    from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager


class FlextInfraEnsurePyreflyConfigPhase:
    """Ensure standard Pyrefly configuration for max-strict typing."""

    def __init__(self, tool_config: m.Infra.ToolConfigDocument) -> None:
        """Store tool configuration used when enforcing pyrefly project settings."""
        self._tool_config = tool_config

    def _phase(
        self,
        *,
        context: m.Infra.PyprojectAnalyzerContext,
        paths_manager: FlextInfraExtraPathsManager | None,
        stale_error_keys: t.StrSequence,
    ) -> m.Infra.DepsToml.PhaseConfig:
        """Build the canonical pyrefly phase definition.

        Returns:
            The resulting ``m.Infra.DepsToml.PhaseConfig``.

        """
        pyrefly_rules = self._tool_config.tools.pyrefly
        path_rules = pyrefly_rules.path_rules
        project_dir = context.project_dir
        declared_python_dirs = context.declared_python_dirs
        if project_dir is not None and paths_manager is not None:
            expected_search: t.StrSequence = paths_manager.pyrefly_search_paths(
                project_dir=project_dir,
                is_root=context.is_root,
            )
            expected_includes: t.StrSequence = paths_manager.pyrefly_project_includes(
                project_dir=project_dir,
                is_root=context.is_root,
            )
        else:
            expected_search = [c.Infra.DEFAULT_SRC_DIR]
            expected_includes = [f"{c.Infra.DEFAULT_SRC_DIR}/**/*.py*"]
        # Keep pre-write Pyrefly scope identical to the first
        # post-write discovery without fabricating directories on disk.
        if context.declared_python_dirs_are_complete:
            declared_import_roots = (
                (path_rules.source_dir,)
                if path_rules.source_dir in declared_python_dirs
                else ()
            )
            # Why (fleet-wide fix): sorted({...}) places "."
            # before "src" (ASCII '.' < 's'), so pyrefly resolves every
            # module twice (pkg.X via src AND src.pkg.X via "."),
            # producing phantom bad-argument-type errors. The declared
            # source import root must stay first; everything else (typically
            # ".", for tests.* resolution) sorts after it.
            merged_search = {
                *expected_search,
                *path_rules.project_shared_search_paths,
                path_rules.project_root,
            }
            if not declared_import_roots:
                merged_search.discard(path_rules.source_dir)
            merged_search.difference_update(declared_import_roots)
            expected_search = [*declared_import_roots, *sorted(merged_search)]
            # Analysis roots belong in
            # project-includes; only import roots belong in search-path.
            expected_includes = tuple(
                f"{directory}/**/*.py*" for directory in declared_python_dirs
            )
        toml = m.Infra.DepsToml
        return toml.PhaseConfig(
            name="pyrefly",
            table_path=(c.Infra.PYREFLY,),
            operations=(
                toml.SetOp(
                    key=c.Infra.PYTHON_VERSION_HYPHEN,
                    value=pyrefly_rules.python_version,
                ),
                toml.RemoveOp(key="python-interpreter-path"),
                toml.RemoveOp(key="disable-search-path-heuristics"),
                toml.RemoveOp(key="fallback-python-interpreter-name"),
                # Interpreter discovery resolves PEP 660 editable siblings.
                toml.RemoveOp(key="site-package-path"),
                toml.RemoveOp(key="skip-interpreter-query"),
                toml.RemoveOp(key="ignore-errors-in-generated-code"),
                # Search-path order is semantic; never sort this operation.
                toml.ListOp(
                    key=c.Infra.SEARCH_PATH,
                    values=expected_search,
                    sort=False,
                ),
                (
                    toml.SetOp(key=c.Infra.PROJECT_INCLUDES, value=[])
                    if context.declared_python_dirs_are_complete
                    and not expected_includes
                    else toml.ListOp(
                        key=c.Infra.PROJECT_INCLUDES,
                        values=expected_includes,
                    )
                ),
                toml.SetOp(
                    key="disable-project-excludes-heuristics",
                    value=pyrefly_rules.disable_project_excludes_heuristics,
                ),
                toml.SetOp(
                    key="use-ignore-files",
                    value=pyrefly_rules.use_ignore_files,
                ),
                toml.ListOp(
                    key=c.Infra.PROJECT_EXCLUDES,
                    values=u.Infra.pyrefly_project_excludes(
                        pyrefly_rules.project_exclude_globs,
                    ),
                ),
            ),
            nested_tables=(
                toml.PhaseConfig(
                    name="pyrefly",
                    root_path=(),
                    table_path=("errors",),
                    operations=(
                        *(
                            toml.SetOp(key=error_rule, value="error")
                            for error_rule in pyrefly_rules.strict_errors
                        ),
                        *(
                            toml.RemoveOp(key=error_rule)
                            for error_rule in stale_error_keys
                        ),
                    ),
                ),
            ),
        )

    def apply_payload(
        self,
        payload: t.MutableJsonMapping,
        *,
        context: m.Infra.PyprojectAnalyzerContext,
        paths_manager: FlextInfraExtraPathsManager | None = None,
    ) -> t.StrSequence:
        """Apply canonical pyrefly settings to one normalized payload.

        Returns:
            The resulting ``t.StrSequence``.

        """
        configured_error_keys = frozenset(self._tool_config.tools.pyrefly.strict_errors)
        errors_table = u.Cli.toml_mapping_path(
            payload,
            (c.Infra.TOOL, c.Infra.PYREFLY, "errors"),
        )
        return u.Infra.apply_toml_phases(
            payload,
            self._phase(
                context=context,
                paths_manager=paths_manager,
                stale_error_keys=tuple(
                    key
                    for key in errors_table or ()
                    if key not in configured_error_keys
                ),
            ),
        )


__all__: list[str] = ["FlextInfraEnsurePyreflyConfigPhase"]
