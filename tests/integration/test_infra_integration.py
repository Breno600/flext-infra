"""Integration tests for flext_infra cross-module flows.

Every test here exercises a real cross-module flow through the public
runtime surfaces: the markdown gate fix contract over the filesystem, and
the canonical CLI process boundary driving real git and external commands.
Detector, discovery, and result-monad behavior keep their dedicated suites.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraMarkdownGate, m
from tests import TestsFlextInfraUtilities as tu, u

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]


class TestsFlextInfraIntegrationInfraIntegration:
    """Integration tests for the public FlextInfra surface."""

    @staticmethod
    @pytest.mark.integration
    def test_markdown_fix_reports_residual_after_repair(tmp_path: Path) -> None:
        """A fixable finding is repaired; an unfixable one stays reported for check."""
        project_dir = tu.Tests.mk_project(tmp_path, "markdown-fmt-contract")
        document = project_dir / "README.md"
        document.write_text("not a heading   \n", encoding="utf-8")
        tu.Tests.initialize_git_repo(project_dir)
        context = m.Infra.GateContext(
            repository_root=tmp_path,
            reports_dir=tmp_path,
            apply_fixes=True,
        )

        execution = FlextInfraMarkdownGate(tmp_path).fix(project_dir, context)

        # rumdl completed under its declared findings status: the repair
        # verb does not break, and the residual finding stays reported.
        tm.that(execution.result.passed, eq=True)
        tm.that(document.read_text(encoding="utf-8"), eq="not a heading\n")
        tm.that(execution.issues[0].code, eq="MD041")

    @staticmethod
    @pytest.mark.integration
    def test_markdown_check_retains_normalization_finding(tmp_path: Path) -> None:
        """A native MD013 normalization diagnostic remains visible to callers."""
        project_dir = tu.Tests.mk_project(tmp_path, "markdown-normalization")
        (project_dir / ".markdownlint.json").write_text(
            tm.ok(
                u.Cli.json_dumps({
                    "default": False,
                    "MD013": {
                        "line_length": 60,
                        "reflow": True,
                        "reflow-mode": "normalize",
                    },
                }),
            ),
            encoding="utf-8",
        )
        (project_dir / "README.md").write_text(
            "# Title\n\nThis paragraph has\n"
            "several short lines that could be joined without\n"
            "changing the meaning of its content.\n",
            encoding="utf-8",
        )
        tu.Tests.initialize_git_repo(project_dir)

        execution = FlextInfraMarkdownGate(tmp_path).check(
            project_dir,
            m.Infra.GateContext(repository_root=tmp_path, reports_dir=tmp_path),
        )

        tm.that(execution.result.passed, eq=False)
        tm.that(execution.issues[0].code, eq="MD013")

    @staticmethod
    @pytest.mark.integration
    def test_cli_capture_git_current_branch_in_real_repo(tmp_path: Path) -> None:
        """Test git branch detection through the canonical CLI runtime surface."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        init_result = u.Cli.run_checked(["git", "init"], cwd=repo_root)
        tm.ok(init_result)
        email_result = u.Cli.run_checked(
            ["git", "config", "user.email", "infra@example.com"],
            cwd=repo_root,
        )
        tm.ok(email_result)
        name_result = u.Cli.run_checked(
            ["git", "config", "user.name", "Infra Test"],
            cwd=repo_root,
        )
        tm.ok(name_result)
        sample_file = repo_root / "README.md"
        _ = sample_file.write_text("infra test\n", encoding="utf-8")
        add_result = u.Cli.run_checked(["git", "add", "README.md"], cwd=repo_root)
        tm.ok(add_result)
        commit_result = u.Cli.run_checked(
            ["git", "commit", "-m", "initial"],
            cwd=repo_root,
        )
        tm.ok(commit_result)
        branch_result = u.Cli.capture(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
        )
        tm.ok(branch_result)
        tm.that(branch_result.value, ne="")

    @staticmethod
    @pytest.mark.integration
    def test_command_runner_capture_executes_real_command() -> None:
        """Test u.Cli.capture with a real external command."""
        capture_result = u.Cli.capture(["python3", "-c", "print('infra-ok')"])
        tm.ok(capture_result)
        tm.that(capture_result.value, eq="infra-ok")
