"""OPTIONS=Y displays a built-in verb's contract without effects.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, m, u
from tests.unit.codegen.conform_support import TestsFlextInfraConformSupport

pytestmark = [pytest.mark.slow]


class TestsFlextInfraCodegenMakeVerbContract:
    """The generated contract mode runs no prerequisite, hook or handler."""

    @staticmethod
    def _scaffold(root: Path) -> None:
        """Materialize the generated Makefile with a hook that marks execution."""
        workspace = TestsFlextInfraConformSupport.standalone_workspace(root)
        TestsFlextInfraConformSupport.apply_conform_surface(
            root,
            workspace,
            c.Infra.CodegenConformSurface.MAKEFILE,
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk",
                ".PHONY: pre-upg pre-check\n"
                "pre-upg:\n\t@echo HOOK_RAN\n"
                "pre-check:\n\t@echo HOOK_RAN\n",
            ),
        )

    @staticmethod
    @pytest.mark.parametrize(
        ("verb", "selector"),
        [("upg", "OPTIONS=Y"), ("upg", "OPTIONS=yes"), ("check", "HELP=1")],
    )
    def test_contract_selector_displays_the_verb_without_effects(
        infra_git_repo: Path,
        verb: str,
        selector: str,
    ) -> None:
        """The verb prints its contract and leaves the tree untouched."""
        root = infra_git_repo
        TestsFlextInfraCodegenMakeVerbContract._scaffold(root)
        before = sorted(path.relative_to(root) for path in root.rglob("*"))
        outcome = u.Cli.run_raw(
            ["make", "-C", str(root), verb, selector],
            options=m.Cli.ProcessOptions(remove_env_keys=("MAKEFLAGS",)),
        )
        output = tm.ok(outcome)
        tm.that(
            u.Cli.process_succeeded(output.outcome),
            eq=True,
            msg=output.stdout + output.stderr,
        )
        tm.that(output.stdout, has=[verb, "displays this contract without effects"])
        tm.that(output.stdout + output.stderr, lacks="HOOK_RAN")
        after = sorted(path.relative_to(root) for path in root.rglob("*"))
        tm.that(after, eq=before)

    @staticmethod
    def test_disabled_selector_keeps_the_verb_executing(infra_git_repo: Path) -> None:
        """An empty or disabled selector still runs the verb's prerequisites."""
        root = infra_git_repo
        TestsFlextInfraCodegenMakeVerbContract._scaffold(root)
        outcome = u.Cli.run_raw(
            ["make", "-C", str(root), "check", "OPTIONS=N"],
            options=m.Cli.ProcessOptions(remove_env_keys=("MAKEFLAGS",)),
        )
        output = tm.ok(outcome)
        tm.that(u.Cli.process_succeeded(output.outcome), eq=False)
        tm.that(output.stderr, has="make upg records the Mise release")
        tm.that(output.stdout + output.stderr, lacks="displays this contract")
