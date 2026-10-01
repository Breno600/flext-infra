"""Syntax acceptance precedes every CSV campaign publication effect.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import m, u
from flext_infra.codemod import FlextInfraApplyRenames


class TestsRenamePreflight:
    """Observe real native rename events without replacing publication owners."""

    @staticmethod
    def test_target_override_rejects_the_campaign_before_text_publication(
        mod_workspace: Path,
    ) -> None:
        """Test target override rejects the campaign before text publication."""
        driver = mod_workspace / "renames.csv"
        driver.write_text("old,new\nOld,New\n", encoding="utf-8")
        (mod_workspace / "definer.py").write_text(
            "class Public:\n    New = 37\n",
            encoding="utf-8",
        )
        consumer = mod_workspace / "consumer.py"
        original = "from definer import Public\nclass Derived(Public):\n    New = 99\nvalue = Derived.Old\n"
        consumer.write_text(original, encoding="utf-8")
        guide = mod_workspace / "guide.md"
        guide.write_text("Old\n", encoding="utf-8")
        with pytest.raises(ValueError, match="overrides the declared destination"):
            FlextInfraApplyRenames.run(
                m.Infra.ApplyRenamesInput(
                    csv=str(driver),
                    roots=(str(mod_workspace),),
                    apply=True,
                    bindings={"": ("definer.Public",)},
                    text_globs=("**/*.md",),
                ),
            )
        tm.that(consumer.read_text(), eq=original)
        tm.that(guide.read_text(), eq="Old\n")

    @staticmethod
    def test_invalid_docstring_replacement_has_no_publication(
        mod_workspace: Path,
    ) -> None:
        """Test invalid docstring replacement has no publication."""
        guide = mod_workspace / "guide.md"
        source = mod_workspace / "syntax.py"
        guide.write_text("campaign_token\n", encoding="utf-8")
        source.write_text('"""campaign_token"""\n', encoding="utf-8")
        (mod_workspace / "renames.csv").write_text(
            'old,new\ncampaign_token,""""\n',
            encoding="utf-8",
        )
        script = (
            "import sys\nfrom pathlib import Path\nimport pytest\n"
            "from flext_infra import m\n"
            "from flext_infra.codemod import FlextInfraApplyRenames\n"
            "root = Path(sys.argv[1])\neffects = []\n"
            "def observe(event, args):\n"
            "    if event == 'os.rename' and Path(str(args[1])).name in {'guide.md', 'syntax.py'}:\n"
            "        effects.append(event)\n"
            "sys.addaudithook(observe)\n"
            "with pytest.raises(SyntaxError):\n"
            "    FlextInfraApplyRenames.run(m.Infra.ApplyRenamesInput(\n"
            "        csv=str(root / 'renames.csv'), roots=(str(root),), apply=True,\n"
            "        text_globs=('**/*.md',), python_documentation=True))\n"
            "print(len(effects))\n"
        )
        output = tm.ok(u.Cli.run((sys.executable, "-c", script, str(mod_workspace))))
        tm.that(output.stdout, eq="0\n")
        tm.that(guide.read_text(), eq="campaign_token\n")
        tm.that(source.read_text(), eq='"""campaign_token"""\n')
