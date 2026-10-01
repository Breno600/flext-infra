"""A blanket Ruff mask is unrepresentable, not merely detected after the fact.

``ALL`` in ``per-file-ignores`` disables every lint rule for a path. It is a
mask, not a policy: it hides real defects and it cannot be reviewed, because
the set of rules it suppresses is unbounded and changes with every Ruff
release. Each exemption names its rule.

The tooling owner is the only place a per-file exemption is declared; these
tests pin its typed boundary, so no configuration that renders a blanket mask
can be constructed at all.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pytest
from flext_tests import tm

from flext_infra import config, m, t


class TestsFlextInfraRuffBlanketMaskIsUnrepresentable:
    @staticmethod
    def _lint_policy(per_file_ignores: t.JsonDict) -> t.JsonDict:
        """Return the shipped fleet lint policy with one replaced exemption map."""
        policy = config.Infra.tooling.tools.ruff.lint.model_dump(
            mode="json", by_alias=True,
        )
        return {**policy, "per-file-ignores": per_file_ignores}

    def test_fleet_policy_declares_no_blanket_mask(self) -> None:
        """No glob in the shipped fleet policy suppresses every rule."""
        per_file_ignores = config.Infra.tooling.tools.ruff.lint.per_file_ignores

        masked = {
            pattern
            for pattern, rules in per_file_ignores.items()
            if any(rule.strip().upper() == "ALL" for rule in rules)
        }

        tm.that(masked, eq=set())

    def test_fleet_policy_rejects_a_blanket_mask_for_any_glob(self) -> None:
        """The typed boundary refuses ALL, not just for ``**/__init__.py``."""
        payload = self._lint_policy({"src/flext_sample/generated.py": ["ALL"]})

        with pytest.raises(m.ValidationError) as failure:
            _ = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(str(failure.value), has="ALL")

    def test_named_rule_exemptions_remain_representable(self) -> None:
        """Rejecting the mask must not reject a named per-rule exemption."""
        payload = self._lint_policy({"src/flext_sample/_config.py": ["N802"]})

        parsed = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(parsed.per_file_ignores["src/flext_sample/_config.py"], eq=("N802",))

    def test_surrounding_whitespace_is_normalized_away(self) -> None:
        """A padded rule renders as its bare name, never with its padding."""
        payload = self._lint_policy({"src/flext_sample/_config.py": ["  N802  "]})

        parsed = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(parsed.per_file_ignores["src/flext_sample/_config.py"], eq=("N802",))

    def test_whitespace_only_rule_is_rejected(self) -> None:
        """Blank padding names no rule, so it cannot be an exemption."""
        payload = self._lint_policy({"src/flext_sample/_config.py": ["   "]})

        with pytest.raises(m.ValidationError):
            _ = m.Infra.RuffLintConfig.model_validate(payload)
