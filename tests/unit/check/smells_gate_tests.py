"""Fail-closed public behavior for the qlty smells gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c
from flext_infra.check.gate_registry import FlextInfraGateRegistry
from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from flext_infra.gates.smells import FlextInfraSmellsGate
from tests import m, t, u


@pytest.fixture
def smells_project(tmp_path: Path) -> Path:
    """One declared project inside ``tmp_path`` for qlty to scan.

    Returns:
        The resulting ``Path``.

    """
    name = f"smells-{tmp_path.name}"
    return u.Tests.mk_project(
        tmp_path,
        name,
        pyproject=f'[project]\nname = "{name}"\nversion = "0.1.0"\n',
        with_src=True,
    )


class TestsFlextInfraSmellsGate:
    """Exercise observable gate behavior with the real setup-provisioned tool."""

    @staticmethod
    def _detector_config(root: Path) -> m.ConfigDocument:
        """Read the same merged native configuration that the scanner loads.

        Returns:
            The resulting ``m.ConfigDocument``.
        """
        output = tm.ok(u.Cli.run([c.Infra.QLTY_BINARY, "config", "show"], cwd=root))
        path = root / "effective-qlty.yaml"
        path.write_text(output.stdout, encoding=c.Cli.ENCODING_DEFAULT)
        return tm.ok(u.Cli.config_load(path, expand_env=False))

    @staticmethod
    def _comparison_rule(config: m.ConfigDocument, rule: str) -> t.JsonMapping:
        """Follow Qlty's language override, enablement, then global precedence.

        Returns:
            The resulting ``t.JsonMapping``.
        """
        override = u.Cli.json_deep_mapping(
            config.data,
            "language",
            "python",
            "smells",
            rule,
        )
        if override and (
            override["enabled"] is False or override["threshold"] is not None
        ):
            return override
        return u.Cli.json_deep_mapping(config.data, "smells", rule)

    @classmethod
    def _comparison_config(cls, root: Path, variation: str) -> m.ConfigDocument:
        """Vary only temporary input, deriving every threshold from native config.

        Returns:
            The resulting ``m.ConfigDocument``.
        """
        config = cls._detector_config(root)
        if variation == "current":
            return config
        overrides: t.JsonDict = {}
        for rule in ("identical_code", "similar_code"):
            selected = cls._comparison_rule(config, rule)
            changed: t.JsonDict = {
                "enabled": selected["enabled"]
                if variation == "raised"
                or (variation == "similar-only" and rule == "similar_code")
                else False,
            }
            if variation == "raised" and selected["enabled"] is True:
                tm.that(type(selected["threshold"]) is int, eq=True)
                changed["threshold"] = tm.ok(u.parse(selected["threshold"], int)) * 2
            overrides[rule] = changed
        if variation == "raised":
            nodes = u.Cli.json_walk_path(
                config.data,
                ("language", "python", "smells", "duplication", "nodes_threshold"),
            )
            if nodes is None:
                nodes = u.Cli.json_walk_path(
                    config.data,
                    ("smells", "duplication", "nodes_threshold"),
                )
            tm.that(type(nodes) is int, eq=True)
            overrides["duplication"] = {
                "nodes_threshold": tm.ok(u.parse(nodes, int)) * 2,
            }
        path = root / c.Infra.QLTY_CONFIG_DIRNAME / c.Infra.QLTY_CONFIG_FILENAME
        tm.ok(
            u.Cli.toml_write_mapping(
                path,
                u.config_merge(
                    tm.ok(u.Cli.toml_read_json(path)),
                    {
                        "smells": overrides,
                        "language": {"python": {"smells": overrides}},
                    },
                ),
            ),
        )
        return cls._detector_config(root)

    @classmethod
    def _write_comparisons(cls, config: m.ConfigDocument, package: Path) -> bool:
        """Two real functions exceed configured line and AST-node limits.

        Returns:
            The resulting ``bool``.
        """
        language = u.Cli.json_deep_mapping(config.data, "language", "python")
        mode = u.Cli.json_walk_path(language, ("smells", "mode"))
        if mode is None:
            mode = u.Cli.json_walk_path(config.data, ("smells", "mode"))
        identical = cls._comparison_rule(config, "identical_code")
        similar = cls._comparison_rule(config, "similar_code")
        limits = [
            rule["threshold"]
            for rule in (identical, similar)
            if rule["enabled"] is True
        ]
        nodes = u.Cli.json_walk_path(
            language,
            ("smells", "duplication", "nodes_threshold"),
        )
        limits.append(
            nodes
            if nodes is not None
            else u.Cli.json_walk_path(
                config.data,
                ("smells", "duplication", "nodes_threshold"),
            ),
        )
        tm.that(all(type(limit) is int for limit in limits), eq=True)
        statements = max(tm.ok(u.parse(limit, int)) for limit in limits) + 1
        body = "\n".join(f"    value += {index}" for index in range(statements))
        for index, name in enumerate(("first.py", "second.py")):
            function = (
                "repeated" if identical["enabled"] is True else f"repeated_{index}"
            )
            (package / name).write_text(
                f"def {function}(value):\n{body}\n    return value\n",
                encoding=c.Cli.ENCODING_DEFAULT,
            )
        return (
            language["enabled"] is True
            and mode != "disabled"
            and (identical["enabled"] is True or similar["enabled"] is True)
        )

    @staticmethod
    def _assert_native_span(original: t.JsonMapping, retained: t.JsonMapping) -> None:
        """Compare raw protocol coordinates without the production span parser."""
        original_physical = u.Cli.json_deep_mapping(original, "physicalLocation")
        retained_physical = u.Cli.json_deep_mapping(retained, "physicalLocation")
        tm.that(
            u.Cli.json_pick_str(
                u.Cli.json_deep_mapping(retained_physical, "artifactLocation"),
                "uri",
            ),
            eq=u.Cli.json_pick_str(
                u.Cli.json_deep_mapping(original_physical, "artifactLocation"),
                "uri",
            ),
        )
        original_region = u.Cli.json_deep_mapping(original_physical, "region")
        retained_region = u.Cli.json_deep_mapping(retained_physical, "region")
        for coordinate in ("startLine", "startColumn", "endLine", "endColumn"):
            tm.that(coordinate in retained_region, eq=coordinate in original_region)
            tm.that(retained_region.get(coordinate), eq=original_region.get(coordinate))

    @classmethod
    def _assert_native_result(
        cls,
        original: t.JsonMapping,
        retained: t.JsonMapping,
    ) -> None:
        """Retain every primary and comparison location in native order."""
        for key in ("locations", "relatedLocations"):
            native_locations = u.Cli.json_deep_mapping_list(original, key)
            emitted_locations = u.Cli.json_deep_mapping_list(retained, key)
            tm.that(len(emitted_locations), eq=len(native_locations))
            for observed, emitted in zip(
                native_locations,
                emitted_locations,
                strict=True,
            ):
                cls._assert_native_span(observed, emitted)

    @staticmethod
    def _ctx(root: Path) -> m.Infra.GateContext:
        return m.Infra.GateContext(repository_root=root, reports_dir=root / "reports")

    @staticmethod
    def _package(project: Path) -> Path:
        return project / "src" / project.name.replace("-", "_")

    @staticmethod
    def test_registry_exposes_the_canonical_gate() -> None:
        """Test registry exposes the canonical gate."""
        gate = FlextInfraGateRegistry.default().get("smells")
        tm.that(gate is FlextInfraSmellsGate, eq=True)

    def test_missing_project_configuration_is_a_blocking_failure(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        """Test missing project configuration is a blocking failure."""
        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project,
            self._ctx(tmp_path),
        )

        tm.that(execution.result.passed, eq=False)
        tm.that(len(execution.issues), eq=1)
        tm.that(execution.issues[0].severity, eq=str(c.Infra.GateSeverity.ERROR.value))
        tm.that(
            "generated qlty configuration is absent" in execution.issues[0].message,
            eq=True,
        )

    @staticmethod
    def _configure(root: Path) -> None:
        tm.ok(u.Cli.run_checked(["git", "init", "-q", str(root)]))
        config_dir = root / c.Infra.QLTY_CONFIG_DIRNAME
        config_dir.mkdir()
        generated_config = (
            Path(__file__).resolve().parents[3]
            / c.Infra.QLTY_CONFIG_DIRNAME
            / c.Infra.QLTY_CONFIG_FILENAME
        )
        (config_dir / c.Infra.QLTY_CONFIG_FILENAME).write_text(
            generated_config.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            encoding=c.Cli.ENCODING_DEFAULT,
        )

    def test_zero_findings_scan_is_a_pass(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        """Test zero findings scan is a pass."""
        self._configure(tmp_path)

        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project,
            self._ctx(tmp_path),
        )

        tm.that(execution.result.passed, eq=True)
        tm.that(len(execution.issues), eq=0)

    def test_finding_states_the_concrete_problem_and_the_fix(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        """Test finding states the concrete problem and the fix."""
        self._configure(tmp_path)
        params = ", ".join(
            f"p{index}" for index in range(c.SMELL_THRESHOLDS["params"] * 2)
        )
        (self._package(smells_project) / "wide.py").write_text(
            f"def wide({params}):\n    return p0\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project,
            self._ctx(tmp_path),
        )

        tm.that(execution.result.passed, eq=False)
        messages = [issue.message for issue in execution.issues]
        tm.that(any("wide" in message for message in messages), eq=True)
        tm.that(any("{" in message for message in messages), eq=False)
        tm.that(all(" Fix: " in message for message in messages), eq=True)

    def test_qlty_scan_does_not_run_runtime_census(
        self,
        tmp_path: Path,
        smells_project: Path,
    ) -> None:
        """Qlty owns this gate even when census project metadata is unavailable."""
        self._configure(tmp_path)
        (smells_project / c.PYPROJECT_FILENAME).unlink()

        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project,
            self._ctx(tmp_path),
        )

        tm.that(execution.result.passed, eq=True)
        tm.that(execution.issues, length=0)

    @pytest.mark.parametrize(
        "variation",
        ["current", "raised", "similar-only", "disabled"],
    )
    def test_workspace_report_round_trips_native_comparison_spans(
        self,
        tmp_path: Path,
        smells_project: Path,
        variation: str,
    ) -> None:
        """The public checker retains exactly the spans emitted by real qlty."""
        self._configure(tmp_path)
        comparison_enabled = self._write_comparisons(
            self._comparison_config(tmp_path, variation),
            self._package(smells_project),
        )
        reports_dir = tmp_path / "reports"
        projects = tm.ok(
            FlextInfraWorkspaceChecker.model_validate({
                "repository_root": tmp_path,
            }).run_projects(
                [smells_project.name],
                [c.Infra.SMELLS],
                reports_dir=reports_dir,
            ),
        )
        execution = projects[0].gates[c.Infra.SMELLS]
        native = u.Cli.json_as_mapping(tm.ok(u.Cli.json_parse(execution.raw_output)))
        report_text = (reports_dir / c.Infra.CHECK_REPORT_SARIF_FILENAME).read_text(
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        published = u.Cli.json_as_mapping(tm.ok(u.Cli.json_parse(report_text)))
        native_results = tuple(
            result
            for run in u.Cli.json_deep_mapping_list(native, "runs")
            for result in u.Cli.json_deep_mapping_list(run, "results")
        )
        report_results = tuple(
            result
            for run in u.Cli.json_deep_mapping_list(published, "runs")
            for result in u.Cli.json_deep_mapping_list(run, "results")
        )
        if comparison_enabled:
            tm.that(bool(native_results), eq=True)
            tm.that(
                any(
                    u.Cli.json_deep_mapping_list(result, "relatedLocations")
                    for result in native_results
                ),
                eq=True,
            )
        else:
            tm.that(
                any(
                    u.Cli.json_deep_mapping_list(result, "relatedLocations")
                    for result in native_results
                ),
                eq=False,
            )
        tm.that(len(report_results), eq=len(native_results))
        tm.that(execution.finding_count, eq=len(native_results))
        for observed, emitted in zip(native_results, report_results, strict=True):
            self._assert_native_result(observed, emitted)
        report = m.Infra.SarifReport.model_validate_json(report_text)
        round_trip = m.Infra.SarifReport.model_validate_json(report.model_dump_json())
        tm.that(round_trip, eq=report)
