"""make fix always applies the mandatory unsafe repair channel (2026-10-05 law).

The unsafe-fix flag is OBLIGATORY in every lint_fix configuration and must never
be disabled again: a configuration without it is unrepresentable, the SSOT
carries it, and every generated pyproject follows the same fix policy as
``make fix`` for direct or IDE Ruff runs.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
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
    """The mandatory unsafe lint-repair contract and its projection."""

    @staticmethod
    def test_lint_fix_requires_the_unsafe_fix_flag() -> None:
        """Disabling the mandatory unsafe channel is unrepresentable."""
        ruff = config.Infra.codegen.make.ruff
        tm.that(c.Infra.RUFF_UNSAFE_FIXES_FLAG in ruff.lint_fix, eq=True)
        payload = ruff.model_dump()
        payload["lint_fix"] = tuple(
            flag for flag in ruff.lint_fix if flag != c.Infra.RUFF_UNSAFE_FIXES_FLAG
        )

        with pytest.raises(m.ValidationError) as failure:
            _ = m.Infra.MakeRuffSpec.model_validate(payload)

        tm.that(str(failure.value), has=c.Infra.RUFF_UNSAFE_FIXES_FLAG)
        tm.that(str(failure.value), has="operator law 2026-10-05")

    @staticmethod
    def test_ssot_lint_fix_carries_the_mandatory_channel() -> None:
        """The config SSOT itself runs the mandatory unsafe repair surface."""
        ruff = config.Infra.codegen.make.ruff
        tm.that(list(ruff.lint_fix), eq=["--preview", "--fix", "--unsafe-fixes"])

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
