"""Generated Make scope options must match the real CLI route contract."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, main
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.services.cli_routes import FlextInfraCliRouteService
from tests import u


class TestsFlextInfraCliRepositoryRootContract:
    @pytest.fixture
    def rendered_makefile(self, tmp_path: Path) -> str:
        """Use the conform owner and typed fixtures, not a copied Make recipe."""
        repository = u.Tests.repository_ref("scope-contract-fixture")
        request = u.Tests.conform_request(
            tmp_path, what=c.Infra.CodegenConformSurface.MAKEFILE
        )
        plan = tm.ok(
            FlextInfraCodegenConform(
                repository_root=tmp_path,
                request=request,
                initial_workspace=u.Tests.workspace_spec(
                    repository, project=u.Tests.project_spec(repository.name)
                ),
            ).plan(request)
        )
        return u.Tests.codegen_file_text(
            next(
                file
                for file in plan.files
                if file.path.name == c.Infra.MAKEFILE_FILENAME
            )
        )

    @pytest.mark.parametrize(
        ("group", "command", "generated_command"),
        [
            (c.Infra.CLI_GROUP_CHECK, c.Infra.VERB_RUN, c.Infra.VERB_RUN),
            (c.Infra.CLI_GROUP_DEPS, "modernize", "modernize"),
            (c.Infra.CLI_GROUP_CODEGEN, "init", "init"),
            *[
                (c.Infra.CLI_GROUP_DOCS, action, '"$$action"')
                for action in config.Infra.codegen.make.docs.mutable_actions
            ],
        ],
    )
    def test_generated_scope_matches_route_and_help(
        self, rendered_makefile: str, group: str, command: str, generated_command: str
    ) -> None:
        """Reject stale recipes and hidden service aliases as well as CLI drift."""
        route = next(
            route
            for route in FlextInfraCliRouteService.route_table_for(group)
            if route.name == command
        )
        fields = route.model_cls.model_fields
        tm.that(tuple(fields), has="repository_root")
        tm.that(tuple(fields), lacks="workspace")
        scope = fields["repository_root"]
        tm.that(scope.alias is None, eq=True)
        tm.that(scope.validation_alias is None, eq=True)
        tm.that(scope.serialization_alias is None, eq=True)
        option = "--repository-root"
        tm.that(
            rendered_makefile,
            has=f'{group} {generated_command} {option} "$(PROJECT_ROOT)"',
        )
        # The route model field IS the CLI option (typed contract above); help must
        # render, and its styled text is presentation, never the contract.
        tm.that(main([group, route.name, "--help"]), eq=0)
