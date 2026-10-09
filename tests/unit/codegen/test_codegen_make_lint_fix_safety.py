"""make fix never deletes information: the lint repair applies safe fixes only.

Ruff's unsafe fixes delete code: the T201 fix removed
``print(..., file=sys.stderr)`` from a consumer script and turned its failures
silent. The typed Make contract refuses the unsafe-fix flag, and every
generated pyproject carries the fix-safety policy of the tooling SSOT, so a
direct or IDE Ruff run follows the same policy as ``make fix``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraCodegenMakeLintFixSafety:
    """The lint repair contract and its projection preserve information."""

    @staticmethod
    def test_lint_fix_rejects_the_unsafe_fix_flag() -> None:
        """An information-destroying lint repair is unrepresentable."""
        ruff = config.Infra.codegen.make.ruff
        payload = ruff.model_dump()
        payload["lint_fix"] = (*ruff.lint_fix, c.Infra.RUFF_UNSAFE_FIXES_FLAG)

        with pytest.raises(m.ValidationError) as failure:
            _ = m.Infra.MakeRuffSpec.model_validate(payload)

        tm.that(str(failure.value), has=c.Infra.RUFF_UNSAFE_FIXES_FLAG)

    @staticmethod
    @pytest.mark.slow
    def test_scaffold_pyproject_renders_the_fix_safety_policy(
        tmp_path: Path,
    ) -> None:
        """The rendered Ruff lint table carries the SSOT fix-safety lists."""
        policy = config.Infra.tooling.tools.ruff.lint
        pyproject = u.Tests.scaffold_text(
            tmp_path / "fixture-project",
            c.PYPROJECT_FILENAME,
        )

        tm.that(
            list(
                u.Tests.toml_strings_at(pyproject, "tool", "ruff", "lint", "unfixable"),
            ),
            eq=sorted(policy.unfixable),
        )
        tm.that(
            list(
                u.Tests.toml_strings_at(
                    pyproject,
                    "tool",
                    "ruff",
                    "lint",
                    "extend-safe-fixes",
                ),
            ),
            eq=sorted(policy.extend_safe_fixes),
        )
        tm.that(
            list(u.Tests.toml_strings_at(pyproject, "tool", "ruff", "lint", "ignore")),
            eq=list(policy.ignore),
        )
