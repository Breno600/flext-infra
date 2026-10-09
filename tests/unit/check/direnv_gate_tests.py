"""Public direnv gate behavior: static contracts plus activation smoke.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, m
from flext_infra.gates.direnv import FlextInfraDirenvGate
from flext_infra.workspace.environment_contracts import (
    FlextInfraWorkspaceEnvironmentContracts,
)
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraDirenvGate:
    """Tests for ``FlextInfraDirenvGate``."""

    @staticmethod
    def allowed_check(root: Path) -> m.Infra.GateExecution:
        """Check one workspace whose ``.envrc`` the real direnv approved.

        Returns:
            The resulting ``m.Infra.GateExecution``.

        """
        allow = (c.Infra.CLI_DIRENV, "allow", str(root))
        tm.ok(u.Cli.run_checked(allow, cwd=root))
        execution = FlextInfraDirenvGate(root).check(root, u.Tests.gate_context(root))
        tm.ok(u.Cli.run_checked((c.Infra.CLI_DIRENV, "deny", str(root)), cwd=root))
        return execution

    @staticmethod
    def issue_codes(execution: m.Infra.GateExecution) -> t.StrSequence:
        """Return the issue codes one gate execution reported, in order.

        Returns:
            The issue codes one gate execution reported, in order.

        """
        return [issue.code for issue in execution.issues]

    @staticmethod
    def messages(
        violations: t.VariadicTuple[m.Infra.EnvironmentContractViolation],
    ) -> t.StrSequence:
        """Render typed violations exactly as the gate reports them.

        Returns:
            The resulting ``t.StrSequence``.

        """
        return [f"line {v.line}: {v.message}" for v in violations]

    class TestsDirenvContractLint:
        """Pure-lint contracts for managed environment files."""

        @staticmethod
        def test_unguarded_direnv_dir_reads_fail(tmp_path: Path) -> None:
            """strict_env does not export DIRENV_DIR; unguarded reads violate."""
            violations = (
                FlextInfraWorkspaceEnvironmentContracts.envrc_contract_violations(
                    'checkout_root="${DIRENV_DIR#-}"\n'
                    'other="${DIRENV_DIR}"\n'
                    "bare=$DIRENV_DIR\n",
                    root=tmp_path,
                )
            )
            tm.that(len(violations), eq=3)

        @staticmethod
        def test_guarded_direnv_dir_reads_pass(tmp_path: Path) -> None:
            """Guarded reads keep working under strict_env."""
            violations = (
                FlextInfraWorkspaceEnvironmentContracts.envrc_contract_violations(
                    'fallback="${DIRENV_DIR:-missing}"\noptional="${DIRENV_DIR-}"\n',
                    root=tmp_path,
                )
            )
            tm.that(violations, eq=())

        @staticmethod
        def test_missing_literal_target_fails(tmp_path: Path) -> None:
            """Literal source_env and watch_file targets must exist."""
            (tmp_path / "present.envrc").write_text("export OK=1\n", encoding="utf-8")
            violations = (
                FlextInfraWorkspaceEnvironmentContracts.envrc_contract_violations(
                    'source_env "present.envrc"\nwatch_file "absent.envrc"\n',
                    root=tmp_path,
                )
            )
            tm.that(len(violations), eq=1)
            tm.that("absent.envrc" in violations[0].message, eq=True)

        @staticmethod
        def test_dynamic_targets_are_skipped(tmp_path: Path) -> None:
            """Runtime-derived targets cannot be validated statically."""
            violations = (
                FlextInfraWorkspaceEnvironmentContracts.envrc_contract_violations(
                    'watch_file "$some_var/relstate.json"\n',
                    root=tmp_path,
                )
            )
            tm.that(violations, eq=())

        @staticmethod
        @pytest.mark.parametrize("prefix", ["${HOME}", "$HOME", "~"])
        def test_home_targets_validated_only_when_resolving(
            tmp_path: Path,
            prefix: str,
        ) -> None:
            """resolve_home=False skips ${HOME} targets (generation-time lint)."""
            contracts = FlextInfraWorkspaceEnvironmentContracts
            violations = contracts.envrc_contract_violations(
                f'source_env "{prefix}/.config/environment.d/projects/absent.envrc"\n',
                root=tmp_path,
                resolve_home=False,
            )
            tm.that(violations, eq=())

        @staticmethod
        @pytest.mark.parametrize("prefix", ["${HOME}", "$HOME", "~"])
        def test_home_targets_resolve_against_the_real_home(
            tmp_path: Path,
            prefix: str,
        ) -> None:
            """resolve_home=True substitutes the real home for the prefix.

            Regression: the prefix used to be stripped without substitution,
            probing a bogus absolute path (``/.``) that never exists.
            """
            violations = (
                FlextInfraWorkspaceEnvironmentContracts.envrc_contract_violations(
                    f'source_env "{prefix}"\n'
                    f'watch_file "{prefix}/.flext-infra-contract-absent-marker"\n',
                    root=tmp_path,
                )
            )
            tm.that(len(violations), eq=1)
            tm.that(
                ".flext-infra-contract-absent-marker" in violations[0].message,
                eq=True,
            )
            tm.that("/./" not in violations[0].message, eq=True)

    class TestsEnvrcLocalContracts:
        """Local overrides never carry generated activation residue."""

        stale_section = (
            "# Generated by `flext-infra codegen conform`.\n"
            "# === SECTION: Gas City Beads activation (managed) ===\n"
            "unset GT_ROOT\n"
            "# End SECTION: Gas City Beads activation\n"
        )

        def test_normalizer_keeps_custom_and_strips_generated(self) -> None:
            """Custom operator content survives; generated content is removed."""
            normalized = FlextInfraWorkspaceEnvironmentContracts.envrc_local_normalized(
                self.stale_section + "export CUSTOM_OVERRIDE=1\n",
            )
            tm.that(normalized, eq="export CUSTOM_OVERRIDE=1\n")

        def test_normalizer_removes_residue_only_file(self) -> None:
            """A file carrying only generated residue normalizes to empty."""
            normalized = FlextInfraWorkspaceEnvironmentContracts.envrc_local_normalized(
                self.stale_section,
            )
            tm.that(normalized, eq="")

        @staticmethod
        def test_normalizer_removes_unterminated_section() -> None:
            """A truncated managed section never leaks its body."""
            normalized = FlextInfraWorkspaceEnvironmentContracts.envrc_local_normalized(
                "# === SECTION: Gas City Beads activation (managed) ===\n"
                "unset GT_ROOT\n"
                "export CUSTOM_OVERRIDE=1\n",
            )
            tm.that(normalized, eq="")

        @staticmethod
        def test_normalizer_keeps_clean_content_verbatim() -> None:
            """Already-clean overrides round-trip unchanged."""
            normalized = FlextInfraWorkspaceEnvironmentContracts.envrc_local_normalized(
                "export CUSTOM_OVERRIDE=1\nPATH_add bin\n",
            )
            tm.that(normalized, eq="export CUSTOM_OVERRIDE=1\nPATH_add bin\n")

        def test_violations_flag_activation_residue(self) -> None:
            """Markers and Beads variables are typed per line with their token."""
            violations = (
                FlextInfraWorkspaceEnvironmentContracts.envrc_local_contract_violations(
                    self.stale_section + "export BEADS_DOLT_AUTO_START=0\n",
                )
            )
            tm.that(len(violations), eq=5)
            tm.that(tuple(v.line for v in violations), eq=(1, 2, 3, 4, 5))
            tm.that(violations[4].token, eq="BEADS_DOLT_")
            tm.that(
                TestsFlextInfraDirenvGate.messages(violations)[4].endswith(
                    "Beads activation variable in local overrides: BEADS_DOLT_",
                ),
                eq=True,
            )

        @staticmethod
        def test_clean_local_content_passes() -> None:
            """Custom overrides carry no violations."""
            violations = (
                FlextInfraWorkspaceEnvironmentContracts.envrc_local_contract_violations(
                    "export CUSTOM_OVERRIDE=1\nPATH_add bin\n",
                )
            )
            tm.that(violations, eq=())

        def test_gate_fails_on_local_residue(self, tmp_path: Path) -> None:
            """The direnv gate fails a workspace whose overrides carry residue."""
            _ = (tmp_path / c.Infra.ENVRC_FILENAME).write_text(
                "export OK=1\n",
                encoding="utf-8",
            )
            _ = (tmp_path / c.Infra.ENVRC_LOCAL_RELPATH).write_text(
                self.stale_section,
                encoding="utf-8",
            )
            execution = FlextInfraDirenvGate(tmp_path).check(
                tmp_path,
                u.Tests.gate_context(tmp_path),
            )
            tm.that(execution.result.passed, eq=False)
            tm.that(
                set(TestsFlextInfraDirenvGate.issue_codes(execution)),
                eq={"DIRENV_CONTRACT"},
            )

        @staticmethod
        def test_gate_passes_clean_local_overrides(tmp_path: Path) -> None:
            """Clean local overrides keep the gate green."""
            _ = (tmp_path / c.Infra.ENVRC_FILENAME).write_text(
                "export OK=1\n",
                encoding="utf-8",
            )
            _ = (tmp_path / c.Infra.ENVRC_LOCAL_RELPATH).write_text(
                "export CUSTOM_OVERRIDE=1\n",
                encoding="utf-8",
            )
            execution = TestsFlextInfraDirenvGate.allowed_check(tmp_path)
            tm.that(execution.result.passed, eq=True)

    class TestsDirenvGate:
        """Fail-closed gate behavior over the two enforcement stages."""

        @staticmethod
        def test_workspace_without_envrc_cannot_pass(tmp_path: Path) -> None:
            """A selected gate with no inputs cannot establish acceptance."""
            execution = FlextInfraDirenvGate(tmp_path).check(
                tmp_path,
                u.Tests.gate_context(tmp_path),
            )
            tm.that(execution.result.passed, eq=False)
            tm.that(
                execution.result.errors,
                eq=["direnv: no check targets were collected"],
            )

        @staticmethod
        def test_contract_violation_fails_before_smoke(tmp_path: Path) -> None:
            """The static lint fails the gate before the unapproved smoke runs."""
            _ = (tmp_path / c.Infra.ENVRC_FILENAME).write_text(
                'checkout_root="${DIRENV_DIR#-}"\n',
                encoding="utf-8",
            )
            execution = FlextInfraDirenvGate(tmp_path).check(
                tmp_path,
                u.Tests.gate_context(tmp_path),
            )
            tm.that(execution.result.passed, eq=False)
            tm.that(
                TestsFlextInfraDirenvGate.issue_codes(execution),
                eq=["DIRENV_CONTRACT"],
            )

        @staticmethod
        def test_activation_smoke_passes(tmp_path: Path) -> None:
            """An approved clean envrc passes through a real direnv exec."""
            _ = (tmp_path / c.Infra.ENVRC_FILENAME).write_text(
                "export OK=1\n",
                encoding="utf-8",
            )
            execution = TestsFlextInfraDirenvGate.allowed_check(tmp_path)
            tm.that(execution.result.passed, eq=True)
            tm.that(execution.issues, eq=())

        @staticmethod
        def test_activation_smoke_fails_loud(tmp_path: Path) -> None:
            """An unapproved envrc fails real activation with direnv's own error."""
            _ = (tmp_path / c.Infra.ENVRC_FILENAME).write_text(
                "export OK=1\n",
                encoding="utf-8",
            )
            execution = FlextInfraDirenvGate(tmp_path).check(
                tmp_path,
                u.Tests.gate_context(tmp_path),
            )
            tm.that(execution.result.passed, eq=False)
            tm.that(
                TestsFlextInfraDirenvGate.issue_codes(execution),
                eq=["DIRENV_ACTIVATE"],
            )
            tm.that(execution.issues[0].message, ne="")
