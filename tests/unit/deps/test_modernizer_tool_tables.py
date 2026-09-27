"""Config-owned tool table phase tests for the deps modernizer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPyprojectModernizer, FlextInfraToolTablesPhase, config
from tests import t, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import m


class TestsFlextInfraDepsModernizerToolTables:
    """Every policy table mirrors ``config.Infra.tooling`` and converges once."""

    @staticmethod
    def _applied(
        tmp_path: Path,
        source: str = "",
        *,
        tool_config: m.Infra.ToolConfigDocument | None = None,
        project_kind: str = "core",
    ) -> t.Pair[t.MutableJsonMapping, t.StrSequence]:
        """Apply the phase to one named project payload; return payload and changes."""
        project_dir = tmp_path / "flext-sample"
        (project_dir / "src" / "flext_sample").mkdir(parents=True, exist_ok=True)
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python(
            u.Tests.toml_payload(f'[project]\nname = "flext-sample"\n{source}')
        )
        changes = FlextInfraToolTablesPhase(
            tool_config or config.Infra.tooling
        ).apply_payload(
            payload, path=project_dir / "pyproject.toml", project_kind=project_kind
        )
        return payload, changes

    @staticmethod
    def _table(payload: t.JsonMapping, *path: str) -> t.JsonMapping:
        """Unwrap one nested table below ``[tool]``."""
        table = u.Tests.toml_mapping(payload["tool"])
        for segment in path:
            table = u.Tests.toml_mapping(table[segment])
        return table

    def test_mypy_table_mirrors_policy(self, tmp_path: Path) -> None:
        """Render toolchain Python plus config-owned plugins, codes, and overrides."""
        mypy_policy = config.Infra.tooling.tools.mypy
        payload, _ = self._applied(
            tmp_path,
            "[tool.mypy]\n"
            'plugins = ["custom.plugin"]\n'
            "strict_concatenate = true\n"
            'overrides = [{ module = ["legacy.*"], disable_error_code = ["misc"] }]\n',
        )
        mypy = self._table(payload, "mypy")
        tm.that(
            mypy["python_version"], eq=config.Infra.codegen.toolchain.python_version
        )
        tm.that(mypy, lacks="strict_concatenate")
        tm.that(
            list(u.Tests.toml_strings(mypy["plugins"])), eq=list(mypy_policy.plugins)
        )
        tm.that(
            list(u.Tests.toml_strings(mypy["disable_error_code"])),
            eq=sorted(mypy_policy.disabled_error_codes),
        )
        tm.that(
            list(u.Tests.toml_list(mypy["overrides"])),
            eq=[
                {
                    "module": list(entry.modules),
                    **(
                        {"disable_error_code": list(entry.disable_error_codes)}
                        if entry.disable_error_codes
                        else {}
                    ),
                    **(
                        {"follow_untyped_imports": entry.follow_untyped_imports}
                        if entry.follow_untyped_imports is not None
                        else {}
                    ),
                }
                for entry in mypy_policy.overrides
            ],
        )
        for key, value in {
            **mypy_policy.boolean_settings,
            **mypy_policy.string_settings,
        }.items():
            tm.that(mypy[key], eq=value)

    def test_pytest_table_replaces_policy_and_merges_extensions(
        self, tmp_path: Path
    ) -> None:
        """Replace policy flags while retaining declared discovery extensions."""
        policy = config.Infra.tooling.tools.pytest
        payload, _ = self._applied(
            tmp_path,
            "[tool.pytest.ini_options]\n"
            'python_classes = ["Spec*"]\n'
            'addopts = ["--maxfail=1"]\n'
            'markers = ["custom: custom marker"]\n',
        )
        ini = self._table(payload, "pytest", "ini_options")
        tm.that(ini["minversion"], eq=policy.min_version)
        tm.that(ini["flext_slow_timeout_seconds"], eq=str(policy.slow_timeout_seconds))
        tm.that(
            set(u.Tests.strings(ini["python_classes"])),
            eq={"Spec*", *policy.python_classes},
        )
        tm.that(
            set(u.Tests.strings(ini["addopts"])),
            eq={*policy.standard_addopts, f"--timeout={policy.case_timeout_seconds}"},
        )
        tm.that(
            set(u.Tests.strings(ini["markers"])),
            eq={"custom: custom marker", *policy.standard_markers},
        )

    def test_formatting_tables_mirror_policy(self, tmp_path: Path) -> None:
        """Render codespell, hatch, tomlsort, yamlfix, pydantic-mypy, and vulture."""
        tools = config.Infra.tooling.tools
        payload, changes = self._applied(
            tmp_path,
            '[tool.codespell]\nskip = ".git"\n'
            "[tool.pydantic-mypy]\nwarn_untyped_fields = true\n",
        )
        codespell = self._table(payload, "codespell")
        tm.that(codespell, lacks="skip")
        tm.that(changes, has="tool.codespell.skip removed")
        tm.that(codespell["check-filenames"], eq=tools.codespell.check_filenames)
        tm.that(
            self._table(payload, "hatch", "metadata")["allow-direct-references"],
            eq=tools.hatch.allow_direct_references,
        )
        tomlsort = self._table(payload, "tomlsort")
        tm.that(tomlsort["all"], eq=tools.tomlsort.all)
        tm.that(
            list(u.Tests.toml_strings(tomlsort["sort_first"])),
            eq=sorted(tools.tomlsort.sort_first),
        )
        yamlfix = self._table(payload, "yamlfix")
        tm.that(yamlfix["line_length"], eq=tools.yamlfix.line_length)
        tm.that(yamlfix["explicit_start"], eq=tools.yamlfix.explicit_start)
        pydantic_mypy = self._table(payload, "pydantic-mypy")
        tm.that(pydantic_mypy, lacks="warn_untyped_fields")
        tm.that(pydantic_mypy["init_typed"], eq=tools.pydantic_mypy.init_typed)
        vulture = self._table(payload, "vulture")
        tm.that(vulture["min_confidence"], eq=tools.vulture.min_confidence)

    @pytest.mark.parametrize(
        "project_kind", ["core", "domain", "platform", "integration", "app"]
    )
    def test_coverage_threshold_follows_project_kind(
        self, tmp_path: Path, project_kind: str
    ) -> None:
        """Select the configured threshold for every classified project kind."""
        coverage = config.Infra.tooling.tools.coverage
        payload, _ = self._applied(tmp_path, project_kind=project_kind)
        report = self._table(payload, "coverage", "report")
        thresholds: t.IntMapping = {
            "core": coverage.fail_under.core,
            "domain": coverage.fail_under.domain,
            "platform": coverage.fail_under.platform,
            "integration": coverage.fail_under.integration,
            "app": coverage.fail_under.app,
        }
        tm.that(report["fail_under"], eq=thresholds[project_kind])
        tm.that(report["show_missing"], eq=coverage.show_missing)
        tm.that(
            list(u.Tests.strings(self._table(payload, "coverage", "run")["omit"])),
            eq=sorted(set(coverage.omit)),
        )

    def test_coverage_source_round_trips_arbitrary_config(self, tmp_path: Path) -> None:
        """Project an arbitrary configured coverage source without hardcoding it."""
        tooling = config.Infra.tooling
        arbitrary_source = ("arbitrary-production-root",)
        configured = tooling.model_copy(
            update={
                "tools": tooling.tools.model_copy(
                    update={
                        "coverage": tooling.tools.coverage.model_copy(
                            update={"source": arbitrary_source}
                        )
                    }
                )
            }
        )
        payload, _ = self._applied(tmp_path, tool_config=configured)
        tm.that(
            list(u.Tests.strings(self._table(payload, "coverage", "run")["source"])),
            eq=list(arbitrary_source),
        )

    def test_deptry_first_party_includes_project_and_declared_flext_deps(
        self, tmp_path: Path
    ) -> None:
        """Detect the project package and declared FLEXT dependencies as first party."""
        payload, _ = self._applied(tmp_path, 'dependencies = ["flext-core>=0.1.0"]\n')
        tm.that(
            set(
                u.Tests.toml_strings(
                    self._table(payload, "deptry")["known_first_party"]
                )
            ),
            eq={
                *config.Infra.tooling.tools.deptry.known_first_party,
                "flext_core",
                "flext_sample",
            },
        )

    def test_tables_are_idempotent(self, tmp_path: Path) -> None:
        """A second application over the converged payload changes nothing."""
        payload, first = self._applied(tmp_path)
        second = FlextInfraToolTablesPhase(config.Infra.tooling).apply_payload(
            payload, path=tmp_path / "flext-sample" / "pyproject.toml"
        )
        tm.that(first, empty=False)
        tm.that(second, empty=True)

    def test_modernizer_roots_and_members_converge_on_their_kind(
        self, tmp_path: Path
    ) -> None:
        """Keep topology-owned roots distinct from dependency-classified members."""
        thresholds = config.Infra.tooling.tools.coverage.fail_under
        modernizer = FlextInfraPyprojectModernizer(
            repository_root=tmp_path, skip_check=True
        )
        root_path = tmp_path / "pyproject.toml"
        root_first: str = tm.ok(
            modernizer.conform_source(
                '[project]\nname = "arbitrary-root"\n',
                path=root_path,
                project_kind="platform",
            )
        )
        member_path = tmp_path / "arbitrary-member" / "pyproject.toml"
        member_path.parent.mkdir()
        member_first: str = tm.ok(
            modernizer.conform_source(
                '[project]\nname = "arbitrary-member"\n'
                'dependencies = ["flext-core", "flext-cli", "flext-ldap"]\n',
                path=member_path,
            )
        )
        tm.that(
            tm.ok(
                modernizer.conform_source(
                    root_first, path=root_path, project_kind="platform"
                )
            ),
            eq=root_first,
        )
        tm.that(
            tm.ok(modernizer.conform_source(member_first, path=member_path)),
            eq=member_first,
        )
        tm.that(
            u.Tests.toml_table_at(root_first, "tool", "coverage", "report")[
                "fail_under"
            ],
            eq=thresholds.platform,
        )
        tm.that(
            u.Tests.toml_table_at(member_first, "tool", "coverage", "report")[
                "fail_under"
            ],
            eq=thresholds.app,
        )


__all__: list[str] = ["TestsFlextInfraDepsModernizerToolTables"]
