"""A blanket Ruff mask or an unauthorized exception is unrepresentable.

``ALL`` disables every lint rule for its scope. It is a mask, not a policy: it
hides real defects and it cannot be reviewed, because the set of rules it
suppresses is unbounded and changes with every Ruff release. Each exception
names its rules and carries the operator ruling that authorized it.

The tooling owner is the only place an exception is declared; these tests pin
its typed boundary, so no configuration that renders a blanket mask or an
unauthorized exception can be constructed at all.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pytest
from flext_tests import tm

from flext_infra import config, m, t


class TestsFlextInfraRuffBlanketMaskIsUnrepresentable:
    """Tests for ``FlextInfraRuffBlanketMaskIsUnrepresentable``."""

    SCOPE = "src/flext_sample/_config.py"

    @staticmethod
    def _lint_policy(*exceptions: t.JsonDict) -> t.JsonDict:
        """Return the shipped fleet lint policy with its exceptions replaced.

        Returns:
            The shipped fleet lint policy with its exceptions replaced.

        """
        policy = config.Infra.tooling.tools.ruff.lint.model_dump(
            mode="json",
            by_alias=True,
            exclude_computed_fields=True,
        )
        return {**policy, "authorized-exceptions": list(exceptions)}

    @staticmethod
    def _exception(*rules: str, files: str | None = SCOPE) -> t.JsonDict:
        """Return one authorized exception entry for the sample scope.

        Returns:
            One authorized exception entry for the sample scope.

        """
        entry: t.JsonDict = {
            "rules": list(rules),
            "authority": "operator-ruling-sample",
            "reason": "The sample scope cannot hold these rules.",
        }
        return entry if files is None else {**entry, "files": files}

    @staticmethod
    def test_fleet_policy_declares_no_blanket_mask() -> None:
        """No shipped exception suppresses every rule."""
        lint = config.Infra.tooling.tools.ruff.lint

        masked = {
            entry.files or "every file"
            for entry in lint.authorized_exceptions
            if any(rule.strip().upper() == "ALL" for rule in entry.rules)
        }

        tm.that(masked, eq=set())

    @pytest.mark.parametrize("name", ["__basse__", "__init_subclas__", "__custom__"])
    def test_native_descriptor_policy_rejects_unapproved_names(
        self,
        name: str,
    ) -> None:
        """Unrelated or misspelled dunders cannot enter the native allowlist."""
        payload = self._lint_policy()
        payload["pylint"] = {"allow-dunder-method-names": [name]}

        with pytest.raises(m.ValidationError) as failure:
            _ = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(str(failure.value), has=name)

    @pytest.mark.parametrize("files", ["src/flext_sample/generated.py", None])
    def test_typed_boundary_rejects_a_blanket_mask_for_any_scope(
        self,
        files: str | None,
    ) -> None:
        """The typed boundary refuses ALL, scoped or not."""
        payload = self._lint_policy(self._exception("ALL", files=files))

        with pytest.raises(m.ValidationError) as failure:
            _ = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(str(failure.value), has="ALL")

    def test_scoped_exception_renders_as_per_file_ignores(self) -> None:
        """A named rule for one glob renders under that glob only."""
        payload = self._lint_policy(self._exception("invalid-function-name"))

        parsed = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(parsed.per_file_ignores, eq={self.SCOPE: ("invalid-function-name",)})
        tm.that(parsed.ignore, eq=())

    def test_unscoped_exception_renders_as_ignore(self) -> None:
        """A named rule without a glob is excepted for every file."""
        payload = self._lint_policy(
            self._exception("invalid-function-name", files=None),
        )

        parsed = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(parsed.ignore, eq=("invalid-function-name",))
        tm.that(parsed.per_file_ignores, eq={})

    def test_surrounding_whitespace_is_normalized_away(self) -> None:
        """A padded rule renders as its bare name, never with its padding."""
        payload = self._lint_policy(self._exception("  invalid-function-name  "))

        parsed = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(parsed.per_file_ignores, eq={self.SCOPE: ("invalid-function-name",)})

    def test_whitespace_only_rule_is_rejected(self) -> None:
        """Blank padding names no rule, so it cannot be an exception."""
        payload = self._lint_policy(self._exception("   "))

        with pytest.raises(m.ValidationError):
            _ = m.Infra.RuffLintConfig.model_validate(payload)

    def test_exception_without_authority_is_rejected(self) -> None:
        """An exception exists only with the ruling that authorized it."""
        entry = self._exception("invalid-function-name")
        unauthorized: t.JsonDict = {
            key: value for key, value in entry.items() if key != "authority"
        }
        payload = self._lint_policy(unauthorized)

        with pytest.raises(m.ValidationError) as failure:
            _ = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(str(failure.value), has="authority")

    def test_exception_declared_twice_is_rejected(self) -> None:
        """One rule excepted twice for one scope is an ambiguous record."""
        payload = self._lint_policy(
            self._exception("invalid-function-name"),
            self._exception("invalid-function-name"),
        )

        with pytest.raises(m.ValidationError) as failure:
            _ = m.Infra.RuffLintConfig.model_validate(payload)

        tm.that(str(failure.value), has="declared twice")
