"""Tests for catalog-driven enforcement fixer orchestration."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import ClassVar

import pytest

from flext_cli import cli
from flext_core import r
from flext_infra import m, main as infra_main, p, t, u
from flext_infra.fixers.gate_fixer import FlextInfraGateFixerAdapter
from flext_infra.fixers.manual_fixer import FlextInfraManualFixerAdapter
from flext_infra.fixers.orchestrator import FlextInfraEnforcementFixerOrchestrator
from flext_infra.fixers.rope_fixer import FlextInfraRopeFixerAdapter
from flext_tests import tm
from tests import c


class TestsEnforcementFixerOrchestrator:
    """Root-cause guardrails for fixer collection and routing."""

    @staticmethod
    def _rule(rule_id: str) -> m.EnforcementRuleSpec:
        catalog = u.build_canonical_catalog()
        return next(rule for rule in catalog.enabled_rules() if rule.id == rule_id)

    @staticmethod
    def _orchestrator(workspace: Path) -> FlextInfraEnforcementFixerOrchestrator:
        return FlextInfraEnforcementFixerOrchestrator(
            workspace_root=workspace, selected_projects=("demo",)
        )

    def test_validator_import_failure_is_failed_fix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validator import failure is not reported as an empty violation set."""
        original_import = importlib.import_module

        def fake_import(name: str, package: str | None = None) -> ModuleType:
            if name == "flext_tests.validator":
                msg = "validator unavailable"
                raise ImportError(msg)
            return original_import(name, package)

        monkeypatch.setattr(importlib, "import_module", fake_import)
        project_dir = tmp_path / "demo"
        project_dir.mkdir()
        project = m.Infra.ProjectInfo(name="demo", path=project_dir, stack="python")

        def fake_projects(
            workspace_root: Path,
        ) -> p.Result[t.SequenceOf[p.Infra.ProjectInfo]]:
            _ = workspace_root
            return r[t.SequenceOf[p.Infra.ProjectInfo]].ok((project,))

        monkeypatch.setattr(u.Infra, "projects", staticmethod(fake_projects))
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            workspace_root=tmp_path,
            selected_projects=("demo",),
            rules=("ENFORCE-016",),
            safe_only=False,
        )
        result = orchestrator.execute()

        tm.fail(result)
        tm.that(result.error, has="unable to import flext_tests.validator")

    def test_python_file_enumeration_failure_is_failed_fix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Project file enumeration failure is not hidden as zero work."""

        def fake_iter_python_files(
            request: m.Infra.SourceScanRequest,
        ) -> p.Result[t.SequenceOf[Path]]:
            _ = request
            return r[t.SequenceOf[Path]].fail("enumeration failed")

        monkeypatch.setattr(
            u.Infra, "iter_python_files", staticmethod(fake_iter_python_files)
        )
        project_dir = tmp_path / "demo"
        project_dir.mkdir()
        project = m.Infra.ProjectInfo(name="demo", path=project_dir, stack="python")

        def fake_projects(
            workspace_root: Path,
        ) -> p.Result[t.SequenceOf[p.Infra.ProjectInfo]]:
            _ = workspace_root
            return r[t.SequenceOf[p.Infra.ProjectInfo]].ok((project,))

        monkeypatch.setattr(u.Infra, "projects", staticmethod(fake_projects))
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            workspace_root=tmp_path,
            selected_projects=("demo",),
            rules=("ENFORCE-045",),
            safe_only=False,
        )
        result = orchestrator.execute()

        tm.fail(result)
        tm.that(result.error, has="enumeration failed")

    def test_beartype_rules_collect_real_python_file_probes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The public dry-run reports a no-change skip for a clean source file."""
        project_dir = tmp_path / "demo"
        source_file = project_dir / "src" / "demo" / "sample.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("from __future__ import annotations\n", encoding="utf-8")
        project = m.Infra.ProjectInfo(name="demo", path=project_dir, stack="python")

        def fake_projects(
            workspace_root: Path,
        ) -> p.Result[t.SequenceOf[p.Infra.ProjectInfo]]:
            _ = workspace_root
            return r[t.SequenceOf[p.Infra.ProjectInfo]].ok((project,))

        monkeypatch.setattr(u.Infra, "projects", staticmethod(fake_projects))
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            workspace_root=tmp_path,
            selected_projects=("demo",),
            rules=("ENFORCE-045",),
            safe_only=False,
        )
        result = orchestrator.execute()

        tm.ok(result)
        tm.that(result.unwrap(), has="skipped: 1")
        tm.that(
            source_file.read_text(encoding="utf-8"),
            eq="from __future__ import annotations\n",
        )

    def test_stub_file_rule_collects_pyi_probes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The public dry-run reports source stubs and ignores virtualenv stubs."""
        project_dir = tmp_path / "demo"
        stub_file = project_dir / "src" / "demo" / "__init__.pyi"
        excluded_stub = project_dir / ".venv" / "ignored.pyi"
        stub_file.parent.mkdir(parents=True)
        excluded_stub.parent.mkdir(parents=True)
        stub_file.write_text("from demo import x as x\n", encoding="utf-8")
        excluded_stub.write_text("x: int\n", encoding="utf-8")
        project = m.Infra.ProjectInfo(name="demo", path=project_dir, stack="python")

        def fake_projects(
            workspace_root: Path,
        ) -> p.Result[t.SequenceOf[p.Infra.ProjectInfo]]:
            _ = workspace_root
            return r[t.SequenceOf[p.Infra.ProjectInfo]].ok((project,))

        monkeypatch.setattr(u.Infra, "projects", staticmethod(fake_projects))
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            workspace_root=tmp_path,
            selected_projects=("demo",),
            rules=("ENFORCE-090",),
            safe_only=False,
        )
        result = orchestrator.execute()

        tm.ok(result)
        report = result.unwrap()
        tm.that(report, has=str(stub_file))
        tm.that(report, lacks=str(excluded_stub))

    def test_remove_stub_file_dry_run_does_not_unlink(self, tmp_path: Path) -> None:
        """The remove-stub adapter previews deletion in dry-run."""
        project_dir = tmp_path / "demo"
        stub_file = project_dir / "src" / "demo" / "__init__.pyi"
        stub_file.parent.mkdir(parents=True)
        stub_file.write_text("from demo import x as x\n", encoding="utf-8")
        adapter = FlextInfraRopeFixerAdapter(tmp_path)
        ctx = m.Infra.FixEnforcementCommand(
            workspace=str(tmp_path), projects=("demo",), apply=False
        )

        result = adapter.fix_project(
            project_dir,
            ((self._rule("ENFORCE-090"), SimpleNamespace(file_path=str(stub_file))),),
            ctx,
        )

        tm.that(stub_file.exists(), eq=True)
        tm.that(len(result.previewed), eq=1)
        tm.that(result.fixed, eq=())
        tm.that(result.failed, eq=())

    def test_remove_stub_file_apply_unlinks_only_stub(self, tmp_path: Path) -> None:
        """The remove-stub adapter deletes the reported ``.pyi`` in apply mode."""
        project_dir = tmp_path / "demo"
        stub_file = project_dir / "src" / "demo" / "__init__.pyi"
        stub_file.parent.mkdir(parents=True)
        stub_file.write_text("from demo import x as x\n", encoding="utf-8")
        adapter = FlextInfraRopeFixerAdapter(tmp_path)
        ctx = m.Infra.FixEnforcementCommand(
            workspace=str(tmp_path), projects=("demo",), apply=True
        )

        result = adapter.fix_project(
            project_dir,
            ((self._rule("ENFORCE-090"), SimpleNamespace(file_path=str(stub_file))),),
            ctx,
        )

        tm.that(stub_file.exists(), eq=False)
        tm.that(len(result.fixed), eq=1)
        tm.that(result.files_modified, eq=(str(stub_file),))
        tm.that(result.failed, eq=())

    def test_manual_fix_dry_run_previews_without_mutation(self, tmp_path: Path) -> None:
        """Manual fix actions produce explicit previews in dry-run."""
        rule = self._rule("ENFORCE-097")
        fix_action = rule.fix_action
        if fix_action is None:
            pytest.fail("ENFORCE-097 must declare a manual fix action")
        adapter = FlextInfraManualFixerAdapter(tmp_path)
        tm.that(adapter.can_fix(fix_action), eq=True)
        source_file = tmp_path / "demo" / "src" / "demo" / "sample.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("VALUE = 42\n", encoding="utf-8")

        result = adapter.fix_project(
            tmp_path / "demo",
            (
                (
                    rule,
                    SimpleNamespace(file_path=str(source_file), line=1, literal="42"),
                ),
            ),
            m.Infra.FixEnforcementCommand(
                workspace=str(tmp_path), projects=("demo",), apply=False
            ),
        )

        tm.that(source_file.read_text(encoding="utf-8"), eq="VALUE = 42\n")
        tm.that(len(result.previewed), eq=1)
        tm.that(result.previewed[0].message, has="magic literal 42")
        tm.that(result.fixed, eq=())
        tm.that(result.failed, eq=())

    def test_manual_fix_apply_fails_loudly(self, tmp_path: Path) -> None:
        """Manual fix actions cannot be reported as applied automatically."""
        rule = self._rule("ENFORCE-097")
        adapter = FlextInfraManualFixerAdapter(tmp_path)

        result = adapter.fix_project(
            tmp_path / "demo",
            (
                (
                    rule,
                    SimpleNamespace(
                        file_path=str(tmp_path / "demo" / "sample.py"),
                        line=7,
                        literal="42",
                    ),
                ),
            ),
            m.Infra.FixEnforcementCommand(
                workspace=str(tmp_path), projects=("demo",), apply=True
            ),
        )

        tm.that(result.previewed, eq=())
        tm.that(len(result.failed), eq=1)
        tm.that(result.failed[0].error, has="manual fix required for ENFORCE-097")

    def test_missing_selected_project_fails_resolution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A typoed project filter is a hard failure, not a zero-project success."""
        demo = m.Infra.ProjectInfo(name="demo", path=tmp_path / "demo", stack="python")

        def fake_projects(
            workspace_root: Path,
        ) -> p.Result[t.SequenceOf[p.Infra.ProjectInfo]]:
            _ = workspace_root
            return r[t.SequenceOf[p.Infra.ProjectInfo]].ok((demo,))

        monkeypatch.setattr(u.Infra, "projects", staticmethod(fake_projects))
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            workspace_root=tmp_path,
            selected_projects=("missing",),
            rules=("ENFORCE-090",),
            safe_only=False,
        )

        result = orchestrator.execute()

        tm.fail(result)
        tm.that((result.error or ""), has="missing")

    def test_explicit_unsafe_rule_fails_under_safe_only(self, tmp_path: Path) -> None:
        """Explicit unsafe fix requests must fail instead of becoming no-op success."""
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            workspace_root=tmp_path,
            selected_projects=("demo",),
            rules=("ENFORCE-067",),
            safe_only=True,
        )
        result = orchestrator.execute()

        tm.fail(result)
        tm.that(result.error, has="unsafe under --safe-only")

    def test_gate_dry_run_uses_non_mutating_check_preview(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gate dry-run uses the non-mutating check path."""

        class FakeGate:
            can_fix: ClassVar[bool] = True
            checked: ClassVar[bool] = False
            fixed: ClassVar[bool] = False

            def __init__(self, workspace_root: Path) -> None:
                self.workspace_root = workspace_root

            def check(
                self, project_dir: Path, ctx: m.Infra.GateContext
            ) -> m.Infra.GateExecution:
                _ = self.workspace_root
                tm.that(ctx.check_only, eq=True)
                tm.that(ctx.apply_fixes, eq=False)
                FakeGate.checked = True
                return m.Infra.GateExecution(
                    result=m.Infra.GateResult(
                        gate="smells", project=project_dir.name, passed=True
                    ),
                    issues=(
                        m.Infra.Issue(
                            file=str(project_dir / "src" / "demo.py"),
                            line=1,
                            column=1,
                            code="boolean-logic",
                            message="boolean logic",
                            severity="error",
                        ),
                    ),
                    raw_output="check only",
                )

            def fix(
                self, project_dir: Path, ctx: m.Infra.GateContext
            ) -> m.Infra.GateExecution:
                _ = project_dir, ctx
                FakeGate.fixed = True
                msg = "dry-run must not execute gate fixes"
                raise AssertionError(msg)

        class FakeRegistry:
            def get(self, target: str) -> type[FakeGate] | None:
                return FakeGate if target == "smells" else None

        def fake_registry(self: FlextInfraGateFixerAdapter) -> FakeRegistry:
            _ = self
            return FakeRegistry()

        monkeypatch.setattr(FlextInfraGateFixerAdapter, "_registry", fake_registry)
        adapter = FlextInfraGateFixerAdapter(tmp_path)
        project_dir = tmp_path / "demo"

        result = adapter.fix_project(
            project_dir,
            ((self._rule("ENFORCE-074"), SimpleNamespace(file_path=str(project_dir))),),
            m.Infra.FixEnforcementCommand(
                workspace=str(tmp_path), projects=("demo",), apply=False
            ),
        )

        tm.that(FakeGate.checked, eq=True)
        tm.that(FakeGate.fixed, eq=False)
        tm.that(len(result.previewed), eq=1)
        tm.that(result.failed, eq=())

    # Exemplar: this drives the real CLI entry point against a real Git
    # repository, so its cost is the runtime's import chain plus several git
    # invocations. The slow marker opts into the config-owned slow-item budget.
    @pytest.mark.slow
    def test_fix_enforcement_dry_run_leaves_worktree_unchanged(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A real CLI dry-run leaves its owned committed repository unchanged."""
        project_dir = tmp_path / "demo-project"
        source_dir = project_dir / "src" / "demo"
        constants_dir = source_dir / "_constants"
        constants_dir.mkdir(parents=True)
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        (source_dir / "__init__.py").write_text(
            '"""Demo package."""\n', encoding="utf-8"
        )
        (constants_dir / "__init__.py").write_text(
            '"""Demo constants."""\n', encoding="utf-8"
        )
        (constants_dir / "worker.py").write_text(
            '"""Worker constants."""\n', encoding="utf-8"
        )
        (source_dir / "worker.py").write_text(
            '"""Demo worker."""\n\n'
            "from typing import ClassVar\n\n"
            'MODULE_KIND: ClassVar[str] = "demo"\n\n\n'
            "class DemoWorker:\n"
            '    """Worker with one misplaced constant."""\n\n'
            '    GROUPS: ClassVar[tuple[str, ...]] = ("alpha", "beta")\n\n'
            "    def groups(self) -> tuple[str, ...]:\n"
            '        """Return the configured groups."""\n'
            "        return self.GROUPS\n",
            encoding="utf-8",
        )

        def run_git(args: t.StrSequence) -> None:
            output = cli.run_raw([c.Infra.GIT, *args], cwd=project_dir).value
            tm.that(output.exit_code, eq=0)

        run_git(("init",))
        run_git(("add", "--", "pyproject.toml", "src"))
        run_git((
            "-c",
            "user.name=FLEXT Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "baseline",
            "--",
            "pyproject.toml",
            "src",
        ))
        runner_root = Path(__file__).parents[4]

        def git_status() -> str:
            capture_result: p.Result[str] = cli.capture(
                [c.Infra.GIT, "-C", str(project_dir), "status", "--short"],
                cwd=runner_root,
            )
            stdout: str = capture_result.value
            return stdout

        pre_status = git_status()
        with tm.scope(env={"GIT_CONFIG_GLOBAL": os.devnull}):
            exit_code = infra_main([
                "check",
                "fix-enforcement",
                "--workspace",
                str(project_dir),
                "--rules",
                "ENFORCE-079",
                "--dry-run",
                "--no-check-after",
            ])
        output = capsys.readouterr()
        post_status = git_status()
        tm.that(exit_code, eq=0, msg=output.err or output.out)
        # A dry run previews; it never fixes. `fixed` and `previewed` are
        # distinct counters, and --dry-run feeds the latter.
        tm.that(output.out, has="fixed: 0")
        tm.that(output.out, has="previewed: 1")
        tm.that(output.out, has="failed: 0")
        # The read-only guarantee is the worktree itself: a dry run forces
        # check_after=False, so no gate can rewrite a file behind the preview.
        tm.that(pre_status, eq=post_status)
