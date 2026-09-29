"""Declared finding-count receipts for ast-grep rules, through the public CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, main as infra_main, u


@pytest.mark.slow
class TestsFlextInfraModRuleExpectedReceipt:
    """Prove the ast-grep phase honours the receipt the sed phase already owns.

    Every case drives the real ``refactor mod`` CLI over a workspace, so they
    all belong to the declared slow class.
    """

    @staticmethod
    def _declare(workspace: Path, *, expected: str) -> None:
        """Point the workspace at one local rule carrying the receipt clause."""
        rules_root = workspace / "codemod" / c.Cli.RULES_DIR_NAME
        tm.ok(u.Cli.ensure_dir(rules_root))
        tm.ok(
            u.Cli.atomic_write_text_file(
                workspace / c.Infra.CODEMOD_CONFIG_FILENAME,
                "ruleDirs:\n  - codemod/rules\ntestConfigs: []\n",
            )
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                rules_root / "receipt-probe.yml",
                (
                    "id: receipt-probe\n"
                    "language: Python\n"
                    "severity: warning\n"
                    "rule:\n"
                    "  pattern: value = dict()\n"
                    "fix: value = list()\n"
                    "message: probe the declared receipt\n"
                    f"{expected}"
                ),
            )
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                workspace / "receipt_sample.py", "value = dict()\n"
            )
        )

    def test_scan_fails_loud_when_the_count_drifts_from_the_receipt(
        self, mod_workspace: Path
    ) -> None:
        """A rule declaring two findings over one occurrence is a defect.

        The receipt is a validator, so it escapes with its own exception and
        traceback rather than being translated into a finding or an exit code:
        the engine unwraps every scan, and a defect in the rule catalog is not
        a repairable finding.
        """
        self._declare(mod_workspace, expected="metadata:\n  expected: 2\n")

        with pytest.raises(
            RuntimeError,
            match=r"receipt-probe declares 2 finding\(s\), scan produced 1",
        ):
            infra_main(["refactor", "mod", "--repository-root", str(mod_workspace)])

    def test_a_matching_receipt_does_not_block_the_scan(
        self, mod_workspace: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A receipt that matches the occurrence count raises no receipt failure."""
        self._declare(mod_workspace, expected="metadata:\n  expected: 1\n")

        infra_main(["refactor", "mod", "--repository-root", str(mod_workspace)])
        capture = capsys.readouterr()

        tm.that(capture.out + capture.err, lacks="receipt-probe declares")
