"""Tests for catalog-driven enforcement fixer orchestration."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from flext_cli import cli
from flext_tests import tm

from flext_infra import m, main as infra_main, p, t
from flext_infra.fixers.manual_fixer import FlextInfraManualFixerAdapter
from flext_infra.fixers.orchestrator import FlextInfraEnforcementFixerOrchestrator
from tests import c, u


class TestsFlextInfraEnforcementFixerOrchestrator:
    """Root-cause guardrails for fixer collection and routing."""

    @staticmethod
    def _orchestrator(workspace: Path) -> FlextInfraEnforcementFixerOrchestrator:
        return FlextInfraEnforcementFixerOrchestrator(
            repository_root=workspace, selected_projects=("demo",)
        )

    def test_beartype_rules_collect_real_python_file_probes(
        self, tmp_path: Path
    ) -> None:
        """The public dry-run reports a no-change skip for a clean source file."""
        project_dir = u.Tests.mk_project(
            tmp_path, "demo", pyproject='[project]\nname = "demo"\nversion = "0.1.0"\n'
        )
        # Discovery only reaches declared members: an undeclared child directory
        # is not a project of this root, so the selector would not resolve.
        u.Tests.declare_workspace_projects(tmp_path, ("demo",))
        source_file = project_dir / "src" / "demo" / "sample.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("from __future__ import annotations\n", encoding="utf-8")
        u.Tests.initialize_git_repo(project_dir)
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            repository_root=project_dir,
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

    def test_stub_file_rule_collects_pyi_probes(self, tmp_path: Path) -> None:
        """The public dry-run reports source stubs and ignores virtualenv stubs."""
        project_dir = u.Tests.mk_project(
            tmp_path, "demo", pyproject='[project]\nname = "demo"\nversion = "0.1.0"\n'
        )
        # Discovery only reaches declared members: an undeclared child directory
        # is not a project of this root, so the selector would not resolve.
        u.Tests.declare_workspace_projects(tmp_path, ("demo",))
        stub_file = project_dir / "src" / "demo" / "__init__.pyi"
        excluded_stub = project_dir / ".venv" / "ignored.pyi"
        stub_file.parent.mkdir(parents=True)
        excluded_stub.parent.mkdir(parents=True)
        stub_file.write_text("from demo import x as x\n", encoding="utf-8")
        excluded_stub.write_text("x: int\n", encoding="utf-8")
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            repository_root=project_dir,
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

        result = u.Tests.run_rope_fixer(
            tmp_path,
            project_dir,
            u.Tests.enforcement_rule("ENFORCE-090"),
            stub_file,
            apply=False,
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

        result = u.Tests.run_rope_fixer(
            tmp_path,
            project_dir,
            u.Tests.enforcement_rule("ENFORCE-090"),
            stub_file,
            apply=True,
        )

        tm.that(stub_file.exists(), eq=False)
        tm.that(len(result.fixed), eq=1)
        tm.that(result.files_modified, eq=(str(stub_file),))
        tm.that(result.failed, eq=())

    def test_manual_fix_dry_run_previews_without_mutation(self, tmp_path: Path) -> None:
        """Manual fix actions produce explicit previews in dry-run."""
        rule = u.Tests.enforcement_rule("ENFORCE-097")
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
                repository_root=str(tmp_path), projects=("demo",), apply=False
            ),
        )

        tm.that(source_file.read_text(encoding="utf-8"), eq="VALUE = 42\n")
        tm.that(len(result.previewed), eq=1)
        tm.that(result.previewed[0].message, has="magic literal 42")
        tm.that(result.fixed, eq=())
        tm.that(result.failed, eq=())

    def test_manual_fix_apply_fails_loudly(self, tmp_path: Path) -> None:
        """Manual fix actions cannot be reported as applied automatically."""
        rule = u.Tests.enforcement_rule("ENFORCE-097")
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
                repository_root=str(tmp_path), projects=("demo",), apply=True
            ),
        )

        tm.that(result.previewed, eq=())
        tm.that(len(result.failed), eq=1)
        tm.that(result.failed[0].error, has="manual fix required for ENFORCE-097")

    def test_missing_selected_project_fails_resolution(self, tmp_path: Path) -> None:
        """A typoed project filter is a hard failure, not a zero-project success."""
        _ = u.Tests.mk_project(
            tmp_path, "demo", pyproject='[project]\nname = "demo"\nversion = "0.1.0"\n'
        )
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            repository_root=tmp_path,
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
            repository_root=tmp_path,
            selected_projects=("demo",),
            rules=("ENFORCE-067",),
            safe_only=True,
        )
        result = orchestrator.execute()

        tm.fail(result)
        tm.that(result.error, has="unsafe under --safe-only")

    def test_every_catalog_fix_action_resolves_to_an_adapter(
        self, tmp_path: Path
    ) -> None:
        """Preflight proves the catalog and the adapter registry agree.

        An enabled rule declaring a fix action the runtime cannot route is a
        contract defect: it must stop the run before any project is touched,
        not surface later as a per-project failed fix.
        """
        orchestrator = FlextInfraEnforcementFixerOrchestrator(
            repository_root=tmp_path, selected_projects=("demo",)
        )

        result = orchestrator.execute()

        tm.that((result.error or ""), lacks="no registered fixer adapter")

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
            '    GROUPS: ClassVar[t.VariadicTuple[str]] = ("alpha", "beta")\n\n'
            "    def groups(self) -> t.VariadicTuple[str]:\n"
            '        """Return the configured groups."""\n'
            "        return self.GROUPS\n",
            encoding="utf-8",
        )

        def run_git(args: t.StrSequence) -> None:
            output = cli.run_raw([c.Infra.GIT, *args], cwd=project_dir).value
            tm.that(u.Cli.process_succeeded(output.outcome), eq=True)

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
                "--repository-root",
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
