"""Public mod circuit converges across semantic, AST, and text boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, main as infra_main, u
from flext_infra.codemod import FlextInfraModGateEngine


@pytest.mark.slow
class TestsJointModFixedPoint:
    """Exercise real configured rules through the public refactor CLI."""

    @staticmethod
    def _run(root: Path) -> int:
        """Invoke the same public application route as the workspace dispatcher."""
        return infra_main([
            "refactor",
            "mod",
            "--repository-root",
            str(root),
            "--apply",
        ])

    @staticmethod
    def _rules(root: Path, *, cycle: bool) -> None:
        """Declare a syntax rule and a text rule with no optional migration receipt."""
        rules = root / "codemod" / c.Cli.RULES_DIR_NAME
        u.Cli.ensure_dir(rules).unwrap()
        u.Cli.atomic_write_text_file(
            root / c.Infra.CODEMOD_CONFIG_FILENAME,
            "ruleDirs:\n  - codemod/rules\ntestConfigs: []\n",
        ).unwrap()
        u.Cli.atomic_write_text_file(
            rules / "joint.yml",
            "id: joint-ast\nlanguage: Python\nrule:\n"
            "  pattern: marker = dict()\nfix: marker = tuple()\nseverity: warning\n",
        ).unwrap()
        source = "tuple" if cycle else "list"
        u.Cli.atomic_write_text_file(
            root / c.Infra.CODEMOD_TEXT_RULES_RELPATH,
            "rules:\n  - id: joint-text\n"
            "    include: ['sample.py']\n"
            f"    find: 'marker = {source}\\(\\)'\n"
            "    replace: 'marker = dict()'\n",
        ).unwrap()

    def test_semantic_only_findings_are_applied_without_ast_rewrites(
        self, mod_workspace: Path
    ) -> None:
        """A missing future import selects its semantic owner on its own."""
        sample = mod_workspace / "sample.py"
        u.Cli.atomic_write_text_file(
            sample, '"""Semantic-only source."""\n\nmarker = tuple()\n'
        ).unwrap()
        before = FlextInfraModGateEngine.scan(mod_workspace, fix=False).unwrap()
        tm.that(before.actionable, eq=0)
        tm.that(
            any(
                item.rule_id == "require-future-annotations" for item in before.entries
            ),
            eq=True,
        )

        tm.that(self._run(mod_workspace), eq=0)

        first = sample.read_bytes()
        tm.that(first.decode(), has="from __future__ import annotations")
        tm.that(self._run(mod_workspace), eq=0)
        tm.that(sample.read_bytes(), eq=first)

    def test_text_exposes_ast_work_and_both_converge_idempotently(
        self, mod_workspace: Path
    ) -> None:
        """A text rewrite must not leave an actionable AST result behind success."""
        self._rules(mod_workspace, cycle=False)
        sample = mod_workspace / "sample.py"
        u.Cli.atomic_write_text_file(
            sample,
            '"""Cross-phase source."""\nfrom __future__ import annotations\n\nmarker = list()\n',
        ).unwrap()

        tm.that(self._run(mod_workspace), eq=0)

        first = sample.read_bytes()
        tm.that(first.decode(), has="marker = tuple()")
        tm.that(
            FlextInfraModGateEngine.scan(mod_workspace, fix=False).unwrap().actionable,
            eq=0,
        )
        tm.that(self._run(mod_workspace), eq=0)
        tm.that(sample.read_bytes(), eq=first)

    def test_cross_phase_cycle_fails_without_a_fixed_point_claim(
        self, mod_workspace: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AST and regex cannot alternate indefinitely or report a false fixed point."""
        self._rules(mod_workspace, cycle=True)
        sample = mod_workspace / "sample.py"
        u.Cli.atomic_write_text_file(
            sample,
            '"""Cyclic source."""\nfrom __future__ import annotations\n\nmarker = dict()\n',
        ).unwrap()

        tm.that(self._run(mod_workspace), ne=0)

        capture = capsys.readouterr()
        console = capture.out + capture.err
        tm.that(console, has="cross-phase cycle")
        tm.that(console, lacks="fixed point verified")
