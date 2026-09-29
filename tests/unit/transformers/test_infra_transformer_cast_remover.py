"""Deactivation contract for the ENFORCE-039 cast-remover fix target.

The cast remover rewrote sources through the raw ``ast`` module and removed
casts that were load-bearing (an untyped third-party module lookup, a
``Literal`` narrowing), raising the type-error count. Raw ``ast`` rewriting is
not an approved surface — only ast-grep codemod rules (``make mod``) and rope
are — and neither approved surface can decide whether a cast is redundant,
because that is a type-inference question. The fix target is therefore
deactivated: the violation is still reported, the automatic rewrite is off.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import m, u
from flext_infra.fixers.transformer_fixer import FlextInfraTransformerFixerAdapter

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraCastRemoverDeactivated:
    """Runtime contract for the deactivated cast-remover fix target."""

    _DEACTIVATED_TARGET = "cast_remover"

    _LOAD_BEARING_SOURCE = '''"""Probe module."""


from typing import Literal, cast


def link_count(value: object) -> Literal[1] | None:
    """Narrow an unknown value the checker cannot infer on its own."""
    return cast("Literal[1] | None", value)
'''

    def _rule(self) -> m.EnforcementRuleSpec:
        """Return the enabled catalog rule whose fix target is deactivated."""
        catalog = u.build_canonical_catalog()
        return next(
            rule
            for rule in catalog.enabled_rules()
            if rule.fix_action is not None
            and rule.fix_action.target == self._DEACTIVATED_TARGET
        )

    def test_adapter_still_owns_the_catalog_fix_action(self, tmp_path: Path) -> None:
        """The adapter keeps claiming the catalog action so preflight resolves."""
        fix_action = self._rule().fix_action
        tm.that(fix_action is None, eq=False)
        if fix_action is not None:
            adapter = FlextInfraTransformerFixerAdapter(tmp_path)
            tm.that(adapter.can_fix(fix_action), eq=True)

    def test_load_bearing_cast_file_is_left_untouched(self, tmp_path: Path) -> None:
        """Applying the fix rewrites nothing and reports the deactivation."""
        module = tmp_path / "probe.py"
        module.write_text(self._LOAD_BEARING_SOURCE, encoding="utf-8")
        rule = self._rule()
        probe = SimpleNamespace(file_path=str(module))
        adapter = FlextInfraTransformerFixerAdapter(tmp_path)
        ctx = m.Infra.FixEnforcementCommand(
            repository_root=str(tmp_path), apply=True, check_after=False
        )
        result = adapter.fix_project(tmp_path, ((rule, probe),), ctx)
        tm.that(module.read_text(encoding="utf-8"), eq=self._LOAD_BEARING_SOURCE)
        tm.that(result.fixed, eq=())
        tm.that(len(result.skipped), eq=1)
        tm.that(result.skipped[0].rule_id, eq=rule.id)
        tm.that(result.skipped[0].reason, has="deactivated")
