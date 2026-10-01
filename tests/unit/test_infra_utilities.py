"""Tests for u facade.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from pathlib import Path

from flext_tests import tm

from flext_infra import c
from tests import u


class TestsFlextInfraInfraUtilities:
    """Test u class import and structure."""

    def test_extract_definition_keeps_multiline_class_header_intact(self) -> None:
        """Multi-line class headers must keep their closing line during extraction."""
        source = (
            "class ExamplesFlextModels(\n"
            "    m,\n"
            "):\n"
            '    """Doc."""\n'
            "\n"
            "    class Examples:\n"
            "        pass\n"
        )

        block = u.Infra.extract_definition(source, "ExamplesFlextModels", kind="class")

        tm.that(u.Infra.bracket_balance_line("class ExamplesFlextModels("), eq=1)
        tm.that(block, eq=source.rstrip("\n"))

    def test_ast_grep_command_loads_utility_rules_from_owner_config(self) -> None:
        """Build scans through sgconfig so shared utility matches always resolve."""
        root = Path(__file__).parents[2]
        rule = (
            root
            / c.Infra.CODEMOD_CONFIG_RELPATH.parent
            / c.Cli.RULES_DIR_NAME
            / "config-dict-type-from-typings.yml"
        )

        command = u.Infra.ast_grep_scan_command(rule)

        tm.that(command, has=c.Infra.SG_CONFIG_FLAG)
        tm.that(command, has=c.Infra.SG_FILTER_FLAG)
        rule_filter = command[command.index(c.Infra.SG_FILTER_FLAG) + 1]
        tm.that(re.fullmatch(rule_filter, rule.stem) is not None, eq=True)
        tm.that(re.fullmatch(rule_filter, f"{rule.stem}-other") is None, eq=True)
        tm.that(re.fullmatch(rule_filter, f"other-{rule.stem}") is None, eq=True)
        tm.that(command, lacks="--rule")
