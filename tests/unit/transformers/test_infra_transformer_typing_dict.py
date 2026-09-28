r"""Deactivation contract for the ENFORCE-031/ENFORCE-032 Dict fix targets.

Both transformers rewrote sources with a raw regex over the whole file
(``\bDict\s*\[`` and ``\btyping\s*\.\s*Dict\s*\[``). A regex cannot tell
a type node from text, so one run rewrote docstrings that documented the
pattern, comments naming it, and the string literals of this package's own
rewrite tables — corrupting ten files. Regex rewriting is not an approved
surface; only ast-grep codemod rules (``make mod``) and rope are. The rewrite is
recomposed as the ast-grep rule ``typing-dict-to-mapping-kv`` (with the
detection-only companion ``typing-dict-missing-t-import``), which matches
tree-sitter nodes and therefore cannot reach a string, docstring or comment.
The transformer fix targets are deactivated: the violation is still reported,
the automatic rewrite is off.

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


class TestsFlextInfraTypingDictDeactivated:
    """Runtime contract for the deactivated Dict rewrite fix targets."""

    _DEACTIVATED_TARGETS = ("typing_dict_import", "typing_dict_attr")

    # Every construct the regex corrupted, in one module: a docstring documenting
    # the pattern, a rewrite table holding it as string data, a comment naming it,
    # and the real annotations that are the only legitimate rewrite targets.
    _CORRUPTION_PROBE_SOURCE = '''"""Rewrite ``Dict[K, V]`` to ``t.MappingKV[K, V]``."""


import typing
from typing import Dict

from flext_core import t

_REWRITES = (("Dict[", "t.MappingKV"), ("typing.Dict[", "t.MappingKV"))

# A comment naming Dict[...] and typing.Dict[...] must survive untouched.


def bare(x: Dict[str, int]) -> None:
    """Take a Dict[str, int] as documented here."""


def attr(y: typing.Dict[str, int]) -> None:
    """Take a typing.Dict[str, int] as documented here."""
'''

    def _rule(self, target: str) -> m.EnforcementRuleSpec:
        """Return the enabled catalog rule whose fix target is deactivated."""
        catalog = u.build_canonical_catalog()
        return next(
            rule
            for rule in catalog.enabled_rules()
            if rule.fix_action is not None and rule.fix_action.target == target
        )

    def test_adapter_still_owns_the_catalog_fix_actions(self, tmp_path: Path) -> None:
        """The adapter keeps claiming both actions so preflight resolves."""
        adapter = FlextInfraTransformerFixerAdapter(tmp_path)
        for target in self._DEACTIVATED_TARGETS:
            fix_action = self._rule(target).fix_action
            tm.that(fix_action is None, eq=False)
            if fix_action is not None:
                tm.that(adapter.can_fix(fix_action), eq=True)

    def test_corruption_probe_is_left_byte_identical(self, tmp_path: Path) -> None:
        """Applying either fix rewrites nothing and reports the deactivation."""
        for target in self._DEACTIVATED_TARGETS:
            module = tmp_path / f"{target}_probe.py"
            module.write_text(self._CORRUPTION_PROBE_SOURCE, encoding="utf-8")
            rule = self._rule(target)
            probe = SimpleNamespace(file_path=str(module))
            adapter = FlextInfraTransformerFixerAdapter(tmp_path)
            ctx = m.Infra.FixEnforcementCommand(
                repository_root=tmp_path, apply=True, check_after=False
            )
            result = adapter.fix_project(tmp_path, ((rule, probe),), ctx)
            tm.that(
                module.read_text(encoding="utf-8"), eq=self._CORRUPTION_PROBE_SOURCE
            )
            tm.that(result.fixed, eq=())
            tm.that(len(result.skipped), eq=1)
            tm.that(result.skipped[0].rule_id, eq=rule.id)
            tm.that(result.skipped[0].reason, has="deactivated")
