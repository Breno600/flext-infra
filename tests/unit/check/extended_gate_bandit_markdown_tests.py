"""Public Bandit and Markdown gate behavior tests using protocol runners."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from flext_infra import m, p, r, t
from flext_infra.gates.bandit import FlextInfraBanditGate
from flext_infra.gates.markdown import FlextInfraMarkdownGate
from flext_tests import tm
from tests import TestsFlextInfraUtilities as u

if TYPE_CHECKING:
    from pathlib import Path


class TestBanditAndMarkdownGates:
    """Declarative public-contract tests for Bandit and Markdown gates."""

    @staticmethod
    def make_ctx(root: Path) -> m.Infra.GateContext:
        return m.Infra.GateContext(workspace=root, reports_dir=root)

    @staticmethod
    def make_runner(*results: p.Result[m.Cli.CommandOutput]) -> u.Tests.SequenceRunner:
        return u.Tests.SequenceRunner(list(results))

    @pytest.mark.parametrize(
        ("with_src", "runner_results", "passed", "issues_len"),
        [
            (False, (), True, 0),
            (
                True,
                (
                    r.ok(
                        u.Tests.stub_run(
                            stdout='{"results": [{"filename": "a.py", "line_number": 1, "test_id": "B101", "issue_text": "Assert used", "issue_severity": "MEDIUM"}]}',
                            returncode=1,
                        )
                    ),
                ),
                False,
                1,
            ),
            (
                True,
                (r.ok(u.Tests.stub_run(stdout="invalid json", returncode=1)),),
                False,
                1,
            ),
        ],
    )
    def test_bandit_check(
        self,
        *,
        tmp_path: Path,
        with_src: bool,
        runner_results: tuple[r[m.Cli.CommandOutput], ...],
        passed: bool,
        issues_len: int,
    ) -> None:
        project_dir = u.Tests.mk_project(tmp_path, "bandit-project")
        if with_src:
            (project_dir / "src").mkdir()
            (project_dir / "src" / "main.py").write_text("# code\n", encoding="utf-8")

        gate = FlextInfraBanditGate(
            tmp_path,
            runner=self.make_runner(*runner_results) if runner_results else None,
        )
        result = gate.check(project_dir, self.make_ctx(tmp_path))

        tm.that(result.result.passed, eq=passed)
        tm.that(len(result.issues), eq=issues_len)

    @pytest.mark.parametrize(
        (
            "markdown_text",
            "config_text",
            "runner_result",
            "passed",
            "issues_len",
            "raw_output",
        ),
        [
            ("", None, None, True, 0, ""),
            (
                "# Test\n",
                None,
                r.ok(
                    u.Tests.stub_run(
                        stdout="README.md:1:1: [MD001] Heading level", returncode=1
                    )
                ),
                False,
                1,
                "README.md:1:1: [MD001] Heading level",
            ),
            (
                "# Test\n",
                None,
                r.ok(u.Tests.stub_run(stderr="rumdl failed", returncode=1)),
                False,
                1,
                "rumdl failed",
            ),
        ],
    )
    def test_markdown_check(
        self,
        *,
        tmp_path: Path,
        markdown_text: str,
        config_text: str | None,
        runner_result: p.Result[m.Cli.CommandOutput] | None,
        passed: bool,
        issues_len: int,
        raw_output: str,
    ) -> None:
        project_dir = u.Tests.mk_project(tmp_path, "markdown-project")
        if markdown_text:
            (project_dir / "README.md").write_text(markdown_text, encoding="utf-8")
        if config_text is not None:
            (project_dir / ".markdownlint.json").write_text(
                config_text, encoding="utf-8"
            )

        gate = FlextInfraMarkdownGate(
            tmp_path,
            runner=self.make_runner(runner_result)
            if runner_result is not None
            else None,
        )
        result = gate.check(project_dir, self.make_ctx(tmp_path))

        tm.that(result.result.passed, eq=passed)
        tm.that(len(result.issues), eq=issues_len)
        if raw_output:
            tm.that(result.raw_output, contains=raw_output)

    def test_markdown_prefers_local_config_when_root_is_missing(
        self, tmp_path: Path
    ) -> None:
        project_dir = u.Tests.mk_project(tmp_path, "markdown-settings-project")
        (project_dir / "README.md").write_text("# Test\n", encoding="utf-8")
        (project_dir / ".markdownlint.json").write_text("{}", encoding="utf-8")
        runner = self.make_runner(r.ok(u.Tests.stub_run()))

        gate = FlextInfraMarkdownGate(tmp_path, runner=runner)
        _ = gate.check(project_dir, self.make_ctx(tmp_path))

        tm.that(runner.commands[0], has="--config")

    def test_markdown_uses_uv_managed_tool_with_sanitized_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Prove the real gate cannot bind a host or mise-provided executable."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-managed-tool")
        (project_dir / "README.md").write_text("# Test\n", encoding="utf-8")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")

        result = FlextInfraMarkdownGate(tmp_path).check(
            project_dir, self.make_ctx(tmp_path)
        )

        tm.that(result.result.passed, eq=True)
        tm.that(result.issues, eq=())

    def test_markdown_accepts_existing_nested_relative_link(
        self, tmp_path: Path
    ) -> None:
        """Exercise the real linter's path resolution at the project boundary."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-relative-link")
        docs_dir = project_dir / "docs"
        target_dir = docs_dir / "generated"
        target_dir.mkdir(parents=True)
        (docs_dir / "README.md").write_text(
            "# Documentation\n\n[Overview](generated/overview.md)\n", encoding="utf-8"
        )
        (target_dir / "overview.md").write_text("# Overview\n", encoding="utf-8")

        result = FlextInfraMarkdownGate(tmp_path).check(
            project_dir, self.make_ctx(tmp_path)
        )

        tm.that(result.result.passed, eq=True)
        tm.that(result.issues, eq=())

    def test_markdown_resolves_same_link_per_source_directory(
        self, tmp_path: Path
    ) -> None:
        """Do not let one missing target poison an equal valid relative link."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-link-scope")
        valid_docs = project_dir / "valid"
        invalid_docs = project_dir / "invalid"
        (valid_docs / "generated").mkdir(parents=True)
        invalid_docs.mkdir()
        body = "# Documentation\n\n[Overview](generated/overview.md)\n"
        (valid_docs / "README.md").write_text(body, encoding="utf-8")
        (invalid_docs / "README.md").write_text(body, encoding="utf-8")
        (valid_docs / "generated" / "overview.md").write_text(
            "# Overview\n", encoding="utf-8"
        )

        result = FlextInfraMarkdownGate(tmp_path).check(
            project_dir, self.make_ctx(tmp_path)
        )

        tm.that(result.result.passed, eq=False)
        tm.that(len(result.issues), eq=1)
        tm.that(result.issues[0].file, eq="invalid/README.md")

    def test_markdown_rechecks_link_target_state_without_cache(
        self, tmp_path: Path
    ) -> None:
        """A cached source hash must not hide a removed relative-link target."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-cache-state")
        target = project_dir / "target.md"
        (project_dir / "README.md").write_text(
            "# Documentation\n\n[Target](target.md)\n", encoding="utf-8"
        )
        target.write_text("# Target\n", encoding="utf-8")
        gate = FlextInfraMarkdownGate(tmp_path)

        first = gate.check(project_dir, self.make_ctx(tmp_path))
        target.unlink()
        second = gate.check(project_dir, self.make_ctx(tmp_path))

        tm.that(first.result.passed, eq=True)
        tm.that(second.result.passed, eq=False)
        tm.that(second.issues[0].code, eq="MD057")

    def test_markdown_fix_applies_the_auto_fixable_rules(self, tmp_path: Path) -> None:
        """`make fix APPLY=Y` repairs the markdown findings that check blocks on.

        mro-38p39: the markdown gate reports MD009/MD012 with the linter's own
        `[*]` auto-fixable marker, but declared can_fix=False. So `make check`
        blocked on ten findings while `make fmt APPLY=Y` and `make fix APPLY=Y`
        both exited 0 without repairing any of them -- the canonical sequence
        could never reach green, and the only way out was hand-editing a file
        the gate owns.

        The gate uses the tool's formatter so a successful repair exits zero even
        when the input also contains non-fixable findings.
        """
        project_dir = u.Tests.mk_project(tmp_path, "markdown-fix-project")
        (project_dir / "README.md").write_text("# Title   \n", encoding="utf-8")
        runner = self.make_runner(r.ok(u.Tests.stub_run()))
        context = m.Infra.GateContext(
            workspace=tmp_path, reports_dir=tmp_path, apply_fixes=True
        )

        gate = FlextInfraMarkdownGate(tmp_path, runner=runner)
        result = gate.fix(project_dir, context)

        tm.that(result.result.passed, eq=True)
        tm.that(runner.commands, ne=[])
        tm.that(runner.commands[0], has="fmt")
        tm.that(runner.commands[0], lacks="--fix")


__all__: t.StrSequence = []
