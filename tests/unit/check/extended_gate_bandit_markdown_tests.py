"""Public Bandit and Markdown gate behavior against the real lane tools.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, ClassVar

import pytest
from flext_cli import cli
from flext_tests import tm

from flext_infra import config, m, t
from flext_infra.gates.bandit import FlextInfraBanditGate
from flext_infra.gates.markdown import FlextInfraMarkdownGate
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraBanditAndMarkdownGates:
    """Declarative public-contract tests for Bandit and Markdown gates."""

    BANDIT_OWNER_CASES: ClassVar[
        t.VariadicTuple[tuple[m.Infra.BanditAuthorizedException, str, str]]
    ] = tuple(
        (
            entry,
            pattern,
            pattern.replace("**/", "").replace("*", "probe").removesuffix(".py")
            + ".py",
        )
        for entry in config.Infra.tooling.tools.bandit.authorized_exceptions
        for pattern in entry.files
    )
    HEADING_SKIP = "# Test\n\n### Skip\n"
    REFLOW_HINT = (
        "# Test\n\n"
        "Alpha beta gamma delta epsilon zeta eta theta iota.\n"
        "Kappa lambda mu nu xi omicron pi rho sigma tau.\n"
    )
    LONG_LINE = "# Test\n\n" + " ".join(["word"] * 30) + "\n"
    # The .markdownlint.json projection renders this exact typed SSOT; tests
    # of the markdown contract read it instead of freezing a config literal.
    CANONICAL_MARKDOWNLINT_CONFIG: ClassVar[str] = cli.json_dumps(
        dict(config.Infra.tooling.tools.markdown.rules),
    ).unwrap()

    @staticmethod
    def test_bandit_reports_real_finding(tmp_path: Path) -> None:
        """Test bandit reports real finding."""
        project_dir = u.Tests.mk_project(tmp_path, "bandit-project")
        (project_dir / c.Infra.DEFAULT_SRC_DIR).mkdir()
        (project_dir / c.Infra.DEFAULT_SRC_DIR / "main.py").write_text(
            "def check(value):\n    assert value\n",
            encoding="utf-8",
        )

        result = u.Tests.check_gate_asserting(
            FlextInfraBanditGate,
            tmp_path,
            project_dir,
            passed=False,
            issues_len=1,
        )

        tm.that(result.issues[0].code, eq="B101")

    @staticmethod
    def test_bandit_excludes_generated_source_trees(tmp_path: Path) -> None:
        """Generated-source modules stay outside the audited package surface."""
        names = config.Infra.codegen.generated_sources
        tm.that(names, empty=False)
        project_dir = u.Tests.mk_project(tmp_path, "bandit-project")
        package = project_dir / c.Infra.DEFAULT_SRC_DIR / "pkg"
        tree = package / names[0]
        tree.mkdir(parents=True)
        for module in (tree / "wire_pb2.py", package / "main.py"):
            module.write_text("def check(value):\n    assert value\n", encoding="utf-8")

        result = u.Tests.check_gate_asserting(
            FlextInfraBanditGate,
            tmp_path,
            project_dir,
            passed=False,
            issues_len=1,
        )

        tm.that(result.issues[0].file, has="main.py")

    @staticmethod
    @pytest.mark.parametrize(
        ("entry", "pattern", "owner"),
        BANDIT_OWNER_CASES,
    )
    def test_bandit_owner_scope_skips_only_its_authorized_tests(
        tmp_path: Path,
        entry: m.Infra.BanditAuthorizedException,
        pattern: str,
        owner: str,
    ) -> None:
        """An authorized owner module drops only its tests; others keep all.

        Premise (operator-ruling-2026-10-08-subprocess-test-imports): Bandit
        has no per-path exception, so the gate audits the owner modules in
        their own run that skips only the authorized tests.
        """
        # A literal Bandit exclusion for the owner also matches this filename;
        # the consumer must instead remain in the exact unowned partition.
        consumer = f"{c.Infra.DEFAULT_SRC_DIR}/consumer/{owner}_extra.py"
        entries = config.Infra.tooling.tools.bandit.authorized_exceptions
        tm.that(PurePosixPath(owner).full_match(pattern), eq=True)
        tm.that(
            any(
                PurePosixPath(consumer).full_match(authorized)
                for configured in entries
                for authorized in configured.files
            ),
            eq=False,
        )
        project_dir = u.Tests.mk_project(tmp_path, "bandit-owner-project")
        for relative in (owner, consumer):
            module = project_dir / relative
            module.parent.mkdir(parents=True, exist_ok=True)
            module.write_text(
                "import subprocess\n\n\ndef spawn(argv):\n"
                "    assert argv\n    return subprocess.run(argv, check=True)\n",
                encoding="utf-8",
            )

        result = u.Tests.run_gate_check(FlextInfraBanditGate, tmp_path, project_dir)

        codes = {
            relative: {issue.code for issue in result.issues if issue.file == relative}
            for relative in (owner, consumer)
        }
        tm.that(result.result.passed, eq=False)
        raised_codes = {"B101", "B404", "B603"}
        tm.that(codes[owner], eq=raised_codes - set(entry.tests))
        tm.that(codes[consumer], eq=raised_codes)

    @staticmethod
    @pytest.mark.parametrize(
        ("entry", "pattern", "owner"),
        BANDIT_OWNER_CASES,
    )
    def test_bandit_owner_scope_alone_obeys_its_authorized_tests(
        tmp_path: Path,
        entry: m.Infra.BanditAuthorizedException,
        pattern: str,
        owner: str,
    ) -> None:
        """An owner-only project's verdict follows the declared exception."""
        tm.that(PurePosixPath(owner).full_match(pattern), eq=True)
        project_dir = u.Tests.mk_project(tmp_path, "bandit-owner-only")
        module = project_dir / owner
        module.parent.mkdir(parents=True)
        module.write_text(
            "import subprocess\n\n\ndef spawn(argv):\n"
            "    return subprocess.run(argv, check=True)\n",
            encoding="utf-8",
        )

        result = u.Tests.run_gate_check(FlextInfraBanditGate, tmp_path, project_dir)

        remaining = {"B404", "B603"} - set(entry.tests)
        tm.that(result.result.passed, eq=not remaining, msg=str(result.issues))
        tm.that({issue.code for issue in result.issues}, eq=remaining)

    @staticmethod
    def test_bandit_syntax_error_is_a_failed_audit(tmp_path: Path) -> None:
        """Bandit's successful process exit cannot approve an unaudited source."""
        project = u.Tests.mk_project(tmp_path, "bandit-invalid-source")
        source = project / c.Infra.DEFAULT_SRC_DIR / "invalid.py"
        source.parent.mkdir(parents=True)
        source.write_text("def invalid(:\n", encoding="utf-8")

        result = u.Tests.run_gate_check(FlextInfraBanditGate, tmp_path, project)

        tm.that(result.result.passed, eq=False)
        tm.that(result.outcome, eq=c.Infra.ToolOutcome.ERROR)
        tm.that(result.issues, length=1)
        tm.that(result.issues[0].file, has=source.name)
        tm.that(result.issues[0].code, eq=c.Infra.ToolOutcome.ERROR.value)

    @staticmethod
    @pytest.mark.parametrize(
        ("pattern", "owner"),
        [(pattern, owner) for _, pattern, owner in BANDIT_OWNER_CASES],
    )
    def test_bandit_owner_cannot_alias_a_source_outside_the_project(
        tmp_path: Path,
        pattern: str,
        owner: str,
    ) -> None:
        """An owner path cannot grant subprocess relief to an external source."""
        tm.that(PurePosixPath(owner).full_match(pattern), eq=True)
        project = u.Tests.mk_project(tmp_path, "bandit-external-owner")
        external = tmp_path / "external.py"
        external.write_text("import subprocess\n", encoding="utf-8")
        source = project / owner
        source.parent.mkdir(parents=True)
        source.symlink_to(external)

        with pytest.raises(ValueError, match="is not in the subpath of"):
            u.Tests.run_gate_check(FlextInfraBanditGate, tmp_path, project)

    @staticmethod
    @pytest.mark.parametrize(
        "report",
        [
            "{}",
            '{"errors":[]}',
            '{"results":[]}',
            '{"results":null,"errors":[]}',
            '{"results":[],"errors":null}',
            '{"results":{},"errors":[]}',
            '{"results":[],"errors":{}}',
            '{"results":[{}],"errors":[]}',
            '{"results":[],"errors":[{}]}',
            '{"results":[],"errors":[{"filename":"source.py","reason":7}]}',
            (
                '{"results":[{"filename":"source.py","line_number":"1",'
                '"test_id":"B101","issue_text":"assert used"}],"errors":[]}'
            ),
        ],
    )
    def test_bandit_report_rejects_missing_or_malformed_native_arrays(
        report: str,
    ) -> None:
        """The public typed boundary rejects unauditable native report shapes."""
        result = u.validate_value(
            m.Infra.BanditReport,
            report,
            from_json=True,
            strict=True,
        )

        tm.that(result.failure, eq=True)

    @staticmethod
    def test_bandit_report_accepts_explicit_clean_native_arrays() -> None:
        """Two explicit empty native arrays represent a clean report."""
        result = u.validate_value(
            m.Infra.BanditReport,
            '{"results":[],"errors":[]}',
            from_json=True,
            strict=True,
        )

        tm.that(result.success, eq=True)
        report = result.unwrap()
        tm.that(report.results, empty=True)
        tm.that(report.errors, empty=True)

    @staticmethod
    def test_bandit_without_source_tree_has_no_audit_surface(
        tmp_path: Path,
    ) -> None:
        """A project without ``src`` does not select bandit at all.

        Premise (#1223 content selection): an unselected gate never runs and
        never passes; a direct check without inputs establishes no acceptance.
        """
        project_dir = u.Tests.mk_project(tmp_path, "p1")

        tm.that(FlextInfraBanditGate(tmp_path).selected_for(project_dir), eq=False)
        result = u.Tests.run_gate_check(FlextInfraBanditGate, tmp_path, project_dir)

        tm.that(result.result.passed, eq=False)
        tm.that(" | ".join(result.result.errors), has="no check targets were collected")

    @staticmethod
    def test_bandit_scans_large_tree_with_sanitized_path(tmp_path: Path) -> None:
        """The workspace interpreter runs Bandit without any PATH-provided tool."""
        project_dir = u.Tests.mk_project(tmp_path, "p1", with_src=True)
        for index in range(51):
            (project_dir / c.Infra.DEFAULT_SRC_DIR / f"module_{index}.py").write_text(
                "def identity(value):\n    return value\n",
                encoding="utf-8",
            )
        empty_path = tmp_path / "empty-path"
        empty_path.mkdir()

        with tm.scope(env={"PATH": str(empty_path)}):
            result = u.Tests.run_gate_check(FlextInfraBanditGate, tmp_path, project_dir)

        tm.that(result.result.passed, eq=True)
        tm.that(result.issues, eq=())
        tm.that(result.raw_output.startswith("{"), eq=True)
        tm.that(result.raw_output, lacks="Working...")

    @staticmethod
    @pytest.mark.parametrize(
        ("markdown_text", "config_text", "findings_block", "codes"),
        [
            (HEADING_SKIP, None, True, ["MD001"]),
            ("# Test\n", '{"broken": [', True, [c.Infra.ToolOutcome.ERROR]),
            # A residual MD013 reflow finding remains blocking when the
            # formatter cannot normalize the paragraph.
            (
                REFLOW_HINT,
                (
                    '{"MD013": {"line_length": 88, "reflow": true,'
                    ' "reflow-mode": "normalize"}}'
                ),
                True,
                ["MD013"],
            ),
            # A hand-wrapped document that rumdl's normalize pass would only
            # hint at must pass under the PROJECTED config: the canonical
            # MD013 declares reflow disabled (flext-md-converge: wrapping is
            # hand-owned — the normalize pass joins paragraphs into lines no
            # verb can repair), so the hint path cannot fire and the gate
            # reads the same typed rules SSOT the .markdownlint.json
            # projection renders. A hand-written config literal here would
            # freeze a shape no projection produces.
            (REFLOW_HINT, CANONICAL_MARKDOWNLINT_CONFIG, False, []),
        ],
    )
    def test_markdown_check(
        *,
        tmp_path: Path,
        markdown_text: str,
        config_text: str | None,
        findings_block: bool,
        codes: t.StrSequence,
    ) -> None:
        """Test markdown check."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-project")
        if markdown_text:
            (project_dir / "README.md").write_text(markdown_text, encoding="utf-8")
        if config_text is not None:
            (project_dir / c.Infra.MARKDOWNLINT_CONFIG_FILENAME).write_text(
                config_text,
                encoding="utf-8",
            )
        result = u.Tests.check_gate_asserting(
            FlextInfraMarkdownGate,
            tmp_path,
            project_dir,
            passed=not findings_block,
            issues_len=len(codes),
        )

        tm.that([issue.code for issue in result.issues], eq=list(codes))
        if codes:
            tm.that(
                [issue.severity.lower() for issue in result.issues],
                eq=[str(c.Infra.GateSeverity.ERROR.value)] * len(codes),
            )

    @staticmethod
    def test_markdown_gate_is_not_selected_without_markdown(
        tmp_path: Path,
    ) -> None:
        """A project without governed Markdown never selects the gate."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-empty")
        gate = FlextInfraMarkdownGate(tmp_path)

        tm.that(gate.selected_for(project_dir), eq=False)
        tm.that(
            gate.check(project_dir, u.Tests.gate_context(tmp_path)).result.passed,
            eq=False,
        )

    @staticmethod
    def test_bandit_is_not_selected_without_a_src_tree(tmp_path: Path) -> None:
        """A project without a ``src`` package surface never selects bandit."""
        bare = u.Tests.mk_project(tmp_path, "bandit-bare")
        packaged = u.Tests.mk_project(tmp_path, "bandit-packaged", with_src=True)

        tm.that(FlextInfraBanditGate(tmp_path).selected_for(bare), eq=False)
        tm.that(FlextInfraBanditGate(tmp_path).selected_for(packaged), eq=True)

    def test_markdown_applies_only_the_local_config(self, tmp_path: Path) -> None:
        """A standalone project's gate never crosses its repository boundary."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-local-owner")
        (project_dir / "README.md").write_text(self.LONG_LINE, encoding="utf-8")
        disabled = '{"MD013": false}'
        (tmp_path / c.Infra.MARKDOWNLINT_CONFIG_FILENAME).write_text(
            disabled,
            encoding="utf-8",
        )

        inherited = u.Tests.check_gate_asserting(
            FlextInfraMarkdownGate,
            tmp_path,
            project_dir,
            passed=False,
            issues_len=1,
        )
        (project_dir / c.Infra.MARKDOWNLINT_CONFIG_FILENAME).write_text(
            disabled,
            encoding="utf-8",
        )
        _ = u.Tests.check_gate_asserting(
            FlextInfraMarkdownGate,
            tmp_path,
            project_dir,
            passed=True,
            issues_len=0,
        )

        tm.that(inherited.issues[0].code, eq="MD013")

    @pytest.mark.parametrize(
        "owner_parts",
        [
            *sorted(
                (name,)
                for name in c.Infra.CHECK_EXCLUDED_DIRS - c.Infra.COMMON_EXCLUDED_DIRS
            ),
            *sorted((".github", name) for name in c.Infra.GITHUB_AGENT_PROJECTION_DIRS),
        ],
    )
    def test_markdown_excludes_non_project_markdown(
        self,
        tmp_path: Path,
        owner_parts: t.StrSequence,
    ) -> None:
        """Tracker storage and provider projections are not live project docs."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-excluded-owner")
        (project_dir / "README.md").write_text("# Test\n", encoding="utf-8")
        excluded = project_dir.joinpath(*owner_parts, "projected.md")
        excluded.parent.mkdir(parents=True, exist_ok=True)
        excluded.write_text(self.HEADING_SKIP, encoding="utf-8")

        _ = u.Tests.check_gate_asserting(
            FlextInfraMarkdownGate,
            tmp_path,
            project_dir,
            passed=True,
            issues_len=0,
        )

    def test_markdown_keeps_project_owned_github_markdown(self, tmp_path: Path) -> None:
        """Shared GitHub roots retain non-provider Markdown in the native gate."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-github-project-owner")
        (project_dir / "README.md").write_text("# Test\n", encoding="utf-8")
        project_owned = project_dir / ".github" / "prompts" / "project.md"
        project_owned.parent.mkdir(parents=True)
        project_owned.write_text(self.HEADING_SKIP, encoding="utf-8")

        result = u.Tests.check_gate_asserting(
            FlextInfraMarkdownGate,
            tmp_path,
            project_dir,
            passed=False,
            issues_len=1,
        )

        tm.that(result.issues[0].file, eq=".github/prompts/project.md")

    @staticmethod
    def test_markdown_uses_uv_managed_tool_with_sanitized_path(
        tmp_path: Path,
    ) -> None:
        """Prove the real gate cannot bind a host or mise-provided executable."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-managed-tool")
        (project_dir / "README.md").write_text("# Test\n", encoding="utf-8")
        empty_path = tmp_path / "empty-path"
        empty_path.mkdir()
        # Source discovery needs Git; the Markdown linter remains unavailable on PATH.
        (empty_path / "git").symlink_to(tm.not_none(shutil.which("git")))
        with tm.scope(env={"PATH": str(empty_path)}):
            result = FlextInfraMarkdownGate(tmp_path).check(
                project_dir,
                u.Tests.gate_context(tmp_path),
            )

        tm.that(result.result.passed, eq=True)
        tm.that(result.issues, eq=())

    @staticmethod
    def test_markdown_accepts_existing_nested_relative_link(
        tmp_path: Path,
    ) -> None:
        """Exercise the real linter's path resolution at the project boundary."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-relative-link")
        docs_dir = project_dir / "docs"
        target_dir = docs_dir / "generated"
        target_dir.mkdir(parents=True)
        (docs_dir / "README.md").write_text(
            "# Documentation\n\n[Overview](generated/overview.md)\n",
            encoding="utf-8",
        )
        (target_dir / "overview.md").write_text("# Overview\n", encoding="utf-8")

        result = FlextInfraMarkdownGate(tmp_path).check(
            project_dir,
            u.Tests.gate_context(tmp_path),
        )

        tm.that(result.result.passed, eq=True)
        tm.that(result.issues, eq=())

    @staticmethod
    def test_markdown_resolves_same_link_per_source_directory(
        tmp_path: Path,
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
            "# Overview\n",
            encoding="utf-8",
        )

        result = FlextInfraMarkdownGate(tmp_path).check(
            project_dir,
            u.Tests.gate_context(tmp_path),
        )

        tm.that(result.result.passed, eq=False)
        tm.that(len(result.issues), eq=1)
        tm.that(result.issues[0].file, eq="invalid/README.md")

    @staticmethod
    def test_markdown_rechecks_link_target_state_without_cache(
        tmp_path: Path,
    ) -> None:
        """A cached source hash must not hide a removed relative-link target."""
        project_dir = u.Tests.mk_project(tmp_path, "markdown-cache-state")
        target = project_dir / "target.md"
        (project_dir / "README.md").write_text(
            "# Documentation\n\n[Target](target.md)\n",
            encoding="utf-8",
        )
        target.write_text("# Target\n", encoding="utf-8")
        gate = FlextInfraMarkdownGate(tmp_path)

        first = gate.check(project_dir, u.Tests.gate_context(tmp_path))
        target.unlink()
        second = gate.check(project_dir, u.Tests.gate_context(tmp_path))

        tm.that(first.result.passed, eq=True)
        tm.that(second.result.passed, eq=False)
        tm.that(second.issues[0].code, eq="MD057")

    @staticmethod
    def test_markdown_fix_applies_the_auto_fixable_rules(tmp_path: Path) -> None:
        """`make fix` repairs the markdown findings that check blocks on.

        The markdown gate reports MD009/MD012 with the linter's own
        `[*]` auto-fixable marker, but declared can_fix=False. So `make check`
        blocked on findings while `make fmt` and `make fix` both exited 0
        without repairing any of them. The gate uses the tool's formatter so a
        successful repair exits zero and leaves the file clean for `check`.
        """
        project_dir = u.Tests.mk_project(tmp_path, "markdown-fix-project")
        readme = project_dir / "README.md"
        readme.write_text("# Title   \n", encoding="utf-8")
        u.Tests.initialize_git_repo(project_dir)
        context = m.Infra.GateContext(
            repository_root=tmp_path,
            reports_dir=tmp_path,
            apply_fixes=True,
        )

        result = FlextInfraMarkdownGate(tmp_path).fix(project_dir, context)

        tm.that(result.result.passed, eq=True)
        tm.that(readme.read_text(encoding="utf-8"), eq="# Title\n")
        _ = u.Tests.check_gate_asserting(
            FlextInfraMarkdownGate,
            tmp_path,
            project_dir,
            passed=True,
            issues_len=0,
        )
