"""Fail-closed public behavior for the qlty smells gate."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c
from flext_infra.check.gate_registry import FlextInfraGateRegistry
from flext_infra.gates.smells import FlextInfraSmellsGate
from tests import m, u

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def smells_project(tmp_path: Path) -> Iterator[Path]:
    """One declared, importable project inside ``tmp_path``.

    The gate also runs the runtime census, which discovers projects through
    their ``[project]`` table and imports their package, failing loud on
    either gap — exactly as in a real lane, whose package is importable from
    its environment. The package name is unique per test so no module cached
    by another test stands in for this one.
    """
    name = f"smells-{tmp_path.name}"
    project = u.Tests.mk_project(
        tmp_path,
        name,
        pyproject=f'[project]\nname = "{name}"\nversion = "0.1.0"\n',
        with_src=True,
    )
    src = str(project / "src")
    sys.path.insert(0, src)
    importlib.invalidate_caches()
    try:
        yield project
    finally:
        sys.path.remove(src)
        importlib.invalidate_caches()


class TestsFlextInfraSmellsGate:
    """Exercise observable gate behavior with the real setup-provisioned tool."""

    def _ctx(self, root: Path) -> m.Infra.GateContext:
        return m.Infra.GateContext(repository_root=root, reports_dir=root / "reports")

    @staticmethod
    def _package(project: Path) -> Path:
        return project / "src" / project.name.replace("-", "_")

    def test_registry_exposes_the_canonical_gate(self) -> None:
        gate = FlextInfraGateRegistry.default().get("smells")
        tm.that(gate is FlextInfraSmellsGate, eq=True)

    def test_missing_project_configuration_is_a_blocking_failure(
        self, tmp_path: Path, smells_project: Path
    ) -> None:
        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project, self._ctx(tmp_path)
        )

        tm.that(execution.result.passed, eq=False)
        tm.that(len(execution.issues), eq=1)
        tm.that(execution.issues[0].severity, eq=str(c.Infra.GateSeverity.ERROR.value))
        tm.that(
            "generated qlty configuration is absent" in execution.issues[0].message,
            eq=True,
        )

    def _configure(self, root: Path) -> None:
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
        self, tmp_path: Path, smells_project: Path
    ) -> None:
        self._configure(tmp_path)

        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project, self._ctx(tmp_path)
        )

        tm.that(execution.result.passed, eq=True)
        tm.that(len(execution.issues), eq=0)

    def test_finding_states_the_concrete_problem_and_the_fix(
        self, tmp_path: Path, smells_project: Path
    ) -> None:
        self._configure(tmp_path)
        params = ", ".join(
            f"p{index}" for index in range(c.SMELL_THRESHOLDS["params"] * 2)
        )
        (self._package(smells_project) / "wide.py").write_text(
            f"def wide({params}):\n    return p0\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project, self._ctx(tmp_path)
        )

        tm.that(execution.result.passed, eq=False)
        messages = [issue.message for issue in execution.issues]
        tm.that(any("wide" in message for message in messages), eq=True)
        tm.that(any("{" in message for message in messages), eq=False)
        tm.that(all(" Fix: " in message for message in messages), eq=True)

    def test_runtime_census_smell_families_are_graded_here(
        self, tmp_path: Path, smells_project: Path
    ) -> None:
        """Premise (operator 2026-10-01): make smells owns every smell family.

        A class method over the parameter threshold trips the runtime-census
        smell; the smells gate reports it as a blocking finding.
        """
        self._configure(tmp_path)
        params = ", ".join(
            f"p{index}" for index in range(c.SMELL_THRESHOLDS["params"] + 1)
        )
        (self._package(smells_project) / "__init__.py").write_text(
            '"""Fixture package with one wide method."""\n\n\n'
            "class Wide:\n"
            '    """Holds one method over the parameter threshold."""\n\n'
            f"    def run(self, {params}):\n"
            '        """Too many parameters."""\n'
            "        return p0\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        execution = FlextInfraSmellsGate(tmp_path).check(
            smells_project, self._ctx(tmp_path)
        )

        tm.that(execution.result.passed, eq=False)
        census_tags = {
            tag
            for issue in execution.issues
            for tag in c.ENFORCEMENT_SMELL_TAGS
            if issue.message.endswith(f"[{tag}]")
        }
        tm.that("smell_function_parameters" in census_tags, eq=True)
