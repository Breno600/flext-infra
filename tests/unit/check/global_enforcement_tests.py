"""Global activation changes acceptance, never native checker evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, m
from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraGlobalEnforcement:
    """Exercise native analyzers and conformity through the public checker."""

    @staticmethod
    def _project(root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "pyproject.toml").write_text(
            '[project]\nname = "enforcement-consumer"\nversion = "0.1.0"\n'
            '[tool.ruff.lint]\nselect = ["F401"]\n'
            '[tool.mypy]\ncheck_untyped_defs = true\n'
            '[tool.pyrefly]\nproject-includes = ["src"]\n'
            '[tool.pyright]\ninclude = ["src"]\n',
            encoding="utf-8",
        )
        source = root / "src"
        source.mkdir()
        (source / "consumer.py").write_text(
            'import os\n\nvalue: int = "wrong"\n', encoding="utf-8"
        )

    @pytest.mark.parametrize("enabled", [False, True])
    @pytest.mark.parametrize("gate", ["lint", "mypy", "pyrefly", "pyright"])
    def test_native_findings_always_block(
        self, tmp_path: Path, gate: str, *, enabled: bool
    ) -> None:
        self._project(tmp_path)
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path,
            check_policy=m.Infra.CheckPolicySpec(
                enforcement_enabled=enabled, gates=("namespace",)
            ),
        )
        params = m.Infra.RunCommand(
            repository_root=tmp_path,
            projects=(".",),
            gates=(gate,),
            reports_dir=str(tmp_path / "reports"),
        )
        result = checker.check_payload(params)
        tm.fail(result)
        evidence = tm.ok(checker.run_project(".", (gate,)))
        execution = evidence[0].gates[gate]
        tm.that(execution.result.passed, eq=False)
        tm.that(execution.error_count > 0, eq=True)
        tm.that(any(issue.code == "TOOL_ERROR" for issue in execution.issues), eq=False)
        tm.that(any("consumer.py" in issue.file for issue in execution.issues), eq=True)

    @pytest.mark.parametrize("enabled", [False, True])
    def test_broken_native_invocation_always_fails(
        self, tmp_path: Path, *, enabled: bool
    ) -> None:
        self._project(tmp_path)
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path,
            check_policy=m.Infra.CheckPolicySpec(
                enforcement_enabled=enabled, gates=("namespace",)
            ),
        )
        result = checker.check_payload(
            m.Infra.RunCommand(
                repository_root=tmp_path,
                projects=(".",),
                gates=(c.Infra.LINT,),
                ruff_args="--nonexistent-enforcement-test-option",
                reports_dir=str(tmp_path / "reports"),
            )
        )
        tm.fail(result)

    @pytest.mark.parametrize("enabled", [False, True])
    def test_conformity_activation_controls_fail_fast(
        self, tmp_path: Path, *, enabled: bool
    ) -> None:
        for name in ("first", "second"):
            self._project(tmp_path / name)
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path,
            check_policy=m.Infra.CheckPolicySpec(
                enforcement_enabled=enabled, gates=("namespace",)
            ),
        )
        results = tm.ok(
            checker.run_projects(("first", "second"), ("namespace",), fail_fast=True)
        )
        tm.that(len(results), eq=1 if enabled else 2)
        tm.that(all(not result.passed for result in results), eq=True)

    @pytest.mark.parametrize("enabled", [False, True])
    @pytest.mark.parametrize(
        "gate", ["lint", "format", "markdown-code", "mypy", "pyrefly", "pyright"]
    )
    def test_analyzers_cannot_be_declared_observational(
        self, gate: str, *, enabled: bool
    ) -> None:
        with pytest.raises(ValueError, match="always-blocking analyzers"):
            m.Infra.CheckPolicySpec(enforcement_enabled=enabled, gates=(gate,))

    def test_unknown_gate_fails_before_execution(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="unknown gates"):
            FlextInfraWorkspaceChecker(
                repository_root=tmp_path,
                check_policy=m.Infra.CheckPolicySpec(gates=("undeclared-gate",)),
            )


__all__: list[str] = ["TestsFlextInfraGlobalEnforcement"]
