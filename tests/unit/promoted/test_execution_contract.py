"""Promoted commands execute their declared operation through the public API."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import m
from tests import c, u


class TestsFlextInfraPromotedExecutionContract:
    """Promoted contracts always execute without an effect selector."""

    def test_workspace_configuration_and_promoted_facts_preserve_their_domains(
        self, tmp_path: Path
    ) -> None:
        """Facade composition exposes both schemas without a name collision."""
        repository = u.Tests.repository_ref("semantic-spec")
        workspace = u.Tests.workspace_spec(repository)
        facts = u.Infra.promoted_workspace_spec(tmp_path)
        tm.that(workspace.repository, eq=repository)
        tm.that(facts.root, eq=tmp_path)
        tm.that(facts.scripts, eq=tmp_path / c.Infra.DIR_SCRIPTS)

    class TestsFlextInfraPromotedAlwaysExecutes:
        """Validate commands with and without declared domain parameters."""

        def test_command_contract_accepts_mutating_command_without_parameters(
            self, tmp_path: Path
        ) -> None:
            """A mutating command can declare an operation without parameters."""
            command = u.Tests.promoted_command(
                path=tmp_path / "scripts" / "probe" / "all.py"
            )
            u.Infra.promoted_validate_command_contract(command)

        def test_command_contract_accepts_declared_domain_parameter(
            self, tmp_path: Path
        ) -> None:
            """A domain parameter remains part of the command's input contract."""
            param = m.Infra.PromotedParam(
                name="TARGET", help="Destination", choices=("alpha", "beta")
            )
            command = u.Tests.promoted_command(
                path=tmp_path / "scripts" / "probe" / "all.py", params=(param,)
            )
            u.Infra.promoted_validate_command_contract(command)
