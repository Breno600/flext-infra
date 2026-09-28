"""Declared signature migrations rewrite call sites through the public verb."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, main as infra_main, u


@pytest.mark.slow
class TestsFlextInfraRefactorSignaturePropagation:
    """Prove a parameter rename reaches every call site from one declaration."""

    @staticmethod
    def _declare(workspace: Path, body: str) -> None:
        """Write the repository's declared signature catalogue."""
        tm.ok(
            u.Cli.atomic_write_text_file(
                workspace / c.Infra.REFACTOR_SIGNATURE_RULES_RELPATH, body
            )
        )

    def test_declared_rename_rewrites_every_call_site(
        self, mod_workspace: Path
    ) -> None:
        """One declaration renames the keyword at each call, not one by one."""
        self._declare(
            mod_workspace,
            (
                "migrations:\n"
                "  - id: session-value-to-session\n"
                "    target_simple_names: [publish]\n"
                "    keyword_renames:\n"
                "      session_value: session\n"
            ),
        )
        # The orchestrator scans a project's declared source root, which is
        # where consumer call sites live.
        package = next((mod_workspace / c.Infra.DEFAULT_SRC_DIR).iterdir())
        module = package / "call_sites.py"
        tm.ok(
            u.Cli.atomic_write_text_file(
                module, "publish(session_value=1)\npublish(session_value=2)\n"
            )
        )

        exit_code = infra_main([
            "refactor",
            "propagate-signatures",
            "--repository-root",
            str(mod_workspace),
            "--apply",
        ])
        rewritten = module.read_text(encoding="utf-8")

        tm.that(exit_code, eq=0)
        tm.that(rewritten.count("session="), eq=2)
        tm.that(rewritten, lacks="session_value=")

    def test_an_empty_catalogue_reports_instead_of_inventing_work(
        self, mod_workspace: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No declared migration is the steady state, never a failure."""
        self._declare(mod_workspace, "migrations: []\n")

        exit_code = infra_main([
            "refactor",
            "propagate-signatures",
            "--repository-root",
            str(mod_workspace),
            "--apply",
        ])
        capture = capsys.readouterr()

        tm.that(exit_code, eq=0)
        tm.that(capture.out + capture.err, has="no migration declared")

    def test_a_migration_without_a_rewrite_fails_loud(
        self, mod_workspace: Path
    ) -> None:
        """A declaration that targets callables but rewrites nothing is a defect."""
        self._declare(
            mod_workspace,
            "migrations:\n  - id: empty-rewrite\n    target_simple_names: [publish]\n",
        )

        exit_code = infra_main([
            "refactor",
            "propagate-signatures",
            "--repository-root",
            str(mod_workspace),
            "--apply",
        ])

        tm.that(exit_code, ne=0)
