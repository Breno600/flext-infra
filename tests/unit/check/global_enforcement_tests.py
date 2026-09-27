"""Global activation changes acceptance, never native checker evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, m
from flext_infra.check.workspace_check import FlextInfraWorkspaceChecker
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraGlobalEnforcement:
    """Exercise native analyzers and conformity through the public checker."""

    @staticmethod
    def _project(root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "pyproject.toml").write_text(
            '[project]\nname = "enforcement-consumer"\nversion = "0.1.0"\n'
            "dependencies = []\n"
            '[tool.ruff.lint]\nselect = ["F401"]\n'
            "[tool.mypy]\ncheck_untyped_defs = true\n"
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
    def test_codemod_findings_use_global_activation(
        self, tmp_path: Path, *, enabled: bool
    ) -> None:
        self._project(tmp_path)
        rules = tmp_path / "codemod" / "rules"
        rules.mkdir(parents=True)
        (tmp_path / c.Infra.CODEMOD_CONFIG_FILENAME).write_text(
            "ruleDirs:\n  - codemod/rules\ntestConfigs: []\n", encoding="utf-8"
        )
        (rules / "declared-probe.yml").write_text(
            "id: declared-probe\nlanguage: Python\nseverity: error\n"
            "rule:\n  pattern: import os\nmessage: declared import violation\n",
            encoding="utf-8",
        )
        checker = FlextInfraWorkspaceChecker(
            repository_root=tmp_path,
            check_policy=m.Infra.CheckPolicySpec(
                enforcement_enabled=enabled, gates=("codemod",)
            ),
        )
        execution = tm.ok(checker.run_project(".", ("codemod",)))[0].gates["codemod"]
        tm.that(execution.result.passed, eq=False)
        tm.that(bool(execution.issues), eq=True)
        tm.that(any(issue.code == "TOOL_ERROR" for issue in execution.issues), eq=False)
        result = checker.check_payload(
            m.Infra.RunCommand(
                repository_root=tmp_path,
                projects=(".",),
                gates=("codemod",),
                reports_dir=str(tmp_path / "reports"),
            )
        )
        tm.that(result.success, eq=not enabled)

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

    def test_unknown_requested_gate_fails_before_execution(
        self, tmp_path: Path
    ) -> None:
        self._project(tmp_path)
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        result = checker.check_payload(
            m.Infra.RunCommand(
                repository_root=tmp_path,
                projects=(".",),
                gates=("undeclared-gate",),
                reports_dir=str(tmp_path / "reports"),
            )
        )
        tm.fail(result, has="unknown gate")
        tm.that((tmp_path / "reports").exists(), eq=False)

    def test_missing_selected_project_fails_without_skip(self, tmp_path: Path) -> None:
        checker = FlextInfraWorkspaceChecker(repository_root=tmp_path)
        with pytest.raises(FileNotFoundError):
            checker.check_payload(
                m.Infra.RunCommand(
                    repository_root=tmp_path,
                    projects=("missing",),
                    gates=("namespace",),
                    reports_dir=str(tmp_path / "reports"),
                )
            )

    @pytest.mark.parametrize("enabled", [False, True])
    @pytest.mark.parametrize("location", ["package", "module"])
    def test_census_import_failure_escapes_unchanged(
        self, tmp_path: Path, location: str, *, enabled: bool
    ) -> None:
        name = f"flext-census-{location}-{int(enabled)}"
        root, package = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name=name, package_name=name.replace("-", "_")
        )
        fault = package / ("__init__.py" if location == "package" else "broken.py")
        fault.write_text(
            "raise RuntimeError('census import failed unchanged')\n", encoding="utf-8"
        )
        checker = FlextInfraWorkspaceChecker(
            repository_root=root,
            check_policy=m.Infra.CheckPolicySpec(
                enforcement_enabled=enabled, gates=("runtime-census",)
            ),
        )
        with (
            tm.scope(python_paths=[str(package.parent)]),
            pytest.raises(
                RuntimeError, match="census import failed unchanged"
            ) as raised,
        ):
            checker.check_payload(
                m.Infra.RunCommand(
                    repository_root=root,
                    projects=(".",),
                    gates=("runtime-census",),
                    reports_dir=str(root / "reports"),
                )
            )
        tm.that(str(raised.traceback[-1].path), eq=str(fault))


__all__: list[str] = ["TestsFlextInfraGlobalEnforcement"]
