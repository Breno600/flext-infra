"""Phase: mirror every config-owned tool table whose shape is pure policy data.

pytest, mypy, pydantic-mypy, codespell, hatch metadata, tomlsort, yamlfix,
deptry namespaces, vulture, and coverage share one behavior: each table is a
direct projection of ``config.Infra.tooling``. One declarative phase set owns
them so no per-tool class re-implements the same apply contract.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, config, m, t, u

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraToolTablesPhase:
    """Apply the config-owned policy tables to one normalized payload."""

    def __init__(self, tool_config: m.Infra.ToolConfigDocument) -> None:
        """Capture the canonical tooling document projected into each table."""
        self._tool_config = tool_config

    @staticmethod
    def first_party_namespaces(
        payload: t.MutableJsonMapping, *, path: Path
    ) -> t.StrSequence:
        """Return base, discovered, declared-FLEXT, and own first-party namespaces."""
        return sorted({
            *config.Infra.tooling.tools.deptry.known_first_party,
            *u.Infra.discover_first_party_namespaces(path.parent),
            *u.Infra.flext_dependency_namespaces_from_payload(payload),
            u.Infra.project_name_from_payload(path, payload).replace("-", "_"),
        })

    def _mypy_phase(self) -> m.Infra.DepsToml.PhaseConfig:
        """Build the mypy table: toolchain Python plus config-owned policy."""
        mypy = self._tool_config.tools.mypy
        replace = c.Infra.TomlMergeMode.REPLACE
        builder = (
            m.Infra.DepsToml
            .PhaseConfigBuilder("mypy")
            .table(c.Infra.MYPY)
            .deprecated("strict_concatenate")
            .value(
                c.Infra.PYTHON_VERSION_UNDERSCORE,
                config.Infra.codegen.toolchain.python_version,
            )
            .list(c.Infra.PLUGINS, mypy.plugins, strategy=replace)
            .list(
                c.Infra.DISABLE_ERROR_CODE,
                sorted(mypy.disabled_error_codes),
                strategy=replace,
            )
        )
        builder = (
            builder.value(c.Infra.EXCLUDE, mypy.exclude)
            if mypy.exclude
            else builder.deprecated(c.Infra.EXCLUDE)
        )
        builder = builder.value(
            "overrides",
            u.normalize_to_json_value([
                {
                    "module": list(entry.modules),
                    "disable_error_code": list(entry.disable_error_codes),
                    "follow_untyped_imports": entry.follow_untyped_imports,
                }
                for entry in mypy.overrides
            ]),
        )
        settings: t.MappingKV[str, t.JsonValue] = {
            **mypy.boolean_settings,
            **mypy.string_settings,
        }
        for key, setting in settings.items():
            builder = builder.value(key, setting)
        return builder.build()

    def _phases(
        self, *, first_party: t.StrSequence
    ) -> t.SequenceOf[m.Infra.DepsToml.PhaseConfig]:
        """Build every policy table; coverage is measured, never floor-gated."""
        tools = self._tool_config.tools
        phase = m.Infra.DepsToml.PhaseConfigBuilder
        merge, replace = c.Infra.TomlMergeMode.MERGE, c.Infra.TomlMergeMode.REPLACE
        pytest, coverage = tools.pytest, tools.coverage
        codespell = (
            phase("codespell")
            .table("codespell")
            .value("check-filenames", tools.codespell.check_filenames)
        )
        if tools.codespell.ignore_words_list:
            codespell = codespell.value(
                "ignore-words-list", tools.codespell.ignore_words_list
            )
        return (
            phase("pytest")
            .table(c.Infra.PYTEST, c.Infra.INI_OPTIONS)
            .value(c.Infra.MINVERSION, pytest.min_version)
            .value(c.Infra.FLEXT_SLOW_TIMEOUT_SECONDS, str(pytest.slow_timeout_seconds))
            .value(
                c.Infra.ASYNCIO_DEFAULT_FIXTURE_LOOP_SCOPE,
                pytest.asyncio_default_fixture_loop_scope,
            )
            .list(c.Infra.PYTHON_CLASSES, pytest.python_classes, strategy=merge)
            .list(c.Infra.PYTHON_FILES, pytest.python_files, strategy=merge)
            .list("testpaths", pytest.test_paths, strategy=replace)
            .list(
                c.Infra.ADDOPTS,
                (*pytest.standard_addopts, f"--timeout={pytest.case_timeout_seconds}"),
                strategy=replace,
            )
            .list(c.Infra.MARKERS, pytest.standard_markers, strategy=merge)
            .list("filterwarnings", pytest.filter_warnings, strategy=replace)
            .build(),
            self._mypy_phase(),
            phase("pydantic-mypy")
            .table("pydantic-mypy")
            .value("init_forbid_extra", tools.pydantic_mypy.init_forbid_extra)
            .value("init_typed", tools.pydantic_mypy.init_typed)
            .value(
                "warn_required_dynamic_aliases",
                tools.pydantic_mypy.warn_required_dynamic_aliases,
            )
            .deprecated("warn_untyped_fields")
            .build(),
            codespell.deprecated("skip").build(),
            phase("hatch")
            .table("hatch", "metadata")
            .value("allow-direct-references", tools.hatch.allow_direct_references)
            .build(),
            phase("tomlsort")
            .table("tomlsort")
            .value("all", tools.tomlsort.all)
            .value("in_place", tools.tomlsort.in_place)
            .list("sort_first", tools.tomlsort.sort_first)
            .build(),
            phase("yamlfix")
            .table("yamlfix")
            .value("line_length", tools.yamlfix.line_length)
            .value("preserve_quotes", tools.yamlfix.preserve_quotes)
            .value("whitelines", tools.yamlfix.whitelines)
            .value("section_whitelines", tools.yamlfix.section_whitelines)
            .value("explicit_start", tools.yamlfix.explicit_start)
            .build(),
            phase("namespace-tooling")
            .table(c.Infra.DEPTRY)
            .list(c.Infra.KNOWN_FIRST_PARTY_UNDERSCORE, first_party)
            .build(),
            phase("vulture")
            .table("vulture")
            .deprecated("min-confidence")
            .list("exclude", tools.vulture.exclude)
            .value("min_confidence", tools.vulture.min_confidence)
            .list("paths", tools.vulture.paths)
            .value("verbose", tools.vulture.verbose)
            .build(),
            phase("coverage-report")
            .table("coverage", "report")
            .deprecated("fail_under")
            .value("show_missing", coverage.show_missing)
            .value("skip_covered", coverage.skip_covered)
            .value("precision", coverage.precision)
            .list("exclude_also", sorted(set(coverage.exclude_also)))
            .build(),
            phase("coverage-run")
            .table("coverage", "run")
            .list("source", coverage.source)
            .list("omit", sorted(set(coverage.omit)))
            .build(),
        )

    def apply_payload(
        self, payload: t.MutableJsonMapping, *, path: Path
    ) -> t.StrSequence:
        """Apply every policy table to one normalized payload."""
        return u.Infra.apply_toml_phases(
            payload,
            *self._phases(first_party=self.first_party_namespaces(payload, path=path)),
        )


__all__: list[str] = ["FlextInfraToolTablesPhase"]
