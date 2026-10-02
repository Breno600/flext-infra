"""The parsed rule catalog is cached by content and never served stale.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import c, config
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRuleCatalogCache:
    """Drive the public rule plan against a real local provider."""

    @staticmethod
    def _project(tmp_path: Path, message: str) -> tuple[Path, Path]:
        project = tmp_path / "catalog-cache"
        config_path = project / c.Infra.CODEMOD_CONFIG_RELPATH
        rules = config_path.parent / c.Cli.RULES_DIR_NAME
        rules.mkdir(parents=True, exist_ok=True)
        (project / "src").mkdir(exist_ok=True)
        (project / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "catalog-cache"\nversion = "1.0.0"\ndependencies = []\n',
            encoding="utf-8",
        )
        config_path.write_text(
            f"ruleDirs: [{c.Cli.RULES_DIR_NAME}]\n",
            encoding="utf-8",
        )
        rule = rules / "only.yml"
        rule.write_text(
            "id: cache-only\nlanguage: Python\nseverity: error\n"
            f"message: {message}\nrule:\n  pattern: only($VALUE)\n",
            encoding="utf-8",
        )
        return project, rule

    @staticmethod
    def _entries() -> frozenset[str]:
        directory = u.Infra.external_cache_directory(
            config.Infra.codegen.make.codemod_rules_cache,
        )
        if not directory.is_dir():
            return frozenset()
        return frozenset(entry.name for entry in directory.iterdir())

    def test_a_plan_publishes_one_entry_per_catalog_content(
        self,
        tmp_path: Path,
    ) -> None:
        """Planning writes the catalog once; the same content adds nothing."""
        project, _ = self._project(tmp_path, "first")
        before = self._entries()

        first = tm.ok(u.Infra.codemod_rule_plan(project))
        published = self._entries() - before
        again = tm.ok(u.Infra.codemod_rule_plan(project))

        tm.that(published, empty=False)
        tm.that(self._entries() - before, eq=published)
        tm.that(
            tuple(rule.digest for rule in again.rules),
            eq=tuple(rule.digest for rule in first.rules),
        )

    def test_an_edited_rule_is_a_new_key_never_the_stale_rule(
        self,
        tmp_path: Path,
    ) -> None:
        """Changing a rule's text re-parses it under a new content key."""
        project, rule = self._project(tmp_path, "before")
        first = tm.ok(u.Infra.codemod_rule_plan(project))
        after_first = self._entries()

        rule.write_text(
            rule.read_text(encoding="utf-8").replace("before", "after"),
            encoding="utf-8",
        )
        second = tm.ok(u.Infra.codemod_rule_plan(project))

        tm.that(self._entries() - after_first, empty=False)
        local = {rule.id: rule.digest for rule in first.rules}
        edited = {rule.id: rule.digest for rule in second.rules}
        tm.that(edited["cache-only"], ne=local["cache-only"])
