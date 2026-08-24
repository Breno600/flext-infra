"""Coverage phase tests for deps modernizer."""

from __future__ import annotations

import tomllib
from pathlib import Path

from flext_infra import config
from flext_infra.deps.modernizer import FlextInfraPyprojectModernizer
from flext_infra.deps.phases.ensure_coverage import FlextInfraEnsureCoverageConfigPhase
from flext_tests import tm
from tests import t, u


def _doc_mapping(doc: t.Cli.TomlDocument) -> t.JsonMapping:
    return t.Cli.JSON_MAPPING_ADAPTER.validate_python(
        u.normalize_to_json_value(doc.unwrap())
    )


def _mapping(value: t.JsonValue) -> t.JsonMapping:
    return t.Cli.JSON_MAPPING_ADAPTER.validate_python(value)


def _strings(value: t.JsonValue) -> t.StrSequence:
    result: t.StrSequence = t.Infra.STR_SEQ_ADAPTER.validate_python(value)
    return result


class TestsFlextInfraDepsModernizerCoverage:
    """Tests coverage settings phase behavior."""

    def test_apply_round_trips_config_owned_source(self) -> None:
        """Project an arbitrary configured coverage source without hardcoding it."""
        tool_config = config.Infra.tooling
        arbitrary_source = ("arbitrary-production-root",)
        coverage_config = tool_config.tools.coverage.model_copy(
            update={"source": arbitrary_source}
        )
        tools_config = tool_config.tools.model_copy(
            update={"coverage": coverage_config}
        )
        configured = tool_config.model_copy(update={"tools": tools_config})
        doc = u.Cli.toml_document()

        _ = FlextInfraEnsureCoverageConfigPhase(configured).apply(doc)

        tool = _mapping(_doc_mapping(doc)["tool"])
        coverage = _mapping(tool["coverage"])
        run = _mapping(coverage["run"])
        tm.that(list(_strings(run["source"])), eq=list(arbitrary_source))

    def test_apply_sets_report_and_run_state(self) -> None:
        """Verify apply sets report and run state."""
        tool_config = config.Infra.tooling
        doc = u.Cli.toml_document()

        _ = FlextInfraEnsureCoverageConfigPhase(tool_config).apply(
            doc, project_kind="integration"
        )

        tool = _mapping(_doc_mapping(doc)["tool"])
        coverage = _mapping(tool["coverage"])
        report = _mapping(coverage["report"])
        run = _mapping(coverage["run"])
        tm.that(
            report["fail_under"], eq=tool_config.tools.coverage.fail_under.integration
        )
        tm.that(report["show_missing"], eq=True)
        tm.that(report["skip_covered"], eq=False)
        tm.that(report["precision"], eq=tool_config.tools.coverage.precision)
        tm.that(
            list(_strings(report["exclude_also"])),
            eq=sorted(set(tool_config.tools.coverage.exclude_also)),
        )
        tm.that(
            list(_strings(run["omit"])), eq=sorted(set(tool_config.tools.coverage.omit))
        )
        # Declaration-layer Protocol facades are never runtime coverage targets.
        tm.that("*/protocols.py" in tool_config.tools.coverage.omit, eq=True)
        tm.that("*/_protocols/*" in tool_config.tools.coverage.omit, eq=True)

    def test_apply_is_idempotent(self) -> None:
        """Verify apply is idempotent."""
        tool_config = config.Infra.tooling
        phase = FlextInfraEnsureCoverageConfigPhase(tool_config)
        doc = u.Cli.toml_document()

        _ = phase.apply(doc, project_kind="core")
        second_changes = phase.apply(doc, project_kind="core")

        tm.that(second_changes, empty=True)

    def test_explicit_platform_root_and_inferred_member_app_are_idempotent(
        self, tmp_path: Path
    ) -> None:
        """Keep topology-owned roots distinct from dependency-classified members."""
        thresholds = config.Infra.tooling.tools.coverage.fail_under
        root_path = tmp_path / "pyproject.toml"
        root_source = '[project]\nname = "arbitrary-root"\n'
        root_modernizer = FlextInfraPyprojectModernizer(
            workspace_root=tmp_path, skip_check=True
        )
        root_first = tm.ok(
            root_modernizer.conform_source(
                root_source, path=root_path, project_kind="platform"
            )
        )
        root_second = tm.ok(
            root_modernizer.conform_source(
                root_first, path=root_path, project_kind="platform"
            )
        )

        member_path = tmp_path / "arbitrary-member" / "pyproject.toml"
        member_source = """[project]
name = "arbitrary-member"
dependencies = ["flext-core", "flext-cli", "flext-ldap"]
"""
        member_first = tm.ok(
            root_modernizer.conform_source(member_source, path=member_path)
        )
        member_second = tm.ok(
            root_modernizer.conform_source(member_first, path=member_path)
        )

        root_report = tomllib.loads(root_first)["tool"]["coverage"]["report"]
        member_report = tomllib.loads(member_first)["tool"]["coverage"]["report"]
        tm.that(root_second, eq=root_first)
        tm.that(member_second, eq=member_first)
        tm.that(root_report["fail_under"], eq=thresholds.platform)
        tm.that(member_report["fail_under"], eq=thresholds.app)
