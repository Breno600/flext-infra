"""Public behavior tests for the SonarCloud server-side settings sync.

The sync writes an external web API; these tests exercise everything that
decides what is written and when, without opening a network socket: the
project key derived from a real Git origin, the request plan derived from the
codegen SSOT, the no-op decision against the measured response shape, and the
token preflight that fails before any effect through the public CLI.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraSonarcloudSettingsSync, c, config, m
from tests import u

if TYPE_CHECKING:
    from tests import t

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraSonarcloudSettingsSync:
    """Validate the settings sync through its public service contract."""

    _ORGANIZATION = "example-org"
    _REPOSITORY = "example-repo"

    @staticmethod
    def _spec(count: int | None = None) -> m.Infra.SonarcloudSpec:
        """Use the current SSOT or validate a different exclusion cardinality."""
        spec = config.Infra.codegen.sonarcloud
        if count is None:
            return spec
        return m.Infra.SonarcloudSpec.model_validate({
            **spec.model_dump(),
            "issue_exclusions": tuple(
                m.Infra.SonarcloudIssueExclusionSpec(
                    rule_key=f"text:S{1000 + index}",
                    resource_key=f"inputs/{index}.toml",
                    reason=f"Contract scenario {index}",
                )
                for index in range(count)
            ),
        })

    @staticmethod
    def _server_payload(
        pairs: t.VariadicTuple[t.Pair[str, str]],
        *,
        inherited: bool = False,
        include_setting: bool = True,
    ) -> str:
        """Render an ``api/settings/values`` body in the measured shape."""
        settings: list[t.JsonValue] = []
        if include_setting:
            field_values: list[t.JsonValue] = [
                {"resourceKey": resource, "ruleKey": rule} for rule, resource in pairs
            ]
            settings.append({
                "key": c.Infra.SONARCLOUD_ISSUE_IGNORE_KEY,
                "fieldValues": field_values,
                "inherited": inherited,
            })
        return tm.ok(u.Cli.json_dumps({"settings": settings}))

    @staticmethod
    def _pairs(spec: m.Infra.SonarcloudSpec) -> t.VariadicTuple[t.Pair[str, str]]:
        """Read expectations from the exact typed config the service receives."""
        return tuple(
            (exclusion.rule_key, exclusion.resource_key)
            for exclusion in spec.issue_exclusions
        )

    def _cli(
        self, repository_root: Path, env: t.StrMapping | None = None
    ) -> t.Pair[int, str]:
        """Run the public CLI route in a child process without SONAR_TOKEN."""
        result = tm.ok(
            u.Cli.run_raw(
                [
                    sys.executable,
                    "-m",
                    "flext_infra",
                    c.Infra.CLI_GROUP_MAINTENANCE,
                    c.Infra.VERB_SONARCLOUD_SYNC,
                    "--repository-root",
                    str(repository_root),
                ],
                env={"COLUMNS": "200", **(env or {})},
                remove_env_keys=() if env else ("SONAR_TOKEN",),
            )
        )
        return result.outcome.raw_return_code, result.stdout + result.stderr

    @pytest.mark.parametrize(
        "origin",
        [
            "https://github.com/example-org/example-repo.git",
            "git@github.com:example-org/example-repo.git",
        ],
    )
    def test_project_key_joins_origin_organization_and_repository(
        self, tmp_path: Path, origin: str
    ) -> None:
        """The key is <organization>_<repository> whatever the origin transport."""
        u.Tests.initialize_git_repo(tmp_path, origin_url=origin)

        key = tm.ok(FlextInfraSonarcloudSettingsSync.project_key(tmp_path))

        tm.that(
            key,
            eq=f"{self._ORGANIZATION}{c.Infra.SONARCLOUD_PROJECT_KEY_SEPARATOR}"
            f"{self._REPOSITORY}",
        )

    @pytest.mark.parametrize("count", [None, 0, 1, 3])
    def test_plan_selects_reset_or_the_complete_property_set(
        self, count: int | None
    ) -> None:
        """The request honors both the current SSOT and arbitrary valid configs."""
        spec = self._spec(count)
        plan = tm.ok(FlextInfraSonarcloudSettingsSync.settings_plan(spec, "org_repo"))
        request = FlextInfraSonarcloudSettingsSync.settings_write_request(plan)
        form = request.form

        tm.that(form[0], eq=("component", "org_repo"))
        if spec.issue_exclusions:
            tm.that(request.api_path, eq=c.Infra.SONARCLOUD_API_SETTINGS_SET_PATH)
            tm.that(form[1], eq=("key", c.Infra.SONARCLOUD_ISSUE_IGNORE_KEY))
        else:
            tm.that(request.api_path, eq=c.Infra.SONARCLOUD_API_SETTINGS_RESET_PATH)
            tm.that(form[1], eq=("keys", c.Infra.SONARCLOUD_ISSUE_IGNORE_KEY))
        sent = tuple(
            (entry.rule_key, entry.resource_key)
            for name, value in form[2:]
            if name == "fieldValues"
            for entry in (m.Infra.SonarcloudIssueFieldValue.model_validate_json(value),)
        )
        for name, value in form[2:]:
            tm.that(name, eq="fieldValues")
            tm.that(value, has='"ruleKey"')
            tm.that(value, has='"resourceKey"')
        tm.that(len(form), eq=2 + len(sent))
        tm.that(sent, eq=self._pairs(spec))
        tm.that(plan.api_url, eq=spec.api_url)
        tm.that(plan.timeout_seconds, eq=spec.api_timeout_seconds)

    @pytest.mark.parametrize("count", [0, 1, 3])
    @pytest.mark.parametrize("inherited", [False, True])
    def test_plan_matches_effective_server_values(
        self, count: int, *, inherited: bool
    ) -> None:
        """Inherited entries affect convergence exactly like project entries."""
        spec = self._spec(count)
        plan = tm.ok(FlextInfraSonarcloudSettingsSync.settings_plan(spec, "org_repo"))
        pairs = self._pairs(spec)
        values = m.Infra.SonarcloudSettingsValues.model_validate_json

        for ordered in (pairs, tuple(reversed(pairs))):
            current = values(self._server_payload(ordered, inherited=inherited))
            tm.that(
                FlextInfraSonarcloudSettingsSync.in_sync_with(plan, current), eq=True
            )
        absent = values(self._server_payload((), include_setting=False))
        tm.that(
            FlextInfraSonarcloudSettingsSync.in_sync_with(plan, absent),
            eq=not spec.issue_exclusions,
        )
        extra = values(
            self._server_payload(
                (*pairs, ("text:S0000", "extra.toml")), inherited=inherited
            )
        )
        tm.that(FlextInfraSonarcloudSettingsSync.in_sync_with(plan, extra), eq=False)

    @pytest.mark.parametrize("count", [1, 3])
    def test_repeated_config_entries_fail_and_server_duplicates_require_a_write(
        self, count: int
    ) -> None:
        """Config and readback must contain every declared pair exactly once."""
        spec = self._spec(count)
        repeated = m.Infra.SonarcloudSpec.model_validate({
            **spec.model_dump(),
            "issue_exclusions": spec.issue_exclusions * 2,
        })
        tm.fail(
            FlextInfraSonarcloudSettingsSync.settings_plan(repeated, "org_repo"),
            has="repeats",
        )
        plan = tm.ok(FlextInfraSonarcloudSettingsSync.settings_plan(spec, "org_repo"))
        current = m.Infra.SonarcloudSettingsValues.model_validate_json(
            self._server_payload(self._pairs(spec) * 2)
        )
        tm.that(FlextInfraSonarcloudSettingsSync.in_sync_with(plan, current), eq=False)

    def test_workspace_root_fans_the_verb_out(self) -> None:
        """The workspace orchestrator accepts the verb so the root reaches members."""
        tm.that(c.Infra.ORCHESTRATED_VERBS, has=c.Infra.VERB_SONARCLOUD_SYNC)

    def test_absent_token_fails_before_any_effect(self, tmp_path: Path) -> None:
        """Without SONAR_TOKEN the verb fails first, before reading origin or API."""
        u.Tests.initialize_git_repo(tmp_path)

        code, output = self._cli(tmp_path)

        tm.that(code, ne=0)
        tm.that(output, has="SONAR_TOKEN is required")

    def test_whitespace_token_is_refused(self, tmp_path: Path) -> None:
        """A whitespace-only token is absent, never trimmed into a request."""
        u.Tests.initialize_git_repo(tmp_path)

        code, output = self._cli(tmp_path, env={"SONAR_TOKEN": "   "})

        tm.that(code, ne=0)
        tm.that(output, has="SONAR_TOKEN is required")
