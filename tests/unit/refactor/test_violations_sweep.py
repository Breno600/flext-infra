"""Refactor violations-sweep: repair through the canonical verbs, prove reduction.

Every case drives the public ``refactor violations-sweep`` CLI over the real
mod-workspace fixture with a recording Makefile standing in for the repair
verbs, so the sweep's own scans, receipt, and always-reducing verdict are the
behavior under test.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import c, m, main, u

if TYPE_CHECKING:
    from collections.abc import Iterator


RECORDING_MAKEFILE = (
    ".PHONY: fix fmt mod\nfix fmt mod:\n\t@printf '%s\\n' '$@' >> ran.txt\n"
)

MOD_GROWS_MAKEFILE = (
    ".PHONY: fix fmt mod\n"
    "fix fmt mod:\n"
    "\t@printf '%s\\n' '$@' >> ran.txt\n"
    "\t@printf 'marker = dict()\\n' > violating.py\n"
)

LOCAL_RULE_CATALOG = "ruleDirs:\n  - rules\ntestConfigs: []\n"

LOCAL_GROWTH_RULE = (
    "id: sweep-growth\n"
    "language: Python\n"
    "rule:\n"
    "  pattern: marker = dict()\n"
    "fix: marker = tuple()\n"
    "severity: warning\n"
)


class TestsFlextInfraRefactorViolationsSweep:
    """Behavior contract for the ``refactor violations-sweep`` verb."""

    @staticmethod
    def _prepare(root: Path, *, makefile: str, local_rule: bool) -> None:
        """Install the recording repair surface and the optional growth rule."""
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / c.Infra.MAKEFILE_FILENAME,
                makefile,
            ),
        )
        if local_rule:
            config_path = root / c.Infra.CODEMOD_CONFIG_RELPATH
            rules = config_path.parent / c.Cli.RULES_DIR_NAME
            tm.ok(u.Cli.ensure_dir(rules))
            tm.ok(u.Cli.atomic_write_text_file(config_path, LOCAL_RULE_CATALOG))
            tm.ok(
                u.Cli.atomic_write_text_file(
                    rules / "sweep.yml",
                    LOCAL_GROWTH_RULE,
                ),
            )

    @staticmethod
    def _sweep(root: Path) -> int:
        """Run the public violations-sweep CLI once.

        Returns:
            The resulting ``int``.

        """
        return main([
            c.Infra.CLI_GROUP_REFACTOR,
            c.Infra.VIOLATIONS_SWEEP_ROUTE_NAME,
            "--repository-root",
            str(root),
        ])

    @staticmethod
    def _receipt(root: Path) -> m.Infra.ViolationsSweepReport:
        """Load the typed receipt the verb publishes.

        Returns:
            The resulting ``m.Infra.ViolationsSweepReport``.

        """
        path = root / c.Infra.VIOLATIONS_SWEEP_REPORT_RELATIVE_PATH
        return m.Infra.ViolationsSweepReport.model_validate_json(
            path.read_bytes(),
        )

    @staticmethod
    def _verbs_ran(root: Path) -> Iterator[str]:
        """Yield the repair verbs the recording Makefile observed.

        Yields:
            Each recorded verb name.

        """
        lines = (root / "ran.txt").read_text(encoding="utf-8").splitlines()
        yield from (line for line in lines if line)

    def test_clean_tree_is_a_no_op_success_with_zero_delta(
        self,
        mod_workspace: Path,
    ) -> None:
        """The canonical sequence runs in order and no total moves."""
        root = mod_workspace
        self._prepare(root, makefile=RECORDING_MAKEFILE, local_rule=False)

        tm.that(self._sweep(root), eq=0)

        tm.that(
            list(self._verbs_ran(root)),
            eq=list(c.Infra.VIOLATIONS_SWEEP_REPAIR_VERBS),
        )
        report = self._receipt(root)
        tm.that(
            report.schema_version,
            eq=c.Infra.VIOLATIONS_SWEEP_REPORT_SCHEMA_VERSION,
        )
        tm.that(report.before, eq=report.after)
        tm.that(report.increased_totals, eq=())

    def test_rerun_republishes_identical_receipt(
        self,
        mod_workspace: Path,
    ) -> None:
        """A second sweep over the unchanged tree rewrites the same bytes."""
        root = mod_workspace
        self._prepare(root, makefile=RECORDING_MAKEFILE, local_rule=False)
        receipt_path = root / c.Infra.VIOLATIONS_SWEEP_REPORT_RELATIVE_PATH

        tm.that(self._sweep(root), eq=0)
        first = receipt_path.read_bytes()

        tm.that(self._sweep(root), eq=0)

        tm.that(receipt_path.read_bytes(), eq=first)

    def test_growing_total_fails_and_still_publishes_the_receipt(
        self,
        mod_workspace: Path,
    ) -> None:
        """A repair verb that adds a violation fails the command.

        The planted ``violating.py`` trips the local growth rule and the
        catalog's own detection rules, so the exact class mix is the
        catalog's; the law under test is that every total only moves down.
        """
        root = mod_workspace
        self._prepare(root, makefile=MOD_GROWS_MAKEFILE, local_rule=True)

        tm.that(self._sweep(root), ne=0)

        report = self._receipt(root)
        tm.that(
            "findings" in report.increased_totals,
            eq=True,
        )
        tm.that(
            report.after.findings > report.before.findings,
            eq=True,
        )
