"""Phase: mirror every config-owned tool table whose shape is pure policy data.

pytest, mypy, pydantic-mypy, codespell, hatch metadata, tomlsort, yamlfix,
deptry namespaces, vulture, and coverage share one behavior: each table is a
direct projection of ``config.Infra.tooling``. One declarative phase set owns
them so no per-tool class re-implements the same apply contract.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, m, t, u


class FlextInfraToolTablesPhase:
    """Apply the config-owned policy tables to one normalized payload."""

    def __init__(self, tool_config: m.Infra.ToolConfigDocument) -> None:
        """Capture the canonical tooling document projected into each table."""
        self._tool_config = tool_config

    @staticmethod
    def first_party_namespaces(project_dir: Path) -> t.StrSequence:
        """Derive the project's first-party namespaces from one source each.

        The config-owned base namespaces, the live packages under ``src/``
        (never a name invented from the distribution), and, for a workspace
        root, the packages of the subprojects it declares. Ruff's projected
        known-first-party and the lazy-init renderer both read this owner.

        Returns:
            The sorted first-party namespaces.

        """
        return sorted({
            *config.Infra.tooling.tools.deptry.known_first_party,
            *u.Infra.discover_first_party_namespaces(project_dir),
            *FlextInfraToolTablesPhase._workspace_project_namespaces(project_dir),
        })

    @staticmethod
    def _workspace_project_namespaces(project_dir: Path) -> t.StrSequence:
        """Discover child project packages when generating repository root settings.

        Returns:
            The resulting ``t.StrSequence``.

        Raises:
            ValueError: If ``discovered.failure``.

        """
        if not (project_dir / c.PYPROJECT_FILENAME).is_file():
            return ()
        discovered = u.Infra.discover_projects(project_dir)
        if discovered.failure:
            # A real discovery error (malformed pyproject, IO) must never
            # silently generate root Ruff settings with an empty child-package
            # list — that conformed artifact would drift from the workspace
            # with no signal. Mirrors _workspace_exclusion_globs fail-loud.
            raise ValueError(
                discovered.error or "workspace project discovery is unavailable",
            )
        return sorted({
            project.package_name
            for project in discovered.value
            if (
                project.package_name
                and project.package_name.isidentifier()
                and project.declared_subproject
            )
        })

    def _mypy_phase(self) -> m.Infra.DepsToml.PhaseConfig:
        """Declare the mypy table from toolchain and config-owned policy.

        Returns:
            The resulting ``m.Infra.DepsToml.PhaseConfig``.

        """
        mypy = self._tool_config.tools.mypy
        toml = m.Infra.DepsToml
        replace = c.Infra.TomlMergeMode.REPLACE
        operations: t.MutableSequenceOf[
            m.Infra.DepsToml.SetOp | m.Infra.DepsToml.ListOp | m.Infra.DepsToml.RemoveOp
        ] = [
            toml.RemoveOp(key="strict_concatenate"),
            toml.SetOp(
                key=c.Infra.PYTHON_VERSION_UNDERSCORE,
                value=config.Infra.codegen.toolchain.python_version,
            ),
            toml.ListOp(key=c.Infra.PLUGINS, values=mypy.plugins, strategy=replace),
        ]
        operations.append(
            toml.SetOp(
                key="overrides",
                value=u.normalize_to_json_value([
                    {
                        "module": list(entry.modules),
                        "follow_untyped_imports": entry.follow_untyped_imports,
                    }
                    for entry in mypy.overrides
                ]),
            ),
        )
        settings: t.MappingKV[str, t.JsonValue] = {
            **mypy.boolean_settings,
            **mypy.string_settings,
        }
        operations.extend(
            toml.SetOp(key=key, value=setting) for key, setting in settings.items()
        )
        return toml.PhaseConfig(
            name="mypy",
            table_path=(c.Infra.MYPY,),
            operations=tuple(operations),
        )

    @staticmethod
    def excluded_roots(project_dir: Path) -> frozenset[str]:
        """First segments of the workspace manifest's declared non-participants.

        A workspace that retired a tree declares it once in its manifest
        (``exclusions``, ``content_only`` or ``external_dependency_paths``);
        every root-scoped projection (vulture paths, ruff src/namespace-
        packages/per-file-ignores) filters on this declared set instead of
        probing the disk, which oscillates between the deps pass and the
        root-materializing gen pass. An invalid manifest fails loud.

        Returns:
            The resulting ``frozenset[str]``.

        """
        return frozenset(
            Path(path).parts[0]
            for path in u.Infra.manifest_nonparticipant_paths(project_dir.resolve())
        )

    def _phases(
        self,
        *,
        first_party: t.StrSequence,
        path: Path,
    ) -> t.SequenceOf[m.Infra.DepsToml.PhaseConfig]:
        """Build every policy table; coverage is measured, never floor-gated.

        Returns:
            The resulting ``t.SequenceOf[m.Infra.DepsToml.PhaseConfig]``.

        """
        tools = self._tool_config.tools
        toml = m.Infra.DepsToml
        merge, replace = c.Infra.TomlMergeMode.MERGE, c.Infra.TomlMergeMode.REPLACE
        pytest, coverage = tools.pytest, tools.coverage
        excluded_roots = self.excluded_roots(path.parent)
        codespell_operations: t.MutableSequenceOf[
            m.Infra.DepsToml.SetOp | m.Infra.DepsToml.RemoveOp
        ] = [
            toml.SetOp(key="check-filenames", value=tools.codespell.check_filenames),
            toml.RemoveOp(key="skip"),
        ]
        if tools.codespell.ignore_words_list:
            codespell_operations.append(
                toml.SetOp(
                    key="ignore-words-list",
                    value=tools.codespell.ignore_words_list,
                ),
            )
        return (
            toml.PhaseConfig(
                name="pytest",
                table_path=(c.Infra.PYTEST, c.Infra.INI_OPTIONS),
                operations=(
                    toml.SetOp(key=c.Infra.MINVERSION, value=pytest.min_version),
                    toml.SetOp(
                        key=c.Infra.FLEXT_SLOW_TIMEOUT_SECONDS,
                        value=str(pytest.slow_timeout_seconds),
                    ),
                    toml.SetOp(
                        key=c.Infra.ASYNCIO_DEFAULT_FIXTURE_LOOP_SCOPE,
                        value=pytest.asyncio_default_fixture_loop_scope,
                    ),
                    toml.ListOp(
                        key=c.Infra.PYTHON_CLASSES,
                        values=pytest.python_classes,
                        strategy=merge,
                    ),
                    toml.ListOp(
                        key=c.Infra.PYTHON_FILES,
                        values=pytest.python_files,
                        strategy=merge,
                    ),
                    toml.ListOp(
                        key="testpaths",
                        values=pytest.test_paths,
                        strategy=replace,
                    ),
                    toml.ListOp(
                        key=c.Infra.ADDOPTS,
                        values=(
                            *pytest.standard_addopts,
                            f"--timeout={pytest.case_timeout_seconds}",
                        ),
                        strategy=replace,
                    ),
                    toml.ListOp(
                        key=c.Infra.MARKERS,
                        values=pytest.standard_markers,
                        strategy=merge,
                    ),
                    toml.ListOp(
                        key="filterwarnings",
                        values=pytest.filter_warnings,
                        strategy=replace,
                    ),
                ),
            ),
            self._mypy_phase(),
            toml.PhaseConfig(
                name="pydantic-mypy",
                table_path=("pydantic-mypy",),
                operations=(
                    toml.SetOp(
                        key="init_forbid_extra",
                        value=tools.pydantic_mypy.init_forbid_extra,
                    ),
                    toml.SetOp(key="init_typed", value=tools.pydantic_mypy.init_typed),
                    toml.SetOp(
                        key="warn_required_dynamic_aliases",
                        value=tools.pydantic_mypy.warn_required_dynamic_aliases,
                    ),
                    toml.RemoveOp(key="warn_untyped_fields"),
                ),
            ),
            toml.PhaseConfig(
                name="codespell",
                table_path=("codespell",),
                operations=tuple(codespell_operations),
            ),
            toml.PhaseConfig(
                name="hatch",
                table_path=("hatch", "metadata"),
                operations=(
                    toml.SetOp(
                        key="allow-direct-references",
                        value=tools.hatch.allow_direct_references,
                    ),
                ),
            ),
            toml.PhaseConfig(
                name="tomlsort",
                table_path=("tomlsort",),
                operations=(
                    toml.SetOp(key="all", value=tools.tomlsort.all),
                    toml.SetOp(key="in_place", value=tools.tomlsort.in_place),
                    toml.ListOp(key="sort_first", values=tools.tomlsort.sort_first),
                ),
            ),
            toml.PhaseConfig(
                name="yamlfix",
                table_path=("yamlfix",),
                operations=(
                    toml.SetOp(key="line_length", value=tools.yamlfix.line_length),
                    toml.SetOp(
                        key="preserve_quotes",
                        value=tools.yamlfix.preserve_quotes,
                    ),
                    toml.SetOp(key="whitelines", value=tools.yamlfix.whitelines),
                    toml.SetOp(
                        key="section_whitelines",
                        value=tools.yamlfix.section_whitelines,
                    ),
                    toml.SetOp(
                        key="explicit_start",
                        value=tools.yamlfix.explicit_start,
                    ),
                ),
            ),
            toml.PhaseConfig(
                name="namespace-tooling",
                table_path=(c.Infra.DEPTRY,),
                operations=(
                    toml.ListOp(
                        key=c.Infra.KNOWN_FIRST_PARTY_UNDERSCORE,
                        values=first_party,
                    ),
                ),
            ),
            toml.PhaseConfig(
                name="vulture",
                table_path=("vulture",),
                operations=(
                    toml.RemoveOp(key="min-confidence"),
                    toml.ListOp(key="exclude", values=tools.vulture.exclude),
                    toml.SetOp(
                        key="min_confidence",
                        value=tools.vulture.min_confidence,
                    ),
                    # Production roots are config-declared; a workspace that
                    # retired a tree (analysis exclusion in its SSOT) must not
                    # stay in the dead-code scan scope.
                    toml.ListOp(
                        key="paths",
                        values=tuple(
                            root
                            for root in tools.vulture.paths
                            if root not in excluded_roots
                        ),
                    ),
                    toml.SetOp(key="verbose", value=tools.vulture.verbose),
                ),
            ),
            toml.PhaseConfig(
                name="coverage-report",
                table_path=("coverage", "report"),
                operations=(
                    toml.RemoveOp(key="fail_under"),
                    toml.SetOp(key="show_missing", value=coverage.show_missing),
                    toml.SetOp(key="skip_covered", value=coverage.skip_covered),
                    toml.SetOp(key="precision", value=coverage.precision),
                    toml.ListOp(
                        key="exclude_also",
                        values=sorted(set(coverage.exclude_also)),
                    ),
                ),
            ),
            toml.PhaseConfig(
                name="coverage-run",
                table_path=("coverage", "run"),
                operations=(
                    toml.ListOp(key="source", values=coverage.source),
                    toml.ListOp(key="omit", values=sorted(set(coverage.omit))),
                ),
            ),
        )

    def apply_payload(
        self,
        payload: t.MutableJsonMapping,
        *,
        path: Path,
    ) -> t.StrSequence:
        """Apply every policy table to one normalized payload.

        Returns:
            The resulting ``t.StrSequence``.

        """
        return u.Infra.apply_toml_phases(
            payload,
            *self._phases(
                first_party=self.first_party_namespaces(path.parent),
                path=path.parent,
            ),
        )


__all__: list[str] = ["FlextInfraToolTablesPhase"]
